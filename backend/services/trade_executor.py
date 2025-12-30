import asyncio
import uuid
from typing import Union
from dataclasses import dataclass

from ..config import get_settings
from .kalshi_client import KalshiClient
from .paper_trading import PaperTradingService, PaperTradeResult
from .arbitrage_detector import ArbitrageOpportunity


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
    """Routes trades to paper simulation or live Kalshi based on mode"""

    def __init__(self, kalshi_client: KalshiClient):
        self.kalshi = kalshi_client
        self.paper = PaperTradingService()
        self.settings = get_settings()

    @property
    def is_paper_mode(self) -> bool:
        return self.settings.paper_trading_mode

    async def get_balance(self) -> dict:
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
        if self.is_paper_mode:
            return await self.paper.get_positions()
        else:
            return await self.kalshi.get_positions()

    async def execute_arbitrage(
        self,
        opportunity: ArbitrageOpportunity,
        num_contracts: int
    ) -> Union[PaperTradeResult, LiveTradeResult]:

        if self.is_paper_mode:
            return await self.paper.execute_arbitrage(opportunity, num_contracts)
        else:
            return await self._execute_live(opportunity, num_contracts)

    async def _execute_live(
        self,
        opportunity: ArbitrageOpportunity,
        num_contracts: int
    ) -> LiveTradeResult:
        """Execute real arbitrage on Kalshi"""
        trade_id = str(uuid.uuid4())

        # Place orders for all brackets concurrently
        tasks = []
        for bracket in opportunity.brackets:
            tasks.append(
                self.kalshi.place_order(
                    ticker=bracket.ticker,
                    side="yes",
                    action="buy",
                    count=num_contracts,
                    price=int(bracket.yes_price * 100)
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        orders = []
        total_cost = 0
        total_fees = 0
        all_filled = True

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                all_filled = False
                orders.append({
                    "ticker": opportunity.brackets[i].ticker,
                    "status": "failed",
                    "error": str(result)
                })
            else:
                order = result.get("order", {})
                filled = order.get("filled_count", 0)
                orders.append({
                    "ticker": opportunity.brackets[i].ticker,
                    "order_id": order.get("order_id"),
                    "filled": filled,
                    "status": order.get("status")
                })
                if filled < num_contracts:
                    all_filled = False

        return LiveTradeResult(
            trade_id=trade_id,
            status="success" if all_filled else "partial",
            orders=orders,
            total_cost=total_cost,
            total_fees=total_fees,
            expected_payout=num_contracts if all_filled else 0,
            expected_profit=0,
            message="Live arbitrage executed" if all_filled else "Some orders failed"
        )
