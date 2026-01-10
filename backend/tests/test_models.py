"""
Unit tests for data models.
"""

import pytest
from datetime import datetime, timezone, timedelta
from backend.models import (
    Market, Orderbook, Event, Position, Order,
    OrderbookLevelModel, NWSForecast, LocationConfig,
    MarketStatus, OrderSide, OrderAction, WeatherPattern,
    KALSHI_LOCATIONS,
)


class TestOrderbook:
    """Test orderbook logic"""

    def test_yes_ask_from_no_bids(self):
        """YES ask = 100 - best NO bid"""
        ob = Orderbook(
            ticker="TEST",
            yes_bids=[],
            no_bids=[
                OrderbookLevelModel(price_cents=45, quantity=100),
                OrderbookLevelModel(price_cents=40, quantity=200),
            ]
        )
        # Best NO bid is 45, so YES ask is 55
        assert ob.yes_ask() == 55

    def test_no_ask_from_yes_bids(self):
        """NO ask = 100 - best YES bid"""
        ob = Orderbook(
            ticker="TEST",
            yes_bids=[
                OrderbookLevelModel(price_cents=60, quantity=100),
                OrderbookLevelModel(price_cents=55, quantity=200),
            ],
            no_bids=[]
        )
        # Best YES bid is 60, so NO ask is 40
        assert ob.no_ask() == 40

    def test_take_yes_cost(self):
        """Calculate cost to buy YES contracts"""
        ob = Orderbook(
            ticker="TEST",
            yes_bids=[],
            no_bids=[
                OrderbookLevelModel(price_cents=45, quantity=100),  # YES @ 55
                OrderbookLevelModel(price_cents=40, quantity=100),  # YES @ 60
            ]
        )

        # Buy 50 YES - should fill at 55 cents
        result = ob.take_yes_cost(50)
        assert result['fillable'] == 50
        assert result['total_cost_cents'] == 50 * 55

        # Buy 150 YES - should fill 100 at 55, 50 at 60
        result = ob.take_yes_cost(150)
        assert result['fillable'] == 150
        assert result['total_cost_cents'] == (100 * 55) + (50 * 60)

    def test_take_yes_insufficient_liquidity(self):
        """Handle case where orderbook has less than requested"""
        ob = Orderbook(
            ticker="TEST",
            yes_bids=[],
            no_bids=[
                OrderbookLevelModel(price_cents=45, quantity=50),
            ]
        )

        result = ob.take_yes_cost(100)
        assert result['fillable'] == 50
        assert result['unfilled'] == 50

    def test_empty_orderbook(self):
        """Handle empty orderbook gracefully"""
        ob = Orderbook(ticker="TEST")

        assert ob.yes_ask() is None
        assert ob.no_ask() is None
        assert ob.best_yes_bid() is None
        assert ob.best_no_bid() is None

        result = ob.take_yes_cost(100)
        assert result['fillable'] == 0

    def test_take_no_cost(self):
        """Calculate cost to buy NO contracts"""
        ob = Orderbook(
            ticker="TEST",
            yes_bids=[
                OrderbookLevelModel(price_cents=60, quantity=100),  # NO @ 40
                OrderbookLevelModel(price_cents=55, quantity=100),  # NO @ 45
            ],
            no_bids=[]
        )

        # Buy 50 NO - should fill at 40 cents
        result = ob.take_no_cost(50)
        assert result['fillable'] == 50
        assert result['total_cost_cents'] == 50 * 40

        # Buy 150 NO - should fill 100 at 40, 50 at 45
        result = ob.take_no_cost(150)
        assert result['fillable'] == 150
        assert result['total_cost_cents'] == (100 * 40) + (50 * 45)

    def test_liquidity_at_price(self):
        """Test liquidity calculation at specific price"""
        ob = Orderbook(
            ticker="TEST",
            yes_bids=[],
            no_bids=[
                OrderbookLevelModel(price_cents=50, quantity=100),  # YES @ 50
                OrderbookLevelModel(price_cents=45, quantity=200),  # YES @ 55
                OrderbookLevelModel(price_cents=40, quantity=300),  # YES @ 60
            ]
        )

        # At price 55 or less, we have 100 + 200 = 300 YES available
        assert ob.yes_liquidity_at_price(55) == 300
        # At price 50 or less, we have only 100 YES available
        assert ob.yes_liquidity_at_price(50) == 100

    def test_orderbook_staleness(self):
        """Test if orderbook is stale"""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        ob = Orderbook(ticker="TEST", timestamp=old_time)

        assert ob.is_stale(max_age_seconds=5.0) is True
        assert ob.is_stale(max_age_seconds=15.0) is False


