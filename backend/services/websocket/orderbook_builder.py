"""
Builds and maintains orderbook state from WebSocket deltas.

CRITICAL UNDERSTANDING:
- Kalshi WebSocket sends snapshots, then deltas
- Deltas are CHANGES to quantity at a price level
- delta = -50 means "50 fewer contracts at this price"
- delta = 0 or removing a level means "no contracts at this price"
"""

import logging
from typing import Dict, Optional, List, Callable
from datetime import datetime, timezone
from dataclasses import dataclass, field
from threading import Lock

from ..log_config import get_logger

logger = get_logger("orderbook_builder")


@dataclass
class OrderbookLevelModel:
    """Single price level in an orderbook"""
    price_cents: int
    quantity: int


@dataclass
class Orderbook:
    """Complete orderbook state for a market"""
    ticker: str
    yes_bids: List[OrderbookLevelModel] = field(default_factory=list)
    no_bids: List[OrderbookLevelModel] = field(default_factory=list)
    sequence: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class OrderbookState:
    """Internal state for a single orderbook"""
    ticker: str
    yes_bids: Dict[int, int] = field(default_factory=dict)  # price -> quantity
    no_bids: Dict[int, int] = field(default_factory=dict)
    sequence: int = 0
    last_update: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    snapshot_received: bool = False


