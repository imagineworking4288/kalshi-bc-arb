"""
Enhanced prediction engine with fee-aware calculations.

Addresses Issues #5-#10:
- #5: Correct probability math (CDF difference)
- #6: Uses forecast_std_dev from NWSForecast
- #7: Fee-aware expected value calculation
- #8: Position-aware recommendations
- #9: Kelly criterion with fractional Kelly (0.25)
- #10: Minimum edge threshold (5%)
"""

import math
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from ..core.fee_calculator import calculate_fee, FeeResult


class RecommendationAction(str, Enum):
    """Recommended trading action."""
    BUY_YES = "buy_yes"
    BUY_NO = "buy_no"
    HOLD = "hold"
    SKIP = "skip"  # Don't trade (edge too low or position conflict)


@dataclass
class BracketAnalysis:
    """Complete analysis for a single bracket."""
    ticker: str
    floor_strike: Optional[int]
    cap_strike: Optional[int]
    label: str

    # Probability
    model_probability: float
    market_implied_probability: float
    probability_edge: float  # model - market

    # Pricing
    yes_price_cents: Optional[int]
    no_price_cents: Optional[int]

    # Fee-aware EV (Issue #7)
    yes_ev_cents: float
    no_ev_cents: float
    yes_ev_after_fee: float
    no_ev_after_fee: float

    # Fees
    yes_fee_cents: float
    no_fee_cents: float

    # Recommendation
    recommended_action: RecommendationAction
    recommended_side: Optional[str] = None  # "yes" or "no"
    kelly_fraction: float = 0.0
    recommended_contracts: int = 0

    # Position awareness (Issue #8)
    has_existing_position: bool = False
    existing_side: Optional[str] = None
    existing_quantity: int = 0
    position_conflict: bool = False

    # Confidence
    confidence: float = 0.0

    @property
    def has_edge(self) -> bool:
        """Check if there's a meaningful edge (Issue #10: 5% threshold)."""
        return abs(self.probability_edge) >= 0.05

    @property
    def best_ev_after_fee(self) -> float:
        """Best EV after fees between YES and NO."""
        return max(self.yes_ev_after_fee, self.no_ev_after_fee)


@dataclass
class PredictionResult:
    """Complete prediction result for an event."""
    event_ticker: str
    city: str
    forecast_high: int
    forecast_std_dev: float
    forecast_source: str

    brackets: List[BracketAnalysis]
    total_probability: float

    # Best opportunity
    best_bracket: Optional[BracketAnalysis] = None
    total_recommended_cost: float = 0.0

    # Metadata
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: List[str] = field(default_factory=list)

    @property
    def has_opportunities(self) -> bool:
        """Check if any bracket has a tradeable opportunity."""
        return any(b.recommended_action in [RecommendationAction.BUY_YES, RecommendationAction.BUY_NO]
                   for b in self.brackets)


@dataclass
class PositionInfo:
    """Information about existing position."""
    ticker: str
    side: str  # "yes" or "no"
    quantity: int
    avg_cost_cents: float = 0.0