class TestMarket:
    """Test market model"""

    def test_strike_conversion_to_int(self):
        """Strikes should be integers, not floats"""
        m = Market(
            ticker="TEST-62-63",
            event_ticker="TEST",
            title="62-63°F",
            status=MarketStatus.OPEN,
            floor_strike=62.0,  # Float input
            cap_strike=63.0,
        )

        assert isinstance(m.floor_strike, int)
        assert isinstance(m.cap_strike, int)
        assert m.floor_strike == 62
        assert m.cap_strike == 63

    def test_bracket_label(self):
        """Test human-readable bracket labels"""
        m1 = Market(
            ticker="TEST", event_ticker="E", title="T",
            status=MarketStatus.OPEN,
            floor_strike=62, cap_strike=63
        )
        assert m1.bracket_label() == "62-63°F"

        m2 = Market(
            ticker="TEST", event_ticker="E", title="T",
            status=MarketStatus.OPEN,
            floor_strike=70, cap_strike=None
        )
        assert m2.bracket_label() == "≥70°F"

        m3 = Market(
            ticker="TEST", event_ticker="E", title="T",
            status=MarketStatus.OPEN,
            floor_strike=None, cap_strike=65
        )
        assert m3.bracket_label() == "<65°F"

    def test_timezone_aware_datetime(self):
        """Timestamps should be timezone-aware UTC"""
        m = Market(
            ticker="TEST",
            event_ticker="E",
            title="T",
            status=MarketStatus.OPEN,
            close_time="2025-01-10T22:00:00Z"
        )

        assert m.close_time is not None
        assert m.close_time.tzinfo is not None

    def test_is_near_settlement(self):
        """Detect markets close to settlement"""
        # Market closing in 1 hour
        m = Market(
            ticker="TEST",
            event_ticker="E",
            title="T",
            status=MarketStatus.OPEN,
            close_time=datetime.now(timezone.utc) + timedelta(hours=1)
        )

        assert m.is_near_settlement(threshold_hours=2.0) is True
        assert m.is_near_settlement(threshold_hours=0.5) is False

    def test_is_tradeable(self):
        """Test tradeable status"""
        m_open = Market(
            ticker="TEST", event_ticker="E", title="T",
            status=MarketStatus.OPEN
        )
        assert m_open.is_tradeable() is True

        m_closed = Market(
            ticker="TEST", event_ticker="E", title="T",
            status=MarketStatus.CLOSED
        )
        assert m_closed.is_tradeable() is False

    def test_data_staleness(self):
        """Test if market data is stale"""
        old_time = datetime.now(timezone.utc) - timedelta(seconds=60)
        m = Market(
            ticker="TEST", event_ticker="E", title="T",
            status=MarketStatus.OPEN,
            fetched_at=old_time
        )

        assert m.is_stale(max_age_seconds=30.0) is True
        assert m.is_stale(max_age_seconds=120.0) is False


