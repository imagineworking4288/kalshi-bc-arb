"""Opportunity logging and history management"""

import json
from dataclasses import asdict
from datetime import datetime
from typing import List, Optional

from ..database.connection import db
from .arbitrage_engine import ArbitrageOpportunity


class OpportunityLogger:
    """Service for logging and querying opportunities"""

    async def log_opportunity(self, opportunity: ArbitrageOpportunity) -> None:
        """Save detected opportunity to database"""
        # Serialize brackets
        brackets_json = json.dumps(
            [
                {
                    "ticker": b.ticker,
                    "title": b.title,
                    "low_bound": b.low_bound,
                    "high_bound": b.high_bound,
                    "yes_price": b.yes_price
                }
                for b in opportunity.required_brackets
            ]
        )

        async with db.get_connection() as conn:
            await conn.execute("""
                INSERT OR REPLACE INTO opportunities (
                    id, detected_at, asset, settlement_time,
                    threshold_ticker, threshold_strike, threshold_direction,
                    threshold_yes_price, implied_price, divergence, spot_price,
                    gross_profit_pct, estimated_fees, net_profit_pct,
                    max_liquidity_usd, trade_direction, brackets_snapshot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                opportunity.id,
                opportunity.detected_at.isoformat(),
                opportunity.asset,
                opportunity.settlement_time.isoformat(),
                opportunity.threshold_ticker,
                opportunity.threshold_strike,
                opportunity.threshold_direction,
                opportunity.threshold_yes_price,
                opportunity.implied_price,
                opportunity.divergence,
                opportunity.spot_price,
                opportunity.gross_profit_pct,
                opportunity.estimated_fees,
                opportunity.net_profit_pct,
                opportunity.max_liquidity_usd,
                opportunity.trade_direction,
                brackets_json
            ))
            await conn.commit()

    async def close_opportunity(self, opportunity_id: str) -> None:
        """Mark opportunity as closed (no longer available)"""
        async with db.get_connection() as conn:
            now = datetime.utcnow()

            # Get detected_at to calculate duration
            cursor = await conn.execute(
                "SELECT detected_at FROM opportunities WHERE id = ?",
                (opportunity_id,)
            )
            row = await cursor.fetchone()

            if row:
                detected_at = datetime.fromisoformat(row["detected_at"])
                duration = int((now - detected_at).total_seconds())

                await conn.execute("""
                    UPDATE opportunities
                    SET closed_at = ?, duration_seconds = ?
                    WHERE id = ?
                """, (now.isoformat(), duration, opportunity_id))
                await conn.commit()

    async def mark_traded(self, opportunity_id: str, trade_id: str) -> None:
        """Mark opportunity as traded"""
        async with db.get_connection() as conn:
            await conn.execute("""
                UPDATE opportunities
                SET was_traded = 1, trade_id = ?
                WHERE id = ?
            """, (trade_id, opportunity_id))
            await conn.commit()

    async def get_opportunity(self, opportunity_id: str) -> Optional[dict]:
        """Get a single opportunity by ID"""
        return await db.fetch_one(
            "SELECT * FROM opportunities WHERE id = ?",
            (opportunity_id,)
        )

    async def get_history(
        self,
        asset: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        min_profit: Optional[float] = None,
        traded_only: bool = False,
        limit: int = 100
    ) -> List[dict]:
        """Query opportunity history with filters"""
        query = "SELECT * FROM opportunities WHERE 1=1"
        params = []

        if asset:
            query += " AND asset = ?"
            params.append(asset)

        if start_date:
            query += " AND detected_at >= ?"
            params.append(start_date.isoformat())

        if end_date:
            query += " AND detected_at <= ?"
            params.append(end_date.isoformat())

        if min_profit is not None:
            query += " AND net_profit_pct >= ?"
            params.append(min_profit)

        if traded_only:
            query += " AND was_traded = 1"

        query += " ORDER BY detected_at DESC LIMIT ?"
        params.append(limit)

        return await db.fetch_all(query, tuple(params))

    async def get_active_opportunities(
        self,
        asset: Optional[str] = None
    ) -> List[dict]:
        """Get opportunities that haven't been closed"""
        query = """
            SELECT * FROM opportunities
            WHERE closed_at IS NULL
            AND settlement_time > ?
        """
        params = [datetime.utcnow().isoformat()]

        if asset:
            query += " AND asset = ?"
            params.append(asset)

        query += " ORDER BY net_profit_pct DESC"

        return await db.fetch_all(query, tuple(params))