class PredictionEngineV2:
    """
    Enhanced prediction engine with fee-aware EV and position awareness.

    Improvements over v1:
    - Fee-aware expected value (Issue #7)
    - Position conflict detection (Issue #8)
    - Kelly criterion sizing (Issue #9)
    - Edge threshold (Issue #10)
    """

    # Configuration
    MIN_EDGE_THRESHOLD = 0.05  # 5% minimum edge (Issue #10)
    KELLY_FRACTION = 0.25     # Fractional Kelly for safety (Issue #9)
    DEFAULT_CONTRACTS = 10    # Default contracts if Kelly not used
    MIN_CONFIDENCE = 0.5
    MAX_CONFIDENCE = 0.95

    def __init__(
        self,
        min_edge: float = 0.05,
        kelly_fraction: float = 0.25,
        max_position_per_market: int = 100,
        bankroll_cents: int = 100000,  # $1000 default
    ):
        self.min_edge = min_edge
        self.kelly_fraction = kelly_fraction
        self.max_position_per_market = max_position_per_market
        self.bankroll_cents = bankroll_cents

    def analyze_brackets(
        self,
        brackets: List[Dict[str, Any]],
        forecast_high: int,
        forecast_std_dev: float,
        positions: Optional[List[PositionInfo]] = None,
        forecast_source: str = "nws",
        event_ticker: str = "",
        city: str = "",
    ) -> PredictionResult:
        """
        Analyze bracket markets with fee-aware calculations.

        Args:
            brackets: List of bracket dicts with keys:
                - ticker: Market ticker
                - floor_strike: Lower bound (or None for "below X")
                - cap_strike: Upper bound (or None for "X or above")
                - yes_price: Current YES ask in cents (optional)
                - no_price: Current NO ask in cents (optional)
                - yes_ask: Alternative key for yes_price
                - no_ask: Alternative key for no_price
            forecast_high: Forecasted high temperature
            forecast_std_dev: Standard deviation of forecast
            positions: List of existing positions
            forecast_source: Source of forecast data
            event_ticker: Event ticker
            city: City code

        Returns:
            PredictionResult with analysis for each bracket
        """
        warnings = []
        position_map = self._build_position_map(positions or [])

        # Calculate probabilities for all brackets
        bracket_analyses = []
        total_prob = 0.0

        for bracket in brackets:
            ticker = bracket.get("ticker", "")
            floor_strike = bracket.get("floor_strike") or bracket.get("floor")
            cap_strike = bracket.get("cap_strike") or bracket.get("cap")

            # Get market prices
            yes_price = bracket.get("yes_price") or bracket.get("yes_ask")
            no_price = bracket.get("no_price") or bracket.get("no_ask")

            # Calculate model probability
            model_prob = self._bracket_probability(
                forecast_high, forecast_std_dev, floor_strike, cap_strike
            )
            total_prob += model_prob

            # Calculate market implied probability
            market_prob = (yes_price / 100.0) if yes_price else 0.5

            # Calculate edge
            edge = model_prob - market_prob

            # Get existing position
            existing_pos = position_map.get(ticker)
            has_position = existing_pos is not None
            existing_side = existing_pos.side if existing_pos else None
            existing_qty = existing_pos.quantity if existing_pos else 0

            # Calculate fee-aware EV (Issue #7)
            yes_ev, yes_ev_after_fee, yes_fee = self._calculate_fee_aware_ev(
                prob=model_prob,
                price_cents=yes_price,
                side="yes",
            ) if yes_price else (0.0, 0.0, 0.0)

            no_ev, no_ev_after_fee, no_fee = self._calculate_fee_aware_ev(
                prob=1 - model_prob,
                price_cents=no_price,
                side="no",
            ) if no_price else (0.0, 0.0, 0.0)

            # Determine recommendation (Issue #8: position-aware)
            action, side, kelly, contracts = self._get_recommendation(
                model_prob=model_prob,
                yes_price=yes_price,
                no_price=no_price,
                yes_ev_after_fee=yes_ev_after_fee,
                no_ev_after_fee=no_ev_after_fee,
                existing_side=existing_side,
                existing_qty=existing_qty,
            )

            # Check for position conflict
            position_conflict = False
            if has_position and action in [RecommendationAction.BUY_YES, RecommendationAction.BUY_NO]:
                rec_side = "yes" if action == RecommendationAction.BUY_YES else "no"
                if existing_side and existing_side != rec_side:
                    position_conflict = True
                    action = RecommendationAction.SKIP
                    contracts = 0
                    warnings.append(f"Position conflict in {ticker}: have {existing_side}, want {rec_side}")

            # Calculate confidence
            confidence = self._calculate_confidence(
                model_prob, forecast_std_dev, edge
            )

            analysis = BracketAnalysis(
                ticker=ticker,
                floor_strike=floor_strike,
                cap_strike=cap_strike,
                label=self._bracket_label(floor_strike, cap_strike),
                model_probability=model_prob,
                market_implied_probability=market_prob,
                probability_edge=edge,
                yes_price_cents=yes_price,
                no_price_cents=no_price,
                yes_ev_cents=yes_ev,
                no_ev_cents=no_ev,
                yes_ev_after_fee=yes_ev_after_fee,
                no_ev_after_fee=no_ev_after_fee,
                yes_fee_cents=yes_fee,
                no_fee_cents=no_fee,
                recommended_action=action,
                recommended_side=side,
                kelly_fraction=kelly,
                recommended_contracts=contracts,
                has_existing_position=has_position,
                existing_side=existing_side,
                existing_quantity=existing_qty,
                position_conflict=position_conflict,
                confidence=confidence,
            )

            bracket_analyses.append(analysis)

        # Normalize probabilities if needed
        if abs(total_prob - 1.0) > 0.05:
            warnings.append(f"Probabilities summed to {total_prob:.3f}, expected ~1.0")
            if total_prob > 0:
                for b in bracket_analyses:
                    b.model_probability /= total_prob
                total_prob = 1.0

        # Find best opportunity
        tradeable = [b for b in bracket_analyses
                     if b.recommended_action in [RecommendationAction.BUY_YES, RecommendationAction.BUY_NO]]
        best_bracket = max(tradeable, key=lambda b: b.best_ev_after_fee) if tradeable else None

        # Calculate total recommended cost
        total_cost = sum(
            b.recommended_contracts * (b.yes_price_cents if b.recommended_side == "yes" else b.no_price_cents or 0)
            for b in bracket_analyses if b.recommended_contracts > 0
        )

        return PredictionResult(
            event_ticker=event_ticker,
            city=city,
            forecast_high=forecast_high,
            forecast_std_dev=forecast_std_dev,
            forecast_source=forecast_source,
            brackets=bracket_analyses,
            total_probability=total_prob,
            best_bracket=best_bracket,
            total_recommended_cost=total_cost,
            warnings=warnings,
        )

    def _bracket_probability(
        self,
        mean: float,
        std_dev: float,
        floor_strike: Optional[int],
        cap_strike: Optional[int],
    ) -> float:
        """
        Calculate probability that temperature falls in bracket.
        Issue #5: Correct CDF difference calculation.
        """
        if floor_strike is None and cap_strike is None:
            return 0.0

        # Handle edge brackets (open-ended)
        if floor_strike is None:
            # "Below X" bracket: P(T < cap)
            return self._norm_cdf(cap_strike, mean, std_dev)

        if cap_strike is None:
            # "X or above" bracket: P(T >= floor) = 1 - P(T < floor)
            return 1.0 - self._norm_cdf(floor_strike, mean, std_dev)

        # Normal bracket: P(floor <= T <= cap)
        # For integer temps: P(floor <= T <= cap) = P(T < cap+1) - P(T < floor)
        prob_below_cap = self._norm_cdf(cap_strike + 1, mean, std_dev)
        prob_below_floor = self._norm_cdf(floor_strike, mean, std_dev)

        return max(0.0, prob_below_cap - prob_below_floor)

    def _norm_cdf(self, x: float, mean: float, std_dev: float) -> float:
        """Cumulative distribution function for normal distribution."""
        if std_dev <= 0:
            return 1.0 if x >= mean else 0.0
        z = (x - mean) / std_dev
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def _calculate_fee_aware_ev(
        self,
        prob: float,
        price_cents: Optional[int],
        side: str,
        contracts: int = 10,
    ) -> Tuple[float, float, float]:
        """
        Calculate fee-aware expected value.
        Issue #7: Include fees in EV calculation.

        Returns: (ev_cents, ev_after_fee_cents, fee_cents)
        """
        if price_cents is None or price_cents <= 0 or price_cents >= 100:
            return 0.0, 0.0, 0.0

        # Basic EV: E[profit] = prob * 100 - price
        # If we win, we get 100 cents. If we lose, we get 0.
        # Cost is price_cents per contract.
        ev_cents = (prob * 100) - price_cents

        # Calculate fee
        fee_result = calculate_fee(contracts, price_cents, is_maker=False)
        fee_per_contract = fee_result.fee_cents / contracts if contracts > 0 else 0

        # EV after fee
        ev_after_fee = ev_cents - fee_per_contract

        return ev_cents, ev_after_fee, fee_result.fee_cents

    def _get_recommendation(
        self,
        model_prob: float,
        yes_price: Optional[int],
        no_price: Optional[int],
        yes_ev_after_fee: float,
        no_ev_after_fee: float,
        existing_side: Optional[str],
        existing_qty: int,
    ) -> Tuple[RecommendationAction, Optional[str], float, int]:
        """
        Get trading recommendation.
        Issues #8, #9, #10: Position-aware, Kelly sizing, edge threshold.

        Returns: (action, side, kelly_fraction, contracts)
        """
        # Check edge threshold (Issue #10)
        yes_edge = model_prob - (yes_price / 100.0 if yes_price else 0.5)
        no_edge = (1 - model_prob) - (no_price / 100.0 if no_price else 0.5)

        has_yes_edge = yes_edge >= self.min_edge and yes_ev_after_fee > 0
        has_no_edge = no_edge >= self.min_edge and no_ev_after_fee > 0

        if not has_yes_edge and not has_no_edge:
            return RecommendationAction.HOLD, None, 0.0, 0

        # Determine best side
        if has_yes_edge and has_no_edge:
            # Both have edge - pick better one
            if yes_ev_after_fee > no_ev_after_fee:
                side = "yes"
                edge = yes_edge
                price = yes_price
                prob = model_prob
            else:
                side = "no"
                edge = no_edge
                price = no_price
                prob = 1 - model_prob
        elif has_yes_edge:
            side = "yes"
            edge = yes_edge
            price = yes_price
            prob = model_prob
        else:
            side = "no"
            edge = no_edge
            price = no_price
            prob = 1 - model_prob

        # Check position conflict (Issue #8)
        if existing_side and existing_side != side:
            return RecommendationAction.SKIP, None, 0.0, 0

        # Calculate Kelly fraction (Issue #9)
        kelly = self._calculate_kelly(prob, price / 100.0 if price else 0.5)
        kelly_fractional = kelly * self.kelly_fraction  # Use fractional Kelly

        # Calculate contracts
        contracts = self._calculate_contracts(kelly_fractional, price)

        # Respect max position
        if existing_side == side:
            remaining = max(0, self.max_position_per_market - existing_qty)
            contracts = min(contracts, remaining)

        action = RecommendationAction.BUY_YES if side == "yes" else RecommendationAction.BUY_NO

        return action, side, kelly_fractional, contracts

    def _calculate_kelly(self, prob: float, price: float) -> float:
        """
        Calculate Kelly criterion bet fraction.
        Issue #9: Proper Kelly sizing.

        Kelly formula: f = (p * b - q) / b
        Where:
        - p = probability of winning
        - q = probability of losing (1 - p)
        - b = odds (payout / stake - 1) = (100 / price - 1)
        """
        if price <= 0 or price >= 1:
            return 0.0

        b = (1.0 / price) - 1  # Odds
        q = 1 - prob

        kelly = (prob * b - q) / b if b > 0 else 0

        # Kelly can't be negative or > 1
        return max(0.0, min(1.0, kelly))

    def _calculate_contracts(self, kelly_fraction: float, price_cents: Optional[int]) -> int:
        """Calculate number of contracts based on Kelly fraction and bankroll."""
        if kelly_fraction <= 0 or not price_cents or price_cents <= 0:
            return 0

        # Position value = bankroll * kelly_fraction
        position_value = self.bankroll_cents * kelly_fraction

        # Contracts = position_value / price
        contracts = int(position_value / price_cents)

        # Apply limits
        contracts = max(1, min(contracts, self.max_position_per_market))

        return contracts

    def _calculate_confidence(
        self,
        probability: float,
        std_dev: float,
        edge: float,
    ) -> float:
        """Calculate confidence in the recommendation."""
        # Higher confidence when:
        # - Lower std_dev (more certain forecast)
        # - Higher edge (bigger mispricing)
        # - Probability away from 50% (clearer outcome)

        std_confidence = max(0.5, 1.0 - (std_dev - 1.5) / 10.0)
        edge_confidence = min(0.95, 0.5 + abs(edge) * 2)
        prob_distance = abs(probability - 0.5)
        prob_confidence = 0.5 + prob_distance

        # Geometric mean
        confidence = (std_confidence * edge_confidence * prob_confidence) ** (1/3)

        return max(self.MIN_CONFIDENCE, min(self.MAX_CONFIDENCE, confidence))

    def _bracket_label(
        self,
        floor_strike: Optional[int],
        cap_strike: Optional[int],
    ) -> str:
        """Generate human-readable bracket label."""
        if floor_strike is None and cap_strike is not None:
            return f"<{cap_strike}F"
        if cap_strike is None and floor_strike is not None:
            return f">={floor_strike}F"
        if floor_strike is not None and cap_strike is not None:
            return f"{floor_strike}-{cap_strike}F"
        return "Unknown"

    def _build_position_map(self, positions: List[PositionInfo]) -> Dict[str, PositionInfo]:
        """Build map of ticker -> position for quick lookup."""
        return {pos.ticker: pos for pos in positions}


# Singleton instance
_engine: Optional[PredictionEngineV2] = None


def get_engine(
    min_edge: float = 0.05,
    kelly_fraction: float = 0.25,
    bankroll_cents: int = 100000,
) -> PredictionEngineV2:
    """Get singleton engine instance."""
    global _engine
    if _engine is None:
        _engine = PredictionEngineV2(
            min_edge=min_edge,
            kelly_fraction=kelly_fraction,
            bankroll_cents=bankroll_cents,
        )
    return _engine


def analyze_brackets(
    brackets: List[Dict[str, Any]],
    forecast_high: int,
    forecast_std_dev: float,
    **kwargs
) -> PredictionResult:
    """Convenience function for bracket analysis."""
    return get_engine().analyze_brackets(
        brackets, forecast_high, forecast_std_dev, **kwargs
    )
