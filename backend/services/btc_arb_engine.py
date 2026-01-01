"""
BTC Arbitrage Engine
Runs continuous scanning and auto-execution in background.
"""

import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
import time

from .btc_arb_scanner import BTCArbitrageScanner, ArbOpportunity
from ..utils.logger import btc_arb_logger as logger, btc_arb_activity


@dataclass
class EngineConfig:
    """Engine configuration."""
    min_edge_percent: float = 3.0
    budget_cents: int = 10000  # $100
    auto_trade_enabled: bool = False
    mode: str = 'paper'  # 'paper' or 'live'
    scan_interval_seconds: float = 2.0
    max_position_per_opp_cents: int = 50000  # $500 max


@dataclass
class EngineStatus:
    """Current engine status."""
    is_running: bool = False
    last_scan_at: Optional[str] = None
    last_scan_duration_ms: int = 0
    total_scans: int = 0
    opportunities_found: int = 0
    auto_executions: int = 0
    last_error: Optional[str] = None


class BTCArbitrageEngine:
    """
    Continuous arbitrage scanning and execution engine.
    Runs in background, constantly scanning for opportunities.
    When auto_trade is enabled, executes immediately on finding edges.
    """

    def __init__(self, kalshi_client, db):
        self.kalshi = kalshi_client
        self.db = db
        self.scanner = BTCArbitrageScanner(kalshi_client)

        self.config = EngineConfig()
        self.status = EngineStatus()

        self._opportunities: List[ArbOpportunity] = []
        self._opportunities_lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the engine."""
        if self.status.is_running:
            return

        await self._load_config()
        await self._ensure_config_exists()
        self.status.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"🚀 Engine started - scanning every {self.config.scan_interval_seconds}s")

    async def stop(self):
        """Stop the engine."""
        self.status.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Engine stopped")

    async def _ensure_config_exists(self):
        """Ensure config row exists in database."""
        try:
            async with self.db.connection() as conn:
                await conn.execute("""
                    INSERT OR IGNORE INTO btc_arb_config (id) VALUES (1)
                """)
                await conn.commit()
        except Exception as e:
            logger.error(f"❌ Error ensuring config: {e}")

    async def _load_config(self):
        """Load config from database."""
        try:
            async with self.db.connection() as conn:
                cursor = await conn.execute("SELECT * FROM btc_arb_config WHERE id = 1")
                row = await cursor.fetchone()
                if row:
                    columns = [d[0] for d in cursor.description]
                    cfg = dict(zip(columns, row))
                    self.config.min_edge_percent = cfg.get('min_edge_percent', 3.0)
                    self.config.budget_cents = cfg.get('default_budget_cents', 10000)
                    self.config.auto_trade_enabled = bool(cfg.get('auto_trade_enabled', 0))
                    self.config.scan_interval_seconds = cfg.get('scan_interval_seconds', 2.0)
                    self.config.max_position_per_opp_cents = cfg.get('max_position_per_opp_cents', 50000)
                    self.config.mode = cfg.get('mode', 'paper')
        except Exception as e:
            logger.error(f"❌ Config load error: {e}")

    async def _save_config(self):
        """Save config to database."""
        try:
            async with self.db.connection() as conn:
                await conn.execute("""
                    INSERT INTO btc_arb_config (id, min_edge_percent, default_budget_cents, auto_trade_enabled, scan_interval_seconds, max_position_per_opp_cents, mode, updated_at)
                    VALUES (1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        min_edge_percent = excluded.min_edge_percent,
                        default_budget_cents = excluded.default_budget_cents,
                        auto_trade_enabled = excluded.auto_trade_enabled,
                        scan_interval_seconds = excluded.scan_interval_seconds,
                        max_position_per_opp_cents = excluded.max_position_per_opp_cents,
                        mode = excluded.mode,
                        updated_at = CURRENT_TIMESTAMP
                """, (
                    self.config.min_edge_percent,
                    self.config.budget_cents,
                    1 if self.config.auto_trade_enabled else 0,
                    self.config.scan_interval_seconds,
                    self.config.max_position_per_opp_cents,
                    self.config.mode
                ))
                await conn.commit()
        except Exception as e:
            logger.error(f"❌ Config save error: {e}")

    async def _run_loop(self):
        """Main scanning loop."""
        while self.status.is_running:
            try:
                await self._scan_cycle()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.status.last_error = str(e)
                logger.error(f"❌ Scan cycle error: {e}")

            await asyncio.sleep(self.config.scan_interval_seconds)

    async def _scan_cycle(self):
        """Single scan cycle."""
        start = time.time()

        # Scan for opportunities
        opportunities = await self.scanner.scan(self.config.min_edge_percent)

        # Update status
        self.status.last_scan_at = datetime.utcnow().isoformat() + 'Z'
        self.status.last_scan_duration_ms = int((time.time() - start) * 1000)
        self.status.total_scans += 1
        self.status.opportunities_found = len(opportunities)

        # Store opportunities for UI access
        async with self._opportunities_lock:
            self._opportunities = opportunities

        # Auto-execute if enabled and opportunities exist
        if self.config.auto_trade_enabled and opportunities:
            best_opp = opportunities[0]
            if best_opp.edge_percent >= self.config.min_edge_percent:
                await self._auto_execute(best_opp)

    async def _auto_execute(self, opportunity: ArbOpportunity):
        """Auto-execute an opportunity."""
        logger.info(f"💰 Auto-executing: {opportunity.range_description} ({opportunity.edge_percent:.1f}% edge)")

        try:
            trade_calc = self.scanner.calculate_trade(
                opportunity,
                min(self.config.budget_cents, self.config.max_position_per_opp_cents)
            )

            if 'error' in trade_calc:
                logger.warning(f"⚠️ Calc error: {trade_calc['error']}")
                return

            result = await self._execute_trade(opportunity, trade_calc)

            if result.get('success'):
                self.status.auto_executions += 1
                logger.info(f"✅ Executed! Profit: ${trade_calc['guaranteed_profit_cents']/100:.2f}")

                # Disable auto-trade after execution (prevent rapid-fire)
                self.config.auto_trade_enabled = False
                await self._save_config()

        except Exception as e:
            logger.error(f"❌ Execution error: {e}")

    async def _execute_trade(self, opportunity: ArbOpportunity, trade_calc: Dict) -> Dict:
        """Execute a trade (paper or live)."""
        contracts = trade_calc['contracts_per_leg']
        execution_id = str(uuid.uuid4())

        if self.config.mode == 'paper':
            return await self._execute_paper(opportunity, contracts, trade_calc, execution_id)
        else:
            return await self._execute_live(opportunity, contracts, trade_calc, execution_id)

    async def _execute_paper(self, opp: ArbOpportunity, contracts: int, calc: Dict, exec_id: str) -> Dict:
        """Execute paper trade."""
        total_with_fees = calc['total_cost_cents'] + calc['total_fees_cents']

        try:
            async with self.db.connection() as conn:
                # Check balance
                cursor = await conn.execute("SELECT balance FROM paper_account WHERE id = 1")
                row = await cursor.fetchone()
                balance_cents = int((row[0] if row else 0) * 100)

                if balance_cents < total_with_fees:
                    return {'success': False, 'error': 'Insufficient balance'}

                # Deduct balance
                new_balance = (balance_cents - total_with_fees) / 100
                await conn.execute(
                    "UPDATE paper_account SET balance = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                    (new_balance,)
                )

                # Record positions for each leg
                for leg in opp.legs:
                    pos_id = str(uuid.uuid4())
                    await conn.execute("""
                        INSERT INTO paper_positions
                        (id, created_at, ticker, side, contracts, avg_price, total_cost, total_fees, settlement_time, trade_id)
                        VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        pos_id, leg.ticker, leg.side, contracts,
                        leg.price_cents / 100,
                        contracts * leg.price_cents / 100,
                        calc['total_fees_cents'] / 300,  # Split fees across 3 legs
                        opp.settlement_time, exec_id
                    ))

                # Record execution
                await conn.execute("""
                    INSERT INTO btc_arb_executions
                    (id, opportunity_id, mode, contracts_per_leg, total_cost_cents, total_fees_cents, guaranteed_profit_cents, status)
                    VALUES (?, ?, 'paper', ?, ?, ?, ?, 'open')
                """, (exec_id, opp.id, contracts, calc['total_cost_cents'], calc['total_fees_cents'], calc['guaranteed_profit_cents']))

                await conn.commit()

            return {
                'success': True,
                'execution_id': exec_id,
                'mode': 'paper',
                'contracts': contracts,
                'profit_cents': calc['guaranteed_profit_cents']
            }
        except Exception as e:
            logger.error(f"❌ Paper execution error: {e}")
            return {'success': False, 'error': str(e)}

    async def _execute_live(self, opp: ArbOpportunity, contracts: int, calc: Dict, exec_id: str) -> Dict:
        """Execute live trade via Kalshi batch API."""
        batch_orders = []
        for leg in opp.legs:
            order = {
                'ticker': leg.ticker,
                'side': leg.side,
                'action': 'buy',
                'count': contracts,
                'type': 'limit',
            }
            if leg.side == 'yes':
                order['yes_price'] = leg.price_cents
            else:
                order['no_price'] = leg.price_cents
            batch_orders.append(order)

        try:
            response = await self.kalshi.place_batch_orders(batch_orders)

            all_filled = all(
                o.get('order', {}).get('status') == 'filled'
                for o in response.get('orders', [])
            )

            # Record execution
            async with self.db.connection() as conn:
                await conn.execute("""
                    INSERT INTO btc_arb_executions
                    (id, opportunity_id, mode, contracts_per_leg, total_cost_cents, total_fees_cents, guaranteed_profit_cents, status, kalshi_response)
                    VALUES (?, ?, 'live', ?, ?, ?, ?, ?, ?)
                """, (
                    exec_id, opp.id, contracts,
                    calc['total_cost_cents'], calc['total_fees_cents'], calc['guaranteed_profit_cents'],
                    'filled' if all_filled else 'partial',
                    str(response)
                ))
                await conn.commit()

            return {
                'success': all_filled,
                'execution_id': exec_id,
                'mode': 'live',
                'contracts': contracts,
                'kalshi_response': response
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    async def get_opportunities(self) -> List[Dict]:
        """Get current opportunities."""
        async with self._opportunities_lock:
            return [opp.to_dict() for opp in self._opportunities]

    async def get_status(self) -> Dict:
        """Get engine status."""
        return {
            'is_running': self.status.is_running,
            'last_scan_at': self.status.last_scan_at,
            'last_scan_duration_ms': self.status.last_scan_duration_ms,
            'total_scans': self.status.total_scans,
            'opportunities_found': self.status.opportunities_found,
            'auto_executions': self.status.auto_executions,
            'last_error': self.status.last_error,
            'config': {
                'min_edge_percent': self.config.min_edge_percent,
                'budget_cents': self.config.budget_cents,
                'auto_trade_enabled': self.config.auto_trade_enabled,
                'mode': self.config.mode,
                'scan_interval_seconds': self.config.scan_interval_seconds
            }
        }

    async def get_full_status(self) -> Dict:
        """Get complete engine status including market data and calculations."""
        # Get basic status
        base_status = await self.get_status()
        opportunities = await self.get_opportunities()

        # Get scan result data
        scan_result = self.scanner.get_last_scan_result()

        # Build market data summary
        market_data = {
            'range_markets': [],
            'threshold_markets': [],
            'event_dates': []
        }

        # Build calculations list (top 20 sorted by cost)
        calculations = []

        # Build stats
        stats = {
            'ranges_checked': 0,
            'thresholds_found': 0,
            'best_cost': None,
            'worst_cost': None,
            'near_misses': 0,
            'missing_prices': 0,
            'missing_thresholds': 0
        }

        # Categorized calculations for UI
        all_calculations = []
        near_misses = []
        profitable = []

        if scan_result:
            # Market data
            market_data['range_markets'] = [m.to_dict() for m in scan_result.range_markets[:50]]
            market_data['threshold_markets'] = [m.to_dict() for m in scan_result.threshold_markets[:50]]
            market_data['event_dates'] = scan_result.stats.get('event_dates', [])

            # ALL calculations with valid costs, sorted by cost (best first)
            sorted_calcs = sorted(
                [c for c in scan_result.calculations if c.total_cost_cents is not None],
                key=lambda x: x.total_cost_cents
            )
            all_calculations = [c.to_dict() for c in sorted_calcs]

            # Near-misses: cost 100-105¢ (close to profitable)
            near_misses = [c.to_dict() for c in sorted_calcs if 100 <= c.total_cost_cents <= 105]

            # Profitable: cost < 100¢
            profitable = [c.to_dict() for c in sorted_calcs if c.total_cost_cents < 100]

            # Top 20 for backwards compatibility
            calculations = [c.to_dict() for c in sorted_calcs[:20]]

            # Stats
            stats = scan_result.stats

        # Get activity log
        activity_log = btc_arb_activity.get_all()

        return {
            **base_status,
            'opportunities': opportunities,
            'market_data': market_data,
            'calculations': calculations,
            'all_calculations': all_calculations,
            'near_misses': near_misses,
            'profitable': profitable,
            'stats': stats,
            'activity_log': activity_log[:50]  # Last 50 log messages
        }

    async def update_config(self, **kwargs) -> Dict:
        """Update configuration."""
        if 'min_edge_percent' in kwargs:
            self.config.min_edge_percent = float(kwargs['min_edge_percent'])
        if 'budget_cents' in kwargs:
            self.config.budget_cents = int(kwargs['budget_cents'])
        if 'auto_trade_enabled' in kwargs:
            self.config.auto_trade_enabled = bool(kwargs['auto_trade_enabled'])
        if 'mode' in kwargs:
            self.config.mode = kwargs['mode']
        if 'scan_interval_seconds' in kwargs:
            self.config.scan_interval_seconds = float(kwargs['scan_interval_seconds'])

        await self._save_config()
        return await self.get_status()

    async def manual_execute(self, opportunity_id: str) -> Dict:
        """Manually execute a specific opportunity."""
        async with self._opportunities_lock:
            opp = next((o for o in self._opportunities if o.id == opportunity_id), None)

        if not opp:
            return {'success': False, 'error': 'Opportunity not found or expired'}

        trade_calc = self.scanner.calculate_trade(opp, self.config.budget_cents)
        if 'error' in trade_calc:
            return {'success': False, 'error': trade_calc['error']}

        return await self._execute_trade(opp, trade_calc)
