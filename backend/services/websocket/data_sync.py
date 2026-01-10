"""
Data synchronization layer.
Single source of truth for market data.
Combines WebSocket real-time data with REST fallback.
"""

import asyncio
import logging
from typing import Dict, Optional, List, Callable, Set, Any
from datetime import datetime, timezone
from dataclasses import dataclass, field

import httpx

from .manager import WebSocketManager, ConnectionState
from .orderbook_builder import OrderbookBuilder, Orderbook
from ..log_config import get_logger
from ...config import get_settings

logger = get_logger("data_sync")


@dataclass
class MarketState:
    """Combined state for a market"""
    ticker: str
    market: Optional[Dict[str, Any]] = None
    orderbook: Optional[Orderbook] = None
    last_rest_update: Optional[datetime] = None
    last_ws_update: Optional[datetime] = None
    subscribed: bool = False


class DataSynchronizer:
    """
    Central data synchronization service.

    Responsibilities:
    - Maintain single source of truth for market data
    - Coordinate WebSocket subscriptions
    - Fallback to REST when WebSocket unavailable
    - Track data freshness
    - Provide unified interface for other components

    Usage:
        sync = DataSynchronizer(ws_manager, orderbook_builder)
        await sync.start()

        # Subscribe to markets
        await sync.subscribe_event("HIGHNY-25JAN10")

        # Get data
        orderbook = sync.get_orderbook("HIGHNY-25JAN10-B2")
        markets = sync.get_event_markets("HIGHNY-25JAN10")
    """

    def __init__(
        self,
        ws_manager: WebSocketManager,
        orderbook_builder: OrderbookBuilder,
        rest_base_url: Optional[str] = None,
        stale_threshold_seconds: float = 5.0,
        rest_fallback_interval: float = 30.0,
    ):
        self.ws = ws_manager
        self.ob_builder = orderbook_builder

        settings = get_settings()
        self.rest_base_url = rest_base_url or settings.kalshi_api_url

        self.stale_threshold = stale_threshold_seconds
        self.rest_fallback_interval = rest_fallback_interval

        # State tracking
        self._markets: Dict[str, MarketState] = {}
        self._events: Dict[str, Set[str]] = {}  # event_ticker -> set of market_tickers

        # HTTP client for REST fallback
        self._http_client: Optional[httpx.AsyncClient] = None

        # Background tasks
        self._fallback_task: Optional[asyncio.Task] = None

        # Callbacks
        self._on_data_update: List[Callable] = []

    async def start(self):
        """Start the synchronization service"""
        # Initialize HTTP client
        self._http_client = httpx.AsyncClient(
            base_url=self.rest_base_url,
            timeout=30.0,
        )

        # Connect WebSocket
        await self.ws.connect()

        # Register handlers
        self.ob_builder.on_update(self._on_orderbook_update)
        self.ws.on('orderbook_snapshot', self.ob_builder.handle_snapshot)
        self.ws.on('orderbook_delta', self.ob_builder.handle_delta)
        self.ws.on('ticker', self._on_ticker_update)

        # Start fallback polling
        self._fallback_task = asyncio.create_task(self._rest_fallback_loop())

        logger.info("DataSynchronizer started")

    async def stop(self):
        """Stop the synchronization service"""
        if self._fallback_task:
            self._fallback_task.cancel()
            try:
                await self._fallback_task
            except asyncio.CancelledError:
                pass

        await self.ws.disconnect()

        if self._http_client:
            await self._http_client.aclose()

        logger.info("DataSynchronizer stopped")

    async def subscribe_event(self, event_ticker: str) -> bool:
        """
        Subscribe to all markets in an event.
        Fetches market list via REST, then subscribes via WebSocket.
        """
        try:
            # Fetch event with markets from REST
            markets = await self._fetch_event_markets(event_ticker)

            if not markets:
                logger.warning(f"No markets found for event {event_ticker}")
                return False

            # Track markets
            market_tickers = []
            for market in markets:
                ticker = market.get('ticker')
                if ticker:
                    self._markets[ticker] = MarketState(ticker=ticker, market=market)
                    market_tickers.append(ticker)

            self._events[event_ticker] = set(market_tickers)

            # Subscribe via WebSocket
            if self.ws.is_connected:
                sid = await self.ws.subscribe(
                    channels=['orderbook_delta', 'ticker'],
                    market_tickers=market_tickers
                )

                if sid:
                    for ticker in market_tickers:
                        self._markets[ticker].subscribed = True
                    logger.info(f"Subscribed to {len(market_tickers)} markets for {event_ticker}")
                    return True

            # Fallback to REST if WebSocket unavailable
            logger.warning("WebSocket unavailable, using REST only")
            await self._fetch_orderbooks_rest(market_tickers)
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to event {event_ticker}: {e}")
            return False

    async def subscribe_markets(self, market_tickers: List[str]) -> bool:
        """
        Subscribe directly to specific markets.
        """
        try:
            # Track markets
            for ticker in market_tickers:
                if ticker not in self._markets:
                    self._markets[ticker] = MarketState(ticker=ticker)

            # Subscribe via WebSocket
            if self.ws.is_connected:
                sid = await self.ws.subscribe(
                    channels=['orderbook_delta', 'ticker'],
                    market_tickers=market_tickers
                )

                if sid:
                    for ticker in market_tickers:
                        self._markets[ticker].subscribed = True
                    logger.info(f"Subscribed to {len(market_tickers)} markets")
                    return True

            # Fallback to REST
            logger.warning("WebSocket unavailable, using REST only")
            await self._fetch_orderbooks_rest(market_tickers)
            return True

        except Exception as e:
            logger.error(f"Failed to subscribe to markets: {e}")
            return False

    async def _fetch_event_markets(self, event_ticker: str) -> List[dict]:
        """Fetch markets for an event via REST"""
        try:
            if not self._http_client:
                return []

            response = await self._http_client.get(
                f"/events/{event_ticker}",
                params={"with_nested_markets": "true"}
            )
            response.raise_for_status()
            data = response.json()
            return data.get('event', {}).get('markets', [])
        except Exception as e:
            logger.error(f"Failed to fetch event {event_ticker}: {e}")
            return []

    async def _fetch_orderbooks_rest(self, tickers: List[str]):
        """Fetch orderbooks via REST (fallback)"""
        if not self._http_client:
            return

        for ticker in tickers:
            try:
                response = await self._http_client.get(f"/markets/{ticker}/orderbook")
                if response.status_code == 200:
                    data = response.json()
                    ob_data = data.get('orderbook', {})

                    # Convert REST format to snapshot format for orderbook builder
                    snapshot = {
                        "type": "orderbook_snapshot",
                        "seq": 0,
                        "msg": {
                            "market_ticker": ticker,
                            "yes": [[l.get('price', 0), l.get('quantity', 0)]
                                   for l in ob_data.get('yes', [])],
                            "no": [[l.get('price', 0), l.get('quantity', 0)]
                                  for l in ob_data.get('no', [])]
                        }
                    }
                    self.ob_builder.handle_snapshot(snapshot)

                    if ticker in self._markets:
                        self._markets[ticker].last_rest_update = datetime.now(timezone.utc)

            except Exception as e:
                logger.error(f"Failed to fetch orderbook for {ticker}: {e}")

    def _on_orderbook_update(self, ticker: str, orderbook: Orderbook):
        """Handle orderbook update from WebSocket"""
        if ticker in self._markets:
            self._markets[ticker].orderbook = orderbook
            self._markets[ticker].last_ws_update = datetime.now(timezone.utc)

        # Notify listeners
        for callback in self._on_data_update:
            try:
                callback('orderbook', ticker, orderbook)
            except Exception as e:
                logger.error(f"Data update callback error: {e}")

    async def _on_ticker_update(self, message: dict):
        """Handle ticker update from WebSocket"""
        msg = message.get('msg', {})
        ticker = msg.get('market_ticker')

        if ticker and ticker in self._markets:
            state = self._markets[ticker]
            if state.market:
                state.market['yes_bid'] = msg.get('yes_bid')
                state.market['yes_ask'] = msg.get('yes_ask')
                state.market['last_price'] = msg.get('price')
                state.market['volume'] = msg.get('volume')
                state.market['open_interest'] = msg.get('open_interest')
            state.last_ws_update = datetime.now(timezone.utc)

    async def _rest_fallback_loop(self):
        """Periodic REST polling for stale data"""
        try:
            while True:
                await asyncio.sleep(self.rest_fallback_interval)

                # Find stale markets
                stale_tickers = [
                    ticker for ticker, state in self._markets.items()
                    if self._is_stale(state)
                ]

                if stale_tickers:
                    logger.info(f"Refreshing {len(stale_tickers)} stale markets via REST")
                    await self._fetch_orderbooks_rest(stale_tickers)

        except asyncio.CancelledError:
            pass

    def _is_stale(self, state: MarketState) -> bool:
        """Check if market data is stale"""
        if not state.last_ws_update and not state.last_rest_update:
            return True

        latest = max(
            state.last_ws_update or datetime.min.replace(tzinfo=timezone.utc),
            state.last_rest_update or datetime.min.replace(tzinfo=timezone.utc)
        )

        age = (datetime.now(timezone.utc) - latest).total_seconds()
        return age > self.stale_threshold

    def get_orderbook(self, ticker: str) -> Optional[Orderbook]:
        """Get current orderbook for a market"""
        # Prefer WebSocket data
        ob = self.ob_builder.get_orderbook(ticker)
        if ob:
            return ob

        # Fall back to cached state
        if ticker in self._markets:
            return self._markets[ticker].orderbook

        return None

    def get_all_orderbooks(self, event_ticker: Optional[str] = None) -> Dict[str, Orderbook]:
        """Get all orderbooks, optionally filtered by event"""
        if event_ticker and event_ticker in self._events:
            result = {}
            for ticker in self._events[event_ticker]:
                ob = self.get_orderbook(ticker)
                if ob:
                    result[ticker] = ob
            return result

        return self.ob_builder.get_all_orderbooks()

    def get_event_markets(self, event_ticker: str) -> List[str]:
        """Get list of market tickers for an event"""
        return list(self._events.get(event_ticker, set()))

    def is_data_fresh(self, ticker: str) -> bool:
        """Check if data for a market is fresh enough for trading"""
        if ticker not in self._markets:
            return False
        return not self._is_stale(self._markets[ticker])

    def get_staleness(self, ticker: str) -> Optional[float]:
        """Get age of data in seconds"""
        if ticker not in self._markets:
            return None

        state = self._markets[ticker]
        latest = max(
            state.last_ws_update or datetime.min.replace(tzinfo=timezone.utc),
            state.last_rest_update or datetime.min.replace(tzinfo=timezone.utc)
        )

        if latest == datetime.min.replace(tzinfo=timezone.utc):
            return None

        return (datetime.now(timezone.utc) - latest).total_seconds()

    def on_data_update(self, callback: Callable):
        """Register callback for data updates: callback(type, ticker, data)"""
        self._on_data_update.append(callback)

    def get_stats(self) -> dict:
        """Get synchronization statistics"""
        ws_stats = self.ws.get_stats()
        ob_stats = self.ob_builder.get_stats()

        fresh_count = sum(1 for t in self._markets if not self._is_stale(self._markets[t]))

        return {
            "websocket": ws_stats,
            "orderbooks": ob_stats,
            "tracked_markets": len(self._markets),
            "tracked_events": len(self._events),
            "fresh_markets": fresh_count,
            "stale_markets": len(self._markets) - fresh_count,
        }
