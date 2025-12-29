"""Kalshi fee calculation utilities"""

import math
from dataclasses import dataclass
from typing import List


@dataclass
class OrderLeg:
    """Represents a single order leg in a trade"""
    ticker: str
    side: str  # "yes" or "no"
    contracts: int
    price: float  # 0.0 to 1.0


@dataclass
class FeeCalculation:
    """Result of fee calculation for a single order"""
    contracts: int
    price: float
    fee: float
    cost: float  # price * contracts
    total: float  # cost + fee


def calculate_fee(contracts: int, price: float) -> float:
    """
    Calculate Kalshi fee using their exact formula.

    Fee = ceil(0.07 * contracts * price * (1 - price))

    Args:
        contracts: Number of contracts
        price: Price per contract (0.0 to 1.0, e.g., 0.65 for 65 cents)

    Returns:
        Fee in dollars (rounded up to nearest cent)
    """
    if price <= 0 or price >= 1:
        return 0.0

    raw_fee = 0.07 * contracts * price * (1 - price)
    # Round up to nearest cent
    return math.ceil(raw_fee * 100) / 100


def calculate_order_cost(leg: OrderLeg) -> FeeCalculation:
    """
    Calculate total cost for an order including fees.

    Args:
        leg: Order leg details

    Returns:
        FeeCalculation with all cost components
    """
    cost = leg.contracts * leg.price
    fee = calculate_fee(leg.contracts, leg.price)

    return FeeCalculation(
        contracts=leg.contracts,
        price=leg.price,
        fee=fee,
        cost=round(cost, 2),
        total=round(cost + fee, 2)
    )


def calculate_arbitrage_cost(legs: List[OrderLeg]) -> dict:
    """
    Calculate total cost and fees for multi-leg arbitrage trade.

    For arbitrage, all legs must be filled to guarantee payout.
    The minimum contracts across all legs determines complete sets.

    Args:
        legs: List of order legs

    Returns:
        Dictionary with:
            - legs: List of FeeCalculation for each leg
            - total_cost: Sum of all leg costs
            - total_fees: Sum of all leg fees
            - total: total_cost + total_fees
            - guaranteed_payout: Number of complete sets * $1
            - net_profit: guaranteed_payout - total
            - net_profit_pct: net_profit / total * 100
    """
    if not legs:
        return {
            "legs": [],
            "total_cost": 0,
            "total_fees": 0,
            "total": 0,
            "guaranteed_payout": 0,
            "net_profit": 0,
            "net_profit_pct": 0
        }

    calculations = [calculate_order_cost(leg) for leg in legs]

    total_cost = sum(c.cost for c in calculations)
    total_fees = sum(c.fee for c in calculations)
    total = total_cost + total_fees

    # For arbitrage, we need complete sets
    # The minimum contracts across all legs determines complete sets
    min_contracts = min(leg.contracts for leg in legs)
    guaranteed_payout = min_contracts  # $1 per complete set

    net_profit = guaranteed_payout - total
    net_profit_pct = (net_profit / total * 100) if total > 0 else 0

    return {
        "legs": calculations,
        "total_cost": round(total_cost, 2),
        "total_fees": round(total_fees, 2),
        "total": round(total, 2),
        "guaranteed_payout": guaranteed_payout,
        "net_profit": round(net_profit, 2),
        "net_profit_pct": round(net_profit_pct, 2)
    }


def calculate_max_contracts_for_budget(
    budget: float,
    prices: List[float]
) -> int:
    """
    Calculate maximum contracts that can be purchased within budget.

    This accounts for fees in the calculation.

    Args:
        budget: Total budget in dollars
        prices: List of prices for each leg (0.0 to 1.0)

    Returns:
        Maximum number of contracts that can be purchased
    """
    if not prices or budget <= 0:
        return 0

    # Binary search for maximum contracts
    low, high = 0, int(budget * 10)  # Upper bound guess

    while low < high:
        mid = (low + high + 1) // 2
        legs = [
            OrderLeg(ticker="", side="yes", contracts=mid, price=p)
            for p in prices
        ]
        result = calculate_arbitrage_cost(legs)

        if result["total"] <= budget:
            low = mid
        else:
            high = mid - 1

    return low


def estimate_profit_at_size(
    contracts: int,
    prices: List[float]
) -> dict:
    """
    Estimate profit for a given position size.

    Args:
        contracts: Number of contracts per leg
        prices: List of prices for each leg

    Returns:
        Dictionary with cost, payout, and profit details
    """
    legs = [
        OrderLeg(ticker="", side="yes", contracts=contracts, price=p)
        for p in prices
    ]
    return calculate_arbitrage_cost(legs)
