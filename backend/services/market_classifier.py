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

    THRESHOLD_PATTERN = r"\$?([\d,]+(?:\.\d+)?)\s*(or\s+)?(above|below|over|under)"
    BRACKET_PATTERN = r"\$?([\d,]+(?:\.\d+)?)\s*[-\u2013to]+\s*\$?([\d,]+(?:\.\d+)?)"

    def classify(self, market: dict) -> Tuple[Optional[MarketType], dict]:
        # Use subtitle field for Events API markets, fallback to title for legacy
        subtitle = market.get("subtitle", "")
        title = market.get("title", "")
        text = subtitle if subtitle else title
        text_lower = text.lower()

        # Check if BTC market (check both title and subtitle)
        title_lower = title.lower()
        is_btc = any(re.search(p, title_lower) for p in self.BTC_PATTERNS) or \
                 any(re.search(p, text_lower) for p in self.BTC_PATTERNS)
        if not is_btc:
            return None, {}

        # Try threshold pattern (e.g., "$99,250 or above", "$75,249.99 or below")
        match = re.search(self.THRESHOLD_PATTERN, text, re.IGNORECASE)
        if match:
            strike = float(match.group(1).replace(",", ""))
            direction_word = match.group(3).lower()
            direction = "above" if direction_word in ["above", "over"] else "below"
            return MarketType.THRESHOLD, {"asset": "BTC", "strike": strike, "direction": direction}

        # Try bracket pattern (e.g., "$98,750 to 99,249.99")
        match = re.search(self.BRACKET_PATTERN, text)
        if match:
            low = float(match.group(1).replace(",", ""))
            high = float(match.group(2).replace(",", ""))
            return MarketType.BRACKET, {"asset": "BTC", "low_bound": min(low, high), "high_bound": max(low, high)}

        return None, {}
