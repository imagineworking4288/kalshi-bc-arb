"""Trade execution and position sizing"""

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from .arbitrage_engine import ArbitrageOpportunity
from .fee_calculator import OrderLeg, calculate_fee
from .kalshi_client import KalshiClient


@dataclass
class OrderResult:
    """Result of a single order execution"""
    ticker: str
    order_id: str
    status: str  # 'filled', 'partial', 'rejected'
    contracts_filled: int
    contracts_requested: int
    fill_price: float
    fees: float


@dataclass
class TradeResult:
    """Result of an arbitrage trade execution"""
    trade_id: str
    opportunity_id: str
    status: str  # 'success', 'partial', 'failed'
    orders: List[OrderResult]
    total_cost: float
    total_fees: float
    expected_payout: float
    expected_profit: float
    message: str


class TradeExecutor:
    """Executes arbitrage trades"""

    def __init__(self, kalshi_client: KalshiClient):
        self.kalshi = kalshi_client

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        position_size: float
    ) -> TradeResult:
        """
        Execute all legs of an arbitrage trade simultaneously.

        Args:
            opportunity: The arbitrage opportunity to execute
            position_size: Total dollar amount to invest

        Returns:
            TradeResult with execution details
        """
        trade_id = str(uuid.uuid4())

        # Build order legs based on opportunity type
        legs = self._build_order_legs(opportunity, position_size)

        if not legs:
            return TradeResult(
                trade_id=trade_id,
                opportunity_id=opportunity.id,
                status="failed",
                orders=[],
                total_cost=0,
                total_fees=0,
                expected_payout=0,
                expected_profit=0,
                message="Could not build order legs"
            )

        # Execute all orders concurrently
        order_tasks = [
            self._place_order(leg)
            for leg in legs
        ]

        results = await asyncio.gather(*order_tasks, return_exceptions=True)

        # Process results
        order_results = []
        total_cost = 0
        total_fees = 0
        all_filled = True

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                order_results.append(OrderResult(
                    ticker=legs[i].ticker,
                    order_id="",
                    status="rejected",
                    contracts_filled=0,
                    contracts_requested=legs[i].contracts,
                    fill_price=0,
                    fees=0
                ))
                all_filled = False
            else:
                order_results.append(result)
                total_cost += result.contracts_filled * result.fill_price
                total_fees += result.fees
                if result.status != "filled":
                    all_filled = False

        # Calculate expected payout and profit
        min_contracts = min(
            (r.contracts_filled for r in order_results),
            default=0
        )
        expected_payout = min_contracts  # $1 per contract set
        expected_profit = expected_payout - total_cost - total_fees

        return TradeResult(
            trade_id=trade_id,
            opportunity_id=opportunity.id,
            status="success" if all_filled else ("partial" if min_contracts > 0 else "failed"),
            orders=order_results,
            total_cost=round(total_cost, 2),
            total_fees=round(total_fees, 2),
            expected_payout=expected_payout,
            expected_profit=round(expected_profit, 2),
            message="All orders filled" if all_filled else "Some orders not filled"
        )

    def _build_order_legs(
        self,
        opportunity: ArbitrageOpportunity,
        position_size: float
    ) -> List[OrderLeg]:
        """Build order legs for the arbitrage trade"""
        # Calculate cost per set based on trade direction
        if opportunity.trade_direction == "buy_brackets":
            # Buy all brackets
            cost_per_set = sum(
                b.yes_ask for b in opportunity.required_brackets
            )
        else:
            # Buy threshold + brackets below
            cost_per_set = opportunity.threshold_market.yes_ask
            # Note: required_brackets are the brackets we DON'T buy
            # We need to find brackets below threshold

        if cost_per_set <= 0:
            return []

        contracts_per_set = int(position_size / cost_per_set)

        if contracts_per_set <= 0:
            return []

        # Limit by liquidity
        contracts_per_set = min(
            contracts_per_set,
            opportunity.max_liquidity_contracts
        )

        legs = []

        if opportunity.trade_direction == "buy_brackets":
            # Buy all required brackets
            for bracket in opportunity.required_brackets:
                legs.append(OrderLeg(
                    ticker=bracket.ticker,
                    side="yes",
                    contracts=contracts_per_set,
                    price=bracket.yes_ask
                ))
        else:
            # Buy threshold
            legs.append(OrderLeg(
                ticker=opportunity.threshold_ticker,
                side="yes",
                contracts=contracts_per_set,
                price=opportunity.threshold_market.yes_ask
            ))

        return legs

    async def _place_order(self, leg: OrderLeg) -> OrderResult:
        """Place a single order"""
        try:
            result = await self.kalshi.place_order(
                ticker=leg.ticker,
                side=leg.side,
                action="buy",
                count=leg.contracts,
                price=int(leg.price * 100),  # Convert to cents
                order_type="limit"
            )

            order_data = result.get("order", {})

            return OrderResult(
                ticker=leg.ticker,
                order_id=order_data.get("order_id", ""),
                status="filled" if order_data.get("status") == "filled" else "partial",
                contracts_filled=order_data.get("filled_count", 0),
                contracts_requested=leg.contracts,
                fill_price=leg.price,
                fees=order_data.get("fees", 0) / 100
            )
        except Exception as e:
            return OrderResult(
                ticker=leg.ticker,
                order_id="",
                status="rejected",
                contracts_filled=0,
                contracts_requested=leg.contracts,
                fill_price=0,
                fees=0
            )