class TestEvent:
    """Test event model"""

    def test_total_yes_cost(self):
        """Sum of YES asks across markets"""
        markets = [
            Market(ticker="M1", event_ticker="E", title="T", status=MarketStatus.OPEN, yes_ask=15),
            Market(ticker="M2", event_ticker="E", title="T", status=MarketStatus.OPEN, yes_ask=20),
            Market(ticker="M3", event_ticker="E", title="T", status=MarketStatus.OPEN, yes_ask=30),
            Market(ticker="M4", event_ticker="E", title="T", status=MarketStatus.OPEN, yes_ask=25),
        ]

        event = Event(
            event_ticker="E",
            series_ticker="S",
            title="Test",
            category="Test",
            mutually_exclusive=True,
            markets=markets
        )

        assert event.total_yes_cost() == 90  # < 100, arbitrage exists!

    def test_total_yes_cost_with_missing_ask(self):
        """Return None if any market missing YES ask"""
        markets = [
            Market(ticker="M1", event_ticker="E", title="T", status=MarketStatus.OPEN, yes_ask=15),
            Market(ticker="M2", event_ticker="E", title="T", status=MarketStatus.OPEN, yes_ask=None),
        ]

        event = Event(
            event_ticker="E",
            series_ticker="S",
            title="Test",
            category="Test",
            markets=markets
        )

        assert event.total_yes_cost() is None

    def test_mutually_exclusive_check(self):
        """Arbitrage only valid for mutually exclusive events"""
        event = Event(
            event_ticker="E",
            series_ticker="S",
            title="Test",
            category="Test",
            mutually_exclusive=False,
            markets=[]
        )

        assert event.has_arbitrage_opportunity() is False

    def test_open_markets_filtering(self):
        """Should only return tradeable markets"""
        markets = [
            Market(ticker="M1", event_ticker="E", title="T", status=MarketStatus.OPEN),
            Market(ticker="M2", event_ticker="E", title="T", status=MarketStatus.CLOSED),
            Market(ticker="M3", event_ticker="E", title="T", status=MarketStatus.OPEN),
        ]

        event = Event(
            event_ticker="E",
            series_ticker="S",
            title="Test",
            category="Test",
            markets=markets
        )

        assert len(event.open_markets()) == 2


class TestPosition:
    """Test position model"""

    def test_side_property(self):
        """Test position side determination"""
        yes_pos = Position(ticker="TEST", position=10)
        assert yes_pos.side == "yes"
        assert yes_pos.quantity == 10

        no_pos = Position(ticker="TEST", position=-10)
        assert no_pos.side == "no"
        assert no_pos.quantity == 10

        zero_pos = Position(ticker="TEST", position=0)
        assert zero_pos.side is None
        assert zero_pos.quantity == 0

    def test_unrealized_pnl(self):
        """Calculate unrealized P&L"""
        pos = Position(
            ticker="TEST",
            position=100,  # 100 YES contracts
            total_cost_cents=5000,  # Cost 50¢ each
        )

        # Current price 60¢
        pnl = pos.unrealized_pnl(60)
        assert pnl == (100 * 60) - 5000  # 6000 - 5000 = 1000 cents

        # Current price 40¢
        pnl = pos.unrealized_pnl(40)
        assert pnl == (100 * 40) - 5000  # 4000 - 5000 = -1000 cents


class TestOrder:
    """Test order model"""

    def test_to_api_payload(self):
        """Test conversion to Kalshi API format"""
        order = Order(
            ticker="TEST",
            side=OrderSide.YES,
            action=OrderAction.BUY,
            count=10,
            price_cents=55
        )

        payload = order.to_api_payload()

        assert payload["ticker"] == "TEST"
        assert payload["side"] == "yes"
        assert payload["action"] == "buy"
        assert payload["count"] == 10
        assert payload["yes_price"] == 55
        assert payload["type"] == "limit"

    def test_to_api_payload_with_options(self):
        """Test payload with optional fields"""
        order = Order(
            ticker="TEST",
            side=OrderSide.NO,
            action=OrderAction.BUY,
            count=10,
            price_cents=45,
            client_order_id="my-order-123",
            post_only=True
        )

        payload = order.to_api_payload()

        assert payload["no_price"] == 45
        assert payload["client_order_id"] == "my-order-123"
        assert payload["post_only"] is True


