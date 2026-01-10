"""
Tests for WebSocket infrastructure.
"""

import pytest
import time
from datetime import datetime, timezone

from backend.services.websocket.orderbook_builder import (
    OrderbookBuilder,
    Orderbook,
    OrderbookLevelModel,
)


class TestOrderbookBuilder:
    """Tests for OrderbookBuilder without actual WebSocket"""

    def test_handle_snapshot(self):
        """Test processing orderbook snapshot"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST-MARKET",
                "yes": [[55, 100], [50, 200]],
                "no": [[45, 150], [40, 100]]
            }
        }

        builder.handle_snapshot(snapshot)

        ob = builder.get_orderbook("TEST-MARKET")
        assert ob is not None
        assert len(ob.yes_bids) == 2
        assert len(ob.no_bids) == 2
        assert ob.sequence == 1

    def test_snapshot_ordering(self):
        """Test that bids are ordered by price descending"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[30, 100], [50, 200], [40, 150]],
                "no": []
            }
        }

        builder.handle_snapshot(snapshot)

        ob = builder.get_orderbook("TEST")
        assert ob.yes_bids[0].price_cents == 50  # Highest first
        assert ob.yes_bids[1].price_cents == 40
        assert ob.yes_bids[2].price_cents == 30

    def test_handle_delta_add(self):
        """Test delta that adds to existing level"""
        builder = OrderbookBuilder()

        # First, snapshot
        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[55, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        # Then delta adding 50
        delta = {
            "type": "orderbook_delta",
            "sid": 1,
            "seq": 2,
            "msg": {
                "market_ticker": "TEST",
                "price": 55,
                "delta": 50,
                "side": "yes"
            }
        }
        builder.handle_delta(delta)

        ob = builder.get_orderbook("TEST")
        assert ob.yes_bids[0].quantity == 150  # 100 + 50

    def test_handle_delta_new_level(self):
        """Test delta that creates a new price level"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[55, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        # Add new level at price 60
        delta = {
            "type": "orderbook_delta",
            "sid": 1,
            "seq": 2,
            "msg": {
                "market_ticker": "TEST",
                "price": 60,
                "delta": 75,
                "side": "yes"
            }
        }
        builder.handle_delta(delta)

        ob = builder.get_orderbook("TEST")
        assert len(ob.yes_bids) == 2
        assert ob.yes_bids[0].price_cents == 60  # New level is highest
        assert ob.yes_bids[0].quantity == 75

    def test_handle_delta_remove(self):
        """Test delta that removes from level"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[55, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        # Remove all quantity
        delta = {
            "type": "orderbook_delta",
            "sid": 1,
            "seq": 2,
            "msg": {
                "market_ticker": "TEST",
                "price": 55,
                "delta": -100,
                "side": "yes"
            }
        }
        builder.handle_delta(delta)

        ob = builder.get_orderbook("TEST")
        assert len(ob.yes_bids) == 0  # Level removed

    def test_handle_delta_partial_remove(self):
        """Test delta that partially removes from level"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[55, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        delta = {
            "type": "orderbook_delta",
            "sid": 1,
            "seq": 2,
            "msg": {
                "market_ticker": "TEST",
                "price": 55,
                "delta": -30,
                "side": "yes"
            }
        }
        builder.handle_delta(delta)

        ob = builder.get_orderbook("TEST")
        assert ob.yes_bids[0].quantity == 70  # 100 - 30

    def test_sequence_tracking(self):
        """Test sequence number tracking"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[55, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        delta = {
            "type": "orderbook_delta",
            "sid": 1,
            "seq": 2,
            "msg": {
                "market_ticker": "TEST",
                "price": 55,
                "delta": 10,
                "side": "yes"
            }
        }
        builder.handle_delta(delta)

        ob = builder.get_orderbook("TEST")
        assert ob.sequence == 2

    def test_staleness_detection(self):
        """Test stale data detection"""
        builder = OrderbookBuilder(stale_threshold_seconds=0.1)

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[55, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        # Should not be stale immediately
        assert not builder.is_stale("TEST")

        # Wait and check again
        time.sleep(0.2)
        assert builder.is_stale("TEST")

    def test_unknown_ticker_delta_ignored(self):
        """Delta for unknown ticker should be ignored"""
        builder = OrderbookBuilder()

        delta = {
            "type": "orderbook_delta",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "UNKNOWN",
                "price": 55,
                "delta": 100,
                "side": "yes"
            }
        }
        builder.handle_delta(delta)

        assert builder.get_orderbook("UNKNOWN") is None

    def test_missing_ticker_in_snapshot(self):
        """Snapshot without market_ticker should be ignored"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "yes": [[55, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        assert builder.get_stats()["total_books"] == 0

    def test_no_bids_side(self):
        """Test handling NO side deltas"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [],
                "no": [[45, 100]]
            }
        }
        builder.handle_snapshot(snapshot)

        delta = {
            "type": "orderbook_delta",
            "sid": 1,
            "seq": 2,
            "msg": {
                "market_ticker": "TEST",
                "price": 45,
                "delta": 25,
                "side": "no"
            }
        }
        builder.handle_delta(delta)

        ob = builder.get_orderbook("TEST")
        assert len(ob.no_bids) == 1
        assert ob.no_bids[0].quantity == 125  # 100 + 25

    def test_get_all_orderbooks(self):
        """Test getting all orderbooks"""
        builder = OrderbookBuilder()

        for i, ticker in enumerate(["MARKET-1", "MARKET-2", "MARKET-3"]):
            snapshot = {
                "type": "orderbook_snapshot",
                "sid": i + 1,
                "seq": 1,
                "msg": {
                    "market_ticker": ticker,
                    "yes": [[50 + i, 100]],
                    "no": []
                }
            }
            builder.handle_snapshot(snapshot)

        all_books = builder.get_all_orderbooks()
        assert len(all_books) == 3
        assert "MARKET-1" in all_books
        assert "MARKET-2" in all_books
        assert "MARKET-3" in all_books

    def test_clear_single(self):
        """Test clearing a single orderbook"""
        builder = OrderbookBuilder()

        for ticker in ["MARKET-1", "MARKET-2"]:
            snapshot = {
                "type": "orderbook_snapshot",
                "sid": 1,
                "seq": 1,
                "msg": {
                    "market_ticker": ticker,
                    "yes": [[50, 100]],
                    "no": []
                }
            }
            builder.handle_snapshot(snapshot)

        builder.clear("MARKET-1")

        assert builder.get_orderbook("MARKET-1") is None
        assert builder.get_orderbook("MARKET-2") is not None

    def test_clear_all(self):
        """Test clearing all orderbooks"""
        builder = OrderbookBuilder()

        for ticker in ["MARKET-1", "MARKET-2"]:
            snapshot = {
                "type": "orderbook_snapshot",
                "sid": 1,
                "seq": 1,
                "msg": {
                    "market_ticker": ticker,
                    "yes": [[50, 100]],
                    "no": []
                }
            }
            builder.handle_snapshot(snapshot)

        builder.clear()

        assert builder.get_stats()["total_books"] == 0

    def test_get_staleness(self):
        """Test getting staleness value"""
        builder = OrderbookBuilder()

        # Unknown ticker
        assert builder.get_staleness("UNKNOWN") is None

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[50, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        staleness = builder.get_staleness("TEST")
        assert staleness is not None
        assert staleness < 1.0  # Should be very recent

    def test_on_update_callback(self):
        """Test that update callbacks are called"""
        builder = OrderbookBuilder()

        updates = []

        def callback(ticker, orderbook):
            updates.append((ticker, orderbook))

        builder.on_update(callback)

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[50, 100]],
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        assert len(updates) == 1
        assert updates[0][0] == "TEST"
        assert isinstance(updates[0][1], Orderbook)

    def test_get_best_bid(self):
        """Test getting best bid"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[55, 100], [50, 200]],
                "no": [[45, 150]]
            }
        }
        builder.handle_snapshot(snapshot)

        best_yes = builder.get_best_bid("TEST", "yes")
        assert best_yes is not None
        assert best_yes.price_cents == 55

        best_no = builder.get_best_bid("TEST", "no")
        assert best_no is not None
        assert best_no.price_cents == 45

    def test_zero_quantity_removed(self):
        """Test that zero quantity levels are not stored"""
        builder = OrderbookBuilder()

        snapshot = {
            "type": "orderbook_snapshot",
            "sid": 1,
            "seq": 1,
            "msg": {
                "market_ticker": "TEST",
                "yes": [[55, 0], [50, 100]],  # First level has 0 qty
                "no": []
            }
        }
        builder.handle_snapshot(snapshot)

        ob = builder.get_orderbook("TEST")
        assert len(ob.yes_bids) == 1
        assert ob.yes_bids[0].price_cents == 50


class TestOrderbookModel:
    """Tests for Orderbook data model"""

    def test_orderbook_creation(self):
        """Test creating an Orderbook"""
        ob = Orderbook(
            ticker="TEST",
            yes_bids=[OrderbookLevelModel(price_cents=55, quantity=100)],
            no_bids=[OrderbookLevelModel(price_cents=45, quantity=50)],
            sequence=1
        )

        assert ob.ticker == "TEST"
        assert len(ob.yes_bids) == 1
        assert len(ob.no_bids) == 1

    def test_orderbook_level_model(self):
        """Test OrderbookLevelModel"""
        level = OrderbookLevelModel(price_cents=55, quantity=100)
        assert level.price_cents == 55
        assert level.quantity == 100
