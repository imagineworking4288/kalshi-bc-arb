"""
Watchlist Service - Save and manage favorite markets
"""
import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from ..database.connection import db
from .kalshi_client import KalshiClient

logger = logging.getLogger(__name__)


class WatchlistService:
    def __init__(self):
        self.kalshi_client = KalshiClient()

    async def add(self, ticker: str, notes: Optional[str] = None) -> Dict[str, Any]:
        """Add market to watchlist."""
        # Fetch market details from Kalshi
        try:
            market = await self.kalshi_client.get_market(ticker)
            if not market:
                raise ValueError(f"Market {ticker} not found")
        except Exception as e:
            raise ValueError(f"Could not fetch market: {e}")

        item_id = str(uuid.uuid4())

        async with db.connection() as conn:
            # Check if already exists
            cursor = await conn.execute(
                "SELECT id FROM watchlist WHERE ticker = ?", (ticker,)
            )
            existing = await cursor.fetchone()

            if existing:
                # Update notes if provided
                if notes:
                    await conn.execute(
                        "UPDATE watchlist SET notes = ? WHERE ticker = ?",
                        (notes, ticker)
                    )
                    await conn.commit()
                return {"id": existing[0], "ticker": ticker, "already_existed": True}

            # Insert new
            await conn.execute("""
                INSERT INTO watchlist (id, ticker, title, subtitle, notes, added_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                item_id,
                ticker,
                market.get("title", ""),
                market.get("subtitle", ""),
                notes,
                datetime.now(timezone.utc).isoformat()
            ))
            await conn.commit()

        return {
            "id": item_id,
            "ticker": ticker,
            "title": market.get("title", ""),
            "subtitle": market.get("subtitle", ""),
            "notes": notes,
            "already_existed": False
        }

    async def remove(self, ticker: str) -> bool:
        """Remove market from watchlist."""
        async with db.connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM watchlist WHERE ticker = ?", (ticker,)
            )
            await conn.commit()
            return cursor.rowcount > 0

    async def get_all(self) -> List[Dict[str, Any]]:
        """Get all watchlist items with fresh prices."""
        async with db.connection() as conn:
            cursor = await conn.execute("""
                SELECT id, ticker, title, subtitle, notes, added_at
                FROM watchlist
                ORDER BY added_at DESC
            """)
            rows = await cursor.fetchall()

        items = []
        for row in rows:
            item = {
                "id": row[0],
                "ticker": row[1],
                "title": row[2],
                "subtitle": row[3],
                "notes": row[4],
                "added_at": row[5],
                "yes_ask": None,
                "no_ask": None,
                "status": "unknown"
            }

            # Fetch fresh prices
            try:
                market = await self.kalshi_client.get_market(row[1])
                if market:
                    item["yes_ask"] = market.get("yes_ask")
                    item["no_ask"] = market.get("no_ask")
                    item["status"] = market.get("status", "unknown")
                    item["title"] = market.get("title", item["title"])
                    item["subtitle"] = market.get("subtitle", item["subtitle"])
            except Exception as e:
                logger.warning(f"Could not fetch prices for {row[1]}: {e}")

            items.append(item)

        return items
