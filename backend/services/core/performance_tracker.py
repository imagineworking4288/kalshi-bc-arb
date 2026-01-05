"""
Performance tracking and metrics calculation.
Tracks P&L, win rates, and trading statistics.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Trading performance metrics."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl_cents: int = 0
    net_pnl_cents: int = 0  # After fees
    total_fees_cents: int = 0
    avg_win_cents: int = 0
    avg_loss_cents: int = 0
    profit_factor: float = 0.0  # Gross profit / gross loss
    sharpe_ratio: float = 0.0
    max_drawdown_cents: int = 0
    best_trade_cents: int = 0
    worst_trade_cents: int = 0
    avg_trade_duration_hours: float = 0.0

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "total_pnl_cents": self.total_pnl_cents,
            "net_pnl_cents": self.net_pnl_cents,
            "total_fees_cents": self.total_fees_cents,
            "avg_win_cents": self.avg_win_cents,
            "avg_loss_cents": self.avg_loss_cents,
            "profit_factor": round(self.profit_factor, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "max_drawdown_cents": self.max_drawdown_cents,
            "best_trade_cents": self.best_trade_cents,
            "worst_trade_cents": self.worst_trade_cents,
            "avg_trade_duration_hours": round(self.avg_trade_duration_hours, 1)
        }


class PerformanceTracker:
    """
    Tracks trading performance and calculates metrics.

    Stores trade records and computes statistics like:
    - Win rate
    - Profit factor
    - Sharpe ratio (simplified)
    - Max drawdown
    - Average P&L
    """

    def __init__(self, db):
        """
        Initialize performance tracker.

        Args:
            db: Database connection
        """
        self.db = db

    async def record_trade(
        self,
        strategy_type: str,
        ticker: str,
        side: str,
        contracts: int,
        entry_price: int = None,
        fees_cents: int = 0,
        trade_id: Optional[str] = None,
        price_cents: int = None  # Alias for entry_price
    ) -> str:
        """
        Record a new trade entry.

        Args:
            strategy_type: Strategy that generated the trade
            ticker: Market ticker
            side: "yes" or "no"
            contracts: Number of contracts
            entry_price: Entry price in cents (or use price_cents alias)
            fees_cents: Fees paid in cents
            trade_id: Optional trade ID (auto-generated if not provided)
            price_cents: Alias for entry_price

        Returns:
            Trade ID
        """
        trade_id = trade_id or str(uuid.uuid4())
        entry_time = datetime.utcnow().isoformat()
        # Support both entry_price and price_cents parameter names
        actual_price = entry_price if entry_price is not None else price_cents

        async with self.db.connection() as conn:
            await conn.execute("""
                INSERT INTO trade_records (
                    id, strategy_type, ticker, side, contracts,
                    entry_price, fees_cents, status, entry_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """, (
                trade_id, strategy_type, ticker, side, contracts,
                actual_price, fees_cents, entry_time
            ))
            await conn.commit()

        logger.info(
            f"Recorded trade entry: {trade_id[:8]} "
            f"{strategy_type} {ticker} {side} x{contracts} @ {price_cents}¢"
        )

        return trade_id

    async def record_exit(
        self,
        trade_id: str,
        exit_price_cents: int,
        won: bool,
        additional_fees: int = 0
    ) -> int:
        """
        Record trade exit and calculate P&L.

        Args:
            trade_id: Trade ID from record_trade
            exit_price_cents: Exit price in cents
            won: Whether the trade was profitable
            additional_fees: Any additional fees on exit

        Returns:
            P&L in cents
        """
        exit_time = datetime.utcnow().isoformat()

        async with self.db.connection() as conn:
            # Get trade details
            cursor = await conn.execute(
                "SELECT * FROM trade_records WHERE id = ?",
                (trade_id,)
            )
            row = await cursor.fetchone()

            if not row:
                logger.warning(f"Trade not found: {trade_id}")
                return 0

            # Calculate P&L
            entry_price = row["entry_price"]
            contracts = row["contracts"]
            side = row["side"]
            total_fees = row["fees_cents"] + additional_fees

            # For binary options: payout is 100¢ if won, 0 if lost
            if won:
                pnl = (100 - entry_price) * contracts
            else:
                pnl = -entry_price * contracts

            net_pnl = pnl - total_fees

            # Update record
            await conn.execute("""
                UPDATE trade_records
                SET exit_price = ?, pnl_cents = ?, fees_cents = ?,
                    status = 'closed', exit_time = ?
                WHERE id = ?
            """, (exit_price_cents, net_pnl, total_fees, exit_time, trade_id))
            await conn.commit()

        logger.info(
            f"Recorded trade exit: {trade_id[:8]} "
            f"pnl={net_pnl}¢ (won={won})"
        )

        return net_pnl

    async def record_arbitrage_exit(
        self,
        trade_id: str,
        pnl_cents: int,
        fees_cents: int = 0
    ) -> None:
        """
        Record arbitrage trade completion.

        For arbitrage, P&L is predetermined and always positive.

        Args:
            trade_id: Trade ID
            pnl_cents: Actual P&L in cents
            fees_cents: Total fees
        """
        exit_time = datetime.utcnow().isoformat()

        async with self.db.connection() as conn:
            await conn.execute("""
                UPDATE trade_records
                SET pnl_cents = ?, fees_cents = ?,
                    status = 'closed', exit_time = ?
                WHERE id = ?
            """, (pnl_cents, fees_cents, exit_time, trade_id))
            await conn.commit()

        logger.info(f"Recorded arbitrage exit: {trade_id[:8]} pnl={pnl_cents}¢")

    async def get_metrics(
        self,
        strategy_type: Optional[str] = None,
        days: int = 30
    ) -> Metrics:
        """
        Calculate performance metrics.

        Args:
            strategy_type: Filter by strategy (optional)
            days: Number of days to include

        Returns:
            Metrics object with calculated statistics
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        async with self.db.connection() as conn:
            # Build query
            query = """
                SELECT * FROM trade_records
                WHERE status = 'closed'
                AND entry_time > ?
            """
            params = [cutoff]

            if strategy_type:
                query += " AND strategy_type = ?"
                params.append(strategy_type)

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

        if not rows:
            return Metrics()

        # Calculate metrics
        total_trades = len(rows)
        pnl_values = [row["pnl_cents"] for row in rows]
        fees = sum(row["fees_cents"] for row in rows)

        wins = [p for p in pnl_values if p > 0]
        losses = [p for p in pnl_values if p < 0]

        winning_trades = len(wins)
        losing_trades = len(losses)
        win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

        total_pnl = sum(pnl_values)
        avg_win = int(sum(wins) / len(wins)) if wins else 0
        avg_loss = int(sum(losses) / len(losses)) if losses else 0

        # Profit factor = gross profit / abs(gross loss)
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0

        # Calculate drawdown
        max_drawdown = self._calculate_max_drawdown(pnl_values)

        # Simplified Sharpe (using cents, not annualized)
        sharpe = self._calculate_sharpe(pnl_values)

        # Best/worst trades
        best_trade = max(pnl_values) if pnl_values else 0
        worst_trade = min(pnl_values) if pnl_values else 0

        # Average duration
        durations = []
        for row in rows:
            if row["exit_time"]:
                entry = datetime.fromisoformat(row["entry_time"])
                exit = datetime.fromisoformat(row["exit_time"])
                duration = (exit - entry).total_seconds() / 3600
                durations.append(duration)

        avg_duration = sum(durations) / len(durations) if durations else 0

        return Metrics(
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate=win_rate,
            total_pnl_cents=total_pnl,
            net_pnl_cents=total_pnl,  # Already net of fees
            total_fees_cents=fees,
            avg_win_cents=avg_win,
            avg_loss_cents=avg_loss,
            profit_factor=profit_factor,
            sharpe_ratio=sharpe,
            max_drawdown_cents=max_drawdown,
            best_trade_cents=best_trade,
            worst_trade_cents=worst_trade,
            avg_trade_duration_hours=avg_duration
        )

    async def get_daily_pnl(self, days: int = 30) -> List[Dict]:
        """
        Get daily P&L for charting.

        Args:
            days: Number of days to include

        Returns:
            List of {date, pnl_cents, trade_count}
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT
                    DATE(exit_time) as date,
                    SUM(pnl_cents) as pnl,
                    COUNT(*) as trades
                FROM trade_records
                WHERE status = 'closed'
                AND exit_time > ?
                GROUP BY DATE(exit_time)
                ORDER BY date
            """, (cutoff,))
            rows = await cursor.fetchall()

        return [
            {
                "date": row["date"],
                "pnl_cents": row["pnl"],
                "trade_count": row["trades"]
            }
            for row in rows
        ]

    async def get_strategy_breakdown(self, days: int = 30) -> Dict[str, Dict]:
        """
        Get performance breakdown by strategy.

        Args:
            days: Number of days to include

        Returns:
            Dict mapping strategy_type to metrics
        """
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT strategy_type,
                    COUNT(*) as trades,
                    SUM(pnl_cents) as pnl,
                    SUM(CASE WHEN pnl_cents > 0 THEN 1 ELSE 0 END) as wins
                FROM trade_records
                WHERE status = 'closed'
                AND entry_time > ?
                GROUP BY strategy_type
            """, (cutoff,))
            rows = await cursor.fetchall()

        result = {}
        for row in rows:
            win_rate = (row["wins"] / row["trades"] * 100) if row["trades"] > 0 else 0
            result[row["strategy_type"]] = {
                "total_trades": row["trades"],
                "winning_trades": row["wins"],
                "total_pnl_cents": row["pnl"],
                "win_rate": round(win_rate, 1)
            }

        return result

    async def get_recent_trades(
        self,
        limit: int = 20,
        strategy_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get recent trades.

        Args:
            limit: Maximum trades to return
            strategy_type: Filter by strategy (optional)

        Returns:
            List of trade records
        """
        async with self.db.connection() as conn:
            query = """
                SELECT * FROM trade_records
                WHERE status = 'closed'
            """
            params = []

            if strategy_type:
                query += " AND strategy_type = ?"
                params.append(strategy_type)

            query += " ORDER BY exit_time DESC LIMIT ?"
            params.append(limit)

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

        return [dict(row) for row in rows]

    def _calculate_max_drawdown(self, pnl_values: List[int]) -> int:
        """Calculate maximum drawdown from P&L series."""
        if not pnl_values:
            return 0

        cumulative = 0
        peak = 0
        max_dd = 0

        for pnl in pnl_values:
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd

    def _calculate_sharpe(self, pnl_values: List[int]) -> float:
        """Calculate simplified Sharpe ratio."""
        if len(pnl_values) < 2:
            return 0.0

        import statistics

        mean = statistics.mean(pnl_values)
        std = statistics.stdev(pnl_values)

        if std == 0:
            return 0.0

        return mean / std
