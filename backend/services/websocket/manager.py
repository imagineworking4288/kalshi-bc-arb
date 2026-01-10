"""
WebSocket connection manager for Kalshi real-time data.
Handles connection, authentication, subscriptions, and reconnection.
"""

import asyncio
import json
import time
import logging
from typing import Optional, Dict, List, Callable, Any, Set
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    websockets = None
    ConnectionClosed = Exception

from ...utils.kalshi_auth import KalshiAuth
from ..log_config import get_logger

logger = get_logger("websocket_manager")


class ConnectionState(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


@dataclass
class Subscription:
    """Track a channel subscription"""
    sid: int  # Subscription ID from server
    channel: str
    market_tickers: Set[str]
    last_seq: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class WebSocketManager:
    """
    Manages WebSocket connection to Kalshi.

    Features:
    - Automatic reconnection with exponential backoff
    - Subscription management
    - Sequence tracking for gap detection
    - Heartbeat handling
    - Thread-safe message dispatch

    Usage:
        ws = WebSocketManager(api_key_id, private_key_path)
        await ws.connect()

        # Register handlers
        ws.on('orderbook_snapshot', handle_snapshot)
        ws.on('orderbook_delta', handle_delta)

        # Subscribe to markets
        await ws.subscribe(['orderbook_delta'], market_tickers=['MARKET-1', 'MARKET-2'])
    """

    WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
    DEMO_WS_URL = "wss://demo-api.kalshi.co/trade-api/ws/v2"

    def __init__(
        self,
        api_key_id: str,
        private_key_path: str,
        use_demo: bool = False,
        max_reconnect_attempts: int = 10,
        base_reconnect_delay: float = 1.0,
        max_reconnect_delay: float = 60.0,
    ):
        if websockets is None:
            raise ImportError("websockets package is required. Install with: pip install websockets")

        self.api_key_id = api_key_id
        self.private_key_path = private_key_path
        self.auth = KalshiAuth(api_key_id, private_key_path)
        self.use_demo = use_demo
        self.url = self.DEMO_WS_URL if use_demo else self.WS_URL

        # Reconnection settings
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_reconnect_delay = base_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay

        # Connection state
        self.ws: Optional[Any] = None  # websockets.WebSocketClientProtocol
        self.state = ConnectionState.DISCONNECTED
        self.reconnect_attempts = 0

        # Subscriptions: sid -> Subscription
        self.subscriptions: Dict[int, Subscription] = {}
        self._next_request_id = 1
        self._pending_requests: Dict[int, asyncio.Future] = {}

        # Callbacks
        self._message_handlers: Dict[str, List[Callable]] = {
            'orderbook_snapshot': [],
            'orderbook_delta': [],
            'ticker': [],
            'fill': [],
            'error': [],
        }

        # Tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        # Metrics
        self.messages_received = 0
        self.last_message_time: Optional[datetime] = None
        self.connection_start_time: Optional[datetime] = None

    def _create_auth_headers(self) -> Dict[str, str]:
        """Create authentication headers for WebSocket connection"""
        method = "GET"
        path = "/trade-api/ws/v2"
        return self.auth.get_headers(method, path)

    async def connect(self) -> bool:
        """
        Establish WebSocket connection.
        Returns True if successful.
        """
        if self.state == ConnectionState.CONNECTED:
            logger.warning("Already connected")
            return True

        self.state = ConnectionState.CONNECTING

        try:
            headers = self._create_auth_headers()

            self.ws = await websockets.connect(
                self.url,
                additional_headers=headers,
                ping_interval=None,  # We handle pings manually
                close_timeout=10,
            )

            self.state = ConnectionState.CONNECTED
            self.reconnect_attempts = 0
            self.connection_start_time = datetime.now(timezone.utc)

            # Start background tasks
            self._receive_task = asyncio.create_task(self._receive_loop())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            logger.info(f"WebSocket connected to {self.url}")
            return True

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.state = ConnectionState.DISCONNECTED
            return False

    async def disconnect(self):
        """Cleanly disconnect"""
        self.state = ConnectionState.DISCONNECTED

        # Cancel tasks
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        # Close connection
        if self.ws:
            await self.ws.close()
            self.ws = None

        self.subscriptions.clear()
        logger.info("WebSocket disconnected")

    async def _reconnect(self):
        """Attempt reconnection with exponential backoff"""
        if self.state == ConnectionState.RECONNECTING:
            return

        self.state = ConnectionState.RECONNECTING

        while self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1

            # Exponential backoff with jitter
            delay = min(
                self.base_reconnect_delay * (2 ** (self.reconnect_attempts - 1)),
                self.max_reconnect_delay
            )
            delay *= (0.5 + 0.5 * (time.time() % 1))  # Add jitter

            logger.info(f"Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay:.1f}s")
            await asyncio.sleep(delay)

            if await self.connect():
                # Resubscribe to all channels
                await self._resubscribe_all()
                return

        self.state = ConnectionState.FAILED
        logger.error("Max reconnection attempts reached")

    async def _resubscribe_all(self):
        """Resubscribe to all previous subscriptions after reconnect"""
        old_subs = list(self.subscriptions.values())
        self.subscriptions.clear()

        for sub in old_subs:
            await self.subscribe(
                channels=[sub.channel],
                market_tickers=list(sub.market_tickers)
            )

    async def _receive_loop(self):
        """Main loop to receive and dispatch messages"""
        try:
            async for message in self.ws:
                self.messages_received += 1
                self.last_message_time = datetime.now(timezone.utc)

                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON: {message[:100]}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

        except ConnectionClosed as e:
            logger.warning(f"WebSocket closed: {e}")
            await self._reconnect()
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
            await self._reconnect()

    async def _heartbeat_loop(self):
        """Monitor connection health and detect stale connections"""
        try:
            while self.state == ConnectionState.CONNECTED:
                await asyncio.sleep(30)  # Check every 30 seconds

                if self.ws and self.last_message_time:
                    age = (datetime.now(timezone.utc) - self.last_message_time).total_seconds()
                    if age > 60:  # No messages for 60 seconds
                        logger.warning("No messages received for 60s, connection may be stale")

        except asyncio.CancelledError:
            pass

    async def _handle_message(self, data: dict):
        """Route message to appropriate handlers"""
        msg_type = data.get('type')

        # Handle subscription responses
        if msg_type == 'subscribed':
            request_id = data.get('id')
            if request_id in self._pending_requests:
                self._pending_requests[request_id].set_result(data)
            return

        # Handle errors
        if msg_type == 'error':
            logger.error(f"WebSocket error: {data}")
            for handler in self._message_handlers.get('error', []):
                try:
                    await self._call_handler(handler, data)
                except Exception as e:
                    logger.error(f"Error handler failed: {e}")
            return

        # Track sequence for subscriptions
        sid = data.get('sid')
        seq = data.get('seq')
        if sid and seq and sid in self.subscriptions:
            sub = self.subscriptions[sid]
            if seq != sub.last_seq + 1 and sub.last_seq > 0:
                logger.warning(f"Sequence gap detected: expected {sub.last_seq + 1}, got {seq}")
                # Could trigger resubscribe here for fresh snapshot
            sub.last_seq = seq

        # Dispatch to handlers
        handlers = self._message_handlers.get(msg_type, [])
        for handler in handlers:
            try:
                await self._call_handler(handler, data)
            except Exception as e:
                logger.error(f"Handler error for {msg_type}: {e}")

    async def _call_handler(self, handler: Callable, data: dict):
        """Call handler, supporting both sync and async"""
        if asyncio.iscoroutinefunction(handler):
            await handler(data)
        else:
            handler(data)

    def on(self, message_type: str, handler: Callable):
        """Register a handler for a message type"""
        if message_type not in self._message_handlers:
            self._message_handlers[message_type] = []
        self._message_handlers[message_type].append(handler)

    def off(self, message_type: str, handler: Callable):
        """Remove a handler"""
        if message_type in self._message_handlers:
            self._message_handlers[message_type] = [
                h for h in self._message_handlers[message_type] if h != handler
            ]

    async def subscribe(
        self,
        channels: List[str],
        market_tickers: Optional[List[str]] = None,
        market_ticker: Optional[str] = None,
    ) -> Optional[int]:
        """
        Subscribe to channels.

        Args:
            channels: List of channel names (e.g., ['orderbook_delta', 'ticker'])
            market_tickers: List of market tickers (for multi-market subscription)
            market_ticker: Single market ticker

        Returns:
            Subscription ID if successful, None otherwise
        """
        if self.state != ConnectionState.CONNECTED or not self.ws:
            logger.error("Cannot subscribe: not connected")
            return None

        request_id = self._next_request_id
        self._next_request_id += 1

        params: Dict[str, Any] = {"channels": channels}
        if market_tickers:
            params["market_tickers"] = market_tickers
        elif market_ticker:
            params["market_ticker"] = market_ticker

        message = {
            "id": request_id,
            "cmd": "subscribe",
            "params": params
        }

        # Set up future for response
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()
        self._pending_requests[request_id] = future

        try:
            await self.ws.send(json.dumps(message))

            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=10.0)

            # Track subscription
            sid = response.get('msg', {}).get('sid', request_id)
            tickers = set(market_tickers or [market_ticker] if market_ticker else [])

            self.subscriptions[sid] = Subscription(
                sid=sid,
                channel=channels[0],  # Primary channel
                market_tickers=tickers,
            )

            logger.info(f"Subscribed to {channels} for {len(tickers)} markets")
            return sid

        except asyncio.TimeoutError:
            logger.error("Subscribe timeout")
            return None
        except Exception as e:
            logger.error(f"Subscribe error: {e}")
            return None
        finally:
            self._pending_requests.pop(request_id, None)

    async def unsubscribe(self, sids: List[int]):
        """Unsubscribe from channels by subscription ID"""
        if self.state != ConnectionState.CONNECTED or not self.ws:
            return

        message = {
            "id": self._next_request_id,
            "cmd": "unsubscribe",
            "params": {"sids": sids}
        }
        self._next_request_id += 1

        await self.ws.send(json.dumps(message))

        for sid in sids:
            self.subscriptions.pop(sid, None)

    async def add_markets_to_subscription(self, sid: int, market_tickers: List[str]):
        """Add markets to existing subscription"""
        if self.state != ConnectionState.CONNECTED or not self.ws:
            return

        message = {
            "id": self._next_request_id,
            "cmd": "update_subscription",
            "params": {
                "sids": [sid],
                "market_tickers": market_tickers,
                "action": "add_markets"
            }
        }
        self._next_request_id += 1

        await self.ws.send(json.dumps(message))

        if sid in self.subscriptions:
            self.subscriptions[sid].market_tickers.update(market_tickers)

    @property
    def is_connected(self) -> bool:
        return self.state == ConnectionState.CONNECTED

    def get_stats(self) -> dict:
        """Get connection statistics"""
        return {
            "state": self.state.value,
            "messages_received": self.messages_received,
            "last_message_age_seconds": (
                (datetime.now(timezone.utc) - self.last_message_time).total_seconds()
                if self.last_message_time else None
            ),
            "subscriptions": len(self.subscriptions),
            "reconnect_attempts": self.reconnect_attempts,
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self.connection_start_time).total_seconds()
                if self.connection_start_time else 0
            ),
        }
