import uuid
from datetime import datetime, timezone
from typing import List, Optional
from dataclasses import dataclass, field

from .market_classifier import ThresholdMarket, BracketMarket, MarketGroup
from .core.fee_calculator import calculate_fee


@dataclass
class ArbitrageOpportunity:
    id: str
    asset: str
    detected_at: datetime
    settlement_time: datetime

    # Threshold details
    threshold: ThresholdMarket

    # All brackets (for full arbitrage)
    brackets: List[BracketMarket]

    # Pricing
    threshold_yes_price: float
    implied_price: float
    divergence: float

    # Profit calculation (per contract set)
    cost_per_set: float
    fees_per_set: float
    profit_per_set: float
    net_profit_pct: float

    # Liquidity
    max_contracts: int
    max_liquidity_usd: float

    # Context
    spot_price: Optional[float] = None


class ArbitrageDetector:
    """Detects arbitrage opportunities between threshold and bracket markets"""

    def __init__(self, min_profit_pct: float = 1.0, min_liquidity_usd: float = 50.0):
        self.min_profit_pct = min_profit_pct
        self.min_liquidity_usd = min_liquidity_usd

    def find_opportunities(self, groups: List[MarketGroup]) -> List[ArbitrageOpportunity]:
        opportunities = []

        for group in groups:
            if not group.thresholds or not group.brackets:
                continue

            sorted_brackets = sorted(group.brackets, key=lambda b: b.low_bound)

            for threshold in group.thresholds:
                opp = self._analyze_threshold(threshold, sorted_brackets, group)
                if opp:
                    opportunities.append(opp)

        return sorted(opportunities, key=lambda o: o.net_profit_pct, reverse=True)

    def _analyze_threshold(
        self,
        threshold: ThresholdMarket,
        brackets: List[BracketMarket],
        group: MarketGroup
    ) -> Optional[ArbitrageOpportunity]:

        if threshold.direction != "above":
            return None

        if not brackets:
            return None

        # For arbitrage: buy YES on ALL brackets
        # Exactly one will settle YES, guaranteeing $1 payout
        all_brackets_cost = sum(b.yes_price for b in brackets)

        if all_brackets_cost >= 1.0:
            return None  # No arbitrage - prices sum to >= $1

        # Cost per complete set
        cost_per_set = all_brackets_cost

        # Fees
        fees_per_set = sum(calculate_fee(1, b.yes_price) for b in brackets)

        # Profit
        profit_per_set = 1.0 - cost_per_set - fees_per_set
        net_profit_pct = (profit_per_set / (cost_per_set + fees_per_set)) * 100 if cost_per_set > 0 else 0

        if net_profit_pct < self.min_profit_pct:
            return None

        # Liquidity (minimum volume across all brackets)
        max_contracts = min(b.volume for b in brackets) if brackets else 0
        max_liquidity_usd = max_contracts * cost_per_set

        if max_liquidity_usd < self.min_liquidity_usd:
            return None

        # Calculate implied price from brackets above threshold
        brackets_above = [b for b in brackets if b.low_bound >= threshold.strike]
        implied_price = sum(b.yes_price for b in brackets_above) if brackets_above else 0
        divergence = threshold.yes_price - implied_price

        return ArbitrageOpportunity(
            id=str(uuid.uuid4()),
            asset=group.asset,
            detected_at=datetime.now(timezone.utc),
            settlement_time=threshold.settlement_time,
            threshold=threshold,
            brackets=brackets,
            threshold_yes_price=threshold.yes_price,
            implied_price=round(implied_price, 4),
            divergence=round(divergence, 4),
            cost_per_set=round(cost_per_set, 4),
            fees_per_set=round(fees_per_set, 4),
            profit_per_set=round(profit_per_set, 4),
            net_profit_pct=round(net_profit_pct, 2),
            max_contracts=max_contracts,
            max_liquidity_usd=round(max_liquidity_usd, 2),
            spot_price=group.spot_price
        )
