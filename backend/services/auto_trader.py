"""
Auto-Trader Service
Automatically executes trades based on signals from EdgeDetector.
"""

import asyncio
from datetime import datetime, date
from typing import Optional, List, Set
from .edge_detector import EdgeDetector, TradingSignal
from .execution.atomic_executor import AtomicExecutor, ExecutionResult
from .log_config import get_logger

logger = get_logger("auto_trader")


class AutoTrader:
    """Automated trading execution with risk management."""

    def __init__(self, kalshi_client, db, executor: AtomicExecutor = None):
        self.kalshi = kalshi_client
        self.db = db
        self.executor = executor  # Will be injected from main.py
        self.edge_detector = EdgeDetector(kalshi_client, db)

        # Configuration (loaded from DB)
        self.enabled = 0  # 0=off, 1=paper, 2=live
        self.min_edge = 10.0
        self.max_position_size = 100
        self.max_daily_loss = 10000  # cents
        self.max_open_positions = 10
        self.allowed_series = ['KXBTC', 'KXBTCD']
        self.mode = 'paper'  # 'paper' or 'live'

        # Temporary position cache (placeholder for Phase 2 PositionManager)
        self._position_cache: Set[str] = set()

        # Runtime state
        self.is_running = False
        self._task: Optional[asyncio.Task] = None

    async def load_config(self):
        """Load configuration from database."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM auto_trader_config WHERE id = 1"
            )
            row = await cursor.fetchone()
            if row:
                columns = [d[0] for d in cursor.description]
                config = dict(zip(columns, row))
                self.enabled = config.get('enabled', 0)
                self.min_edge = config.get('min_edge_percent', 10.0)
                self.max_position_size = config.get('max_position_size', 100)
                self.max_daily_loss = config.get('max_daily_loss_cents', 10000)
                self.max_open_positions = config.get('max_open_positions', 10)
                series = config.get('allowed_series', 'KXBTC,KXBTCD')
                self.allowed_series = [s.strip() for s in series.split(',')]
                # Set mode based on enabled flag
                self.mode = 'paper' if self.enabled == 1 else 'live'

        await self.edge_detector.load_config()

    async def start(self):
        """Start the auto-trader background loop."""
        if self.is_running:
            logger.warning("AutoTrader already running")
            return

        await self.load_config()
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"AutoTrader started (mode: {self._mode_name()})")

    async def stop(self):
        """Stop the auto-trader."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("AutoTrader stopped")

    def _mode_name(self) -> str:
        return {0: 'DISABLED', 1: 'PAPER ONLY', 2: 'LIVE ENABLED'}[self.enabled]

    async def _run_loop(self):
        """Main trading loop - runs every 60 seconds."""
        while self.is_running:
            try:
                if self.enabled > 0:
                    await self._scan_and_trade()
            except Exception as e:
                logger.error(f"AutoTrader error in main loop: {e}", exc_info=True)

            await asyncio.sleep(60)  # Scan every minute

    async def _scan_and_trade(self):
        """Scan for edges and execute trades."""
        logger.info(f"[{datetime.now().strftime('%H:%M:%S')}] Scanning for edges...")

        # Risk check: daily loss limit
        if await self._daily_loss_exceeded():
            logger.warning("Daily loss limit reached - skipping scan")
            return

        # Scan BTC markets
        signals = await self.edge_detector.scan_btc_markets()

        if not signals:
            logger.info("No edges found")
            return

        logger.info(f"Found {len(signals)} signals with edge >= {self.min_edge}%")

        # Process each signal
        for signal in signals:
            await self._process_signal(signal)

    async def _process_signal(self, signal: TradingSignal):
        """Process single trading signal through AtomicExecutor."""
        logger.info(f"  Signal: {signal.ticker} {signal.signal_type} "
                    f"edge={signal.edge_percent:.1f}% model={signal.model_prob:.1%}")

        # Check if we already have position (will use PositionManager in Phase 2)
        if await self._has_position(signal.ticker):
            logger.info(f"    Skipping - already have position")
            return

        # Check position count limit
        if await self._position_count() >= self.max_open_positions:
            logger.info(f"    Skipping - max positions reached ({self.max_open_positions})")
            return

        # Save signal to database
        signal_id = await self.edge_detector.save_signal(signal)

        # Execute trade based on mode
        if self.enabled == 0:
            logger.info(f"    Signal saved but auto-trading disabled")
            return

        # Calculate size (respect limits)
        size = min(signal.recommended_size, self.max_position_size)

        # Parse signal type (e.g., 'buy_yes', 'buy_no')
        parts = signal.signal_type.split('_')
        action = parts[0] if parts else 'buy'  # 'buy' or 'sell'
        side = parts[1] if len(parts) > 1 else 'yes'  # 'yes' or 'no'

        # Execute through AtomicExecutor
        try:
            if not self.executor:
                logger.error("No executor configured - cannot execute trades")
                return

            mode = 'paper' if self.enabled == 1 else 'live'
            result: ExecutionResult = await self.executor.execute_single(
                ticker=signal.ticker,
                side=side,
                action=action,
                quantity=size,
                price_cents=signal.market_price,
                mode=mode
            )

            if result.success:
                # Update position cache
                self._position_cache.add(signal.ticker)

                fill_price = result.legs[0].fill_price if result.legs else signal.market_price
                logger.info(f"    EXECUTED: {size} contracts @ {fill_price}c (mode={mode})")
                await self._update_signal_status(signal_id, 'executed', fill_price)
            else:
                error_msg = ', '.join(result.errors) if result.errors else 'Unknown error'
                logger.warning(f"    FAILED: {error_msg}")
                await self._update_signal_status(signal_id, 'rejected', notes=error_msg)

        except Exception as e:
            logger.error(f"    ERROR executing trade: {e}", exc_info=True)
            await self._update_signal_status(signal_id, 'rejected', notes=str(e))

    async def _has_position(self, ticker: str) -> bool:
        """Check if we already have a position. Will use PositionManager in Phase 2."""
        # Check local cache first
        if ticker in self._position_cache:
            return True

        # Fall back to DB check
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM paper_positions WHERE ticker = ? AND contracts > 0 AND settled = 0",
                (ticker,)
            )
            if await cursor.fetchone():
                self._position_cache.add(ticker)  # Cache it
                return True
        return False

    async def _position_count(self) -> int:
        """Count total open positions."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM paper_positions WHERE contracts > 0 AND settled = 0"
            )
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def _daily_loss_exceeded(self) -> bool:
        """Check if daily loss limit has been exceeded."""
        today = date.today().isoformat()
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT realized_pnl_cents FROM daily_pnl WHERE date = ?",
                (today,)
            )
            row = await cursor.fetchone()
            if row and row[0] < -self.max_daily_loss:
                return True
        return False

    async def _update_signal_status(self, signal_id: int, status: str,
                                     execution_price: int = None, notes: str = None):
        """Update signal status in database."""
        async with self.db.connection() as conn:
            if execution_price:
                await conn.execute("""
                    UPDATE trading_signals
                    SET status = ?, executed_at = CURRENT_TIMESTAMP,
                        execution_price = ?, notes = ?
                    WHERE id = ?
                """, (status, execution_price, notes, signal_id))
            else:
                await conn.execute("""
                    UPDATE trading_signals
                    SET status = ?, notes = ?
                    WHERE id = ?
                """, (status, notes, signal_id))
            await conn.commit()

    async def get_status(self) -> dict:
        """Get current auto-trader status."""
        return {
            'enabled': self.enabled,
            'mode': self._mode_name(),
            'is_running': self.is_running,
            'min_edge': self.min_edge,
            'max_position_size': self.max_position_size,
            'max_daily_loss_cents': self.max_daily_loss,
            'max_open_positions': self.max_open_positions,
            'allowed_series': self.allowed_series
        }

    async def update_config(self, **kwargs) -> dict:
        """Update auto-trader configuration."""
        valid_fields = ['enabled', 'min_edge_percent', 'max_position_size',
                        'max_daily_loss_cents', 'max_open_positions', 'allowed_series', 'mode']

        updates = {k: v for k, v in kwargs.items() if k in valid_fields}
        if not updates:
            return {'success': False, 'error': 'No valid fields to update'}

        # Build SQL
        set_clause = ', '.join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [1]  # + id

        async with self.db.connection() as conn:
            await conn.execute(
                f"UPDATE auto_trader_config SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values
            )
            await conn.commit()

        await self.load_config()
        return {'success': True, 'config': await self.get_status()}

    async def manual_scan(self) -> list:
        """Manually trigger a scan and return signals without executing."""
        await self.load_config()
        signals = await self.edge_detector.scan_btc_markets()
        return [
            {
                'ticker': s.ticker,
                'signal_type': s.signal_type,
                'edge_percent': s.edge_percent,
                'model_prob': s.model_prob,
                'market_price': s.market_price,
                'recommended_size': s.recommended_size,
                'source': s.source,
                'notes': s.notes
            }
            for s in signals
        ]
