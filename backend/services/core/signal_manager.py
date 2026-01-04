"""
Signal lifecycle management.
Handles creation, storage, expiration, and retrieval of trading signals.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional

from .base_strategy import (
    TradingSignal, SignalStatus, StrategyType, SignalType, SignalLeg
)

logger = logging.getLogger(__name__)


class SignalManager:
    """
    Manages the lifecycle of trading signals.

    Responsibilities:
    - Store signals in database
    - Retrieve pending signals for processing
    - Update signal status
    - Check for duplicate/recent signals
    - Expire old signals
    """

    def __init__(self, db):
        """
        Initialize signal manager.

        Args:
            db: Database connection (from backend/database/connection.py)
        """
        self.db = db

    async def create(
        self,
        signal: TradingSignal,
        expires_in: int = 300
    ) -> TradingSignal:
        """
        Store a new signal in the database.

        Args:
            signal: The trading signal to store
            expires_in: Seconds until expiration (default 5 minutes)

        Returns:
            The stored signal with updated expiration
        """
        # Set expiration if not already set
        if signal.expires_at is None:
            signal.expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Convert legs to JSON
        legs_json = json.dumps([
            {
                "ticker": leg.ticker,
                "side": leg.side,
                "action": leg.action,
                "price_cents": leg.price_cents,
                "strike": leg.strike,
                "lower_bound": leg.lower_bound,
                "upper_bound": leg.upper_bound,
                "description": leg.description
            }
            for leg in signal.legs
        ])

        # Convert metadata to JSON
        metadata_json = json.dumps(signal.metadata)

        async with self.db.connection() as conn:
            await conn.execute("""
                INSERT INTO signals_v2 (
                    id, strategy_type, ticker, signal_type, edge_percent,
                    model_prob, market_price, recommended_size, confidence,
                    is_arbitrage, legs_json, metadata_json, status,
                    created_at, expires_at, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal.id,
                signal.strategy_type.value,
                signal.ticker,
                signal.signal_type.value,
                signal.edge_percent,
                signal.model_prob,
                signal.market_price,
                signal.recommended_size,
                signal.confidence,
                1 if signal.is_arbitrage else 0,
                legs_json,
                metadata_json,
                signal.status.value,
                signal.created_at.isoformat(),
                signal.expires_at.isoformat() if signal.expires_at else None,
                signal.notes
            ))
            await conn.commit()

        logger.info(f"Created signal {signal.id}: {signal.strategy_type.value} "
                   f"{signal.ticker} edge={signal.edge_percent:.1f}%")
        return signal

    async def get_pending(
        self,
        strategy_type: Optional[StrategyType] = None,
        limit: int = 100
    ) -> List[TradingSignal]:
        """
        Get pending signals sorted by edge (highest first).

        Args:
            strategy_type: Filter by strategy type (optional)
            limit: Maximum number of signals to return

        Returns:
            List of pending signals
        """
        async with self.db.connection() as conn:
            if strategy_type:
                cursor = await conn.execute("""
                    SELECT * FROM signals_v2
                    WHERE status = 'pending'
                    AND strategy_type = ?
                    AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY edge_percent DESC
                    LIMIT ?
                """, (strategy_type.value, datetime.utcnow().isoformat(), limit))
            else:
                cursor = await conn.execute("""
                    SELECT * FROM signals_v2
                    WHERE status = 'pending'
                    AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY edge_percent DESC
                    LIMIT ?
                """, (datetime.utcnow().isoformat(), limit))

            rows = await cursor.fetchall()
            return [self._row_to_signal(row) for row in rows]

    async def get_by_id(self, signal_id: str) -> Optional[TradingSignal]:
        """Get a signal by ID."""
        async with self.db.connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM signals_v2 WHERE id = ?",
                (signal_id,)
            )
            row = await cursor.fetchone()
            if row:
                return self._row_to_signal(row)
            return None

    async def update_status(
        self,
        signal_id: str,
        status: SignalStatus,
        notes: Optional[str] = None,
        execution_price: Optional[int] = None
    ) -> bool:
        """
        Update signal status.

        Args:
            signal_id: ID of signal to update
            status: New status
            notes: Optional notes to append
            execution_price: Fill price if executed

        Returns:
            True if updated, False if not found
        """
        async with self.db.connection() as conn:
            executed_at = datetime.utcnow().isoformat() if status == SignalStatus.EXECUTED else None

            result = await conn.execute("""
                UPDATE signals_v2
                SET status = ?,
                    notes = COALESCE(?, notes),
                    executed_at = COALESCE(?, executed_at),
                    execution_price = COALESCE(?, execution_price)
                WHERE id = ?
            """, (status.value, notes, executed_at, execution_price, signal_id))
            await conn.commit()

            updated = result.rowcount > 0
            if updated:
                logger.info(f"Updated signal {signal_id} status to {status.value}")
            return updated

    async def has_recent(
        self,
        ticker: str,
        strategy_type: StrategyType,
        seconds: int = 300
    ) -> bool:
        """
        Check if there's a recent signal for this ticker/strategy.

        Used to prevent duplicate signals within a time window.

        Args:
            ticker: Market ticker
            strategy_type: Strategy type
            seconds: Time window in seconds

        Returns:
            True if a recent signal exists
        """
        cutoff = (datetime.utcnow() - timedelta(seconds=seconds)).isoformat()

        async with self.db.connection() as conn:
            cursor = await conn.execute("""
                SELECT COUNT(*) FROM signals_v2
                WHERE ticker = ?
                AND strategy_type = ?
                AND created_at > ?
                AND status IN ('pending', 'executing', 'executed')
            """, (ticker, strategy_type.value, cutoff))

            row = await cursor.fetchone()
            return row[0] > 0

    async def expire_old(self) -> int:
        """
        Mark expired signals as expired.

        Returns:
            Number of signals expired
        """
        now = datetime.utcnow().isoformat()

        async with self.db.connection() as conn:
            result = await conn.execute("""
                UPDATE signals_v2
                SET status = 'expired'
                WHERE status = 'pending'
                AND expires_at IS NOT NULL
                AND expires_at < ?
            """, (now,))
            await conn.commit()

            count = result.rowcount
            if count > 0:
                logger.info(f"Expired {count} old signals")
            return count

    async def get_history(
        self,
        strategy_type: Optional[StrategyType] = None,
        status: Optional[SignalStatus] = None,
        limit: int = 50
    ) -> List[TradingSignal]:
        """
        Get signal history with optional filters.

        Args:
            strategy_type: Filter by strategy type
            status: Filter by status
            limit: Maximum results

        Returns:
            List of signals
        """
        async with self.db.connection() as conn:
            query = "SELECT * FROM signals_v2 WHERE 1=1"
            params = []

            if strategy_type:
                query += " AND strategy_type = ?"
                params.append(strategy_type.value)

            if status:
                query += " AND status = ?"
                params.append(status.value)

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [self._row_to_signal(row) for row in rows]

    async def get_stats(self, days: int = 7) -> dict:
        """Get signal statistics."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        async with self.db.connection() as conn:
            # Total counts by status
            cursor = await conn.execute("""
                SELECT status, COUNT(*) as count
                FROM signals_v2
                WHERE created_at > ?
                GROUP BY status
            """, (cutoff,))
            status_counts = dict(await cursor.fetchall())

            # Counts by strategy
            cursor = await conn.execute("""
                SELECT strategy_type, COUNT(*) as count
                FROM signals_v2
                WHERE created_at > ?
                GROUP BY strategy_type
            """, (cutoff,))
            strategy_counts = dict(await cursor.fetchall())

            # Average edge for executed signals
            cursor = await conn.execute("""
                SELECT AVG(edge_percent)
                FROM signals_v2
                WHERE created_at > ?
                AND status = 'executed'
            """, (cutoff,))
            row = await cursor.fetchone()
            avg_executed_edge = row[0] if row[0] else 0

            return {
                "period_days": days,
                "status_counts": status_counts,
                "strategy_counts": strategy_counts,
                "avg_executed_edge": round(avg_executed_edge, 2),
                "total_signals": sum(status_counts.values())
            }

    def _row_to_signal(self, row) -> TradingSignal:
        """Convert database row to TradingSignal."""
        # Parse legs JSON
        legs_json = row["legs_json"] or "[]"
        legs_data = json.loads(legs_json)
        legs = [
            SignalLeg(
                ticker=leg["ticker"],
                side=leg["side"],
                action=leg["action"],
                price_cents=leg["price_cents"],
                strike=leg.get("strike"),
                lower_bound=leg.get("lower_bound"),
                upper_bound=leg.get("upper_bound"),
                description=leg.get("description", "")
            )
            for leg in legs_data
        ]

        # Parse metadata JSON
        metadata_json = row["metadata_json"] or "{}"
        metadata = json.loads(metadata_json)

        return TradingSignal(
            id=row["id"],
            strategy_type=StrategyType(row["strategy_type"]),
            ticker=row["ticker"],
            signal_type=SignalType(row["signal_type"]),
            edge_percent=row["edge_percent"],
            model_prob=row["model_prob"],
            market_price=row["market_price"],
            recommended_size=row["recommended_size"],
            confidence=row.get("confidence", 1.0),
            is_arbitrage=bool(row.get("is_arbitrage", 0)),
            legs=legs,
            status=SignalStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
            executed_at=datetime.fromisoformat(row["executed_at"]) if row.get("executed_at") else None,
            execution_price=row.get("execution_price"),
            notes=row.get("notes", ""),
            metadata=metadata
        )
