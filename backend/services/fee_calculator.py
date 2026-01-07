"""
Fee calculator for Kalshi prediction markets.

Kalshi Fee Formula:
- Taker Fee = 7% × price × (1 - price) per contract
- Maker Fee = 3.5% × price × (1 - price) per contract

Example: At 50¢ price → 1.75¢ taker fee per contract
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any, Optional


class OrderType(Enum):
    """Order type for fee calculation."""
    TAKER = "taker"
    MAKER = "maker"


@dataclass
class FeeBreakdown:
    """Detailed fee breakdown for a trade."""
    contracts: int
    price_cents: int
    order_type: OrderType
    fee_per_contract: float
    total_fee: float
    fee_percentage: float


@dataclass
class ArbitrageWithFees:
    """Arbitrage analysis including fee calculations."""
    strategy: str
    gross_cost: int
    total_fees: float
    net_cost: float
    payout: int
    gross_profit: int
    net_profit: float
    is_profitable: bool
    brackets_used: Optional[int] = None


class FeeCalculator:
    """Calculate Kalshi trading fees and analyze arbitrage opportunities."""

    TAKER_RATE = 0.07  # 7%
    MAKER_RATE = 0.035  # 3.5%

    @classmethod
    def fee_per_contract(cls, price_cents: int, order_type: OrderType) -> float:
        """
        Calculate fee per contract using Kalshi formula.

        Formula: rate × price × (1 - price)

        Args:
            price_cents: Price in cents (0-100)
            order_type: TAKER or MAKER

        Returns:
            Fee in cents per contract
        """
        rate = cls.TAKER_RATE if order_type == OrderType.TAKER else cls.MAKER_RATE
        price_decimal = price_cents / 100.0
        fee_cents = rate * price_decimal * (1 - price_decimal) * 100
        return fee_cents

    @classmethod
    def calculate_trade_fee(
        cls,
        price_cents: int,
        contracts: int = 1,
        order_type: OrderType = OrderType.TAKER
    ) -> FeeBreakdown:
        """
        Calculate total fee for a trade.

        Args:
            price_cents: Price in cents (0-100)
            contracts: Number of contracts
            order_type: TAKER or MAKER

        Returns:
            FeeBreakdown with detailed calculations
        """
        fee_per = cls.fee_per_contract(price_cents, order_type)
        total_fee = fee_per * contracts

        # Calculate fee as percentage of trade cost
        trade_cost = price_cents * contracts
        fee_percentage = (total_fee / trade_cost * 100) if trade_cost > 0 else 0

        return FeeBreakdown(
            contracts=contracts,
            price_cents=price_cents,
            order_type=order_type,
            fee_per_contract=fee_per,
            total_fee=total_fee,
            fee_percentage=fee_percentage
        )

    @classmethod
    def analyze_weather_arbitrage(
        cls,
        yes_asks: List[int],
        no_asks: List[int],
        order_type: OrderType = OrderType.TAKER
    ) -> Dict[str, Any]:
        """
        Analyze all three arbitrage strategies for weather markets.

        Strategies:
        1. all_yes: Buy YES on every bracket → payout = 100¢ (one must win)
        2. all_no: Buy NO on every bracket → payout = (n-1) × 100¢ (n-1 must win)
        3. min_2_no: Buy NO on 2 cheapest brackets → payout = 100¢ (at least one must win)

        Args:
            yes_asks: List of YES ask prices in cents
            no_asks: List of NO ask prices in cents
            order_type: TAKER or MAKER

        Returns:
            Dict with analysis for each strategy and best_strategy/has_arbitrage
        """
        if not yes_asks or not no_asks:
            return cls._empty_result()

        n = len(yes_asks)

        # Strategy 1: All YES
        all_yes_result = cls._analyze_all_yes(yes_asks, order_type)

        # Strategy 2: All NO
        all_no_result = cls._analyze_all_no(no_asks, n, order_type)

        # Strategy 3: Min 2-NO
        min_2_no_result = cls._analyze_min_2_no(no_asks, order_type)

        # Determine best strategy (highest net profit among profitable ones)
        best_strategy = None
        best_net_profit = 0

        for name, result in [("all_yes", all_yes_result), ("all_no", all_no_result), ("min_2_no", min_2_no_result)]:
            if result["is_arb"] and result["net_profit"] > best_net_profit:
                best_strategy = name
                best_net_profit = result["net_profit"]

        return {
            "all_yes": all_yes_result,
            "all_no": all_no_result,
            "min_2_no": min_2_no_result,
            "best_strategy": best_strategy,
            "has_arbitrage": best_strategy is not None
        }

    @classmethod
    def _analyze_all_yes(cls, yes_asks: List[int], order_type: OrderType) -> Dict[str, Any]:
        """Analyze all_yes strategy: buy YES on every bracket."""
        gross_cost = sum(yes_asks)
        payout = 100  # One bracket must win

        # Calculate fees for each YES position
        total_fees = sum(cls.fee_per_contract(price, order_type) for price in yes_asks)

        net_cost = gross_cost + total_fees
        gross_profit = payout - gross_cost
        net_profit = payout - net_cost

        return {
            "cost": gross_cost,
            "fees": round(total_fees, 2),
            "net_cost": round(net_cost, 2),
            "payout": payout,
            "gross_profit": gross_profit,
            "net_profit": round(net_profit, 2),
            "is_arb": net_profit > 0,
            "brackets_used": len(yes_asks)
        }

    @classmethod
    def _analyze_all_no(cls, no_asks: List[int], n: int, order_type: OrderType) -> Dict[str, Any]:
        """Analyze all_no strategy: buy NO on every bracket."""
        gross_cost = sum(no_asks)
        payout = (n - 1) * 100  # n-1 brackets must win

        # Calculate fees for each NO position
        total_fees = sum(cls.fee_per_contract(price, order_type) for price in no_asks)

        net_cost = gross_cost + total_fees
        gross_profit = payout - gross_cost
        net_profit = payout - net_cost

        return {
            "cost": gross_cost,
            "fees": round(total_fees, 2),
            "net_cost": round(net_cost, 2),
            "payout": payout,
            "gross_profit": gross_profit,
            "net_profit": round(net_profit, 2),
            "is_arb": net_profit > 0,
            "brackets_used": len(no_asks)
        }

    @classmethod
    def _analyze_min_2_no(cls, no_asks: List[int], order_type: OrderType) -> Dict[str, Any]:
        """Analyze min_2_no strategy: buy NO on 2 cheapest brackets."""
        if len(no_asks) < 2:
            return {
                "cost": 0,
                "fees": 0,
                "net_cost": 0,
                "payout": 100,
                "gross_profit": 0,
                "net_profit": 0,
                "is_arb": False,
                "brackets_used": 0,
                "cheapest_indices": []
            }

        # Find 2 cheapest NO positions with their original indices
        indexed_no = [(price, idx) for idx, price in enumerate(no_asks)]
        sorted_indexed = sorted(indexed_no, key=lambda x: x[0])
        cheapest_2_indexed = sorted_indexed[:2]

        # Extract prices and indices
        cheapest_2 = [price for price, idx in cheapest_2_indexed]
        cheapest_indices = [idx for price, idx in cheapest_2_indexed]

        gross_cost = sum(cheapest_2)
        payout = 100  # At least one of the 2 must win

        # Calculate fees for the 2 positions
        total_fees = sum(cls.fee_per_contract(price, order_type) for price in cheapest_2)

        net_cost = gross_cost + total_fees
        gross_profit = payout - gross_cost
        net_profit = payout - net_cost

        return {
            "cost": gross_cost,
            "fees": round(total_fees, 2),
            "net_cost": round(net_cost, 2),
            "payout": payout,
            "gross_profit": gross_profit,
            "net_profit": round(net_profit, 2),
            "is_arb": net_profit > 0,
            "brackets_used": 2,
            "cheapest_indices": cheapest_indices  # Return indices for bracket lookup
        }

    @classmethod
    def _empty_result(cls) -> Dict[str, Any]:
        """Return empty result when no data available."""
        empty_strategy = {
            "cost": 0,
            "fees": 0,
            "net_cost": 0,
            "payout": 0,
            "gross_profit": 0,
            "net_profit": 0,
            "is_arb": False,
            "brackets_used": 0
        }
        return {
            "all_yes": empty_strategy.copy(),
            "all_no": empty_strategy.copy(),
            "min_2_no": {**empty_strategy.copy(), "cheapest_indices": []},
            "best_strategy": None,
            "has_arbitrage": False
        }


# Convenience function
def calculate_fee(price_cents: int, contracts: int = 1, maker: bool = False) -> float:
    """
    Convenience function to calculate fee for a trade.

    Args:
        price_cents: Price in cents (0-100)
        contracts: Number of contracts
        maker: True for maker fee, False for taker fee

    Returns:
        Total fee in cents
    """
    order_type = OrderType.MAKER if maker else OrderType.TAKER
    breakdown = FeeCalculator.calculate_trade_fee(price_cents, contracts, order_type)
    return breakdown.total_fee
