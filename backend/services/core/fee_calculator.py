"""
Consolidated Fee Calculator for Kalshi Prediction Markets.

This module provides accurate fee calculations for all Kalshi trading operations.
It consolidates the functionality from three previous implementations into a single,
well-documented calculator.

Kalshi Fee Structure:
--------------------
- Taker Fee: 7% x price x (1 - price) per contract
- Maker Fee: 3.5% x price x (1 - price) per contract (50% discount)
- Minimum Fee: 1 cent per contract

Fee Formula Explanation:
-----------------------
The fee is based on the probability-weighted variance of the contract.
At 50 cents (maximum uncertainty), fees are highest.
At extreme prices (near 1 or 99 cents), fees approach minimum.

Examples:
    - 10 contracts at 50 cents (taker): ceil(0.07 * 10 * 0.5 * 0.5 * 100) = 18 cents
    - 10 contracts at 60 cents (taker): ceil(0.07 * 10 * 0.6 * 0.4 * 100) = 17 cents
    - 10 contracts at 30 cents (maker): ceil(0.035 * 10 * 0.3 * 0.7 * 100) = 8 cents

Usage:
    from backend.services.core import FeeCalculator, FeeType, FeeCalculation

    calc = FeeCalculator()

    # Single trade fee
    result = calc.calculate(10, 50, FeeType.TAKER)
    print(f"Fee: {result.fee_cents} cents, Total: {result.total_cost_cents} cents")

    # Multi-leg arbitrage
    legs = [
        {"ticker": "KXBTC-A", "contracts": 10, "price_cents": 25},
        {"ticker": "KXBTC-B", "contracts": 10, "price_cents": 30},
    ]
    result = calc.calculate_multi_leg(legs, FeeType.TAKER)
    print(f"Total fees: {result['total_fees_cents']} cents")

    # Arbitrage profit estimation
    profit = calc.estimate_arbitrage_profit(legs, payout_cents=100)
    print(f"Profitable: {profit['is_profitable']}, Net profit: {profit['profit']} cents")
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Dict, Any


class FeeType(Enum):
    """
    Order type for fee calculation.

    TAKER: Market orders or limit orders that cross the spread (7% rate)
    MAKER: Limit orders that add liquidity to the order book (3.5% rate)
    """

    TAKER = "taker"
    MAKER = "maker"


# Backwards compatibility alias
OrderType = FeeType


@dataclass
class FeeCalculation:
    """
    Complete fee calculation result for a single trade.

    Attributes:
        gross_cost_cents: Cost before fees (contracts * price_cents)
        fee_cents: Calculated fee in cents (integer, rounded up)
        total_cost_cents: Total cost including fees (gross_cost + fee)
        fee_type: Whether this was a taker or maker order
        fee_rate: The rate applied (0.07 for taker, 0.035 for maker)
    """

    gross_cost_cents: int
    fee_cents: int
    total_cost_cents: int
    fee_type: FeeType
    fee_rate: float


@dataclass
class FeeResult:
    """
    Backwards compatibility: Result of fee calculation.
    Mirrors the old analysis.fee_calculator.FeeResult interface.
    """
    fee_cents: float
    fee_dollars: float
    is_maker: bool
    was_capped: bool = False
    raw_fee_cents: float = 0.0
    notional_dollars: float = 0.0
    effective_rate: float = 0.0


class FeeCalculator:
    """
    Calculate Kalshi trading fees with precision and accuracy.

    This calculator implements the official Kalshi fee formula and handles
    all edge cases including minimum fees and multi-leg calculations.

    Fee Formula:
        fee = ceil(rate * contracts * (price/100) * (1 - price/100) * 100)

    Where:
        - rate is 0.07 (taker) or 0.035 (maker)
        - price is in cents (1-99)
        - result is in cents, rounded up

    The minimum fee is 1 cent per contract to ensure profitability
    on small trades.

    Class Constants:
        TAKER_RATE: 7% fee rate for taker orders
        MAKER_RATE: 3.5% fee rate for maker orders (50% discount)
        MIN_FEE_PER_CONTRACT: Minimum 1 cent fee per contract
    """

    TAKER_RATE: float = 0.07
    MAKER_RATE: float = 0.035
    MIN_FEE_PER_CONTRACT: int = 1

    def calculate(
        self,
        contracts: int,
        price_cents: int,
        fee_type: FeeType = FeeType.TAKER,
    ) -> FeeCalculation:
        """
        Calculate fee for a single trade.

        Args:
            contracts: Number of contracts to trade (must be > 0 for valid result)
            price_cents: Price per contract in cents (must be 1-99)
            fee_type: TAKER (7%) or MAKER (3.5%) order type

        Returns:
            FeeCalculation with gross cost, fee, total cost, and metadata

        Raises:
            ValueError: If price_cents is outside valid range (1-99) for non-zero contracts

        Examples:
            >>> calc = FeeCalculator()
            >>> result = calc.calculate(10, 50, FeeType.TAKER)
            >>> result.fee_cents
            18
            >>> result.total_cost_cents
            518
        """
        # Handle zero/negative contracts
        if contracts <= 0:
            return FeeCalculation(
                gross_cost_cents=0,
                fee_cents=0,
                total_cost_cents=0,
                fee_type=fee_type,
                fee_rate=self.TAKER_RATE if fee_type == FeeType.TAKER else self.MAKER_RATE,
            )

        # Validate price range
        if not 1 <= price_cents <= 99:
            raise ValueError(f"price_cents must be 1-99, got {price_cents}")

        # Determine fee rate
        rate = self.TAKER_RATE if fee_type == FeeType.TAKER else self.MAKER_RATE

        # Calculate gross cost
        gross_cost_cents = contracts * price_cents

        # Fee formula: ceil(rate * contracts * (price/100) * (1 - price/100) * 100)
        price_decimal = price_cents / 100.0
        fee_raw = rate * contracts * price_decimal * (1 - price_decimal) * 100
        fee_calculated = math.ceil(fee_raw)

        # Apply minimum fee floor
        min_fee = self.MIN_FEE_PER_CONTRACT * contracts
        fee_cents = max(fee_calculated, min_fee)

        # Calculate total
        total_cost_cents = gross_cost_cents + fee_cents

        return FeeCalculation(
            gross_cost_cents=gross_cost_cents,
            fee_cents=fee_cents,
            total_cost_cents=total_cost_cents,
            fee_type=fee_type,
            fee_rate=rate,
        )

    def calculate_multi_leg(
        self,
        legs: List[Dict[str, Any]],
        fee_type: FeeType = FeeType.TAKER,
    ) -> Dict[str, Any]:
        """
        Calculate fees for multiple trade legs (e.g., bracket arbitrage).

        IMPORTANT: Fees are calculated PER LEG, not on averaged prices.
        This is critical for accurate arbitrage calculations.

        Args:
            legs: List of leg dictionaries, each containing:
                - ticker: Market ticker (string)
                - contracts: Number of contracts (int)
                - price_cents: Price in cents (int, 1-99)
            fee_type: TAKER or MAKER for all legs

        Returns:
            Dictionary with:
                - total_gross_cents: Sum of all leg costs before fees
                - total_fees_cents: Sum of all leg fees
                - total_cost_cents: Grand total including fees
                - legs: List of per-leg breakdowns with:
                    - ticker, contracts, price_cents
                    - gross_cost_cents, fee_cents, total_cost_cents

        Examples:
            >>> calc = FeeCalculator()
            >>> legs = [
            ...     {"ticker": "A", "contracts": 10, "price_cents": 25},
            ...     {"ticker": "B", "contracts": 10, "price_cents": 30},
            ... ]
            >>> result = calc.calculate_multi_leg(legs, FeeType.TAKER)
            >>> result["total_fees_cents"]
            27
        """
        if not legs:
            return {
                "total_gross_cents": 0,
                "total_fees_cents": 0,
                "total_cost_cents": 0,
                "legs": [],
            }

        total_gross = 0
        total_fees = 0
        leg_results = []

        for leg in legs:
            ticker = leg.get("ticker", "")
            contracts = leg.get("contracts", 0)
            price_cents = leg.get("price_cents", 0)

            # Skip invalid legs
            if contracts <= 0 or not (1 <= price_cents <= 99):
                leg_results.append({
                    "ticker": ticker,
                    "contracts": contracts,
                    "price_cents": price_cents,
                    "gross_cost_cents": 0,
                    "fee_cents": 0,
                    "total_cost_cents": 0,
                })
                continue

            # Calculate fee for this leg
            calc_result = self.calculate(contracts, price_cents, fee_type)

            total_gross += calc_result.gross_cost_cents
            total_fees += calc_result.fee_cents

            leg_results.append({
                "ticker": ticker,
                "contracts": contracts,
                "price_cents": price_cents,
                "gross_cost_cents": calc_result.gross_cost_cents,
                "fee_cents": calc_result.fee_cents,
                "total_cost_cents": calc_result.total_cost_cents,
            })

        return {
            "total_gross_cents": total_gross,
            "total_fees_cents": total_fees,
            "total_cost_cents": total_gross + total_fees,
            "legs": leg_results,
        }

    def estimate_arbitrage_profit(
        self,
        legs: List[Dict[str, Any]],
        payout_cents: int = 100,
        fee_type: FeeType = FeeType.TAKER,
    ) -> Dict[str, Any]:
        """
        Estimate profit from an arbitrage opportunity.

        For bracket arbitrage (mutually exclusive markets), buying all brackets
        guarantees exactly one will pay out. This method calculates whether
        the total cost (including fees) is less than the guaranteed payout.

        Args:
            legs: List of leg dictionaries (same format as calculate_multi_leg)
            payout_cents: Guaranteed payout in cents (default 100 for $1 contracts)
            fee_type: TAKER or MAKER for fee calculation

        Returns:
            Dictionary with:
                - cost: Total cost in cents (gross + fees)
                - fees: Total fees in cents
                - payout: Guaranteed payout in cents
                - profit: Net profit in cents (payout - cost)
                - profit_percent: Profit as percentage of cost
                - is_profitable: Boolean indicating if arbitrage exists

        Examples:
            >>> calc = FeeCalculator()
            >>> legs = [
            ...     {"ticker": "A", "contracts": 1, "price_cents": 25},
            ...     {"ticker": "B", "contracts": 1, "price_cents": 30},
            ...     {"ticker": "C", "contracts": 1, "price_cents": 20},
            ... ]
            >>> result = calc.estimate_arbitrage_profit(legs, payout_cents=100)
            >>> result["is_profitable"]
            True
            >>> result["profit"]  # 100 - 75 - fees
            19
        """
        if not legs:
            return {
                "cost": 0,
                "fees": 0,
                "payout": payout_cents,
                "profit": payout_cents,
                "profit_percent": 100.0 if payout_cents > 0 else 0.0,
                "is_profitable": payout_cents > 0,
            }

        # Calculate total cost using multi-leg
        multi_result = self.calculate_multi_leg(legs, fee_type)

        total_cost = multi_result["total_cost_cents"]
        total_fees = multi_result["total_fees_cents"]
        profit = payout_cents - total_cost
        profit_percent = (profit / total_cost * 100) if total_cost > 0 else 0.0

        return {
            "cost": total_cost,
            "fees": total_fees,
            "payout": payout_cents,
            "profit": profit,
            "profit_percent": round(profit_percent, 2),
            "is_profitable": profit > 0,
        }

    @classmethod
    def analyze_weather_arbitrage(
        cls,
        yes_asks: List[int],
        no_asks: List[int],
        order_type: FeeType = FeeType.TAKER
    ) -> Dict[str, Any]:
        """
        Analyze all three weather bracket arbitrage strategies.

        IMPORTANT: This analysis assumes brackets are MUTUALLY EXCLUSIVE.
        Exactly one bracket will win (e.g., temperature falls in one range).
        If brackets can overlap or multiple can win, this analysis is invalid.

        Strategies:
        - all_yes: Buy YES on every bracket. Profitable if sum(yes_asks) + fees < 100
          (Exactly one YES wins -> $1 payout guaranteed)
        - all_no: Buy NO on every bracket. Profitable if sum(no_asks) + fees < (n-1)*100
          (All but one NO wins -> (n-1) * $1 payout)
        - min_2_no: Buy NO on 2 cheapest. Profitable if sum(2 cheapest no) + fees < 100
          (If neither bracket wins, both NOs pay -> $1 payout)

        Args:
            yes_asks: List of YES ask prices in cents (must be mutually exclusive brackets)
            no_asks: List of NO ask prices in cents (must be mutually exclusive brackets)
            order_type: TAKER or MAKER for fee calculation

        Returns:
            Dict with all_yes, all_no, min_2_no strategies and best_strategy
        """
        calc = cls()
        n = len(yes_asks)

        # Empty result structure
        def empty_strategy(brackets_used=0):
            return {
                "cost": 0, "fees": 0, "net_cost": 0,
                "payout": 0, "gross_profit": 0, "net_profit": 0,
                "is_arb": False, "brackets_used": brackets_used
            }

        if n == 0:
            return {
                "all_yes": empty_strategy(),
                "all_no": empty_strategy(),
                "min_2_no": {**empty_strategy(), "cheapest_indices": [], "brackets": []},
                "best_strategy": None,
                "has_arbitrage": False
            }

        # === ALL YES Strategy ===
        # Buy YES on all brackets - exactly one pays out $1
        all_yes_cost = sum(yes_asks)
        all_yes_fees = sum(
            calc.calculate(1, p, order_type).fee_cents
            for p in yes_asks if 1 <= p <= 99
        )
        all_yes_payout = 100  # One bracket wins
        all_yes = {
            "cost": all_yes_cost,
            "fees": all_yes_fees,
            "net_cost": all_yes_cost + all_yes_fees,
            "payout": all_yes_payout,
            "gross_profit": all_yes_payout - all_yes_cost,
            "net_profit": all_yes_payout - all_yes_cost - all_yes_fees,
            "is_arb": (all_yes_payout - all_yes_cost - all_yes_fees) > 0,
            "brackets_used": n
        }

        # === ALL NO Strategy ===
        # Buy NO on all brackets - (n-1) pay out $1 each
        all_no_cost = sum(no_asks)
        all_no_fees = sum(
            calc.calculate(1, p, order_type).fee_cents
            for p in no_asks if 1 <= p <= 99
        )
        all_no_payout = (n - 1) * 100  # All but one bracket pays
        all_no = {
            "cost": all_no_cost,
            "fees": all_no_fees,
            "net_cost": all_no_cost + all_no_fees,
            "payout": all_no_payout,
            "gross_profit": all_no_payout - all_no_cost,
            "net_profit": all_no_payout - all_no_cost - all_no_fees,
            "is_arb": (all_no_payout - all_no_cost - all_no_fees) > 0,
            "brackets_used": n
        }

        # === MIN 2 NO Strategy ===
        # Buy NO on 2 cheapest brackets - if neither wins, both pay $1
        min_2_no = {**empty_strategy(2), "cheapest_indices": [], "brackets": []}
        if n >= 2:
            # Find 2 cheapest NO prices with their indices
            indexed = [(price, idx) for idx, price in enumerate(no_asks)]
            indexed.sort(key=lambda x: x[0])
            cheapest_two = indexed[:2]

            min_2_cost = cheapest_two[0][0] + cheapest_two[1][0]
            min_2_fees = sum(
                calc.calculate(1, p, order_type).fee_cents
                for p, _ in cheapest_two if 1 <= p <= 99
            )
            # If neither of the 2 cheapest brackets wins, both NOs pay $1 each = $1 total
            # (We only need one winning NO for the $1 payout since they're mutually exclusive)
            min_2_payout = 100

            min_2_no = {
                "cost": min_2_cost,
                "fees": min_2_fees,
                "net_cost": min_2_cost + min_2_fees,
                "payout": min_2_payout,
                "gross_profit": min_2_payout - min_2_cost,
                "net_profit": min_2_payout - min_2_cost - min_2_fees,
                "is_arb": (min_2_payout - min_2_cost - min_2_fees) > 0,
                "brackets_used": 2,
                "cheapest_indices": [cheapest_two[0][1], cheapest_two[1][1]],
                "brackets": []
            }

        # Determine best strategy
        strategies = [
            ("all_yes", all_yes),
            ("all_no", all_no),
            ("min_2_no", min_2_no)
        ]

        profitable = [(name, s) for name, s in strategies if s["is_arb"]]
        best_strategy = None
        if profitable:
            # Pick the one with highest net profit
            best_strategy = max(profitable, key=lambda x: x[1]["net_profit"])[0]

        return {
            "all_yes": all_yes,
            "all_no": all_no,
            "min_2_no": min_2_no,
            "best_strategy": best_strategy,
            "has_arbitrage": best_strategy is not None
        }

    @classmethod
    def fee_per_contract(cls, price_cents: int, order_type: FeeType = FeeType.TAKER) -> float:
        """
        Calculate fee per single contract at given price.

        Backwards-compatible class method for routes.py API endpoints.

        Args:
            price_cents: Price in cents (1-99)
            order_type: TAKER (7%) or MAKER (3.5%)

        Returns:
            Fee in cents as float
        """
        if not 1 <= price_cents <= 99:
            return 0.0
        rate = cls.TAKER_RATE if order_type == FeeType.TAKER else cls.MAKER_RATE
        price_decimal = price_cents / 100.0
        return rate * price_decimal * (1 - price_decimal) * 100

    @classmethod
    def calculate_trade_fee(cls, price_cents: int, contracts: int, order_type: FeeType = FeeType.TAKER):
        """
        Calculate fee breakdown for a trade.

        Backwards-compatible class method for routes.py API endpoints.

        Args:
            price_cents: Price in cents (1-99)
            contracts: Number of contracts
            order_type: TAKER (7%) or MAKER (3.5%)

        Returns:
            Object with fee breakdown attributes
        """
        calc = cls()
        result = calc.calculate(contracts, price_cents, order_type)
        fee_per = cls.fee_per_contract(price_cents, order_type)
        gross_cost = contracts * price_cents
        fee_pct = (result.fee_cents / gross_cost * 100) if gross_cost > 0 else 0.0

        # Return a simple object with the expected attributes
        class FeeBreakdown:
            pass

        breakdown = FeeBreakdown()
        breakdown.price_cents = price_cents
        breakdown.contracts = contracts
        breakdown.order_type = order_type
        breakdown.fee_per_contract = fee_per
        breakdown.total_fee = result.fee_cents
        breakdown.fee_percentage = fee_pct
        return breakdown


# Convenience function for simple fee calculation
def calculate_fee(
    contracts: int,
    price_cents: int,
    fee_type: FeeType = FeeType.TAKER,
) -> int:
    """
    Convenience function to calculate fee for a trade.

    Args:
        contracts: Number of contracts
        price_cents: Price in cents (1-99)
        fee_type: TAKER or MAKER

    Returns:
        Fee in cents (integer)
    """
    calc = FeeCalculator()
    result = calc.calculate(contracts, price_cents, fee_type)
    return result.fee_cents


def calculate_multi_leg_fee(
    legs: list,
    fee_type: FeeType = FeeType.TAKER,
) -> tuple:
    """
    Convenience function to calculate fees for multiple trade legs.

    Args:
        legs: List of tuples (contracts, price_cents) or dicts with those keys
        fee_type: TAKER or MAKER

    Returns:
        Tuple of (total_fee_cents, list of per-leg fees)
    """
    calc = FeeCalculator()
    leg_fees = []

    for leg in legs:
        if isinstance(leg, dict):
            contracts = leg.get("contracts", 0)
            price_cents = leg.get("price_cents", leg.get("price", 0))
        else:
            contracts, price_cents = leg

        if contracts > 0 and 1 <= price_cents <= 99:
            result = calc.calculate(contracts, price_cents, fee_type)
            leg_fees.append(result.fee_cents)
        else:
            leg_fees.append(0)

    return sum(leg_fees), leg_fees
