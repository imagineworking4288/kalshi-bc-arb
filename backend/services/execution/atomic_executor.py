"""
Atomic execution of multi-leg orders.

Ensures all-or-nothing execution for arbitrage trades.
Uses batch orders and handles rollback on partial fills.
"""

import asyncio
import uuid
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from backend.services.analysis.fee_calculator import calculate_fee
from backend.services.log_config import get_logger

logger = get_logger("atomic_executor")


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class LegResult:
    """Result for a single leg of execution"""
    ticker: str
    order_id: Optional[str]
    client_order_id: str
    status: str
    side: str
    action: str
    requested_quantity: int
    filled_quantity: int
    requested_price: int
    fill_price: Optional[int]
    fee_cents: float
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "status": self.status,
            "side": self.side,
            "action": self.action,
            "requested_quantity": self.requested_quantity,
            "filled_quantity": self.filled_quantity,
            "requested_price": self.requested_price,
            "fill_price": self.fill_price,
            "fee_cents": self.fee_cents,
            "error": self.error,
        }


@dataclass
class ExecutionResult:
    """Result of atomic execution"""
    execution_id: str
    status: ExecutionStatus
    started_at: datetime
    completed_at: Optional[datetime]

    # Leg results
    legs: List[LegResult] = field(default_factory=list)

    # Summary
    total_legs: int = 0
    filled_legs: int = 0
    failed_legs: int = 0

    total_cost_cents: int = 0
    total_fees_cents: float = 0

    # Rollback info
    rollback_performed: bool = False
    rollback_results: List[dict] = field(default_factory=list)

    # Errors
    errors: List[str] = field(default_factory=list)

    # Timing
    execution_ms: int = 0

    @property
    def success(self) -> bool:
        return self.status == ExecutionStatus.COMPLETED

    @property
    def fully_filled(self) -> bool:
        return self.filled_legs == self.total_legs

    def to_dict(self) -> dict:
        return {
            "execution_id": self.execution_id,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "legs": [leg.to_dict() for leg in self.legs],
            "total_legs": self.total_legs,
            "filled_legs": self.filled_legs,
            "failed_legs": self.failed_legs,
            "total_cost_cents": self.total_cost_cents,
            "total_fees_cents": self.total_fees_cents,
            "rollback_performed": self.rollback_performed,
            "rollback_results": self.rollback_results,
            "errors": self.errors,
            "execution_ms": self.execution_ms,
            "success": self.success,
            "fully_filled": self.fully_filled,
        }


@dataclass
class ExecutorConfig:
    """Configuration for executor"""
    use_fill_or_kill: bool = True  # Use FoK time-in-force for atomicity
    max_retry_attempts: int = 2
    retry_delay_seconds: float = 0.5
    execution_timeout_seconds: float = 30.0
    enable_rollback: bool = True
    paper_mode: bool = True  # Default to paper trading


