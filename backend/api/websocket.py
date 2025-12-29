"""WebSocket handler for real-time updates"""

import asyncio
import json
from typing import List

from fastapi import WebSocket, WebSocketDisconnect

from ..services.arbitrage_engine import ArbitrageEngine
from ..services.cf_benchmarks_client import CFBenchmarksClient
from ..services.kalshi_client import KalshiClient
from ..services.market_service import MarketService


class ConnectionManager:
    """Manages WebSocket connections"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)


# Global connection manager
manager = ConnectionManager()

# Service instances
kalshi = KalshiClient()
cf_benchmarks = CFBenchmarksClient()
market_service = MarketService(kalshi)
arb_engine = ArbitrageEngine()


async def send_price_updates():
    """Send spot price updates periodically"""
    while True:
        try:
            prices = await cf_benchmarks.get_all_prices()
            await manager.broadcast({
                "type": "spot_prices",
                "data": {
                    asset: {
                        "price": p.price,
                        "timestamp": p.timestamp.isoformat(),
                        "cached": p.cached
                    }
                    for asset, p in prices.items()
                }
            })
        except Exception as e:
            print(f"Error sending price updates: {e}")

        await asyncio.sleep(5)


async def send_opportunity_updates():
    """Send opportunity updates periodically"""
    while True:
        try:
            groups = await market_service.get_grouped_markets()

            # Add spot prices
            spot_prices = await cf_benchmarks.get_all_prices()
            for group in groups:
                if group.asset in spot_prices:
                    group.spot_price = spot_prices[group.asset].price

            opportunities = arb_engine.find_opportunities(groups)

            await manager.broadcast({
                "type": "opportunities",
                "data": [
                    {
                        "id": o.id,
                        "asset": o.asset,
                        "threshold_strike": o.threshold_strike,
                        "threshold_direction": o.threshold_direction,
                        "net_profit_pct": o.net_profit_pct,
                        "max_liquidity_usd": o.max_liquidity_usd,
                        "spot_price": o.spot_price,
                        "spot_relation": o.spot_relation,
                        "score": o.score,
                        "trade_direction": o.trade_direction,
                        "settlement_time": o.settlement_time.isoformat()
                    }
                    for o in opportunities
                ]
            })
        except Exception as e:
            print(f"Error sending opportunity updates: {e}")

        await asyncio.sleep(10)


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)

    # Start background tasks
    price_task = asyncio.create_task(send_price_updates())
    opportunity_task = asyncio.create_task(send_opportunity_updates())

    try:
        while True:
            # Handle incoming messages
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30
                )
                message = json.loads(data)

                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})

                elif message.get("type") == "subscribe":
                    # Handle subscription requests
                    topics = message.get("topics", [])
                    await websocket.send_json({
                        "type": "subscribed",
                        "topics": topics
                    })

            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)
        price_task.cancel()
        opportunity_task.cancel()

        try:
            await price_task
        except asyncio.CancelledError:
            pass

        try:
            await opportunity_task
        except asyncio.CancelledError:
            pass
