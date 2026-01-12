"""
Arbitrage calculator for mutually exclusive bracket markets.

Three strategies:
1. All YES: Buy YES on every bracket (arb if sum < 100¢)
2. All NO: Buy NO on every bracket (arb if sum < (n-1)*100¢)
3. Min 2-NO: Buy 2 cheapest NOs (arb if sum < 100¢)

Now includes Kalshi fee calculations!
"""

from typing import List, Dict, Any
from .core.fee_calculator import FeeCalculator, OrderType
from .log_config import get_logger

logger = get_logger("arbitrage_calculator")


class ArbitrageCalculator:
    """Calculate arbitrage opportunities for mutually exclusive brackets."""

    def analyze(self, brackets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze all three arbitrage strategies WITH FEE CALCULATIONS.

        Args:
            brackets: List of bracket dicts with yes_ask, no_ask, etc.

        Returns:
            Dict with all_yes, all_no, min_2_no strategies (including fees) and best_strategy
        """
        if not brackets:
            return self._empty_result()

        n = len(brackets)

        # Extract price lists for fee calculator
        yes_asks = [b.get("yes_ask", 0) or 0 for b in brackets]
        no_asks = [b.get("no_ask", 0) or 0 for b in brackets]

        # Use FeeCalculator to get complete analysis with fees
        fee_analysis = FeeCalculator.analyze_weather_arbitrage(yes_asks, no_asks, OrderType.TAKER)

        # Add bracket details to min_2_no strategy using the indices from FeeCalculator
        cheapest_indices = fee_analysis["min_2_no"].get("cheapest_indices", [])
        if len(cheapest_indices) == 2 and len(brackets) >= 2:
            # Use the exact indices that FeeCalculator used to calculate costs
            fee_analysis["min_2_no"]["brackets"] = [
                {"title": brackets[cheapest_indices[0]].get("title", ""), "no_ask": brackets[cheapest_indices[0]].get("no_ask", 0)},
                {"title": brackets[cheapest_indices[1]].get("title", ""), "no_ask": brackets[cheapest_indices[1]].get("no_ask", 0)}
            ]

        return fee_analysis

    def _empty_result(self) -> Dict[str, Any]:
        """Return empty result with fee structure."""
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
            "min_2_no": {**empty_strategy.copy(), "brackets": []},
            "best_strategy": None,
            "has_arbitrage": False
        }