class PositionSizer:
    """Calculate suggested position sizes"""

    @staticmethod
    def percentage_of_balance(balance: float, percentage: float) -> float:
        """Simple percentage of balance"""
        return balance * (percentage / 100)

    @staticmethod
    def kelly_criterion(
        balance: float,
        cost_per_set: float,
        payout: float = 1.0,
        fraction: float = 0.25
    ) -> float:
        """
        Kelly criterion for optimal bet sizing.

        For guaranteed arb, Kelly suggests 100%, but we use fractional Kelly.

        Args:
            balance: Available balance
            cost_per_set: Cost to buy one complete set
            payout: Expected payout per set
            fraction: Kelly fraction (0.25 = quarter Kelly)

        Returns:
            Suggested position size
        """
        if cost_per_set >= payout:
            return 0

        edge = (payout - cost_per_set) / cost_per_set
        kelly_pct = min(edge, 1.0)  # Cap at 100%

        return balance * kelly_pct * fraction

    @staticmethod
    def max_liquidity(
        max_contracts: int,
        cost_per_set: float
    ) -> float:
        """Maximum size based on available liquidity"""
        return max_contracts * cost_per_set

    @staticmethod
    def get_suggestions(
        balance: float,
        opportunity: ArbitrageOpportunity
    ) -> Dict[str, float]:
        """Get all sizing suggestions"""
        # Calculate cost per set
        if opportunity.trade_direction == "buy_brackets":
            cost_per_set = sum(
                b.yes_ask for b in opportunity.required_brackets
            )
        else:
            cost_per_set = opportunity.threshold_market.yes_ask

        max_liq = PositionSizer.max_liquidity(
            opportunity.max_liquidity_contracts,
            cost_per_set
        )

        return {
            "conservative": round(min(
                PositionSizer.percentage_of_balance(balance, 2),
                max_liq
            ), 2),
            "moderate": round(min(
                PositionSizer.percentage_of_balance(balance, 5),
                max_liq
            ), 2),
            "aggressive": round(min(
                PositionSizer.percentage_of_balance(balance, 10),
                max_liq
            ), 2),
            "kelly": round(min(
                PositionSizer.kelly_criterion(balance, cost_per_set),
                max_liq
            ), 2),
            "max_liquidity": round(max_liq, 2)
        }
