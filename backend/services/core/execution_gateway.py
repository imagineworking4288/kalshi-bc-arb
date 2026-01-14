"""
ExecutionGateway - Single entry point for ALL trade execution.

Every trade in the system - manual, automated, arbitrage - must go through
this gateway. It provides:
- Idempotency (duplicate requests return cached results)
- Risk checks (circuit breaker, position limits)
- Audit logging (every execution recorded)
- Mode routing (paper vs live vs dual)
- Unified fee calculation

Usage:
    gateway = ExecutionGateway(
        kalshi_client=client,
        paper_service=paper,
        risk_manager=risk_mgr,
        circuit_breaker=circuit,
        fee_calculator=fee_calc,
        db=database,
        alert_service=alerts
    )

    # Single order
    result = await gateway.execute_single(
        ticker="KXBTC-24DEC31-100000",
        side="yes",
        action="buy",
        contracts=10,
        price_cents=45,
        mode="paper",
        source="manual"
    )

    # Multi-leg arbitrage
    result = await gateway.execute_arbitrage(
        legs=[{"ticker": "A", "side": "yes", "price_cents": 30}, ...],
        contracts_per_leg=10,
        mode="paper",
        source="orchestrator"
    )
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Literal, Optional, Any

from backend.models.execution_models import (
    ExecutionRequest,
    ExecutionResult,
    ExecutionLeg,
    LegResult,
)
from backend.services.core.risk_manager import RiskManager
from backend.services.core.circuit_breaker import CircuitBreaker
from backend.services.core.fee_calculator import FeeCalculator, FeeType
from backend.services.core.alert_service import AlertService
from backend.services.log_config import get_logger

logger = get_logger("execution_gateway")


@dataclass
class GatewayConfig:
    """
    Configuration for ExecutionGateway behavior.

    Attributes:
        idempotency_ttl_seconds: How long to cache results for duplicate detection
        max_cache_size: Maximum entries in idempotency cache
        require_risk_check: Whether to enforce risk limits
        require_circuit_check: Whether to check circuit breaker
        default_timeout_seconds: Default execution timeout
    """

    idempotency_ttl_seconds: int = 300  # 5 minutes
    max_cache_size: int = 1000
    require_risk_check: bool = True
    require_circuit_check: bool = True
    default_timeout_seconds: float = 30.0


@dataclass
class CachedResult:
    """Cached execution result with timestamp for TTL."""

    result: ExecutionResult
    cached_at: datetime


class ExecutionGateway:
    """
    Single entry point for ALL trade execution.

    Every trade in the system - manual, automated, arbitrage - must go through
    this gateway. It provides:
    - Idempotency (duplicate requests return cached results)
    - Risk checks (circuit breaker, position limits)
    - Audit logging (every execution recorded)
    - Mode routing (paper vs live vs dual)
    - Unified fee calculation

    Thread Safety:
        All methods are async-safe and can be called concurrently.
        Uses asyncio.Lock for critical sections.

    Error Handling:
        All exceptions are caught and converted to ExecutionResult with
        success=False. Errors are logged and recorded in audit.
    """

    def __init__(
        self,
        kalshi_client,  # KalshiClient
        paper_service,  # PaperTradingService
        risk_manager: RiskManager,
        circuit_breaker: CircuitBreaker,
        fee_calculator: FeeCalculator,
        db,  # Database
        alert_service: AlertService,
        config: Optional[GatewayConfig] = None,
        position_manager=None,  # PositionManager for cache invalidation
    ):
        """
        Initialize ExecutionGateway with all dependencies.

        Args:
            kalshi_client: KalshiClient for live order execution
            paper_service: PaperTradingService for paper trading simulation
            risk_manager: RiskManager for position/exposure limits
            circuit_breaker: CircuitBreaker for emergency halt
            fee_calculator: FeeCalculator for fee estimation
            db: Database connection for audit logging
            alert_service: AlertService for notifications
            config: Optional configuration overrides
            position_manager: Optional PositionManager for cache invalidation
        """
        self.kalshi_client = kalshi_client
        self.paper_service = paper_service
        self.risk_manager = risk_manager
        self.circuit_breaker = circuit_breaker
        self.fee_calculator = fee_calculator
        self.db = db
        self.alert_service = alert_service
        self.config = config or GatewayConfig()
        self.position_manager = position_manager

        # Idempotency cache: request_id -> CachedResult
        self._idempotency_cache: Dict[str, CachedResult] = {}

        # Thread safety
        self._lock = asyncio.Lock()

        logger.info("ExecutionGateway initialized")

    async def execute(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute a trade request through the full pipeline.

        Pipeline:
        1. Check idempotency cache (return cached result if exists)
        2. Validate request
        3. Check circuit breaker
        4. Check risk limits for each leg
        5. Calculate expected costs/fees
        6. Route to paper or live execution
        7. Record to audit log
        8. Update circuit breaker with result
        9. Send alerts
        10. Cache result for idempotency

        Args:
            request: ExecutionRequest with all trade details

        Returns:
            ExecutionResult with execution details and audit_id

        Note:
            Never raises exceptions - all errors are returned in
            ExecutionResult with success=False
        """
        start_time = time.time()
        audit_id = ""

        try:
            # 1. Check idempotency cache
            cached = await self._check_idempotency(request.request_id)
            if cached is not None:
                logger.info(f"Idempotency hit for request {request.request_id}")
                return cached

            # 2. Validate request
            await self._validate_request(request)

            # 3. Check circuit breaker
            if self.config.require_circuit_check:
                can_trade, cb_reason = await self.circuit_breaker.can_trade()
                if not can_trade:
                    logger.warning(f"Circuit breaker blocked: {cb_reason}")
                    result = self._create_failed_result(
                        request, start_time, f"Circuit breaker: {cb_reason}"
                    )
                    audit_id = await self._record_audit(request, result)
                    result = ExecutionResult(
                        **{**result.model_dump(), "audit_id": audit_id}
                    )
                    await self._send_alerts(request, result)
                    return result

            # 4. Re-validate prices before execution (live mode only)
            if request.mode in ("live", "dual"):
                prices_valid = await self._revalidate_prices(
                    request, request.max_slippage_cents
                )
                if not prices_valid:
                    result = self._create_failed_result(
                        request, start_time, "Prices have moved beyond acceptable slippage"
                    )
                    audit_id = await self._record_audit(request, result)
                    result = ExecutionResult(
                        **{**result.model_dump(), "audit_id": audit_id}
                    )
                    await self._send_alerts(request, result)
                    return result

            # 4b. Check markets aren't closing soon (live mode only)
            if request.mode in ("live", "dual"):
                for leg in request.legs:
                    market_open = await self._check_market_open(leg.ticker, min_seconds=60)
                    if not market_open:
                        result = self._create_failed_result(
                            request, start_time, f"Market {leg.ticker} is closed or closing soon"
                        )
                        audit_id = await self._record_audit(request, result)
                        result = ExecutionResult(
                            **{**result.model_dump(), "audit_id": audit_id}
                        )
                        await self._send_alerts(request, result)
                        return result

            # 5. Check risk limits for each leg
            if self.config.require_risk_check:
                # Get current balance for risk check
                balance_cents = await self._get_balance_cents(request.mode)

                for leg in request.legs:
                    risk_check = await self.risk_manager.check_trade(
                        ticker=leg.ticker,
                        contracts=leg.contracts,
                        price_cents=leg.price_cents,
                        balance_cents=balance_cents,
                    )
                    if not risk_check.approved:
                        logger.warning(f"Risk check failed: {risk_check.reason}")
                        result = self._create_failed_result(
                            request, start_time, f"Risk check: {risk_check.reason}"
                        )
                        audit_id = await self._record_audit(request, result)
                        result = ExecutionResult(
                            **{**result.model_dump(), "audit_id": audit_id}
                        )
                        await self._send_alerts(request, result)
                        return result

            # 5. Calculate expected fees (for logging purposes)
            _ = self._calculate_expected_fees(request)

            # 6. Route to execution based on mode
            if request.mode == "dual":
                # Execute in paper first, then live
                paper_result = await self._execute_paper(request)
                if paper_result.success:
                    result = await self._execute_live(request)
                else:
                    result = paper_result
            elif request.mode == "paper":
                result = await self._execute_paper(request)
            else:  # live
                result = await self._execute_live(request)

            # Calculate execution time
            execution_time_ms = int((time.time() - start_time) * 1000)
            result = ExecutionResult(
                **{**result.model_dump(), "execution_time_ms": execution_time_ms}
            )

            # 7. Record to audit log
            audit_id = await self._record_audit(request, result)
            result = ExecutionResult(**{**result.model_dump(), "audit_id": audit_id})

            # 8. Invalidate position cache after successful execution
            if result.success and self.position_manager:
                self.position_manager.invalidate_cache()
                logger.debug("Position cache invalidated after successful execution")

            # 9. Update circuit breaker
            await self._update_circuit_breaker(result)

            # 10. Send alerts
            await self._send_alerts(request, result)

            # 11. Cache result
            self._cache_result(request.request_id, result)

            logger.info(
                f"Execution complete: request={request.request_id}, "
                f"success={result.success}, mode={request.mode}, "
                f"legs={len(request.legs)}, time={execution_time_ms}ms"
            )

            return result

        except Exception as e:
            logger.error(f"Execution error: {e}", exc_info=True)

            # Create failure result
            result = self._create_failed_result(request, start_time, str(e))

            # Try to record audit
            try:
                audit_id = await self._record_audit(request, result)
                result = ExecutionResult(
                    **{**result.model_dump(), "audit_id": audit_id}
                )
            except Exception as audit_err:
                logger.error(f"Failed to record audit: {audit_err}")

            # Try to send alert
            try:
                await self.alert_service.error(
                    title="Execution Error",
                    message=str(e),
                    data={"request_id": request.request_id},
                )
            except Exception:
                pass

            return result

    async def execute_arbitrage(
        self,
        legs: List[Dict[str, Any]],
        contracts_per_leg: int,
        mode: Literal["paper", "live", "dual"],
        source: Literal[
            "orchestrator", "manual", "auto_trader", "btc_arb", "strategy"
        ],
        signal_id: Optional[str] = None,
        max_slippage_cents: int = 2,
        request_id: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a multi-leg arbitrage trade.

        Convenience method that builds an ExecutionRequest from parameters.

        Args:
            legs: List of leg dicts with ticker, side, action (optional), price_cents
            contracts_per_leg: Number of contracts for each leg
            mode: Execution mode (paper, live, or dual)
            source: Request source for auditing
            signal_id: Optional originating signal ID
            max_slippage_cents: Maximum acceptable slippage per leg
            request_id: Optional custom request ID (auto-generated if None)

        Returns:
            ExecutionResult with all legs

        Example:
            result = await gateway.execute_arbitrage(
                legs=[
                    {"ticker": "KXBTC-A", "side": "yes", "price_cents": 30},
                    {"ticker": "KXBTC-B", "side": "yes", "price_cents": 25},
                ],
                contracts_per_leg=10,
                mode="paper",
                source="orchestrator"
            )
        """
        # Build ExecutionLeg objects
        execution_legs = [
            ExecutionLeg(
                ticker=leg["ticker"],
                side=leg["side"],
                action=leg.get("action", "buy"),
                contracts=contracts_per_leg,
                price_cents=leg["price_cents"],
            )
            for leg in legs
        ]

        # Create request using factory method
        request = ExecutionRequest.arbitrage(
            legs=execution_legs,
            mode=mode,
            source=source,
            signal_id=signal_id,
            max_slippage_cents=max_slippage_cents,
        )

        # Override request_id if provided
        if request_id:
            request = ExecutionRequest(
                **{**request.model_dump(), "request_id": request_id}
            )

        return await self.execute(request)

    async def execute_single(
        self,
        ticker: str,
        side: Literal["yes", "no"],
        action: Literal["buy", "sell"],
        contracts: int,
        price_cents: int,
        mode: Literal["paper", "live", "dual"],
        source: Literal[
            "orchestrator", "manual", "auto_trader", "btc_arb", "strategy"
        ],
        signal_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ExecutionResult:
        """
        Execute a single-leg order.

        Convenience method that builds an ExecutionRequest for a single order.

        Args:
            ticker: Market ticker (e.g., "KXBTC-24DEC31-100000")
            side: "yes" or "no"
            action: "buy" or "sell"
            contracts: Number of contracts
            price_cents: Limit price in cents (1-99)
            mode: Execution mode (paper, live, or dual)
            source: Request source for auditing
            signal_id: Optional originating signal ID
            request_id: Optional custom request ID (auto-generated if None)

        Returns:
            ExecutionResult with single leg

        Example:
            result = await gateway.execute_single(
                ticker="KXBTC-24DEC31-100000",
                side="yes",
                action="buy",
                contracts=10,
                price_cents=45,
                mode="paper",
                source="manual"
            )
        """
        # Create request using factory method
        request = ExecutionRequest.single_order(
            ticker=ticker,
            side=side,
            action=action,
            contracts=contracts,
            price_cents=price_cents,
            mode=mode,
            source=source,
            signal_id=signal_id,
        )

        # Override request_id if provided
        if request_id:
            request = ExecutionRequest(
                **{**request.model_dump(), "request_id": request_id}
            )

        return await self.execute(request)

    async def _check_idempotency(self, request_id: str) -> Optional[ExecutionResult]:
        """
        Check if this request was already executed.

        Checks in-memory cache with TTL.

        Args:
            request_id: Unique request identifier

        Returns:
            Cached ExecutionResult if exists and not expired, None otherwise
        """
        async with self._lock:
            cached = self._idempotency_cache.get(request_id)
            if cached is None:
                return None

            # Check TTL
            now = datetime.now(timezone.utc)
            cached_at = cached.cached_at
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=timezone.utc)
            age_seconds = (now - cached_at).total_seconds()

            if age_seconds > self.config.idempotency_ttl_seconds:
                # Expired, remove from cache
                del self._idempotency_cache[request_id]
                return None

            return cached.result

    async def _validate_request(self, request: ExecutionRequest) -> None:
        """
        Validate the execution request.

        Args:
            request: ExecutionRequest to validate

        Raises:
            ValueError: If request is invalid
        """
        if not request.legs:
            raise ValueError("At least one execution leg is required")

        for i, leg in enumerate(request.legs):
            if not leg.ticker:
                raise ValueError(f"Leg {i}: ticker is required")
            if leg.contracts <= 0:
                raise ValueError(f"Leg {i}: contracts must be positive")
            if not 1 <= leg.price_cents <= 99:
                raise ValueError(f"Leg {i}: price_cents must be 1-99")
            if leg.side not in ("yes", "no"):
                raise ValueError(f"Leg {i}: side must be 'yes' or 'no'")
            if leg.action not in ("buy", "sell"):
                raise ValueError(f"Leg {i}: action must be 'buy' or 'sell'")

        # Check for conflicting positions (cannot hold YES and NO on same market)
        await self._check_position_conflicts(request)

    async def _check_position_conflicts(self, request: ExecutionRequest) -> None:
        """
        Check if any leg would create a conflicting position.

        Kalshi does NOT allow holding YES and NO on the same market simultaneously.

        Args:
            request: ExecutionRequest to check

        Raises:
            ValueError: If a leg would conflict with existing position
        """
        if not self.kalshi_client:
            return  # Skip check if no client (paper mode only)

        try:
            positions = await self.kalshi_client.get_positions(status="open")
            position_map = {p["ticker"]: p["side"] for p in positions}

            for leg in request.legs:
                if leg.action != "buy":
                    continue  # Sells don't create conflicts

                existing_side = position_map.get(leg.ticker)
                if existing_side and existing_side != leg.side:
                    raise ValueError(
                        f"Position conflict on {leg.ticker}: "
                        f"already have {existing_side.upper()} position, "
                        f"cannot buy {leg.side.upper()}"
                    )
        except ValueError:
            raise  # Re-raise validation errors
        except Exception as e:
            logger.warning(f"Could not check positions: {e}")

    async def _revalidate_prices(
        self, request: ExecutionRequest, max_slippage_cents: int = 2
    ) -> bool:
        """
        Re-validate that market prices haven't moved significantly.

        Fetches current orderbook and compares to expected prices.
        Returns False if price has moved more than max_slippage_cents.

        Args:
            request: ExecutionRequest with expected prices
            max_slippage_cents: Maximum acceptable price movement

        Returns:
            True if prices are still valid, False if stale
        """
        if not self.kalshi_client:
            return True  # Skip validation in paper mode

        for leg in request.legs:
            try:
                orderbook = await self.kalshi_client.get_orderbook(leg.ticker)

                # Get current best price
                if leg.action == "buy":
                    # For buys, check the ask side
                    if leg.side == "yes":
                        asks = orderbook.get("yes", [])
                    else:
                        asks = orderbook.get("no", [])
                    current_price = asks[0][0] if asks else None
                else:
                    # For sells, check the bid side
                    if leg.side == "yes":
                        bids = orderbook.get("yes", [])
                    else:
                        bids = orderbook.get("no", [])
                    current_price = bids[0][0] if bids else None

                if current_price is None:
                    logger.warning(f"No orderbook depth for {leg.ticker}")
                    continue

                slippage = abs(current_price - leg.price_cents)
                if slippage > max_slippage_cents:
                    logger.warning(
                        f"Price stale for {leg.ticker}: "
                        f"expected {leg.price_cents}c, current {current_price}c, "
                        f"slippage {slippage}c > max {max_slippage_cents}c"
                    )
                    return False

            except Exception as e:
                logger.warning(f"Price validation failed for {leg.ticker}: {e}")
                # Don't fail on validation errors, proceed with execution

        return True

    async def _check_market_open(self, ticker: str, min_seconds: int = 60) -> bool:
        """
        Check if market is open and not closing soon.

        Args:
            ticker: Market ticker to check
            min_seconds: Minimum seconds until close required (default 60)

        Returns:
            True if market is open and not closing within min_seconds
        """
        if not self.kalshi_client:
            return True  # Skip check in paper-only mode

        try:
            market = await self.kalshi_client.get_market(ticker)
            if not market:
                logger.warning(f"Market {ticker} not found")
                return False

            # Check market status
            status = market.get("status", "").lower()
            if status != "open":
                logger.warning(f"Market {ticker} is not open (status: {status})")
                return False

            # Check close time
            close_time_str = market.get("close_time") or market.get("expiration_time")
            if close_time_str:
                close_time = datetime.fromisoformat(close_time_str.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                seconds_until_close = (close_time - now).total_seconds()

                if seconds_until_close < min_seconds:
                    logger.warning(
                        f"Market {ticker} closing too soon: {seconds_until_close:.0f}s "
                        f"(min {min_seconds}s required)"
                    )
                    return False

            return True

        except Exception as e:
            logger.warning(f"Market open check failed for {ticker}: {e}")
            # Don't fail on check errors, proceed with execution
            return True

    async def _execute_paper(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute orders in paper mode (instant simulation).

        Args:
            request: ExecutionRequest to execute

        Returns:
            ExecutionResult with simulated fills
        """
        leg_results = []
        total_cost = 0
        total_fees = 0

        for leg in request.legs:
            # Calculate fee
            fee_calc = self.fee_calculator.calculate(
                contracts=leg.contracts,
                price_cents=leg.price_cents,
                fee_type=FeeType.TAKER,
            )

            # Simulate instant fill
            leg_result = LegResult(
                ticker=leg.ticker,
                side=leg.side,
                action=leg.action,
                requested_contracts=leg.contracts,
                filled_contracts=leg.contracts,
                requested_price_cents=leg.price_cents,
                fill_price_cents=leg.price_cents,
                fee_cents=fee_calc.fee_cents,
                status="filled",
                order_id=f"PAPER-{request.request_id[:8]}-{leg.ticker}",
                slippage_cents=0,
            )

            leg_results.append(leg_result)
            total_cost += leg.contracts * leg.price_cents
            total_fees += fee_calc.fee_cents

        logger.info(
            f"Paper execution: {len(leg_results)} legs, "
            f"cost={total_cost}c, fees={total_fees}c"
        )

        return ExecutionResult(
            request_id=request.request_id,
            success=True,
            mode="paper",
            legs=leg_results,
            total_cost_cents=total_cost,
            total_fees_cents=total_fees,
            execution_time_ms=0,  # Will be updated by caller
            audit_id="",  # Will be updated after audit
        )

    async def _execute_live(self, request: ExecutionRequest) -> ExecutionResult:
        """
        Execute orders via Kalshi live API.

        Uses batch orders for atomic multi-leg execution.

        Args:
            request: ExecutionRequest to execute

        Returns:
            ExecutionResult with actual fills
        """
        if not self.kalshi_client:
            return self._create_failed_result(
                request, time.time(), "No Kalshi client configured for live trading"
            )

        # Build orders for Kalshi batch API
        orders = []
        for leg in request.legs:
            order = {
                "ticker": leg.ticker,
                "side": leg.side,
                "action": leg.action,
                "count": leg.contracts,
                "type": "limit",
            }
            # Kalshi uses yes_price or no_price depending on side
            if leg.side == "yes":
                order["yes_price"] = leg.price_cents
            else:
                order["no_price"] = leg.price_cents

            orders.append(order)

        try:
            # Execute batch
            if len(orders) == 1:
                # Single order - use place_order
                response = await self.kalshi_client.place_order(
                    ticker=orders[0]["ticker"],
                    side=orders[0]["side"],
                    action=orders[0]["action"],
                    count=orders[0]["count"],
                    price=orders[0].get("yes_price") or orders[0].get("no_price"),
                    order_type="limit",
                )
                order_results = [{"order": response}]
            else:
                # Multiple orders - use batch
                response = await self.kalshi_client.place_batch_orders(orders)
                order_results = response.get("orders", [])

            # Process results
            leg_results = []
            total_cost = 0
            total_fees = 0
            all_filled = True

            for i, (order_result, leg) in enumerate(zip(order_results, request.legs)):
                if "error" in order_result:
                    # Order failed
                    error_msg = order_result.get("error", {})
                    if isinstance(error_msg, dict):
                        error_msg = error_msg.get("message", "Unknown error")

                    leg_result = LegResult(
                        ticker=leg.ticker,
                        side=leg.side,
                        action=leg.action,
                        requested_contracts=leg.contracts,
                        filled_contracts=0,
                        requested_price_cents=leg.price_cents,
                        fill_price_cents=None,
                        fee_cents=0,
                        status="failed",
                        error=str(error_msg),
                        slippage_cents=0,
                    )
                    all_filled = False
                else:
                    # Order succeeded
                    order_data = order_result.get("order", {})
                    fill_count = order_data.get("count", leg.contracts)
                    fill_price = (
                        order_data.get("yes_price")
                        or order_data.get("no_price")
                        or leg.price_cents
                    )

                    # Calculate fee
                    fee_calc = self.fee_calculator.calculate(
                        contracts=fill_count,
                        price_cents=fill_price,
                        fee_type=FeeType.TAKER,
                    )

                    # Calculate slippage
                    slippage = abs(fill_price - leg.price_cents)

                    leg_result = LegResult(
                        ticker=leg.ticker,
                        side=leg.side,
                        action=leg.action,
                        requested_contracts=leg.contracts,
                        filled_contracts=fill_count,
                        requested_price_cents=leg.price_cents,
                        fill_price_cents=fill_price,
                        fee_cents=fee_calc.fee_cents,
                        status="filled" if fill_count == leg.contracts else "partial",
                        order_id=order_data.get("order_id"),
                        slippage_cents=slippage,
                    )

                    total_cost += fill_count * fill_price
                    total_fees += fee_calc.fee_cents

                leg_results.append(leg_result)

            success = all_filled if request.atomic else any(
                lr.status == "filled" for lr in leg_results
            )

            logger.info(
                f"Live execution: {len(leg_results)} legs, "
                f"success={success}, cost={total_cost}c, fees={total_fees}c"
            )

            return ExecutionResult(
                request_id=request.request_id,
                success=success,
                mode="live",
                legs=leg_results,
                total_cost_cents=total_cost,
                total_fees_cents=total_fees,
                execution_time_ms=0,  # Will be updated by caller
                audit_id="",  # Will be updated after audit
                error=None if success else "One or more legs failed",
            )

        except Exception as e:
            logger.error(f"Live execution failed: {e}")
            return self._create_failed_result(request, time.time(), str(e))

    async def _record_audit(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> str:
        """
        Log execution to execution_audit table.

        Args:
            request: Original execution request
            result: Execution result

        Returns:
            Audit ID (UUID)
        """
        audit_id = str(uuid.uuid4())

        # Serialize legs
        legs_json = json.dumps(
            [
                {
                    "ticker": leg.ticker,
                    "side": leg.side,
                    "action": leg.action,
                    "contracts": leg.contracts,
                    "price_cents": leg.price_cents,
                }
                for leg in request.legs
            ]
        )

        # Serialize leg results
        leg_results_json = json.dumps(
            [
                {
                    "ticker": lr.ticker,
                    "side": lr.side,
                    "action": lr.action,
                    "requested_contracts": lr.requested_contracts,
                    "filled_contracts": lr.filled_contracts,
                    "requested_price_cents": lr.requested_price_cents,
                    "fill_price_cents": lr.fill_price_cents,
                    "fee_cents": lr.fee_cents,
                    "status": lr.status,
                    "order_id": lr.order_id,
                    "error": lr.error,
                    "slippage_cents": lr.slippage_cents,
                }
                for lr in result.legs
            ]
        )

        try:
            async with self.db.connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO execution_audit (
                        id, request_id, source, signal_id, mode,
                        legs_json, atomic, max_slippage_cents,
                        success, total_cost_cents, total_fees_cents,
                        execution_time_ms, leg_results_json, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        audit_id,
                        request.request_id,
                        request.source,
                        request.signal_id,
                        request.mode,
                        legs_json,
                        1 if request.atomic else 0,
                        request.max_slippage_cents,
                        1 if result.success else 0,
                        result.total_cost_cents,
                        result.total_fees_cents,
                        result.execution_time_ms,
                        leg_results_json,
                        result.error,
                    ),
                )
                await conn.commit()

            logger.debug(f"Audit recorded: {audit_id}")

        except Exception as e:
            logger.error(f"Failed to record audit: {e}")
            # Don't raise - audit failure shouldn't fail the trade

        return audit_id

    async def _send_alerts(
        self, request: ExecutionRequest, result: ExecutionResult
    ) -> None:
        """
        Send appropriate alerts based on execution result.

        Args:
            request: Original execution request
            result: Execution result
        """
        primary_ticker = request.legs[0].ticker if request.legs else "UNKNOWN"
        total_contracts = sum(leg.contracts for leg in request.legs)

        try:
            if result.success:
                await self.alert_service.trade_executed(
                    ticker=primary_ticker,
                    contracts=total_contracts,
                    price_cents=request.legs[0].price_cents if request.legs else 0,
                    pnl_cents=0,  # Unknown until settlement
                    mode=request.mode,
                    data={
                        "request_id": request.request_id,
                        "source": request.source,
                        "signal_id": request.signal_id,
                        "legs": len(request.legs),
                        "total_cost_cents": result.total_cost_cents,
                        "total_fees_cents": result.total_fees_cents,
                    },
                )
            else:
                await self.alert_service.trade_failed(
                    ticker=primary_ticker,
                    reason=result.error or "Unknown error",
                    data={
                        "request_id": request.request_id,
                        "source": request.source,
                    },
                )
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")

    async def _update_circuit_breaker(self, result: ExecutionResult) -> None:
        """
        Update circuit breaker with trade result.

        Args:
            result: Execution result
        """
        try:
            # For now, only record failed executions as losses
            # In the future, we'd track actual P&L at settlement
            if not result.success:
                primary_ticker = result.legs[0].ticker if result.legs else ""
                await self.circuit_breaker.record_result(
                    won=False,
                    pnl_cents=0,
                    ticker=primary_ticker,
                )
        except Exception as e:
            logger.error(f"Failed to update circuit breaker: {e}")

    def _cache_result(self, request_id: str, result: ExecutionResult) -> None:
        """
        Cache result in memory for idempotency.

        Args:
            request_id: Request identifier
            result: Result to cache
        """
        # Evict old entries if cache is full
        if len(self._idempotency_cache) >= self.config.max_cache_size:
            # Remove oldest 10% of entries
            entries_to_remove = self.config.max_cache_size // 10
            oldest_keys = sorted(
                self._idempotency_cache.keys(),
                key=lambda k: self._idempotency_cache[k].cached_at,
            )[:entries_to_remove]
            for key in oldest_keys:
                del self._idempotency_cache[key]

        self._idempotency_cache[request_id] = CachedResult(
            result=result,
            cached_at=datetime.now(timezone.utc),
        )

    def _create_failed_result(
        self, request: ExecutionRequest, start_time: float, error: str
    ) -> ExecutionResult:
        """
        Create a failed ExecutionResult.

        Args:
            request: Original request
            start_time: Execution start time
            error: Error message

        Returns:
            ExecutionResult with success=False
        """
        execution_time_ms = int((time.time() - start_time) * 1000)

        # Create failed leg results
        leg_results = [
            LegResult(
                ticker=leg.ticker,
                side=leg.side,
                action=leg.action,
                requested_contracts=leg.contracts,
                filled_contracts=0,
                requested_price_cents=leg.price_cents,
                fill_price_cents=None,
                fee_cents=0,
                status="failed",
                error=error,
                slippage_cents=0,
            )
            for leg in request.legs
        ]

        return ExecutionResult(
            request_id=request.request_id,
            success=False,
            mode=request.mode,
            legs=leg_results,
            total_cost_cents=0,
            total_fees_cents=0,
            execution_time_ms=execution_time_ms,
            audit_id="",
            error=error,
        )

    def _calculate_expected_fees(self, request: ExecutionRequest) -> int:
        """
        Calculate expected fees for all legs.

        Args:
            request: ExecutionRequest

        Returns:
            Total expected fees in cents
        """
        total_fees = 0
        for leg in request.legs:
            fee_calc = self.fee_calculator.calculate(
                contracts=leg.contracts,
                price_cents=leg.price_cents,
                fee_type=FeeType.TAKER,
            )
            total_fees += fee_calc.fee_cents
        return total_fees

    async def _get_balance_cents(self, mode: str) -> int:
        """
        Get current balance in cents for risk checks.

        Args:
            mode: Execution mode

        Returns:
            Balance in cents
        """
        try:
            if mode == "paper" or mode == "dual":
                if self.paper_service:
                    balance = await self.paper_service.get_balance()
                    return int(balance.get("available_balance", 0) * 100)
            else:  # live
                if self.kalshi_client:
                    balance = await self.kalshi_client.get_balance()
                    return int(balance.get("available_balance", 0))
        except Exception as e:
            logger.warning(f"Failed to get balance: {e}")

        return 100000  # Default to $1000 if can't get balance

    def get_status(self) -> Dict[str, Any]:
        """
        Get gateway status for monitoring.

        Returns:
            Dict with status information
        """
        return {
            "config": {
                "idempotency_ttl_seconds": self.config.idempotency_ttl_seconds,
                "max_cache_size": self.config.max_cache_size,
                "require_risk_check": self.config.require_risk_check,
                "require_circuit_check": self.config.require_circuit_check,
            },
            "cache_size": len(self._idempotency_cache),
        }

    async def get_recent_audits(self, limit: int = 50) -> List[Dict]:
        """
        Get recent execution audit records.

        Args:
            limit: Maximum records to return

        Returns:
            List of audit records as dicts
        """
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute(
                    """
                    SELECT * FROM execution_audit
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get audits: {e}")
            return []

    def clear_cache(self) -> int:
        """
        Clear the idempotency cache.

        Returns:
            Number of entries cleared
        """
        count = len(self._idempotency_cache)
        self._idempotency_cache.clear()
        logger.info(f"Cleared {count} entries from idempotency cache")
        return count