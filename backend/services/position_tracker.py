"""Position tracking and P&L calculation"""

import json
from datetime import datetime
from typing import Dict, List, Optional

from ..database.connection import db
from .trade_executor import TradeResult


class PositionTracker:
    """Tracks open positions and calculates P&L"""

    async def save_trade(self, trade: TradeResult) -> None:
        """Save trade to database"""
        orders_json = json.dumps([
            {
                "ticker": o.ticker,
                "order_id": o.order_id,
                "status": o.status,
                "contracts_filled": o.contracts_filled,
                "contracts_requested": o.contracts_requested,
                "fill_price": o.fill_price,
                "fees": o.fees
            }
            for o in trade.orders
        ])

        async with db.get_connection() as conn:
            await conn.execute("""
                INSERT INTO trades (
                    id, opportunity_id, executed_at, asset,
                    total_cost, total_fees, expected_payout, expected_profit,
                    status, orders_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.trade_id,
                trade.opportunity_id,
                datetime.utcnow().isoformat(),
                "",  # Will be filled from opportunity
                trade.total_cost,
                trade.total_fees,
                trade.expected_payout,
                trade.expected_profit,
                trade.status,
                orders_json
            ))
            await conn.commit()

    async def get_open_positions(self) -> List[Dict]:
        """Get all open positions"""
        return await db.fetch_all("""
            SELECT
                t.id as trade_id,
                t.opportunity_id,
                t.executed_at,
                t.total_cost,
                t.expected_payout,
                t.expected_profit,
                t.status,
                t.orders_json,
                o.asset,
                o.settlement_time
            FROM trades t
            JOIN opportunities o ON t.opportunity_id = o.id
            WHERE t.settled_at IS NULL
            AND t.status != 'failed'
            ORDER BY t.executed_at DESC
        """)

    async def get_trade_history(
        self,
        limit: int = 100,
        asset: Optional[str] = None
    ) -> List[Dict]:
        """Get trade history"""
        query = """
            SELECT
                t.*,
                o.asset,
                o.threshold_strike
            FROM trades t
            JOIN opportunities o ON t.opportunity_id = o.id
            WHERE 1=1
        """
        params = []

        if asset:
            query += " AND o.asset = ?"
            params.append(asset)

        query += " ORDER BY t.executed_at DESC LIMIT ?"
        params.append(limit)

        return await db.fetch_all(query, tuple(params))

    async def settle_position(
        self,
        trade_id: str,
        actual_payout: float
    ) -> None:
        """Mark a position as settled"""
        async with db.get_connection() as conn:
            # Get trade details
            cursor = await conn.execute(
                "SELECT total_cost, total_fees FROM trades WHERE id = ?",
                (trade_id,)
            )
            trade = await cursor.fetchone()

            if trade:
                actual_profit = actual_payout - trade["total_cost"] - trade["total_fees"]

                await conn.execute("""
                    UPDATE trades
                    SET settled_at = ?,
                        actual_payout = ?,
                        actual_profit = ?
                    WHERE id = ?
                """, (
                    datetime.utcnow().isoformat(),
                    actual_payout,
                    actual_profit,
                    trade_id
                ))
                await conn.commit()

    async def get_pnl_summary(self) -> Dict:
        """Get P&L summary"""
        result = await db.fetch_one("""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN settled_at IS NOT NULL THEN 1 ELSE 0 END) as settled_trades,
                SUM(total_cost) as total_invested,
                SUM(expected_profit) as total_expected_profit,
                SUM(CASE WHEN settled_at IS NOT NULL THEN actual_profit ELSE 0 END) as realized_profit,
                SUM(CASE WHEN settled_at IS NULL THEN expected_profit ELSE 0 END) as unrealized_profit
            FROM trades
            WHERE status != 'failed'
        """)

        return {
            "total_trades": result["total_trades"] or 0,
            "settled_trades": result["settled_trades"] or 0,
            "total_invested": round(result["total_invested"] or 0, 2),
            "total_expected_profit": round(result["total_expected_profit"] or 0, 2),
            "realized_profit": round(result["realized_profit"] or 0, 2),
            "unrealized_profit": round(result["unrealized_profit"] or 0, 2)
        }
