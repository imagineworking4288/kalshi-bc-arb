"""
Arbitrage calculator for mutually exclusive bracket markets.

Three strategies:
1. All YES: Buy YES on every bracket (arb if sum < 100¢)
2. All NO: Buy NO on every bracket (arb if sum < (n-1)*100¢)
3. Min 2-NO: Buy 2 cheapest NOs (arb if sum < 100¢)
"""

from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ArbitrageCalculator:
    """Calculate arbitrage opportunities for mutually exclusive brackets."""

    def analyze(self, brackets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze all three arbitrage strategies.

        Args:
            brackets: List of bracket dicts with yes_ask, no_ask, etc.

        Returns:
            Dict with all_yes, all_no, min_2_no strategies and best_strategy
        """
        if not brackets:
            return self._empty_result()

        n = len(brackets)

        # Strategy 1: All YES
        yes_cost = sum(b.get("yes_ask", 0) or 0 for b in brackets)
        all_yes = {
            "cost": yes_cost,
            "payout": 100,
            "profit": 100 - yes_cost,
            "is_arb": yes_cost < 100
        }

        # Strategy 2: All NO
        no_cost = sum(b.get("no_ask", 0) or 0 for b in brackets)
        no_payout = (n - 1) * 100  # n-1 brackets lose, each NO pays $1
        all_no = {
            "cost": no_cost,
            "payout": no_payout,
            "profit": no_payout - no_cost,
            "is_arb": no_cost < no_payout
        }

        # Strategy 3: Min 2-NO (cheapest 2 NOs cover all outcomes)
        brackets_with_no = [b for b in brackets if b.get("no_ask")]
        if len(brackets_with_no) >= 2:
            sorted_by_no = sorted(brackets_with_no, key=lambda b: b.get("no_ask", 999))
            cheapest_2 = sorted_by_no[:2]
            min_2_cost = cheapest_2[0]["no_ask"] + cheapest_2[1]["no_ask"]
            min_2_no = {
                "cost": min_2_cost,
                "payout": 100,  # Minimum payout when one of the 2 wins
                "profit": 100 - min_2_cost,
                "brackets": [
                    {"title": cheapest_2[0].get("title", ""), "no_ask": cheapest_2[0]["no_ask"]},
                    {"title": cheapest_2[1].get("title", ""), "no_ask": cheapest_2[1]["no_ask"]}
                ],
                "is_arb": min_2_cost < 100
            }
        else:
            min_2_no = {
                "cost": 0,
                "payout": 100,
                "profit": 0,
                "brackets": [],
                "is_arb": False
            }

        # Determine best strategy
        best = None
        best_profit = 0
        for name, strat in [("all_yes", all_yes), ("all_no", all_no), ("min_2_no", min_2_no)]:
            if strat["is_arb"] and strat["profit"] > best_profit:
                best = name
                best_profit = strat["profit"]

        return {
            "all_yes": all_yes,
            "all_no": all_no,
            "min_2_no": min_2_no,
            "best_strategy": best,
            "has_arbitrage": best is not None
        }

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "all_yes": {"cost": 0, "payout": 100, "profit": 0, "is_arb": False},
            "all_no": {"cost": 0, "payout": 0, "profit": 0, "is_arb": False},
            "min_2_no": {"cost": 0, "payout": 100, "profit": 0, "brackets": [], "is_arb": False},
            "best_strategy": None,
            "has_arbitrage": False
        }
