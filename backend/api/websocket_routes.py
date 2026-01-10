"""
WebSocket endpoints for real-time updates.
Provides real-time orderbook updates, opportunity notifications, and risk metrics.
"""

import asyncio
import json
import logging
from typing import Set, Dict, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections with subscription support"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscriptions: Dict[WebSocket, Set[str]] = {}  # ws -> set of event_tickers
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            self.subscriptions[websocket] = set()
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        async with self._lock:
            self.active_connections.discard(websocket)
            self.subscriptions.pop(websocket, None)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    def subscribe(self, websocket: WebSocket, event_tickers: list):
        """Subscribe a connection to specific event tickers"""
        if websocket in self.subscriptions:
            self.subscriptions[websocket].update(event_tickers)
            logger.debug(f"Subscribed to {event_tickers}. Current subs: {self.subscriptions[websocket]}")

    def unsubscribe(self, websocket: WebSocket, event_tickers: list):
        """Unsubscribe a connection from specific event tickers"""
        if websocket in self.subscriptions:
            self.subscriptions[websocket] -= set(event_tickers)

    def get_subscriptions(self, websocket: WebSocket) -> Set[str]:
        """Get current subscriptions for a connection"""
        return self.subscriptions.get(websocket, set())

    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        message_json = json.dumps(message, default=str)
        disconnected = set()

        for connection in list(self.active_connections):
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                disconnected.add(connection)

        for conn in disconnected:
            await self.disconnect(conn)

    async def send_to_subscribers(self, event_ticker: str, message: dict):
        """Send message to clients subscribed to a specific event"""
        message_json = json.dumps(message, default=str)
        disconnected = set()

        for connection, subs in list(self.subscriptions.items()):
            if event_ticker in subs or '*' in subs:
                try:
                    await connection.send_text(message_json)
                except Exception as e:
                    logger.warning(f"Failed to send to subscriber: {e}")
                    disconnected.add(connection)

        for conn in disconnected:
            await self.disconnect(conn)

    async def send_personal(self, websocket: WebSocket, message: dict):
        """Send a message to a specific connection"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.warning(f"Failed to send personal message: {e}")
            await self.disconnect(websocket)

    def get_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "total_connections": len(self.active_connections),
            "subscribed_events": len(set().union(*self.subscriptions.values())) if self.subscriptions else 0,
            "subscriptions_by_connection": {
                id(ws): list(subs) for ws, subs in self.subscriptions.items()
            }
        }


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for real-time updates.

    Client sends:
    - {"type": "subscribe", "event_tickers": ["HIGHNY-25JAN10", "HIGHCHI-25JAN10"]}
    - {"type": "unsubscribe", "event_tickers": ["HIGHNY-25JAN10"]}
    - {"type": "ping"}
    - {"type": "get_subscriptions"}

    Server sends:
    - {"type": "orderbook_update", "ticker": "...", "orderbook": {...}}
    - {"type": "opportunity_update", "opportunities": [...]}
    - {"type": "risk_update", "risk": {...}}
    - {"type": "execution_update", "execution": {...}}
    - {"type": "subscribed", "event_tickers": [...]}
    - {"type": "unsubscribed", "event_tickers": [...]}
    - {"type": "pong"}
    - {"type": "error", "message": "..."}
    """
    await manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket.send_json({
            "type": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "WebSocket connection established"
        })

        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                msg_type = message.get('type')

                if msg_type == 'subscribe':
                    event_tickers = message.get('event_tickers', [])
                    if not event_tickers:
                        await websocket.send_json({
                            "type": "error",
                            "message": "event_tickers array is required"
                        })
                        continue

                    manager.subscribe(websocket, event_tickers)
                    await websocket.send_json({
                        "type": "subscribed",
                        "event_tickers": event_tickers,
                        "total_subscriptions": list(manager.get_subscriptions(websocket)),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

                elif msg_type == 'unsubscribe':
                    event_tickers = message.get('event_tickers', [])
                    manager.unsubscribe(websocket, event_tickers)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "event_tickers": event_tickers,
                        "remaining_subscriptions": list(manager.get_subscriptions(websocket)),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

                elif msg_type == 'ping':
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

                elif msg_type == 'get_subscriptions':
                    await websocket.send_json({
                        "type": "subscriptions",
                        "event_tickers": list(manager.get_subscriptions(websocket)),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {msg_type}"
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format"
                })

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


@router.websocket("/ws/opportunities")
async def opportunities_websocket(websocket: WebSocket):
    """
    Dedicated WebSocket endpoint for opportunity updates.
    Automatically subscribes to all opportunity updates.
    """
    await manager.connect(websocket)
    manager.subscribe(websocket, ['*'])  # Subscribe to all

    try:
        await websocket.send_json({
            "type": "connected",
            "channel": "opportunities",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        while True:
            data = await websocket.receive_text()

            try:
                message = json.loads(data)
                if message.get('type') == 'ping':
                    await websocket.send_json({"type": "pong"})
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Opportunities WebSocket error: {e}")
        await manager.disconnect(websocket)


# ============ Broadcast Helper Functions ============

async def broadcast_orderbook_update(ticker: str, orderbook: dict):
    """Broadcast orderbook update to subscribers of the event"""
    # Extract event ticker from market ticker (e.g., HIGHNY-25JAN10-B1 -> HIGHNY-25JAN10)
    parts = ticker.split("-")
    if len(parts) >= 2:
        event_ticker = "-".join(parts[:-1]) if parts[-1].startswith("B") or parts[-1].startswith("T") else ticker
    else:
        event_ticker = ticker

    await manager.send_to_subscribers(event_ticker, {
        "type": "orderbook_update",
        "ticker": ticker,
        "event_ticker": event_ticker,
        "orderbook": orderbook,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def broadcast_opportunity_update(opportunities: list):
    """Broadcast opportunity updates to all connected clients"""
    await manager.broadcast({
        "type": "opportunity_update",
        "opportunities": opportunities,
        "count": len(opportunities),
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def broadcast_risk_update(risk: dict):
    """Broadcast risk metrics update to all connected clients"""
    await manager.broadcast({
        "type": "risk_update",
        "risk": risk,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def broadcast_execution_update(execution: dict):
    """Broadcast execution result to all connected clients"""
    await manager.broadcast({
        "type": "execution_update",
        "execution": execution,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def broadcast_alert(alert: dict):
    """Broadcast alert to all connected clients"""
    await manager.broadcast({
        "type": "alert",
        "alert": alert,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


async def broadcast_circuit_breaker_update(status: dict):
    """Broadcast circuit breaker status change"""
    await manager.broadcast({
        "type": "circuit_breaker_update",
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ============ Utility Functions ============

def get_connection_manager() -> ConnectionManager:
    """Get the global connection manager instance"""
    return manager


def get_ws_stats() -> dict:
    """Get WebSocket connection statistics"""
    return manager.get_stats()
