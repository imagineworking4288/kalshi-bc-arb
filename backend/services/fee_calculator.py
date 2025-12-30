import math
from dataclasses import dataclass
from typing import List


@dataclass
class OrderLeg:
    ticker: str
    side: str
    contracts: int
    price: float  # 0.0 to 1.0


def calculate_fee(contracts: int, price: float) -> float:
    """
    Kalshi fee formula: ceil(0.07 * contracts * price * (1 - price))
    Fee is highest at 50c, approaches zero near 0c or 100c
    """
    if contracts <= 0 or price <= 0 or price >= 1:
        return 0.0
    return math.ceil(0.07 * contracts * price * (1 - price) * 100) / 100


def calculate_arbitrage_cost(legs: List[OrderLeg]) -> dict:
    """Calculate total cost for a multi-leg arbitrage trade"""
    if not legs:
        return {"legs": [], "total_cost": 0, "total_fees": 0, "total": 0, "net_profit": 0}

    leg_details = []
    total_cost = 0
    total_fees = 0

    for leg in legs:
        cost = leg.contracts * leg.price
        fee = calculate_fee(leg.contracts, leg.price)
        total_cost += cost
        total_fees += fee
        leg_details.append({
            "ticker": leg.ticker,
            "side": leg.side,
            "contracts": leg.contracts,
            "price": leg.price,
            "cost": round(cost, 4),
            "fee": round(fee, 4)
        })

    # Arbitrage payout is $1 per complete contract set
    min_contracts = min(leg.contracts for leg in legs)
    guaranteed_payout = min_contracts
    net_profit = guaranteed_payout - total_cost - total_fees

    return {
        "legs": leg_details,
        "total_cost": round(total_cost, 4),
        "total_fees": round(total_fees, 4),
        "total": round(total_cost + total_fees, 4),
        "guaranteed_payout": guaranteed_payout,
        "net_profit": round(net_profit, 4),
        "net_profit_pct": round(net_profit / (total_cost + total_fees) * 100, 2) if total_cost > 0 else 0
    }
