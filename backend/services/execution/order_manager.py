"""
Order lifecycle management.
Tracks orders, fills, and maintains order history.
"""

import asyncio
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import deque

from backend.services.log_config import get_logger

logger = get_logger("order_manager")


@dataclass
class TrackedOrder:
    """Tracked order with full lifecycle"""
    order_id: str
    client_order_id: str
    ticker: str
    side: str
    action: str

    # Quantities
    initial_count: int
    filled_count: int = 0
    remaining_count: int = 0

    # Prices
    requested_price: int = 0
    avg_fill_price: Optional[float] = None

    # Status: pending, resting, partial, executed, canceled, expired
    status: str = "pending"

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Fees
    taker_fees: float = 0.0
    maker_fees: float = 0.0

    # Fills
    fills: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "order_id": self.order_id,
            "client_order_id": self.client_order_id,
            "ticker": self.ticker,
            "side": self.side,
            "action": self.action,
            "initial_count": self.initial_count,
            "filled_count": self.filled_count,
            "remaining_count": self.remaining_count,
            "requested_price": self.requested_price,
            "avg_fill_price": self.avg_fill_price,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "taker_fees": self.taker_fees,
            "maker_fees": self.maker_fees,
            "total_fees": self.taker_fees + self.maker_fees,
            "fills_count": len(self.fills),
        }


