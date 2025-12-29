"""Analytics and reporting service"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from ..database.connection import db


class AnalyticsService:
    """Service for analytics and reporting"""

    async def get_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset: Optional[str] = None
    ) -> Dict:
        """Get summary statistics"""
        where_clauses = ["1=1"]
        params = []

        if start_date:
            where_clauses.append("detected_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("detected_at <= ?")
            params.append(end_date.isoformat())

        if asset:
            where_clauses.append("asset = ?")
            params.append(asset)

        where = " AND ".join(where_clauses)

        result = await db.fetch_one(f"""
            SELECT
                COUNT(*) as total,
                AVG(net_profit_pct) as avg_profit,
                MAX(net_profit_pct) as max_profit,
                MIN(net_profit_pct) as min_profit,
                AVG(duration_seconds) as avg_duration,
                SUM(CASE WHEN was_traded = 1 THEN 1 ELSE 0 END) as traded_count,
                AVG(max_liquidity_usd) as avg_liquidity
            FROM opportunities
            WHERE {where}
        """, tuple(params))

        return {
            "total_opportunities": result["total"] or 0,
            "avg_profit_pct": round(result["avg_profit"] or 0, 2),
            "max_profit_pct": round(result["max_profit"] or 0, 2),
            "min_profit_pct": round(result["min_profit"] or 0, 2),
            "avg_duration_seconds": int(result["avg_duration"] or 0),
            "traded_count": result["traded_count"] or 0,
            "avg_liquidity_usd": round(result["avg_liquidity"] or 0, 2)
        }

    async def get_by_asset(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """Get breakdown by asset"""
        where_clauses = ["1=1"]
        params = []

        if start_date:
            where_clauses.append("detected_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("detected_at <= ?")
            params.append(end_date.isoformat())

        where = " AND ".join(where_clauses)

        rows = await db.fetch_all(f"""
            SELECT
                asset,
                COUNT(*) as count,
                AVG(net_profit_pct) as avg_profit,
                AVG(duration_seconds) as avg_duration,
                SUM(CASE WHEN was_traded = 1 THEN 1 ELSE 0 END) as traded_count
            FROM opportunities
            WHERE {where}
            GROUP BY asset
            ORDER BY count DESC
        """, tuple(params))

        return [
            {
                "asset": row["asset"],
                "count": row["count"],
                "avg_profit_pct": round(row["avg_profit"] or 0, 2),
                "avg_duration_seconds": int(row["avg_duration"] or 0),
                "traded_count": row["traded_count"] or 0
            }
            for row in rows
        ]

    async def get_by_date(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset: Optional[str] = None
    ) -> List[Dict]:
        """Get daily breakdown"""
        where_clauses = ["1=1"]
        params = []

        if start_date:
            where_clauses.append("detected_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("detected_at <= ?")
            params.append(end_date.isoformat())

        if asset:
            where_clauses.append("asset = ?")
            params.append(asset)

        where = " AND ".join(where_clauses)

        rows = await db.fetch_all(f"""
            SELECT
                DATE(detected_at) as date,
                COUNT(*) as count,
                AVG(net_profit_pct) as avg_profit,
                SUM(CASE WHEN was_traded = 1 THEN 1 ELSE 0 END) as traded_count
            FROM opportunities
            WHERE {where}
            GROUP BY DATE(detected_at)
            ORDER BY date DESC
        """, tuple(params))

        return [
            {
                "date": row["date"],
                "count": row["count"],
                "avg_profit_pct": round(row["avg_profit"] or 0, 2),
                "traded_count": row["traded_count"] or 0
            }
            for row in rows
        ]

    async def get_by_hour(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset: Optional[str] = None
    ) -> List[Dict]:
        """Get hourly breakdown"""
        where_clauses = ["1=1"]
        params = []

        if start_date:
            where_clauses.append("detected_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("detected_at <= ?")
            params.append(end_date.isoformat())

        if asset:
            where_clauses.append("asset = ?")
            params.append(asset)

        where = " AND ".join(where_clauses)

        rows = await db.fetch_all(f"""
            SELECT
                strftime('%H', detected_at) as hour,
                COUNT(*) as count,
                AVG(net_profit_pct) as avg_profit
            FROM opportunities
            WHERE {where}
            GROUP BY strftime('%H', detected_at)
            ORDER BY hour
        """, tuple(params))

        return [
            {
                "hour": int(row["hour"]),
                "count": row["count"],
                "avg_profit_pct": round(row["avg_profit"] or 0, 2)
            }
            for row in rows
        ]

    async def get_profit_distribution(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset: Optional[str] = None,
        bin_size: float = 0.5
    ) -> List[Dict]:
        """Get profit distribution histogram"""
        where_clauses = ["1=1"]
        params = []

        if start_date:
            where_clauses.append("detected_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("detected_at <= ?")
            params.append(end_date.isoformat())

        if asset:
            where_clauses.append("asset = ?")
            params.append(asset)

        where = " AND ".join(where_clauses)

        rows = await db.fetch_all(f"""
            SELECT
                CAST((net_profit_pct / ?) AS INTEGER) * ? as bin,
                COUNT(*) as count
            FROM opportunities
            WHERE {where}
            GROUP BY CAST((net_profit_pct / ?) AS INTEGER)
            ORDER BY bin
        """, (bin_size, bin_size, bin_size) + tuple(params))

        return [
            {
                "bin_start": row["bin"],
                "bin_end": row["bin"] + bin_size,
                "count": row["count"]
            }
            for row in rows
        ]

    async def get_trade_performance(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict:
        """Get trade performance statistics"""
        where_clauses = ["1=1"]
        params = []

        if start_date:
            where_clauses.append("executed_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("executed_at <= ?")
            params.append(end_date.isoformat())

        where = " AND ".join(where_clauses)

        result = await db.fetch_one(f"""
            SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(total_cost) as total_invested,
                SUM(actual_profit) as total_profit,
                AVG(actual_profit) as avg_profit
            FROM trades
            WHERE {where}
        """, tuple(params))

        total = result["total_trades"] or 0
        successful = result["successful"] or 0

        return {
            "total_trades": total,
            "successful_trades": successful,
            "failed_trades": result["failed"] or 0,
            "success_rate": round(successful / total * 100, 2) if total > 0 else 0,
            "total_invested": round(result["total_invested"] or 0, 2),
            "total_profit": round(result["total_profit"] or 0, 2),
            "avg_profit_per_trade": round(result["avg_profit"] or 0, 2)
        }

    async def export_csv(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        asset: Optional[str] = None
    ) -> str:
        """Export opportunities to CSV format"""
        where_clauses = ["1=1"]
        params = []

        if start_date:
            where_clauses.append("detected_at >= ?")
            params.append(start_date.isoformat())

        if end_date:
            where_clauses.append("detected_at <= ?")
            params.append(end_date.isoformat())

        if asset:
            where_clauses.append("asset = ?")
            params.append(asset)

        where = " AND ".join(where_clauses)

        rows = await db.fetch_all(f"""
            SELECT * FROM opportunities
            WHERE {where}
            ORDER BY detected_at DESC
        """, tuple(params))

        if not rows:
            return "No data"

        # Get column names
        columns = list(rows[0].keys())

        # Build CSV
        lines = [",".join(columns)]
        for row in rows:
            values = []
            for col in columns:
                val = row[col]
                if val is None:
                    values.append("")
                elif isinstance(val, str) and "," in val:
                    values.append(f'"{val}"')
                else:
                    values.append(str(val))
            lines.append(",".join(values))

        return "\n".join(lines)
