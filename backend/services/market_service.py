"""Market fetching, classification, and grouping"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .kalshi_client import KalshiClient


class MarketType(Enum):
    """Market classification type"""
    THRESHOLD = "threshold"
    BRACKET = "bracket"
    UNKNOWN = "unknown"


@dataclass
class ThresholdMarket:
    """Represents a threshold market (e.g., 'BTC above $95,000')"""
    ticker: str
    title: str
    asset: str
    strike: float
    direction: str  # "above" or "below"
    yes_price: float
    no_price: float
    yes_ask: float
    no_ask: float
    yes_bid: float
    no_bid: float
    volume: int
    settlement_time: datetime


@dataclass
class BracketMarket:
    """Represents a bracket market (e.g., 'BTC $95,000-$97,500')"""
    ticker: str
    title: str
    asset: str
    low_bound: float
    high_bound: float
    yes_price: float
    no_price: float
    yes_ask: float
    no_ask: float
    yes_bid: float
    no_bid: float
    volume: int
    settlement_time: datetime


@dataclass
class MarketGroup:
    """Group of related markets for the same asset and settlement time"""
    asset: str
    settlement_time: datetime
    thresholds: List[ThresholdMarket] = field(default_factory=list)
    brackets: List[BracketMarket] = field(default_factory=list)
    spot_price: Optional[float] = None

    @property
    def is_complete(self) -> bool:
        """Check if brackets cover full range without gaps"""
        if not self.brackets:
            return False

        sorted_brackets = sorted(self.brackets, key=lambda b: b.low_bound)

        # Check for gaps between consecutive brackets
        for i in range(len(sorted_brackets) - 1):
            if sorted_brackets[i].high_bound != sorted_brackets[i + 1].low_bound:
                return False

        return True

    @property
    def bracket_range(self) -> Tuple[float, float]:
        """Get the full range covered by brackets"""
        if not self.brackets:
            return (0, 0)

        sorted_brackets = sorted(self.brackets, key=lambda b: b.low_bound)
        return (sorted_brackets[0].low_bound, sorted_brackets[-1].high_bound)


class MarketClassifier:
    """Classify markets as threshold or bracket based on title patterns"""

    # Asset detection patterns
    ASSET_PATTERNS = {
        "BTC": [r"bitcoin", r"\bbtc\b", r"btcusd"],
        "ETH": [r"ethereum", r"\beth\b", r"ethusd"],
        "SPX": [r"s&p\s*500", r"\bspx\b", r"sp500"],
        "NDX": [r"nasdaq", r"\bndx\b", r"nasdaq.?100"],
    }

    # Threshold patterns: "above $X", "below $X", "over X", "under X"
    THRESHOLD_PATTERNS = [
        (r"(above|over|greater than|>=?)\s*\$?([\d,]+(?:\.\d+)?)", "above"),
        (r"(below|under|less than|<=?)\s*\$?([\d,]+(?:\.\d+)?)", "below"),
        (r"(at or above)\s*\$?([\d,]+(?:\.\d+)?)", "above"),
        (r"(at or below)\s*\$?([\d,]+(?:\.\d+)?)", "below"),
    ]

    # Bracket patterns: "$X - $Y", "between X and Y", "range X to Y"
    BRACKET_PATTERNS = [
        r"\$?([\d,]+(?:\.\d+)?)\s*[-–—to]+\s*\$?([\d,]+(?:\.\d+)?)",
        r"between\s*\$?([\d,]+(?:\.\d+)?)\s*and\s*\$?([\d,]+(?:\.\d+)?)",
        r"range\s*\$?([\d,]+(?:\.\d+)?)\s*to\s*\$?([\d,]+(?:\.\d+)?)",
    ]

    def classify(self, market: Dict) -> Tuple[MarketType, Dict]:
        """
        Classify a market and extract relevant data.

        Args:
            market: Market dictionary from Kalshi API

        Returns:
            Tuple of (MarketType, extracted_data)
        """
        title = market.get("title", "").lower()
        subtitle = market.get("subtitle", "").lower()
        full_text = f"{title} {subtitle}"

        # Detect asset
        asset = self._detect_asset(full_text)
        if not asset:
            return MarketType.UNKNOWN, {}

        # Try threshold patterns first
        for pattern, direction in self.THRESHOLD_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                strike = float(match.group(2).replace(",", ""))
                return MarketType.THRESHOLD, {
                    "asset": asset,
                    "direction": direction,
                    "strike": strike
                }

        # Try bracket patterns
        for pattern in self.BRACKET_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                low = float(match.group(1).replace(",", ""))
                high = float(match.group(2).replace(",", ""))
                return MarketType.BRACKET, {
                    "asset": asset,
                    "low_bound": min(low, high),
                    "high_bound": max(low, high)
                }

        return MarketType.UNKNOWN, {"asset": asset}

    def _detect_asset(self, text: str) -> Optional[str]:
        """Detect which asset a market is for"""
        text_lower = text.lower()
        for asset, patterns in self.ASSET_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    return asset
        return None


class MarketService:
    """Service for fetching and organizing markets"""

    def __init__(self, kalshi_client: KalshiClient):
        self.kalshi = kalshi_client
        self.classifier = MarketClassifier()

    async def get_grouped_markets(
        self,
        assets: Optional[List[str]] = None
    ) -> List[MarketGroup]:
        """
        Fetch all markets, classify them, and group by asset + settlement time.

        Args:
            assets: Optional list of assets to filter by

        Returns:
            List of MarketGroup objects
        """
        raw_markets = await self.kalshi.get_markets()

        # Classify and organize
        groups: Dict[str, MarketGroup] = {}

        for market in raw_markets:
            market_type, data = self.classifier.classify(market)

            if market_type == MarketType.UNKNOWN:
                continue

            asset = data.get("asset")
            if assets and asset not in assets:
                continue

            settlement = market.get("close_time") or market.get("expiration_time")

            if not asset or not settlement:
                continue

            # Parse settlement time
            if isinstance(settlement, str):
                if settlement.endswith("Z"):
                    settlement = settlement[:-1] + "+00:00"
                settlement = datetime.fromisoformat(settlement)

            # Create group key
            group_key = f"{asset}_{settlement.isoformat()}"

            if group_key not in groups:
                groups[group_key] = MarketGroup(
                    asset=asset,
                    settlement_time=settlement
                )

            group = groups[group_key]

            # Get orderbook for pricing
            try:
                orderbook = await self.kalshi.get_orderbook(market["ticker"])
            except Exception:
                orderbook = {}

            # Extract prices from orderbook
            yes_book = orderbook.get("yes", [])
            no_book = orderbook.get("no", [])

            # Best bid/ask
            yes_bids = [b for b in yes_book if b.get("side") == "bid"]
            yes_asks = [a for a in yes_book if a.get("side") == "ask"]
            no_bids = [b for b in no_book if b.get("side") == "bid"]
            no_asks = [a for a in no_book if a.get("side") == "ask"]

            yes_bid = max([b.get("price", 0) for b in yes_bids], default=0) / 100
            yes_ask = min([a.get("price", 100) for a in yes_asks], default=100) / 100
            no_bid = max([b.get("price", 0) for b in no_bids], default=0) / 100
            no_ask = min([a.get("price", 100) for a in no_asks], default=100) / 100

            # Mid prices
            yes_price = (yes_bid + yes_ask) / 2 if yes_bid and yes_ask else yes_ask
            no_price = (no_bid + no_ask) / 2 if no_bid and no_ask else no_ask

            if market_type == MarketType.THRESHOLD:
                group.thresholds.append(ThresholdMarket(
                    ticker=market["ticker"],
                    title=market["title"],
                    asset=asset,
                    strike=data["strike"],
                    direction=data["direction"],
                    yes_price=yes_price,
                    no_price=no_price,
                    yes_ask=yes_ask,
                    no_ask=no_ask,
                    yes_bid=yes_bid,
                    no_bid=no_bid,
                    volume=market.get("volume", 0),
                    settlement_time=settlement
                ))
            else:  # BRACKET
                group.brackets.append(BracketMarket(
                    ticker=market["ticker"],
                    title=market["title"],
                    asset=asset,
                    low_bound=data["low_bound"],
                    high_bound=data["high_bound"],
                    yes_price=yes_price,
                    no_price=no_price,
                    yes_ask=yes_ask,
                    no_ask=no_ask,
                    yes_bid=yes_bid,
                    no_bid=no_bid,
                    volume=market.get("volume", 0),
                    settlement_time=settlement
                ))

        # Sort brackets within each group
        for group in groups.values():
            group.brackets.sort(key=lambda b: b.low_bound)
            group.thresholds.sort(key=lambda t: t.strike)

        return list(groups.values())

    async def get_market_details(self, ticker: str) -> Optional[Dict]:
        """
        Get detailed information for a specific market.

        Args:
            ticker: Market ticker

        Returns:
            Market details dictionary or None
        """
        try:
            market = await self.kalshi.get_market(ticker)
            orderbook = await self.kalshi.get_orderbook(ticker)
            return {
                "market": market,
                "orderbook": orderbook
            }
        except Exception:
            return None