class AtomicExecutor:
    """
    Execute multi-leg orders atomically.

    Strategies for atomicity:
    1. Fill-or-Kill: Each leg must fill entirely
    2. Batch Orders: Submit all legs together via Kalshi batch API
    3. Rollback: If any leg fails, cancel/reverse successful legs

    Usage:
        executor = AtomicExecutor(kalshi_client, config)
        result = await executor.execute_arbitrage(legs)

        if result.success:
            print(f"Filled {result.filled_legs} legs")
        else:
            print(f"Failed: {result.errors}")
    """

    def __init__(
        self,
        kalshi_client,  # KalshiClient instance
        config: Optional[ExecutorConfig] = None,
    ):
        self.client = kalshi_client
        self.config = config or ExecutorConfig()
        self._active_executions: Dict[str, ExecutionResult] = {}

    async def execute_arbitrage(
        self,
        legs: List[dict],  # {'ticker', 'side', 'action', 'quantity', 'price_cents'}
        mode: Optional[str] = None,  # 'paper' or 'live'
    ) -> ExecutionResult:
        """
        Execute all legs atomically.

        Args:
            legs: List of order specifications
            mode: 'paper' or 'live' (overrides config if provided)

        Returns:
            ExecutionResult with status and details
        """
        execution_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        result = ExecutionResult(
            execution_id=execution_id,
            status=ExecutionStatus.PENDING,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            total_legs=len(legs),
        )

        self._active_executions[execution_id] = result

        # Determine mode
        use_paper = mode == 'paper' if mode else self.config.paper_mode

        try:
            result.status = ExecutionStatus.EXECUTING

            if use_paper:
                await self._execute_paper(legs, result)
            else:
                await self._execute_live(legs, result)

        except asyncio.TimeoutError:
            result.status = ExecutionStatus.FAILED
            result.errors.append("Execution timed out")
            result.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            logger.error(f"Execution error: {e}")
            result.status = ExecutionStatus.FAILED
            result.errors.append(str(e))
            result.completed_at = datetime.now(timezone.utc)

        finally:
            result.execution_ms = int((time.time() - start_time) * 1000)
            self._active_executions.pop(execution_id, None)

        return result

    async def _execute_paper(self, legs: List[dict], result: ExecutionResult):
        """Execute orders in paper mode (instant simulation)."""
        total_cost = 0
        total_fees = 0.0
        filled_count = 0

        for i, leg in enumerate(legs):
            client_order_id = f"{result.execution_id}-{i}"
            quantity = leg['quantity']
            price_cents = leg['price_cents']

            # Calculate fee
            fee_result = calculate_fee(quantity, price_cents)
            fee = fee_result.fee_cents

            # Simulate instant fill
            leg_result = LegResult(
                ticker=leg['ticker'],
                order_id=f"PAPER-{result.execution_id}-{i}",
                client_order_id=client_order_id,
                status="executed",
                side=leg.get('side', 'yes'),
                action=leg.get('action', 'buy'),
                requested_quantity=quantity,
                filled_quantity=quantity,
                requested_price=price_cents,
                fill_price=price_cents,
                fee_cents=fee,
            )

            result.legs.append(leg_result)
            total_cost += quantity * price_cents
            total_fees += fee
            filled_count += 1

        result.filled_legs = filled_count
        result.failed_legs = 0
        result.total_cost_cents = total_cost
        result.total_fees_cents = total_fees
        result.status = ExecutionStatus.COMPLETED
        result.completed_at = datetime.now(timezone.utc)

        logger.info(
            f"Paper execution {result.execution_id}: {len(legs)} legs, "
            f"cost={total_cost}c, fees={total_fees:.1f}c"
        )

    async def _execute_live(self, legs: List[dict], result: ExecutionResult):
        """Execute orders via Kalshi live API."""
        if not self.client:
            result.status = ExecutionStatus.FAILED
            result.errors.append("No Kalshi client configured for live trading")
            result.completed_at = datetime.now(timezone.utc)
            return

        # Format orders for Kalshi batch API
        orders = []
        for i, leg in enumerate(legs):
            client_order_id = f"{result.execution_id}-{i}"
            side = leg.get('side', 'yes')

            order = {
                "ticker": leg['ticker'],
                "side": side,
                "action": leg.get('action', 'buy'),
                "count": leg['quantity'],
                "type": "limit",
                "client_order_id": client_order_id,
            }

            # Kalshi uses yes_price or no_price depending on side
            if side == "yes":
                order["yes_price"] = leg['price_cents']
            else:
                order["no_price"] = leg['price_cents']

            # Add fill-or-kill if configured
            if self.config.use_fill_or_kill:
                order["time_in_force"] = "fill_or_kill"

            orders.append(order)

        try:
            # Execute batch
            response = await self.client.place_batch_orders(orders)

            # Process results
            filled_count = 0
            failed_count = 0
            total_cost = 0
            total_fees = 0.0

            order_results = response.get("orders", [])

            for i, (order_result, leg) in enumerate(zip(order_results, legs)):
                client_order_id = f"{result.execution_id}-{i}"
                side = leg.get('side', 'yes')

                if "error" in order_result:
                    # Order failed
                    error_msg = order_result.get("error", {})
                    if isinstance(error_msg, dict):
                        error_msg = error_msg.get("message", "Unknown error")

                    leg_result = LegResult(
                        ticker=leg['ticker'],
                        order_id=None,
                        client_order_id=client_order_id,
                        status="failed",
                        side=side,
                        action=leg.get('action', 'buy'),
                        requested_quantity=leg['quantity'],
                        filled_quantity=0,
                        requested_price=leg['price_cents'],
                        fill_price=None,
                        fee_cents=0,
                        error=str(error_msg),
                    )
                    failed_count += 1
                    result.errors.append(f"{leg['ticker']}: {error_msg}")

                else:
                    # Order succeeded
                    order_data = order_result.get("order", {})
                    fill_count = order_data.get("fill_count", leg['quantity'])
                    fill_price = order_data.get("yes_price") or order_data.get("no_price") or leg['price_cents']

                    fee_result = calculate_fee(fill_count, fill_price)
                    fee = fee_result.fee_cents

                    leg_result = LegResult(
                        ticker=leg['ticker'],
                        order_id=order_data.get("order_id"),
                        client_order_id=client_order_id,
                        status="executed",
                        side=side,
                        action=leg.get('action', 'buy'),
                        requested_quantity=leg['quantity'],
                        filled_quantity=fill_count,
                        requested_price=leg['price_cents'],
                        fill_price=fill_price,
                        fee_cents=fee,
                    )

                    total_cost += fill_count * fill_price
                    total_fees += fee
                    filled_count += 1

                result.legs.append(leg_result)

            result.filled_legs = filled_count
            result.failed_legs = failed_count
            result.total_cost_cents = total_cost
            result.total_fees_cents = total_fees

            # Determine final status
            if filled_count == len(legs):
                result.status = ExecutionStatus.COMPLETED
            elif filled_count > 0 and failed_count > 0:
                result.status = ExecutionStatus.PARTIAL

                # Rollback if enabled
                if self.config.enable_rollback:
                    await self._rollback_successful_legs(result)
            else:
                result.status = ExecutionStatus.FAILED

            result.completed_at = datetime.now(timezone.utc)

            logger.info(
                f"Live execution {result.execution_id}: {filled_count}/{len(legs)} filled, "
                f"cost={total_cost}c, fees={total_fees:.1f}c"
            )

        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            result.status = ExecutionStatus.FAILED
            result.errors.append(f"Batch execution error: {e}")
            result.completed_at = datetime.now(timezone.utc)

    async def _rollback_successful_legs(self, result: ExecutionResult):
        """Cancel or reverse successful legs after partial failure."""
        result.rollback_performed = True

        logger.warning(f"Performing rollback for execution {result.execution_id}")

        for leg in result.legs:
            if leg.filled_quantity > 0:
                try:
                    # Create opposite order to unwind position
                    opposite_action = 'sell' if leg.action == 'buy' else 'buy'

                    unwind_response = await self.client.place_order(
                        ticker=leg.ticker,
                        side=leg.side,
                        action=opposite_action,
                        count=leg.filled_quantity,
                        price=leg.fill_price or leg.requested_price,
                        order_type="market",  # Use market for quick unwind
                    )

                    result.rollback_results.append({
                        'ticker': leg.ticker,
                        'action': 'unwind',
                        'success': True,
                        'response': unwind_response,
                    })

                    logger.info(f"Rollback: unwound {leg.filled_quantity} {leg.side} on {leg.ticker}")

                except Exception as e:
                    logger.error(f"Rollback failed for {leg.ticker}: {e}")
                    result.errors.append(f"Rollback failed for {leg.ticker}: {e}")
                    result.rollback_results.append({
                        'ticker': leg.ticker,
                        'action': 'unwind',
                        'success': False,
                        'error': str(e),
                    })

        result.status = ExecutionStatus.ROLLED_BACK

    async def execute_single(
        self,
        ticker: str,
        side: str,
        action: str,
        quantity: int,
        price_cents: int,
        mode: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a single order.

        Convenience method for non-arbitrage trades.
        """
        legs = [{
            'ticker': ticker,
            'side': side,
            'action': action,
            'quantity': quantity,
            'price_cents': price_cents,
        }]

        return await self.execute_arbitrage(legs, mode=mode)

    def estimate_cost(self, legs: List[dict]) -> dict:
        """
        Estimate total cost and fees for a batch.

        Args:
            legs: List of order legs

        Returns:
            Dict with cost_cents, fees_cents, total_cents
        """
        total_cost = 0
        total_fees = 0.0

        for leg in legs:
            quantity = leg['quantity']
            price_cents = leg['price_cents']

            cost = quantity * price_cents
            fee_result = calculate_fee(quantity, price_cents)

            total_cost += cost
            total_fees += fee_result.fee_cents

        return {
            "cost_cents": total_cost,
            "fees_cents": total_fees,
            "total_cents": int(total_cost + total_fees),
        }

    def get_active_executions(self) -> List[ExecutionResult]:
        """Get all active executions"""
        return list(self._active_executions.values())