class OrderManager:
    """
    Manages order lifecycle and history.

    Responsibilities:
    - Track active orders
    - Record fill history
    - Calculate P&L per order
    - Support order reconciliation

    Usage:
        manager = OrderManager()

        # Track new order
        manager.track_order(order_response)

        # Update from WebSocket fill
        manager.record_fill(fill_message)

        # Get order status
        order = manager.get_order("order_123")
    """

    def __init__(self, max_history: int = 1000):
        self._orders: Dict[str, TrackedOrder] = {}
        self._orders_by_client_id: Dict[str, str] = {}  # client_id -> order_id
        self._order_history: deque = deque(maxlen=max_history)
        self._pending_orders: Set[str] = set()
        self._lock = asyncio.Lock()

    async def track_order(self, order_data: dict) -> TrackedOrder:
        """
        Start tracking an order from API response.

        Args:
            order_data: Order data from Kalshi API

        Returns:
            TrackedOrder object
        """
        async with self._lock:
            order_id = order_data.get('order_id', order_data.get('id', ''))
            client_order_id = order_data.get('client_order_id', '')

            # Handle counts
            initial_count = order_data.get('count', order_data.get('initial_count', 0))
            filled_count = order_data.get('fill_count', 0)
            remaining_count = order_data.get('remaining_count', initial_count - filled_count)

            # Get price
            requested_price = (
                order_data.get('yes_price') or
                order_data.get('no_price') or
                order_data.get('price', 0)
            )

            tracked = TrackedOrder(
                order_id=order_id,
                client_order_id=client_order_id,
                ticker=order_data.get('ticker', ''),
                side=order_data.get('side', ''),
                action=order_data.get('action', ''),
                initial_count=initial_count,
                filled_count=filled_count,
                remaining_count=remaining_count,
                requested_price=requested_price,
                status=order_data.get('status', 'pending'),
            )

            self._orders[order_id] = tracked
            if client_order_id:
                self._orders_by_client_id[client_order_id] = order_id

            if tracked.status in ['pending', 'resting']:
                self._pending_orders.add(order_id)

            logger.debug(f"Tracking order {order_id}: {tracked.side} {tracked.action} {tracked.initial_count}x @ {tracked.requested_price}c")

            return tracked

    async def record_fill(self, fill_data: dict) -> Optional[TrackedOrder]:
        """
        Record a fill from WebSocket or API.

        Args:
            fill_data: Fill data from WebSocket fill message or API

        Returns:
            Updated TrackedOrder or None if order not found
        """
        async with self._lock:
            order_id = fill_data.get('order_id')

            if not order_id or order_id not in self._orders:
                # Try client_order_id
                client_id = fill_data.get('client_order_id')
                if client_id and client_id in self._orders_by_client_id:
                    order_id = self._orders_by_client_id[client_id]
                else:
                    logger.warning(f"Fill for unknown order: {fill_data}")
                    return None

            order = self._orders[order_id]

            fill_count = fill_data.get('count', 0)
            fill_price = fill_data.get('yes_price', fill_data.get('no_price', 0))
            is_taker = fill_data.get('is_taker', True)

            # Update order
            order.filled_count += fill_count
            order.remaining_count = order.initial_count - order.filled_count
            order.last_updated = datetime.now(timezone.utc)

            # Calculate average fill price
            if order.avg_fill_price is None:
                order.avg_fill_price = float(fill_price)
            else:
                total_filled = order.filled_count
                prev_filled = total_filled - fill_count
                if total_filled > 0:
                    order.avg_fill_price = (
                        (order.avg_fill_price * prev_filled + fill_price * fill_count) / total_filled
                    )

            # Track fees
            fee_cents = fill_data.get('fee_cents', fill_data.get('fees', 0))
            if is_taker:
                order.taker_fees += fee_cents
            else:
                order.maker_fees += fee_cents

            # Record fill
            order.fills.append({
                'fill_id': fill_data.get('fill_id'),
                'trade_id': fill_data.get('trade_id'),
                'count': fill_count,
                'price': fill_price,
                'is_taker': is_taker,
                'fee_cents': fee_cents,
                'timestamp': datetime.now(timezone.utc).isoformat(),
            })

            # Update status
            if order.remaining_count <= 0:
                order.status = 'executed'
                self._pending_orders.discard(order_id)
                self._order_history.append(order)
            elif order.filled_count > 0:
                order.status = 'partial'

            logger.debug(f"Fill recorded for {order_id}: {fill_count}x @ {fill_price}c, total filled: {order.filled_count}/{order.initial_count}")

            return order

    async def update_order_status(
        self,
        order_id: str,
        status: str,
        reason: Optional[str] = None
    ) -> Optional[TrackedOrder]:
        """Update order status (e.g., from cancel)"""
        async with self._lock:
            if order_id not in self._orders:
                return None

            order = self._orders[order_id]
            order.status = status
            order.last_updated = datetime.now(timezone.utc)

            if status in ['canceled', 'executed', 'expired']:
                self._pending_orders.discard(order_id)
                self._order_history.append(order)

            if reason:
                logger.info(f"Order {order_id} status -> {status}: {reason}")
            else:
                logger.info(f"Order {order_id} status -> {status}")

            return order

    def get_order(self, order_id: str) -> Optional[TrackedOrder]:
        """Get order by ID"""
        return self._orders.get(order_id)

    def get_order_by_client_id(self, client_order_id: str) -> Optional[TrackedOrder]:
        """Get order by client order ID"""
        order_id = self._orders_by_client_id.get(client_order_id)
        if order_id:
            return self._orders.get(order_id)
        return None

    def get_pending_orders(self) -> List[TrackedOrder]:
        """Get all pending/resting orders"""
        return [self._orders[oid] for oid in self._pending_orders if oid in self._orders]

    def get_orders_for_ticker(self, ticker: str) -> List[TrackedOrder]:
        """Get all orders for a specific ticker"""
        return [o for o in self._orders.values() if o.ticker == ticker]

    def get_recent_fills(self, limit: int = 50) -> List[dict]:
        """Get recent fills across all orders"""
        all_fills = []
        for order in self._orders.values():
            for fill in order.fills:
                fill_with_order = {
                    **fill,
                    'ticker': order.ticker,
                    'side': order.side,
                    'action': order.action,
                    'order_id': order.order_id,
                }
                all_fills.append(fill_with_order)

        # Sort by timestamp descending
        all_fills.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return all_fills[:limit]

    def calculate_order_pnl(self, order_id: str, current_price: int) -> Optional[float]:
        """Calculate P&L for an order at current price"""
        order = self._orders.get(order_id)
        if not order or order.filled_count == 0:
            return None

        # Cost basis
        cost = order.filled_count * (order.avg_fill_price or 0)
        fees = order.taker_fees + order.maker_fees

        # Current value
        if order.action == 'buy':
            value = order.filled_count * current_price
            return value - cost - fees
        else:  # sell
            return cost - (order.filled_count * current_price) - fees

    def get_stats(self) -> dict:
        """Get order manager statistics"""
        total_orders = len(self._orders)
        pending_count = len(self._pending_orders)
        executed_count = sum(1 for o in self._orders.values() if o.status == 'executed')
        canceled_count = sum(1 for o in self._orders.values() if o.status == 'canceled')
        partial_count = sum(1 for o in self._orders.values() if o.status == 'partial')

        total_fills = sum(len(o.fills) for o in self._orders.values())
        total_fees = sum(o.taker_fees + o.maker_fees for o in self._orders.values())

        return {
            "total_orders": total_orders,
            "pending": pending_count,
            "executed": executed_count,
            "canceled": canceled_count,
            "partial": partial_count,
            "history_size": len(self._order_history),
            "total_fills": total_fills,
            "total_fees_cents": total_fees,
        }

    async def clear_completed(self):
        """Remove completed orders from active tracking"""
        async with self._lock:
            completed = [
                oid for oid, order in self._orders.items()
                if order.status in ['executed', 'canceled', 'expired']
            ]

            for oid in completed:
                order = self._orders.pop(oid)
                if order.client_order_id in self._orders_by_client_id:
                    self._orders_by_client_id.pop(order.client_order_id)

            logger.info(f"Cleared {len(completed)} completed orders")

    async def sync_with_api(self, kalshi_client) -> int:
        """
        Sync orders with Kalshi API.

        Fetches recent orders and fills to reconcile state.

        Args:
            kalshi_client: KalshiClient instance

        Returns:
            Number of orders synced
        """
        try:
            # Get recent orders
            orders = await kalshi_client.get_orders(limit=100)

            synced = 0
            for order_data in orders:
                order_id = order_data.get('order_id', '')
                if order_id and order_id not in self._orders:
                    await self.track_order(order_data)
                    synced += 1
                elif order_id:
                    # Update existing order
                    order = self._orders[order_id]
                    order.status = order_data.get('status', order.status)
                    order.filled_count = order_data.get('fill_count', order.filled_count)
                    order.remaining_count = order_data.get('remaining_count', order.remaining_count)
                    order.last_updated = datetime.now(timezone.utc)

            logger.info(f"Synced {synced} new orders from API")
            return synced

        except Exception as e:
            logger.error(f"Failed to sync orders: {e}")
            return 0
