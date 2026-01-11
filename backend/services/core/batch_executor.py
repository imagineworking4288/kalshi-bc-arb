"""
Atomic multi-order execution for arbitrage and complex trades.
Supports both paper and live execution modes.
"""

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any, Literal
import warnings

from backend.logging_config import get_logger

logger = get_logger("batch_executor")


class OrderSide(str, Enum):
    """Order side."""
    YES = "yes"
    NO = "no"


class OrderAction(str, Enum):
    """Order action."""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status."""
    PENDING = "pending"
    FILLED = "filled"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class OrderLeg:
    """Single leg of a multi-leg order."""
    ticker: str
    side: OrderSide
    action: OrderAction
    contracts: int
    price_cents: int
    status: OrderStatus = OrderStatus.PENDING
    fill_price: Optional[int] = None
    filled_contracts: int = 0
    order_id: Optional[str] = None
    error: Optional[str] = None
    fee_cents: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "ticker": self.ticker,
            "side": self.side.value,
            "action": self.action.value,
            "contracts": self.contracts,
            "price_cents": self.price_cents,
            "status": self.status.value,
            "fill_price": self.fill_price,
            "filled_contracts": self.filled_contracts,
            "order_id": self.order_id,
            "error": self.error,
            "fee_cents": self.fee_cents
        }


@dataclass
class BatchResult:
    """Result of batch order execution."""
    success: bool
    batch_id: str
    legs: List[OrderLeg]
    total_cost_cents: int = 0
    total_fees_cents: int = 0
    execution_ms: int = 0
    message: str = ""
    mode: str = "paper"
    audit_id: Optional[str] = None  # Set by ExecutionGateway
    source: Optional[str] = None    # Set by ExecutionGateway

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "batch_id": self.batch_id,
            "legs": [leg.to_dict() for leg in self.legs],
            "total_cost_cents": self.total_cost_cents,
            "total_fees_cents": self.total_fees_cents,
            "execution_ms": self.execution_ms,
            "message": self.message,
            "mode": self.mode,
            "audit_id": self.audit_id,
            "source": self.source
        }


class BatchExecutor:
    """
    Executes multi-leg orders atomically.

    Supports:
    - Paper mode: Simulate fills instantly
    - Live mode: Use Kalshi batch orders API
    - Single orders: Convenience for simple trades
    - Arbitrage: Optimized for multi-leg arb trades
    """

    def __init__(
        self,
        kalshi_client,
        paper_service=None,
        fee_calculator=None
    ):
        """
        Initialize batch executor.

        Args:
            kalshi_client: KalshiClient for live orders
            paper_service: PaperTradingService for paper orders
            fee_calculator: Fee calculation module (optional)
        """
        self.kalshi_client = kalshi_client
        self.paper_service = paper_service
        self.fee_calculator = fee_calculator

    def _calculate_fee_cents(self, contracts: int, price_cents: int) -> int:
        """
        Calculate Kalshi trading fee in cents.

        Formula: ceil(0.07 * contracts * price * (1 - price))
        """
        if contracts <= 0 or price_cents <= 0 or price_cents >= 100:
            return 0

        price = price_cents / 100.0
        fee = 0.07 * contracts * price * (1 - price)
        return int(math.ceil(fee * 100))

    async def execute(
        self,
        legs: List[OrderLeg],
        mode: Literal['paper', 'live'],
        atomic: bool = True
    ) -> BatchResult:
        """
        Execute a batch of orders.

        Args:
            legs: List of order legs to execute
            mode: "paper" or "live" (required, no default)
            atomic: If True, all orders must succeed (live mode only)

        Returns:
            BatchResult with execution details
        """
        batch_id = str(uuid.uuid4())
        start_time = time.time()

        if mode == "paper":
            result = await self._execute_paper_batch(legs, batch_id)
        else:
            result = await self._execute_live_batch(legs, batch_id, atomic)

        result.execution_ms = int((time.time() - start_time) * 1000)
        result.mode = mode

        return result

    async def _execute_paper_batch(
        self,
        legs: List[OrderLeg],
        batch_id: str
    ) -> BatchResult:
        """Execute orders in paper mode (instant simulation)."""
        total_cost = 0
        total_fees = 0

        for leg in legs:
            # Calculate cost and fee
            cost = leg.contracts * leg.price_cents
            fee = self._calculate_fee_cents(leg.contracts, leg.price_cents)

            # Simulate instant fill
            leg.status = OrderStatus.FILLED
            leg.fill_price = leg.price_cents
            leg.filled_contracts = leg.contracts
            leg.fee_cents = fee
            leg.order_id = f"PAPER-{batch_id[:8]}-{leg.ticker}"

            total_cost += cost
            total_fees += fee

        logger.info(
            f"Paper execution: {len(legs)} legs, "
            f"cost={total_cost}¢, fees={total_fees}¢"
        )

        return BatchResult(
            success=True,
            batch_id=batch_id,
            legs=legs,
            total_cost_cents=total_cost,
            total_fees_cents=total_fees,
            message=f"Paper: {len(legs)} orders filled"
        )

    async def _execute_live_batch(
        self,
        legs: List[OrderLeg],
        batch_id: str,
        atomic: bool
    ) -> BatchResult:
        """Execute orders via Kalshi live API."""
        if not self.kalshi_client:
            return BatchResult(
                success=False,
                batch_id=batch_id,
                legs=legs,
                message="No Kalshi client configured for live trading"
            )

        # Format orders for Kalshi batch API
        orders = []
        for leg in legs:
            order = {
                "ticker": leg.ticker,
                "side": leg.side.value,
                "action": leg.action.value,
                "count": leg.contracts,
                "type": "limit"
            }
            # Kalshi uses yes_price or no_price depending on side
            if leg.side == OrderSide.YES:
                order["yes_price"] = leg.price_cents
            else:
                order["no_price"] = leg.price_cents

            orders.append(order)

        try:
            # Execute batch
            response = await self.kalshi_client.place_batch_orders(orders)

            # Process response
            total_cost = 0
            total_fees = 0
            all_success = True

            order_results = response.get("orders", [])
            for i, order_result in enumerate(order_results):
                if i < len(legs):
                    leg = legs[i]

                    if "error" in order_result:
                        leg.status = OrderStatus.FAILED
                        leg.error = order_result.get("error", {}).get("message", "Unknown error")
                        all_success = False
                    else:
                        order_data = order_result.get("order", {})
                        leg.status = OrderStatus.FILLED
                        leg.order_id = order_data.get("order_id")
                        leg.fill_price = order_data.get("yes_price") or order_data.get("no_price")
                        leg.filled_contracts = order_data.get("count", leg.contracts)

                        # Calculate actual cost and fee
                        cost = leg.filled_contracts * (leg.fill_price or leg.price_cents)
                        fee = self._calculate_fee_cents(
                            leg.filled_contracts,
                            leg.fill_price or leg.price_cents
                        )
                        leg.fee_cents = fee

                        total_cost += cost
                        total_fees += fee

            success = all_success or not atomic

            logger.info(
                f"Live execution: {len(legs)} legs, "
                f"success={success}, cost={total_cost}¢, fees={total_fees}¢"
            )

            return BatchResult(
                success=success,
                batch_id=batch_id,
                legs=legs,
                total_cost_cents=total_cost,
                total_fees_cents=total_fees,
                message=f"Live: {sum(1 for l in legs if l.status == OrderStatus.FILLED)}/{len(legs)} filled"
            )

        except Exception as e:
            logger.error(f"Live execution failed: {e}")
            for leg in legs:
                leg.status = OrderStatus.FAILED
                leg.error = str(e)

            return BatchResult(
                success=False,
                batch_id=batch_id,
                legs=legs,
                message=f"Execution error: {e}"
            )

    async def execute_arbitrage(
        self,
        legs_data: List[Dict],
        contracts_per_leg: int,
        mode: str = "paper"
    ) -> BatchResult:
        """
        Execute an arbitrage trade.

        Convenience method that creates OrderLeg objects from dict data.

        Args:
            legs_data: List of leg dicts with ticker, side, action, price_cents
            contracts_per_leg: Number of contracts for each leg
            mode: "paper" or "live"

        Returns:
            BatchResult with execution details

        .. deprecated::
            Use ExecutionGateway.execute_arbitrage instead.
        """
        warnings.warn(
            "BatchExecutor.execute_arbitrage is deprecated. "
            "Use ExecutionGateway.execute_arbitrage instead.",
            DeprecationWarning,
            stacklevel=2
        )
        legs = []
        for leg_data in legs_data:
            leg = OrderLeg(
                ticker=leg_data["ticker"],
                side=OrderSide(leg_data["side"]),
                action=OrderAction(leg_data.get("action", "buy")),
                contracts=contracts_per_leg,
                price_cents=leg_data["price_cents"]
            )
            legs.append(leg)

        return await self.execute(legs, mode=mode, atomic=True)

    async def execute_single(
        self,
        ticker: str,
        side: str,
        action: str,
        contracts: int,
        price_cents: int,
        mode: str = "paper"
    ) -> BatchResult:
        """
        Execute a single order.

        Convenience method for simple one-leg trades.

        Args:
            ticker: Market ticker
            side: "yes" or "no"
            action: "buy" or "sell"
            contracts: Number of contracts
            price_cents: Price in cents
            mode: "paper" or "live"

        Returns:
            BatchResult with execution details

        .. deprecated::
            Use ExecutionGateway.execute_single instead.
        """
        warnings.warn(
            "BatchExecutor.execute_single is deprecated. "
            "Use ExecutionGateway.execute_single instead.",
            DeprecationWarning,
            stacklevel=2
        )
        leg = OrderLeg(
            ticker=ticker,
            side=OrderSide(side),
            action=OrderAction(action),
            contracts=contracts,
            price_cents=price_cents
        )

        return await self.execute([leg], mode=mode, atomic=True)

    def estimate_cost(
        self,
        legs: List[OrderLeg]
    ) -> Dict[str, int]:
        """
        Estimate total cost and fees for a batch.

        Args:
            legs: List of order legs

        Returns:
            Dict with cost_cents, fees_cents, total_cents
        """
        total_cost = 0
        total_fees = 0

        for leg in legs:
            cost = leg.contracts * leg.price_cents
            fee = self._calculate_fee_cents(leg.contracts, leg.price_cents)
            total_cost += cost
            total_fees += fee

        return {
            "cost_cents": total_cost,
            "fees_cents": total_fees,
            "total_cents": total_cost + total_fees
        }