class TestNWSForecast:
    """Test weather forecast models"""

    def test_std_dev_by_pattern(self):
        """Standard deviation varies by weather pattern"""
        stable = NWSForecast(
            city="NYC", station_id="KNYC", grid_id="OKX",
            grid_x=33, grid_y=37,
            forecast_high=70, forecast_low=55,
            weather_pattern=WeatherPattern.STABLE,
            generated_at=datetime.now(timezone.utc)
        )

        stormy = NWSForecast(
            city="NYC", station_id="KNYC", grid_id="OKX",
            grid_x=33, grid_y=37,
            forecast_high=70, forecast_low=55,
            weather_pattern=WeatherPattern.STORMY,
            generated_at=datetime.now(timezone.utc)
        )

        assert stable.forecast_std_dev < stormy.forecast_std_dev

    def test_range_based_std_dev(self):
        """Use NWS range when provided"""
        forecast = NWSForecast(
            city="NYC", station_id="KNYC", grid_id="OKX",
            grid_x=33, grid_y=37,
            forecast_high=70, forecast_low=55,
            temperature_range_low=65,
            temperature_range_high=75,
            weather_pattern=WeatherPattern.TRANSITIONAL,
            generated_at=datetime.now(timezone.utc)
        )

        # Range is 10 degrees, so std dev ~2.5
        assert 2.0 < forecast.forecast_std_dev < 4.0

    def test_confidence_adjustment(self):
        """Lower confidence increases std dev"""
        high_confidence = NWSForecast(
            city="NYC", station_id="KNYC", grid_id="OKX",
            grid_x=33, grid_y=37,
            forecast_high=70, forecast_low=55,
            weather_pattern=WeatherPattern.STABLE,
            confidence_level=0.9,
            generated_at=datetime.now(timezone.utc)
        )

        low_confidence = NWSForecast(
            city="NYC", station_id="KNYC", grid_id="OKX",
            grid_x=33, grid_y=37,
            forecast_high=70, forecast_low=55,
            weather_pattern=WeatherPattern.STABLE,
            confidence_level=0.5,
            generated_at=datetime.now(timezone.utc)
        )

        assert high_confidence.forecast_std_dev < low_confidence.forecast_std_dev

    def test_forecast_staleness(self):
        """Test if forecast is stale"""
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        forecast = NWSForecast(
            city="NYC", station_id="KNYC", grid_id="OKX",
            grid_x=33, grid_y=37,
            forecast_high=70, forecast_low=55,
            generated_at=old_time,
            fetched_at=old_time
        )

        assert forecast.is_stale(max_age_hours=1.0) is True
        assert forecast.is_stale(max_age_hours=3.0) is False


class TestLocationConfig:
    """Test location configurations"""

    def test_all_locations_valid(self):
        """All pre-configured locations should be valid"""
        for code, config in KALSHI_LOCATIONS.items():
            assert config.city is not None
            assert config.series_ticker.startswith("KXHIGH")
            assert config.station_id.startswith("K")
            assert -180 <= config.longitude <= 180
            assert -90 <= config.latitude <= 90
            assert len(code) == 3  # All codes should be 3 letters

    def test_specific_locations(self):
        """Test specific known locations"""
        nyc = KALSHI_LOCATIONS["NYC"]
        assert nyc.city == "New York"
        assert nyc.series_ticker == "KXHIGHNY"
        assert nyc.timezone == "America/New_York"

        chi = KALSHI_LOCATIONS["CHI"]
        assert chi.city == "Chicago"
        assert chi.timezone == "America/Chicago"


class TestEnums:
    """Test enum definitions"""

    def test_market_status_enum(self):
        """Test MarketStatus enum values"""
        assert MarketStatus.OPEN.value == "open"
        assert MarketStatus.CLOSED.value == "closed"
        assert MarketStatus.SETTLED.value == "settled"

    def test_order_side_enum(self):
        """Test OrderSide enum values"""
        assert OrderSide.YES.value == "yes"
        assert OrderSide.NO.value == "no"

    def test_weather_pattern_enum(self):
        """Test WeatherPattern enum values"""
        assert WeatherPattern.STABLE.value == "stable"
        assert WeatherPattern.STORMY.value == "stormy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
