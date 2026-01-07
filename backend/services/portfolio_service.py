"""
Portfolio Service - Unified view of paper + live positions
"""
from typing import List, Dict, Any, Optional

from ..database.connection import db
from ..config import get_settings
from .kalshi_client import KalshiClient

from .log_config import get_logger

logger = get_logger("portfolio_service")


class PortfolioService:
    def __init__(self):
        self.settings = get_settings()
        self.kalshi_client = KalshiClient()

    async def get_summary(self) -> Dict[str, Any]:
        """Get portfolio summary across paper and live."""
        summary = {
            "paper_balance": 0,
            "live_balance": 0,
            "paper_positions_count": 0,
            "live_positions_count": 0,
            "paper_positions_value": 0,
            "live_positions_value": 0,
        }

        # Paper balance
        async with db.connection() as conn:
            cursor = await conn.execute("SELECT balance FROM paper_account WHERE id = 1")
            row = await cursor.fetchone()
            summary["paper_balance"] = row[0] if row else 0

            # Paper positions count
            cursor = await conn.execute("SELECT COUNT(*) FROM paper_positions WHERE settled = 0")
            row = await cursor.fetchone()
            summary["paper_positions_count"] = row[0] if row else 0

        # Live balance from Kalshi (API returns cents, convert to dollars)
        try:
            live_balance = await self.kalshi_client.get_balance()
            # Kalshi returns balance in cents, convert to dollars
            summary["live_balance"] = live_balance.get("balance", 0) / 100
        except Exception as e:
            logger.warning(f"Could not fetch live balance: {e}")

        # Live positions count
        try:
            live_positions = await self.kalshi_client.get_positions()
            summary["live_positions_count"] = len(live_positions)
        except Exception as e:
            logger.warning(f"Could not fetch live positions: {e}")

        return summary

    async def get_all_positions(self) -> List[Dict[str, Any]]:
        """Get all positions from both paper and live."""
        positions = []

        # Paper positions
        async with db.connection() as conn:
            cursor = await conn.execute("""
                SELECT ticker, side, contracts, avg_price, total_cost, total_fees, created_at
                FROM paper_positions
                WHERE settled = 0 AND contracts > 0
            """)
            rows = await cursor.fetchall()

            for row in rows:
                positions.append({
                    "mode": "paper",
                    "ticker": row[0],
                    "side": row[1],
                    "contracts": row[2],
                    "avg_price": float(row[3]) if row[3] else 0.0,
                    "total_cost": float(row[4]) if row[4] else 0.0,
                    "created_at": row[6],
                })

        # Live positions from Kalshi
        try:
            live_positions = await self.kalshi_client.get_positions()
            for pos in live_positions:
                # Kalshi returns position as positive (YES) or negative (NO)
                position_count = pos.get("position", 0)
                side = "yes" if position_count > 0 else "no"

                # Kalshi API returns cents, convert to dollars
                market_exposure_cents = pos.get("market_exposure", 0)
                avg_price_cents = market_exposure_cents // abs(position_count) if position_count else 0

                positions.append({
                    "mode": "live",
                    "ticker": pos.get("ticker", ""),
                    "side": side,
                    "contracts": abs(position_count),
                    "avg_price": avg_price_cents / 100.0,
                    "total_cost": market_exposure_cents / 100.0,
                    "created_at": pos.get("created_time", ""),
                })
        except Exception as e:
            logger.warning(f"Could not fetch live positions: {e}")

        return positions

    async def get_orders(self, mode: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent orders from paper (manual_orders table) and live (Kalshi API)."""
        orders = []

        # Get paper orders from database (if mode is 'all' or 'paper')
        if mode is None or mode == "paper":
            async with db.connection() as conn:
                cursor = await conn.execute("""
                    SELECT id, created_at, ticker, side, action, count,
                           price_cents, mode, status, filled_count, total_cost, total_fees
                    FROM manual_orders
                    WHERE mode = 'paper'
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (limit,))

                rows = await cursor.fetchall()

                for row in rows:
                    orders.append({
                        "id": row[0],
                        "created_at": row[1],
                        "ticker": row[2],
                        "side": row[3],
                        "action": row[4],
                        "count": row[5],
                        "price_cents": row[6],
                        "mode": "paper",
                        "status": row[8],
                        "filled_count": row[9],
                        "total_cost_cents": int((row[10] or 0) * 100),
                        "fee_cents": int((row[11] or 0) * 100),
                    })

        # Get live fills from Kalshi API (if mode is 'all' or 'live')
        if mode is None or mode == "live":
            try:
                live_fills = await self.kalshi_client.get_fills(limit=limit)
                for fill in live_fills:
                    # Kalshi fill structure:
                    # trade_id, ticker, side, action, count, yes_price, no_price, created_time
                    side = fill.get("side", "yes")
                    price_cents = fill.get("yes_price") if side == "yes" else fill.get("no_price", 0)
                    count = fill.get("count", 0)

                    orders.append({
                        "id": fill.get("trade_id", ""),
                        "created_at": fill.get("created_time", ""),
                        "ticker": fill.get("ticker", ""),
                        "side": side,
                        "action": fill.get("action", "buy"),
                        "count": count,
                        "price_cents": price_cents,
                        "mode": "live",
                        "status": "filled",
                        "filled_count": count,
                        "total_cost_cents": count * price_cents,
                        "fee_cents": 0,  # Kalshi doesn't expose fee per fill
                    })
            except Exception as e:
                logger.warning(f"Could not fetch live fills: {e}")

        # Sort all orders by created_at descending
        orders.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # Apply limit
        return orders[:limit]
