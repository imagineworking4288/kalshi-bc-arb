import re
from typing import Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class MarketType(Enum):
    THRESHOLD = "threshold"
    BRACKET = "bracket"


@dataclass
class ThresholdMarket:
    ticker: str
    title: str
    asset: str
    strike: float
    direction: str
    yes_price: float
    yes_ask: float
    volume: int
    settlement_time: datetime


@dataclass
class BracketMarket:
    ticker: str
    title: str
    asset: str
    low_bound: float
    high_bound: float
    yes_price: float
    yes_ask: float
    volume: int
    settlement_time: datetime


@dataclass
class MarketGroup:
    asset: str
    settlement_time: datetime
    thresholds: List[ThresholdMarket] = None
    brackets: List[BracketMarket] = None
    spot_price: Optional[float] = None

    def __post_init__(self):
        if self.thresholds is None:
            self.thresholds = []
        if self.brackets is None:
            self.brackets = []


class MarketClassifier:
    """Classifies Kalshi markets as threshold or bracket for BTC"""

    # Patterns for BTC markets
    BTC_PATTERNS = [r"bitcoin", r"\bbtc\b", r"btcusd"]

    THRESHOLD_PATTERN = r"(above|over)\s*\$?([\d,]+)"
    BRACKET_PATTERN = r"\$?([\d,]+(?:\.\d+)?)\s*[-\u2013to]+\s*\$?([\d,]+(?:\.\d+)?)"

    def classify(self, market: dict) -> Tuple[Optional[MarketType], dict]:
        title = market.get("title", "").lower()

        # Check if BTC market
        is_btc = any(re.search(p, title) for p in self.BTC_PATTERNS)
        if not is_btc:
            return None, {}

        # Try threshold pattern
        match = re.search(self.THRESHOLD_PATTERN, title, re.IGNORECASE)
        if match:
            strike = float(match.group(2).replace(",", ""))
            return MarketType.THRESHOLD, {"asset": "BTC", "strike": strike, "direction": "above"}

        # Try bracket pattern
        match = re.search(self.BRACKET_PATTERN, title)
        if match:
            low = float(match.group(1).replace(",", ""))
            high = float(match.group(2).replace(",", ""))
            return MarketType.BRACKET, {"asset": "BTC", "low_bound": min(low, high), "high_bound": max(low, high)}

        return None, {}
