"""Arbitrage detection and opportunity scoring"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from .fee_calculator import OrderLeg, calculate_fee
from .market_service import BracketMarket, MarketGroup, ThresholdMarket


@dataclass
class ArbitrageOpportunity:
    """Represents a detected arbitrage opportunity"""
    id: str
    asset: str
    settlement_time: datetime
    detected_at: datetime

    # Threshold details
    threshold_ticker: str
    threshold_title: str
    threshold_strike: float
    threshold_direction: str
    threshold_yes_price: float

    # Implied from brackets
    implied_price: float
    divergence: float  # threshold_yes_price - implied_price

    # Profit calculation
    gross_profit_pct: float
    estimated_fees: float
    net_profit_pct: float

    # Spot price context
    spot_price: Optional[float]
    spot_relation: str  # "above", "below", or "unknown"
    distance_from_threshold: Optional[float]

    # Liquidity
    max_liquidity_contracts: int
    max_liquidity_usd: float
    limiting_leg: str

    # Component markets
    threshold_market: ThresholdMarket
    required_brackets: List[BracketMarket]

    # Trade direction
    trade_direction: str  # "buy_brackets" or "buy_threshold"

    # Scoring
    score: float


class ArbitrageEngine:
    """Engine for detecting arbitrage opportunities"""

    def __init__(
        self,
        min_profit_pct: float = 1.0,
        min_liquidity: float = 50.0
    ):
        self.min_profit_pct = min_profit_pct
        self.min_liquidity = min_liquidity

    def find_opportunities(
        self,
        groups: List[MarketGroup]
    ) -> List[ArbitrageOpportunity]:
        """
        Find all arbitrage opportunities across market groups.

        Args:
            groups: List of MarketGroup objects

        Returns:
            List of ArbitrageOpportunity sorted by score
        """
        opportunities = []

        for group in groups:
            group_opps = self._analyze_group(group)
            opportunities.extend(group_opps)

        # Sort by score (highest first)
        opportunities.sort(key=lambda o: o.score, reverse=True)

        return opportunities

    def _analyze_group(self, group: MarketGroup) -> List[ArbitrageOpportunity]:
        """Analyze a single market group for opportunities"""
        opportunities = []

        if not group.thresholds or not group.brackets:
            return opportunities

        # Sort brackets by low bound
        sorted_brackets = sorted(group.brackets, key=lambda b: b.low_bound)

        for threshold in group.thresholds:
            opp = self._analyze_threshold(threshold, sorted_brackets, group)
            if opp and opp.net_profit_pct >= self.min_profit_pct:
                if opp.max_liquidity_usd >= self.min_liquidity:
                    opportunities.append(opp)

        return opportunities

    def _analyze_threshold(
        self,
        threshold: ThresholdMarket,
        brackets: List[BracketMarket],
        group: MarketGroup
    ) -> Optional[ArbitrageOpportunity]:
        """
        Analyze a single threshold against brackets.

        For "above T" threshold:
            implied_price = sum of all brackets where low_bound >= T

        Arbitrage exists when:
            threshold.yes_price != implied_price
        """
        # Find brackets above and below threshold
        brackets_above = [
            b for b in brackets
            if b.low_bound >= threshold.strike
        ]

        brackets_below = [
            b for b in brackets
            if b.high_bound <= threshold.strike
        ]

        if not brackets_above and not brackets_below:
            return None

        # Calculate implied price from brackets
        if threshold.direction == "above":
            # For "above T", implied = sum of YES prices for brackets above T
            implied_price = sum(b.yes_price for b in brackets_above)
            required_brackets = brackets_above
        else:
            # For "below T", implied = sum of YES prices for brackets below T
            implied_price = sum(b.yes_price for b in brackets_below)
            required_brackets = brackets_below

        if not required_brackets:
            return None

        # Calculate divergence
        divergence = threshold.yes_price - implied_price

        # Ignore small divergences (less than 1 cent)
        if abs(divergence) < 0.01:
            return None

        # Determine trade direction and calculate costs
        if divergence > 0:
            # Threshold overpriced - buy all brackets for guaranteed $1
            # Trade: Buy YES on all brackets, they must sum to 1.0
            trade_direction = "buy_brackets"
            trade_cost = sum(b.yes_ask for b in brackets)
            limiting_leg = min(brackets, key=lambda b: b.volume).ticker
            min_volume = min(b.volume for b in brackets)
        else:
            # Threshold underpriced - buy threshold + complementary brackets
            # Trade: Buy YES on threshold + YES on brackets below threshold
            trade_direction = "buy_threshold"
            trade_cost = threshold.yes_ask + sum(b.yes_ask for b in brackets_below)
            all_legs = [threshold] + brackets_below
            limiting_leg = min(all_legs, key=lambda x: x.volume).ticker
            min_volume = min(x.volume for x in all_legs)

        # Gross profit before fees (per $1 of contracts)
        gross_profit = 1.0 - trade_cost
        gross_profit_pct = (gross_profit / trade_cost * 100) if trade_cost > 0 else 0

        if gross_profit_pct <= 0:
            return None

        # Calculate fees for 100 contracts (reference)
        contracts = 100
        total_fees = 0
        if trade_direction == "buy_brackets":
            for bracket in brackets:
                total_fees += calculate_fee(contracts, bracket.yes_ask)
        else:
            total_fees += calculate_fee(contracts, threshold.yes_ask)
            for bracket in brackets_below:
                total_fees += calculate_fee(contracts, bracket.yes_ask)

        # Net profit after fees
        total_cost_with_fees = trade_cost * contracts + total_fees
        net_profit = contracts - total_cost_with_fees
        net_profit_pct = (net_profit / total_cost_with_fees * 100) if total_cost_with_fees > 0 else 0

        if net_profit_pct < self.min_profit_pct:
            return None

        # Calculate spot price relation
        spot_relation = "unknown"
        distance = None
        if group.spot_price:
            if group.spot_price > threshold.strike:
                spot_relation = "above"
                distance = group.spot_price - threshold.strike
            else:
                spot_relation = "below"
                distance = threshold.strike - group.spot_price

        # Calculate liquidity
        max_liquidity_usd = min_volume * trade_cost

        # Calculate score
        score = self._calculate_score(
            net_profit_pct=net_profit_pct,
            liquidity_usd=max_liquidity_usd,
            time_to_settlement=(threshold.settlement_time - datetime.utcnow()).total_seconds()
        )

        return ArbitrageOpportunity(
            id=str(uuid.uuid4()),
            asset=group.asset,
            settlement_time=threshold.settlement_time,
            detected_at=datetime.utcnow(),
            threshold_ticker=threshold.ticker,
            threshold_title=threshold.title,
            threshold_strike=threshold.strike,
            threshold_direction=threshold.direction,
            threshold_yes_price=threshold.yes_price,
            implied_price=round(implied_price, 4),
            divergence=round(divergence, 4),
            gross_profit_pct=round(gross_profit_pct, 2),
            estimated_fees=round(total_fees, 2),
            net_profit_pct=round(net_profit_pct, 2),
            spot_price=group.spot_price,
            spot_relation=spot_relation,
            distance_from_threshold=distance,
            max_liquidity_contracts=min_volume,
            max_liquidity_usd=round(max_liquidity_usd, 2),
            limiting_leg=limiting_leg,
            threshold_market=threshold,
            required_brackets=required_brackets,
            trade_direction=trade_direction,
            score=score
        )

    def _calculate_score(
        self,
        net_profit_pct: float,
        liquidity_usd: float,
        time_to_settlement: float
    ) -> float:
        """
        Calculate composite score for ranking opportunities.

        Weights:
        - Profit: 40%
        - Liquidity: 30%
        - Time: 20%
        - Base: 10%

        Args:
            net_profit_pct: Net profit percentage
            liquidity_usd: Maximum liquidity in USD
            time_to_settlement: Seconds until settlement

        Returns:
            Composite score (0-100)
        """
        # Normalize profit (0-10% maps to 0-100)
        profit_score = min(net_profit_pct * 10, 100)

        # Normalize liquidity ($0-$1000 maps to 0-100)
        liquidity_score = min(liquidity_usd / 10, 100)

        # Normalize time (prefer 30min - 2hr, penalize very short or very long)
        hours_remaining = time_to_settlement / 3600
        if hours_remaining < 0:
            time_score = 0  # Expired
        elif hours_remaining < 0.25:  # Less than 15 min - risky
            time_score = 20
        elif hours_remaining < 0.5:  # 15-30 min
            time_score = 60
        elif hours_remaining <= 2:  # 30min - 2hr - ideal
            time_score = 100
        elif hours_remaining <= 6:  # 2-6hr
            time_score = 80
        else:
            time_score = 60

        return (
            profit_score * 0.4 +
            liquidity_score * 0.3 +
            time_score * 0.2 +
            10  # Base points
        )

    def calculate_trade_details(
        self,
        opportunity: ArbitrageOpportunity,
        position_size: float
    ) -> dict:
        """
        Calculate detailed trade information for an opportunity.

        Args:
            opportunity: The opportunity to trade
            position_size: Dollar amount to invest

        Returns:
            Dictionary with trade details
        """
        # Calculate cost per contract set
        if opportunity.trade_direction == "buy_brackets":
            cost_per_set = sum(
                b.yes_ask for b in opportunity.required_brackets
            )
        else:
            cost_per_set = opportunity.threshold_market.yes_ask
            for bracket in opportunity.required_brackets:
                cost_per_set += bracket.yes_ask

        if cost_per_set <= 0:
            return {"error": "Invalid cost calculation"}

        # Calculate number of contracts
        contracts = int(position_size / cost_per_set)

        if contracts <= 0:
            return {"error": "Position size too small"}

        # Constrain by liquidity
        contracts = min(contracts, opportunity.max_liquidity_contracts)

        # Calculate costs and fees
        total_cost = contracts * cost_per_set
        total_fees = 0

        if opportunity.trade_direction == "buy_brackets":
            for bracket in opportunity.required_brackets:
                total_fees += calculate_fee(contracts, bracket.yes_ask)
        else:
            total_fees += calculate_fee(
                contracts, opportunity.threshold_market.yes_ask
            )
            for bracket in opportunity.required_brackets:
                total_fees += calculate_fee(contracts, bracket.yes_ask)

        # Calculate profit
        payout = contracts  # $1 per contract set
        net_profit = payout - total_cost - total_fees

        return {
            "contracts": contracts,
            "cost_per_set": round(cost_per_set, 4),
            "total_cost": round(total_cost, 2),
            "total_fees": round(total_fees, 2),
            "total_investment": round(total_cost + total_fees, 2),
            "guaranteed_payout": payout,
            "net_profit": round(net_profit, 2),
            "net_profit_pct": round(net_profit / (total_cost + total_fees) * 100, 2),
            "trade_direction": opportunity.trade_direction
        }
