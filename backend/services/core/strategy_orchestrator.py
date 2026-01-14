"""
Strategy orchestrator - main trading engine.
Coordinates all strategies, manages execution pipeline, and controls trading.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from .base_strategy import BaseStrategy, TradingSignal, StrategyType, SignalStatus
from .signal_manager import SignalManager
from .kelly_sizing import KellySizing, KellyConfig
from .risk_manager import RiskManager, RiskLimits
from .circuit_breaker import CircuitBreaker, CBConfig
from .batch_executor import BatchExecutor, OrderLeg, OrderSide, OrderAction
from .performance_tracker import PerformanceTracker
from .alert_service import AlertService

from ..log_config import get_logger

logger = get_logger("strategy_orchestrator")


class StrategyOrchestrator:
    """
    Main trading engine that orchestrates all strategies.

    Responsibilities:
    - Register and manage trading strategies
    - Run strategy scan loops
    - Process signals through the execution pipeline:
      1. Validate signal
      2. Calculate position size (Kelly)
      3. Check risk limits
      4. Check circuit breaker
      5. Execute trade
      6. Record performance
      7. Send alerts
    - Provide status and control endpoints
    """

    def __init__(
        self,
        db,
        signals: SignalManager,
        kelly: KellySizing,
        risk: RiskManager,
        circuit: CircuitBreaker,
        executor: BatchExecutor,
        performance: PerformanceTracker,
        alerts: AlertService
    ):
        """
        Initialize the orchestrator with all core components.

        Args:
            db: Database connection
            signals: Signal manager
            kelly: Kelly sizing calculator
            risk: Risk manager
            circuit: Circuit breaker
            executor: Batch order executor
            performance: Performance tracker
            alerts: Alert service
        """
        self.db = db
        self.signals = signals
        self.kelly = kelly
        self.risk = risk
        self.circuit = circuit
        self.executor = executor
        self.performance = performance
        self.alerts = alerts

        # Strategy registry
        self._strategies: Dict[StrategyType, BaseStrategy] = {}

        # Configuration
        self._auto_trade_enabled: bool = False
        self._mode: str = "paper"  # "paper" or "live"

        # State
        self._is_running: bool = False
        self._scan_tasks: Dict[StrategyType, asyncio.Task] = {}
        self._processor_task: Optional[asyncio.Task] = None

        # Stats
        self._signals_processed: int = 0
        self._trades_executed: int = 0
        self._start_time: Optional[datetime] = None

        # Lock for thread safety
        self._lock = asyncio.Lock()

    def register(self, strategy: BaseStrategy) -> None:
        """
        Register a trading strategy.

        Args:
            strategy: Strategy instance to register
        """
        self._strategies[strategy.strategy_type] = strategy
        logger.info(f"Registered strategy: {strategy.name} ({strategy.strategy_type.value})")

    def unregister(self, strategy_type: StrategyType) -> bool:
        """
        Unregister a strategy.

        Args:
            strategy_type: Type of strategy to unregister

        Returns:
            True if unregistered, False if not found
        """
        if strategy_type in self._strategies:
            del self._strategies[strategy_type]
            logger.info(f"Unregistered strategy: {strategy_type.value}")
            return True
        return False

    async def start(self) -> None:
        """Start the orchestrator and all enabled strategies."""
        async with self._lock:
            if self._is_running:
                logger.warning("Orchestrator already running")
                return

            self._is_running = True
            self._start_time = datetime.now(timezone.utc)

            # Start scan loops for enabled strategies
            for strategy_type, strategy in self._strategies.items():
                if strategy.enabled:
                    task = asyncio.create_task(self._run_strategy(strategy))
                    self._scan_tasks[strategy_type] = task
                    logger.info(f"Started scan loop for {strategy.name}")

            # Start signal processor
            self._processor_task = asyncio.create_task(self._process_signals_loop())

            logger.info("Orchestrator started")
            await self.alerts.info("Orchestrator Started", "Trading engine is now running")

    async def stop(self) -> None:
        """Stop the orchestrator and all running tasks."""
        async with self._lock:
            if not self._is_running:
                return

            self._is_running = False

            # Cancel all scan tasks
            for strategy_type, task in self._scan_tasks.items():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

            self._scan_tasks.clear()

            # Cancel processor
            if self._processor_task:
                self._processor_task.cancel()
                try:
                    await self._processor_task
                except asyncio.CancelledError:
                    pass
                self._processor_task = None

            logger.info("Orchestrator stopped")
            await self.alerts.info("Orchestrator Stopped", "Trading engine has stopped")

    async def _run_strategy(self, strategy: BaseStrategy) -> None:
        """
        Run the scan loop for a single strategy.

        Args:
            strategy: Strategy to run
        """
        while self._is_running and strategy.enabled:
            try:
                # Run scan
                signals = await strategy.run_scan()

                # Store non-duplicate signals
                for signal in signals:
                    # Check for recent duplicates
                    has_recent = await self.signals.has_recent(
                        signal.ticker,
                        signal.strategy_type
                    )

                    if not has_recent:
                        await self.signals.create(signal)
                        await self.alerts.opportunity(
                            signal.ticker,
                            signal.edge_percent,
                            strategy.name
                        )

                # Wait for next scan
                await asyncio.sleep(strategy.scan_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in {strategy.name} scan: {e}")
                strategy.last_error = str(e)
                await asyncio.sleep(5)  # Back off on error

    async def _process_signals_loop(self) -> None:
        """Process pending signals continuously."""
        while self._is_running:
            try:
                # Expire old signals
                await self.signals.expire_old()

                # Process pending signals if auto-trade is enabled
                if self._auto_trade_enabled:
                    await self._process_pending_signals()

                await asyncio.sleep(1)  # Check every second

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in signal processor: {e}")
                await asyncio.sleep(5)

    async def _process_pending_signals(self) -> None:
        """Process all pending signals through the execution pipeline."""
        pending = await self.signals.get_pending()

        for signal in pending:
            try:
                result = await self._execute_signal(signal)
                self._signals_processed += 1

                if result:
                    self._trades_executed += 1

            except Exception as e:
                logger.error(f"Error executing signal {signal.id}: {e}")
                await self.signals.update_status(
                    signal.id,
                    SignalStatus.FAILED,
                    notes=str(e)
                )

    async def _execute_signal(self, signal: TradingSignal) -> bool:
        """
        Execute a single signal through the pipeline.

        Pipeline steps:
        1. Validate signal (re-check with strategy)
        2. Calculate position size (Kelly)
        3. Check risk limits
        4. Check circuit breaker
        5. Execute trade
        6. Record performance
        7. Send alerts

        Args:
            signal: Signal to execute

        Returns:
            True if trade was executed successfully
        """
        # Mark as executing
        await self.signals.update_status(signal.id, SignalStatus.EXECUTING)

        # Step 1: Validate signal with strategy
        strategy = self._strategies.get(signal.strategy_type)
        if not strategy:
            await self.signals.update_status(
                signal.id,
                SignalStatus.REJECTED,
                notes="Strategy not registered"
            )
            return False

        if not await strategy.validate_signal(signal):
            await self.signals.update_status(
                signal.id,
                SignalStatus.REJECTED,
                notes="Signal validation failed"
            )
            return False

        # Step 2: Calculate position size
        if signal.is_arbitrage:
            # For arbitrage, use the signal's recommended size or calculate based on cost
            contracts = signal.recommended_size
        else:
            # Get actual balance for Kelly calculation
            balance_cents = await self._get_balance_cents()

            kelly_result = self.kelly.calculate(
                signal.model_prob,
                signal.market_price,
                balance_cents
            )

            if kelly_result.contracts == 0:
                await self.signals.update_status(
                    signal.id,
                    SignalStatus.REJECTED,
                    notes=kelly_result.reason
                )
                return False

            contracts = kelly_result.contracts

        # Step 3: Check risk limits
        balance_cents = await self._get_balance_cents()
        risk_check = await self.risk.check_trade(
            signal.ticker,
            contracts,
            signal.market_price,
            balance_cents
        )

        if not risk_check.approved:
            await self.signals.update_status(
                signal.id,
                SignalStatus.REJECTED,
                notes=risk_check.reason
            )
            await self.alerts.risk_warning("Trade Blocked", risk_check.reason)
            return False

        # Use adjusted size if provided
        if risk_check.adjusted_size:
            contracts = risk_check.adjusted_size

        # Step 4: Check circuit breaker
        can_trade, cb_reason = await self.circuit.can_trade()
        if not can_trade:
            await self.signals.update_status(
                signal.id,
                SignalStatus.REJECTED,
                notes=cb_reason
            )
            return False

        # Step 5: Execute trade
        if signal.is_arbitrage and signal.legs:
            # Arbitrage: execute multiple legs
            legs_data = [
                {
                    "ticker": leg.ticker,
                    "side": leg.side,
                    "action": leg.action,
                    "price_cents": leg.price_cents
                }
                for leg in signal.legs
            ]
            result = await self.executor.execute_arbitrage(
                legs_data,
                contracts,
                self._mode
            )
        else:
            # Single leg trade
            result = await self.executor.execute_single(
                signal.ticker,
                "yes",  # Default to YES side
                "buy",
                contracts,
                signal.market_price,
                self._mode
            )

        if not result.success:
            await self.signals.update_status(
                signal.id,
                SignalStatus.FAILED,
                notes=result.message
            )
            await self.alerts.trade_failed(signal.ticker, result.message)

            # Record loss for circuit breaker
            await self.circuit.record_result(False, 0, signal.ticker)

            return False

        # Step 6: Record performance
        trade_id = await self.performance.record_trade(
            signal.strategy_type.value,
            signal.ticker,
            "yes",
            contracts,
            signal.market_price,
            result.total_fees_cents
        )

        # Step 7: Update signal status
        await self.signals.update_status(
            signal.id,
            SignalStatus.EXECUTED,
            execution_price=signal.market_price
        )

        # Step 8: Record trade in risk manager
        await self.risk.record_trade(
            signal.ticker,
            contracts,
            signal.market_price
        )

        # Step 9: Send alert
        await self.alerts.trade_executed(
            signal.ticker,
            contracts,
            signal.market_price,
            0,  # PnL unknown until settlement
            self._mode,
            {"signal_id": signal.id, "trade_id": trade_id}
        )

        logger.info(
            f"Executed signal {signal.id[:8]}: "
            f"{signal.ticker} x{contracts} @ {signal.market_price}¢"
        )

        return True

    # Control methods

    def enable_strategy(self, strategy_type: StrategyType, enabled: bool = True) -> bool:
        """
        Enable or disable a strategy.

        Args:
            strategy_type: Strategy to enable/disable
            enabled: Whether to enable

        Returns:
            True if strategy found and updated
        """
        if strategy_type not in self._strategies:
            return False

        strategy = self._strategies[strategy_type]
        strategy.enabled = enabled

        # Start/stop scan task
        if self._is_running:
            if enabled and strategy_type not in self._scan_tasks:
                task = asyncio.create_task(self._run_strategy(strategy))
                self._scan_tasks[strategy_type] = task
            elif not enabled and strategy_type in self._scan_tasks:
                self._scan_tasks[strategy_type].cancel()
                del self._scan_tasks[strategy_type]

        logger.info(f"Strategy {strategy.name} enabled={enabled}")
        return True

    def set_auto_trade(self, enabled: bool) -> None:
        """Set auto-trade mode."""
        self._auto_trade_enabled = enabled
        logger.info(f"Auto-trade set to {enabled}")

    def set_mode(self, mode: str) -> None:
        """
        Set trading mode.

        Args:
            mode: "paper" or "live"
        """
        if mode in ("paper", "live"):
            self._mode = mode
            logger.info(f"Trading mode set to {mode}")

    def get_status(self) -> Dict:
        """Get complete orchestrator status."""
        uptime = None
        if self._start_time:
            uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        return {
            "is_running": self._is_running,
            "auto_trade_enabled": self._auto_trade_enabled,
            "mode": self._mode,
            "uptime_seconds": uptime,
            "strategies": {
                st.value: s.get_status()
                for st, s in self._strategies.items()
            },
            "stats": {
                "signals_processed": self._signals_processed,
                "trades_executed": self._trades_executed,
                "active_scan_tasks": len(self._scan_tasks)
            },
            "components": {
                "circuit_breaker": self.circuit.get_status(),
                "risk": self.risk.get_status()
            }
        }

    async def manual_scan(self, strategy_type: Optional[StrategyType] = None) -> List[Dict]:
        """
        Manually trigger a scan.

        Args:
            strategy_type: Specific strategy to scan (all if None)

        Returns:
            List of signals found
        """
        all_signals = []

        strategies = (
            [self._strategies[strategy_type]]
            if strategy_type and strategy_type in self._strategies
            else list(self._strategies.values())
        )

        for strategy in strategies:
            try:
                signals = await strategy.run_scan()
                for signal in signals:
                    await self.signals.create(signal)
                    all_signals.append(signal.to_dict())
            except Exception as e:
                logger.error(f"Manual scan error for {strategy.name}: {e}")

        return all_signals

    async def manual_execute(self, signal_id: str) -> Dict:
        """
        Manually execute a specific signal.

        Args:
            signal_id: ID of signal to execute

        Returns:
            Execution result
        """
        signal = await self.signals.get_by_id(signal_id)
        if not signal:
            return {"success": False, "error": "Signal not found"}

        if signal.status != SignalStatus.PENDING:
            return {"success": False, "error": f"Signal status is {signal.status.value}"}

        result = await self._execute_signal(signal)
        return {
            "success": result,
            "signal_id": signal_id
        }

    async def load_config(self) -> None:
        """Load orchestrator config from database."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM orchestrator_config WHERE id = 1"
            )
            row = await cursor.fetchone()

            if row:
                # Convert Row to dict for safe .get() access
                row_dict = dict(row) if row else {}
                self._auto_trade_enabled = bool(row_dict.get("auto_trade_enabled", 0))
                self._mode = row_dict.get("mode", "paper")
                self.kelly.config.fraction = row_dict.get("kelly_fraction", 0.25)
                self.kelly.config.min_edge_percent = row_dict.get("min_edge_percent", 5.0)
                self.risk.limits.max_position_per_market = row_dict.get("max_position_per_market", 100)
                self.risk.limits.max_daily_loss_cents = row_dict.get("max_daily_loss_cents", 5000)
                self.circuit.config.max_consecutive_losses = row_dict.get("cb_max_consecutive_losses", 5)

                logger.info("Loaded orchestrator config from database")

    async def save_config(self) -> None:
        """Save orchestrator config to database."""
        async with self.db.connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO orchestrator_config (
                    id, auto_trade_enabled, mode, kelly_fraction,
                    min_edge_percent, max_position_per_market,
                    max_daily_loss_cents, cb_max_consecutive_losses,
                    updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                1 if self._auto_trade_enabled else 0,
                self._mode,
                self.kelly.config.fraction,
                self.kelly.config.min_edge_percent,
                self.risk.limits.max_position_per_market,
                self.risk.limits.max_daily_loss_cents,
                self.circuit.config.max_consecutive_losses,
                datetime.now(timezone.utc).isoformat()
            ))
            await conn.commit()
            logger.info("Saved orchestrator config to database")

    async def _get_balance_cents(self) -> int:
        """
        Get current account balance in cents.

        Fetches from paper service (paper mode) or executor (live mode).
        Falls back to 100000 cents ($1000) on error.

        Returns:
            Balance in cents
        """
        try:
            # Try to get balance from executor's paper service
            if hasattr(self.executor, 'paper_service') and self.executor.paper_service:
                balance_info = await self.executor.paper_service.get_balance()
                # Paper service returns dollars, convert to cents
                return int(balance_info.get("available_balance", 0) * 100)

            # Try to get balance from executor's kalshi client (live mode)
            if hasattr(self.executor, 'kalshi_client') and self.executor.kalshi_client:
                balance_info = await self.executor.kalshi_client.get_balance()
                # Kalshi returns cents
                return int(balance_info.get("available_balance", 0))

        except Exception as e:
            logger.warning(f"Failed to get balance: {e}")

        # Fallback to default
        logger.warning("Using fallback balance of $1000 (100000 cents)")
        return 100000
