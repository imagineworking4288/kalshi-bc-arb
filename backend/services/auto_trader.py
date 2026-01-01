"""
Auto-Trader Service
Automatically executes trades based on signals from EdgeDetector.
"""

import asyncio
import logging
from datetime import datetime, date
from typing import Optional, List
from .edge_detector import EdgeDetector, TradingSignal

logger = logging.getLogger(__name__)


class AutoTrader:
    """Automated trading execution with risk management."""

    def __init__(self, kalshi_client, db):
        self.kalshi = kalshi_client
        self.db = db
        self.edge_detector = EdgeDetector(kalshi_client, db)

        # Configuration (loaded from DB)
        self.enabled = 0  # 0=off, 1=paper, 2=live
        self.min_edge = 10.0
        self.max_position_size = 100
        self.max_daily_loss = 10000  # cents
        self.max_open_positions = 10
        self.allowed_series = ['KXBTC', 'KXBTCD']

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
        """Process a single trading signal."""
        logger.info(f"  Signal: {signal.ticker} {signal.signal_type} "
                    f"edge={signal.edge_percent:.1f}% model={signal.model_prob:.1%}")

        # Check if we already have a position in this market
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

        # Parse signal type
        side = 'yes' if 'yes' in signal.signal_type else 'no'
        action = 'buy'  # Currently only buy signals

        # Execute order
        try:
            # Determine execution mode
            use_paper = (self.enabled == 1)
            use_live = (self.enabled == 2)

            if use_paper:
                result = await self._execute_paper_trade(signal.ticker, side, action, size, signal.market_price)
            else:
                result = await self._execute_live_trade(signal.ticker, side, action, size, signal.market_price)

            if result.get('success'):
                logger.info(f"    EXECUTED: {size} contracts @ {signal.market_price}¢ (mode={'paper' if use_paper else 'live'})")
                await self._update_signal_status(signal_id, 'executed', signal.market_price)
            else:
                logger.warning(f"    FAILED: {result.get('error', 'Unknown error')}")
                await self._update_signal_status(signal_id, 'rejected')

        except Exception as e:
            logger.error(f"    ERROR executing trade: {e}", exc_info=True)
            await self._update_signal_status(signal_id, 'rejected')

    async def _execute_paper_trade(self, ticker: str, side: str, action: str, count: int, price_cents: int) -> dict:
        """Execute a paper trade."""
        import uuid
        from .fee_calculator import calculate_fee

        try:
            async with self.db.connection() as conn:
                # Get paper account balance
                cursor = await conn.execute("SELECT balance FROM paper_account WHERE id = 1")
                balance_row = await cursor.fetchone()

                if not balance_row:
                    return {"success": False, "error": "Paper account not initialized"}

                # Calculate cost
                price_dollars = price_cents / 100
                total_cost = count * price_dollars
                total_fees = calculate_fee(count, price_dollars)
                total_debit = total_cost + total_fees

                current_balance = balance_row[0]
                if current_balance < total_debit:
                    return {
                        "success": False,
                        "error": f"Insufficient balance: ${current_balance:.2f} < ${total_debit:.2f}"
                    }

                # Record order
                order_id = str(uuid.uuid4())
                now = datetime.now().isoformat()
                await conn.execute(
                    """INSERT INTO manual_orders
                       (id, created_at, ticker, side, action, count, price_cents, mode, status,
                        filled_count, avg_fill_price, total_cost, total_fees, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (order_id, now, ticker, side, action, count,
                     price_cents, "paper", "filled", count, price_dollars,
                     total_cost, total_fees, now)
                )

                # Create position
                position_id = str(uuid.uuid4())
                await conn.execute(
                    """INSERT INTO paper_positions
                       (id, created_at, ticker, side, contracts, avg_price, total_cost, total_fees,
                        settlement_time, settled, trade_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (position_id, now, ticker, side, count, price_dollars,
                     total_cost, total_fees, now, 0, order_id)
                )

                # Update balance
                new_balance = current_balance - total_debit
                await conn.execute(
                    "UPDATE paper_account SET balance = ?, updated_at = ? WHERE id = 1",
                    (new_balance, now)
                )

                await conn.commit()

                return {
                    "success": True,
                    "order_id": order_id,
                    "position_id": position_id,
                    "total_cost": total_cost,
                    "total_fees": total_fees
                }

        except Exception as e:
            logger.error(f"Error executing paper trade: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _execute_live_trade(self, ticker: str, side: str, action: str, count: int, price_cents: int) -> dict:
        """Execute a live trade via Kalshi API."""
        import uuid

        try:
            kalshi_result = await self.kalshi.place_order(
                ticker=ticker,
                side=side,
                action=action,
                count=count,
                price=price_cents
            )

            # Parse Kalshi response
            order = kalshi_result.get("order", {})
            kalshi_order_id = order.get("order_id")
            filled_count = order.get("yes_count", 0) if side == 'yes' else order.get("no_count", 0)
            status = order.get("status", "pending")

            # Record order in database
            order_id = str(uuid.uuid4())
            now = datetime.now().isoformat()

            async with self.db.connection() as conn:
                await conn.execute(
                    """INSERT INTO manual_orders
                       (id, created_at, ticker, side, action, count, price_cents, mode, status,
                        filled_count, kalshi_order_id, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (order_id, now, ticker, side, action, count,
                     price_cents, "live", status, filled_count, kalshi_order_id, now)
                )
                await conn.commit()

            return {
                "success": status == "resting" or status == "filled",
                "order_id": order_id,
                "kalshi_order_id": kalshi_order_id,
                "status": status,
                "filled_count": filled_count
            }

        except Exception as e:
            logger.error(f"Error executing live trade: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    async def _has_position(self, ticker: str) -> bool:
        """Check if we already have a position in this market."""
        async with self.db.connection() as conn:
            # Check paper positions
            cursor = await conn.execute(
                "SELECT 1 FROM paper_positions WHERE ticker = ? AND contracts > 0 AND settled = 0",
                (ticker,)
            )
            if await cursor.fetchone():
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
                                     execution_price: int = None):
        """Update signal status in database."""
        async with self.db.connection() as conn:
            if execution_price:
                await conn.execute("""
                    UPDATE trading_signals
                    SET status = ?, executed_at = CURRENT_TIMESTAMP, execution_price = ?
                    WHERE id = ?
                """, (status, execution_price, signal_id))
            else:
                await conn.execute(
                    "UPDATE trading_signals SET status = ? WHERE id = ?",
                    (status, signal_id)
                )
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
                        'max_daily_loss_cents', 'max_open_positions', 'allowed_series']

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
