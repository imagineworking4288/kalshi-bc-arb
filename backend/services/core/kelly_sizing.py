"""
Kelly Criterion position sizing.
Calculates optimal bet size based on edge and bankroll.
"""

from dataclasses import dataclass
from typing import Optional

from ..log_config import get_logger

logger = get_logger("kelly_sizing")


@dataclass
class KellyConfig:
    """Configuration for Kelly Criterion sizing."""
    fraction: float = 0.25  # Fraction of Kelly to use (1/4 Kelly is conservative)
    min_edge_percent: float = 5.0  # Minimum edge required to trade
    max_bet_percent: float = 5.0  # Maximum bet as % of bankroll
    min_contracts: int = 1  # Minimum contracts to trade
    max_contracts: int = 100  # Maximum contracts per trade


@dataclass
class KellyResult:
    """Result of Kelly sizing calculation."""
    contracts: int
    kelly_fraction: float  # Raw Kelly fraction
    edge_percent: float
    bet_percent: float  # Actual bet as % of bankroll
    reason: str


class KellySizing:
    """
    Optimal position sizing using the Kelly Criterion.

    The Kelly Criterion determines the optimal bet size to maximize
    long-term growth while managing risk. Formula:

    Kelly % = (edge) / (odds against)

    For binary markets where payout is 100¢:
    Kelly % = edge / (1 - market_prob)

    We use fractional Kelly (typically 1/4) to reduce volatility.
    """

    def __init__(self, config: Optional[KellyConfig] = None):
        """
        Initialize Kelly sizing calculator.

        Args:
            config: Configuration parameters (uses defaults if not provided)
        """
        self.config = config or KellyConfig()

    def calculate(
        self,
        model_prob: float,
        market_price_cents: int,
        bankroll_cents: int
    ) -> KellyResult:
        """
        Calculate optimal position size for a directional trade.

        Args:
            model_prob: Our probability estimate (0.0 to 1.0)
            market_price_cents: Current market price in cents (1-99)
            bankroll_cents: Available bankroll in cents

        Returns:
            KellyResult with recommended contracts and reasoning
        """
        # Convert market price to probability
        market_prob = market_price_cents / 100.0

        # Calculate edge
        edge = model_prob - market_prob
        edge_percent = edge * 100

        # Check minimum edge
        if edge_percent < self.config.min_edge_percent:
            return KellyResult(
                contracts=0,
                kelly_fraction=0,
                edge_percent=edge_percent,
                bet_percent=0,
                reason=f"Edge {edge_percent:.1f}% below minimum {self.config.min_edge_percent}%"
            )

        # Calculate raw Kelly fraction
        # Kelly = edge / (1 - market_prob) for binary outcomes
        if market_prob >= 0.99:
            # Avoid division by near-zero
            raw_kelly = 0
        else:
            raw_kelly = edge / (1 - market_prob)

        # Apply fractional Kelly
        adjusted_kelly = raw_kelly * self.config.fraction

        # Cap at max bet percent
        adjusted_kelly = min(adjusted_kelly, self.config.max_bet_percent / 100)

        # Calculate bet amount in cents
        bet_cents = int(bankroll_cents * adjusted_kelly)

        # Calculate contracts (each contract costs market_price_cents)
        if market_price_cents <= 0:
            contracts = 0
        else:
            contracts = bet_cents // market_price_cents

        # Apply contract limits
        contracts = max(contracts, self.config.min_contracts if contracts > 0 else 0)
        contracts = min(contracts, self.config.max_contracts)

        # Calculate actual bet percent
        actual_bet_cents = contracts * market_price_cents
        bet_percent = (actual_bet_cents / bankroll_cents * 100) if bankroll_cents > 0 else 0

        return KellyResult(
            contracts=contracts,
            kelly_fraction=adjusted_kelly,
            edge_percent=edge_percent,
            bet_percent=bet_percent,
            reason=f"Kelly={raw_kelly:.2f} adj={adjusted_kelly:.3f} -> {contracts} contracts"
        )

    def calculate_arbitrage(
        self,
        total_cost_cents: int,
        payout_cents: int,
        bankroll_cents: int
    ) -> int:
        """
        Calculate position size for arbitrage opportunity.

        Arbitrage has guaranteed profit, so we can be more aggressive.
        We allow up to 10% of bankroll per arbitrage.

        Args:
            total_cost_cents: Total cost to enter the arbitrage position
            payout_cents: Guaranteed payout (typically 100 cents)
            bankroll_cents: Available bankroll in cents

        Returns:
            Number of contract sets to buy
        """
        if total_cost_cents <= 0 or payout_cents <= total_cost_cents:
            return 0

        # Guaranteed edge
        edge_cents = payout_cents - total_cost_cents
        edge_percent = (edge_cents / total_cost_cents) * 100

        # For arbitrage, we can be aggressive: up to 10% of bankroll
        max_investment = int(bankroll_cents * 0.10)

        # How many complete sets can we afford?
        max_sets = max_investment // total_cost_cents

        # Apply limits
        max_sets = max(max_sets, 1) if max_sets > 0 else 0
        max_sets = min(max_sets, self.config.max_contracts)

        logger.info(
            f"Arbitrage sizing: cost={total_cost_cents}¢ edge={edge_percent:.1f}% "
            f"bankroll={bankroll_cents}¢ -> {max_sets} sets"
        )

        return max_sets

    def calculate_for_budget(
        self,
        model_prob: float,
        market_price_cents: int,
        budget_cents: int
    ) -> KellyResult:
        """
        Calculate position size given a fixed budget.

        Useful when you have a specific amount allocated for a trade.

        Args:
            model_prob: Our probability estimate (0.0 to 1.0)
            market_price_cents: Current market price in cents (1-99)
            budget_cents: Maximum amount to spend in cents

        Returns:
            KellyResult with recommended contracts
        """
        # Calculate edge
        market_prob = market_price_cents / 100.0
        edge = model_prob - market_prob
        edge_percent = edge * 100

        # Check minimum edge
        if edge_percent < self.config.min_edge_percent:
            return KellyResult(
                contracts=0,
                kelly_fraction=0,
                edge_percent=edge_percent,
                bet_percent=0,
                reason=f"Edge {edge_percent:.1f}% below minimum {self.config.min_edge_percent}%"
            )

        # Calculate max contracts from budget
        if market_price_cents <= 0:
            contracts = 0
        else:
            contracts = budget_cents // market_price_cents

        # Apply limits
        contracts = min(contracts, self.config.max_contracts)

        # Calculate actual spend
        actual_spend = contracts * market_price_cents
        bet_percent = (actual_spend / budget_cents * 100) if budget_cents > 0 else 0

        return KellyResult(
            contracts=contracts,
            kelly_fraction=0,  # N/A for budget-based
            edge_percent=edge_percent,
            bet_percent=bet_percent,
            reason=f"Budget-based: {contracts} contracts @ {market_price_cents}¢"
        )

    def should_trade(
        self,
        model_prob: float,
        market_price_cents: int
    ) -> tuple[bool, float]:
        """
        Quick check if trade meets minimum edge requirement.

        Args:
            model_prob: Our probability estimate
            market_price_cents: Market price in cents

        Returns:
            Tuple of (should_trade, edge_percent)
        """
        market_prob = market_price_cents / 100.0
        edge_percent = (model_prob - market_prob) * 100

        return edge_percent >= self.config.min_edge_percent, edge_percent
