"""
DEPRECATED: This module is deprecated. Use ExecutionGateway instead.

This module will be removed in a future version. All trade execution
should go through backend.services.core.execution_gateway.ExecutionGateway.

Example migration:
    # Old way (deprecated)
    from backend.services.trade_executor import TradeExecutor
    executor = TradeExecutor(kalshi_client)

    # New way (recommended)
    from backend.services.core import ExecutionGateway
    gateway = ExecutionGateway(kalshi_client)
"""

import asyncio
import uuid
import warnings
from typing import Union, Optional, TYPE_CHECKING
from dataclasses import dataclass

from ..config import get_settings
from .kalshi_client import KalshiClient
from .paper_trading import PaperTradingService, PaperTradeResult
from .arbitrage_detector import ArbitrageOpportunity

if TYPE_CHECKING:
    from .core.execution_gateway import ExecutionGateway


@dataclass
class LiveTradeResult:
    trade_id: str
    status: str
    orders: list
    total_cost: float
    total_fees: float
    expected_payout: float
    expected_profit: float
    message: str
    paper_mode: bool = False


class TradeExecutor:
    """
    DEPRECATED: Routes trades to paper simulation or live Kalshi based on mode.

    This class is deprecated. Use ExecutionGateway instead:

        from backend.services.core import ExecutionGateway
        gateway = ExecutionGateway(kalshi_client)
    """

    def __init__(
        self,
        kalshi_client: KalshiClient,
        gateway: Optional['ExecutionGateway'] = None
    ):
        warnings.warn(
            "TradeExecutor is deprecated. Use ExecutionGateway from "
            "backend.services.core.execution_gateway instead.",
            DeprecationWarning,
            stacklevel=2
        )
        self.kalshi = kalshi_client
        self.paper = PaperTradingService()
        self.settings = get_settings()
        self._gateway = gateway

    @property
    def is_paper_mode(self) -> bool:
        return self.settings.paper_trading_mode

    async def get_balance(self) -> dict:
        if self._gateway:
            return await self._gateway.get_balance()

        if self.is_paper_mode:
            return await self.paper.get_balance()
        else:
            result = await self.kalshi.get_balance()
            return {
                "available_balance": result.get("available_balance", 0) / 100,
                "total_balance": result.get("balance", 0) / 100,
                "paper_mode": False
            }

    async def get_positions(self) -> list:
        if self._gateway:
            return await self._gateway.get_positions()

        if self.is_paper_mode:
            return await self.paper.get_positions()
        else:
            return await self.kalshi.get_positions()

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        num_contracts: int
    ) -> Union[PaperTradeResult, LiveTradeResult]:
        if self._gateway:
            return await self._gateway.execute_arbitrage(opportunity, num_contracts)

        if self.is_paper_mode:
            return await self.paper.execute_arbitrage(opportunity, num_contracts)
        else:
            return await self._execute_live(opportunity, num_contracts)

    async def _execute_live(
        self,
        opportunity: ArbitrageOpportunity,
        num_contracts: int
    ) -> LiveTradeResult:
        """Execute real arbitrage on Kalshi using batch orders for atomic execution"""
        trade_id = str(uuid.uuid4())

        # Build batch order payload
        batch_orders = [
            {
                "ticker": bracket.ticker,
                "side": "yes",
                "action": "buy",
                "count": num_contracts,
                "yes_price": int(bracket.yes_price * 100)
            }
            for bracket in opportunity.brackets
        ]

        # Execute all orders atomically via batch endpoint
        try:
            result = await self.kalshi.place_batch_orders(batch_orders)
            batch_results = result.get("orders", [])
        except Exception as e:
            return LiveTradeResult(
                trade_id=trade_id,
                status="failed",
                orders=[],
                total_cost=0,
                total_fees=0,
                expected_payout=0,
                expected_profit=0,
                message=f"Batch order failed: {str(e)}"
            )

        # Process batch results
        orders = []
        total_cost = 0
        total_fees = 0
        all_filled = True

        for i, order_result in enumerate(batch_results):
            if "error" in order_result:
                all_filled = False
                orders.append({
                    "ticker": opportunity.brackets[i].ticker,
                    "status": "failed",
                    "error": order_result.get("error")
                })
            elif "order" in order_result:
                order = order_result["order"]
                filled = order.get("filled_count", 0)
                fill_price = order.get("yes_price", 0) / 100 if order.get("yes_price") else 0

                # Calculate cost and fees
                cost = filled * fill_price
                fee = order.get("total_fee", 0) / 100 if order.get("total_fee") else 0

                total_cost += cost
                total_fees += fee

                orders.append({
                    "ticker": opportunity.brackets[i].ticker,
                    "order_id": order.get("order_id"),
                    "filled": filled,
                    "status": order.get("status"),
                    "fill_price": fill_price,
                    "fee": fee
                })

                if filled < num_contracts:
                    all_filled = False

        expected_payout = num_contracts if all_filled else 0
        expected_profit = expected_payout - total_cost - total_fees

        return LiveTradeResult(
            trade_id=trade_id,
            status="success" if all_filled else "partial",
            orders=orders,
            total_cost=total_cost,
            total_fees=total_fees,
            expected_payout=expected_payout,
            expected_profit=expected_profit,
            message="Live arbitrage executed atomically" if all_filled else "Some orders failed or partially filled"
        )

    @classmethod
    def from_gateway(cls, gateway: 'ExecutionGateway') -> 'TradeExecutor':
        """
        Create a TradeExecutor that delegates to ExecutionGateway.

        This is useful for backwards compatibility when migrating
        code that expects a TradeExecutor instance.

        Args:
            gateway: ExecutionGateway instance to delegate to

        Returns:
            TradeExecutor instance that delegates all calls to the gateway
        """
        instance = object.__new__(cls)
        instance._gateway = gateway
        instance.kalshi = gateway.kalshi_client
        instance.paper = gateway.paper
        instance.settings = gateway.settings
        return instance