class OrderbookBuilder:
    """
    Maintains orderbook state for multiple markets.
    Thread-safe for concurrent updates.

    Usage:
        builder = OrderbookBuilder()

        # Register for updates
        ws_manager.on('orderbook_snapshot', builder.handle_snapshot)
        ws_manager.on('orderbook_delta', builder.handle_delta)

        # Get current orderbook
        ob = builder.get_orderbook("HIGHNY-25JAN10-B2")
    """

    def __init__(self, stale_threshold_seconds: float = 5.0):
        self._books: Dict[str, OrderbookState] = {}
        self._lock = Lock()
        self.stale_threshold = stale_threshold_seconds

        # Callbacks for orderbook changes
        self._on_update_callbacks: List[Callable] = []

    def on_update(self, callback: Callable):
        """Register callback for orderbook updates: callback(ticker, orderbook)"""
        self._on_update_callbacks.append(callback)

    def handle_snapshot(self, message: dict):
        """
        Process orderbook_snapshot message.

        Message format:
        {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TICKER",
                "yes": [[price, qty], ...],
                "no": [[price, qty], ...]
            }
        }
        """
        msg = message.get('msg', {})
        ticker = msg.get('market_ticker')
        seq = message.get('seq', 0)

        if not ticker:
            logger.warning("Snapshot missing market_ticker")
            return

        with self._lock:
            state = OrderbookState(ticker=ticker)

            # Parse YES bids
            for level in msg.get('yes', []):
                if len(level) >= 2:
                    price, qty = int(level[0]), int(level[1])
                    if qty > 0:
                        state.yes_bids[price] = qty

            # Parse NO bids
            for level in msg.get('no', []):
                if len(level) >= 2:
                    price, qty = int(level[0]), int(level[1])
                    if qty > 0:
                        state.no_bids[price] = qty

            state.sequence = seq
            state.snapshot_received = True
            state.last_update = datetime.now(timezone.utc)

            self._books[ticker] = state

        logger.debug(f"Snapshot for {ticker}: {len(state.yes_bids)} YES, {len(state.no_bids)} NO levels")
        self._notify_update(ticker)

    def handle_delta(self, message: dict):
        """
        Process orderbook_delta message.

        Message format:
        {
            "type": "orderbook_delta",
            "sid": 1,
            "seq": 2,
            "msg": {
                "market_ticker": "TICKER",
                "price": 55,
                "delta": -50,
                "side": "yes"
            }
        }
        """
        msg = message.get('msg', {})
        ticker = msg.get('market_ticker')
        price = msg.get('price')
        delta = msg.get('delta')
        side = msg.get('side')
        seq = message.get('seq', 0)

        if not all([ticker, price is not None, delta is not None, side]):
            logger.warning(f"Invalid delta message: {msg}")
            return

        with self._lock:
            if ticker not in self._books:
                logger.warning(f"Delta for unknown ticker {ticker}, ignoring")
                return

            state = self._books[ticker]

            # Check sequence
            if seq != state.sequence + 1 and state.sequence > 0:
                logger.warning(f"Sequence gap for {ticker}: expected {state.sequence + 1}, got {seq}")
                # Could trigger resubscribe here for fresh snapshot

            state.sequence = seq
            state.last_update = datetime.now(timezone.utc)

            # Apply delta
            book = state.yes_bids if side == 'yes' else state.no_bids
            price = int(price)
            delta = int(delta)

            current_qty = book.get(price, 0)
            new_qty = current_qty + delta

            if new_qty <= 0:
                book.pop(price, None)
            else:
                book[price] = new_qty

        logger.debug(f"Delta for {ticker}: {side} @ {price} delta={delta}")
        self._notify_update(ticker)

    def _notify_update(self, ticker: str):
        """Notify registered callbacks of orderbook update"""
        orderbook = self.get_orderbook(ticker)
        if orderbook:
            for callback in self._on_update_callbacks:
                try:
                    callback(ticker, orderbook)
                except Exception as e:
                    logger.error(f"Update callback error: {e}")

    def get_orderbook(self, ticker: str) -> Optional[Orderbook]:
        """
        Get current orderbook for a market.
        Returns None if no data available.
        """
        with self._lock:
            if ticker not in self._books:
                return None

            state = self._books[ticker]

            if not state.snapshot_received:
                return None

            # Convert internal state to Orderbook model
            yes_bids = [
                OrderbookLevelModel(price_cents=price, quantity=qty)
                for price, qty in sorted(state.yes_bids.items(), reverse=True)
            ]

            no_bids = [
                OrderbookLevelModel(price_cents=price, quantity=qty)
                for price, qty in sorted(state.no_bids.items(), reverse=True)
            ]

            return Orderbook(
                ticker=ticker,
                yes_bids=yes_bids,
                no_bids=no_bids,
                sequence=state.sequence,
                timestamp=state.last_update,
            )

    def get_all_orderbooks(self) -> Dict[str, Orderbook]:
        """Get all current orderbooks"""
        result = {}
        with self._lock:
            for ticker in self._books:
                ob = self.get_orderbook(ticker)
                if ob:
                    result[ticker] = ob
        return result

    def is_stale(self, ticker: str) -> bool:
        """Check if orderbook data is stale"""
        with self._lock:
            if ticker not in self._books:
                return True

            state = self._books[ticker]
            age = (datetime.now(timezone.utc) - state.last_update).total_seconds()
            return age > self.stale_threshold

    def get_staleness(self, ticker: str) -> Optional[float]:
        """Get age of orderbook data in seconds"""
        with self._lock:
            if ticker not in self._books:
                return None

            state = self._books[ticker]
            return (datetime.now(timezone.utc) - state.last_update).total_seconds()

    def clear(self, ticker: Optional[str] = None):
        """Clear orderbook data"""
        with self._lock:
            if ticker:
                self._books.pop(ticker, None)
            else:
                self._books.clear()

    def get_stats(self) -> dict:
        """Get builder statistics"""
        with self._lock:
            stale_count = sum(1 for t in self._books if self.is_stale(t))
            return {
                "total_books": len(self._books),
                "stale_books": stale_count,
                "fresh_books": len(self._books) - stale_count,
            }

    def get_best_bid(self, ticker: str, side: str = "yes") -> Optional[OrderbookLevelModel]:
        """Get best bid for a side (highest price with quantity)"""
        ob = self.get_orderbook(ticker)
        if not ob:
            return None

        bids = ob.yes_bids if side == "yes" else ob.no_bids
        return bids[0] if bids else None

    def get_mid_price(self, ticker: str) -> Optional[float]:
        """Get mid price between best yes and no bids"""
        ob = self.get_orderbook(ticker)
        if not ob or not ob.yes_bids or not ob.no_bids:
            return None

        best_yes = ob.yes_bids[0].price_cents
        best_no = ob.no_bids[0].price_cents
        # In prediction markets, yes_price + no_price should equal 100
        return best_yes  # Return yes price as the reference
