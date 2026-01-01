"""Kalshi fee calculations."""

from dataclasses import dataclass
from typing import Tuple

@dataclass
class FeeCalculator:
    """Calculate Kalshi trading fees."""

    # Fee structure: 7% of (contracts × price × (1 - price))
    FEE_RATE = 0.07

    # Maker discount
    MAKER_DISCOUNT = 0.5

    @classmethod
    def calculate_fee(cls, contracts: int, price_cents: int, is_maker: bool = False) -> int:
        """
        Calculate fee for a trade.

        Args:
            contracts: Number of contracts
            price_cents: Price in cents (1-99)
            is_maker: True if maker order (gets discount)

        Returns:
            Fee in cents
        """
        price = price_cents / 100.0

        # Fee formula: 7% × contracts × price × (1 - price)
        fee = cls.FEE_RATE * contracts * price * (1 - price)

        # Maker discount
        if is_maker:
            fee *= (1 - cls.MAKER_DISCOUNT)

        # Round up to nearest cent
        return max(1, int(fee * 100 + 0.99))

    @classmethod
    def calculate_arbitrage_profit(cls, total_cost_cents: int, contracts: int = 1) -> Tuple[int, int, int]:
        """
        Calculate net profit from bracket arbitrage.

        Args:
            total_cost_cents: Sum of all bracket YES prices
            contracts: Number of contracts per bracket

        Returns:
            Tuple of (gross_profit, total_fees, net_profit) in cents
        """
        # Payout is always $1 (100 cents) per contract
        payout = 100 * contracts
        gross_profit = payout - total_cost_cents

        # Estimate fees (simplified - actual depends on each bracket's price)
        # Use average price for fee estimation
        avg_price = total_cost_cents // contracts if contracts > 0 else 50
        total_fees = 0

        # Would need bracket count for accurate fee calc
        # For now estimate ~2 cents per bracket set
        total_fees = 2 * contracts

        net_profit = gross_profit - total_fees

        return gross_profit, total_fees, net_profit
