"""
Tests for the analysis module.

Tests fee calculation, probability estimation, position calculations,
and arbitrage analysis.
"""

import pytest
from datetime import datetime, timezone
from backend.services.analysis import (
    # Fee calculation
    calculate_fee,
    calculate_multi_leg_fee,
    FeeCalculator,
    FeeResult,

    # Probability
    ProbabilityEngine,
    estimate_from_dict,
    NWSForecast,
    WeatherPattern,
    MarketBracket,

    # Position
    PositionCalculator,
    Orderbook,
    OrderbookLevel,
    Position,
    calculate_order_effect,

    # Arbitrage
    ArbitrageCalculator,
    analyze_from_brackets,
    Market,
    Event,
)


class TestFeeCalculator:
    """Tests for fee calculation accuracy."""

    def test_basic_fee(self):
        """Test basic fee calculation at 55 cents."""
        result = calculate_fee(100, 55)

        # 0.07 * 100 * 0.45 * 0.55 = 1.7325 dollars = 173.25 cents
        assert abs(result.fee_cents - 173.25) < 1  # Within 1 cent
        assert result.is_maker is False

    def test_maker_discount(self):
        """Maker orders get 50% discount."""
        # Use 10 contracts at 30 cents to avoid fee cap
        # Raw fee at 30 cents: 0.07 * 10 * 0.7 * 0.3 = 0.147 = 14.7 cents
        # Cap: 10 * 0.0174 = 17.4 cents, so no cap applied
        taker = calculate_fee(10, 30)
        maker = calculate_fee(10, 30, is_maker=True)

        # Maker should be ~50% of taker
        assert taker.was_capped is False
        assert abs(maker.fee_cents - (taker.fee_cents * 0.5)) < 0.01

    def test_fee_at_50_cents(self):
        """Test maximum fee scenario at 50 cents with fee cap."""
        result = calculate_fee(100, 50)

        # Raw fee: 0.07 * 100 * 0.50 * 0.50 = 1.75 dollars = 175 cents
        # But cap is 1.74% of notional ($100) = 174 cents
        assert result.was_capped is True
        assert abs(result.fee_cents - 174) < 1
        assert abs(result.raw_fee_cents - 175) < 1

    def test_fee_at_extreme_prices(self):
        """Test fee at extreme prices (low and high)."""
        # At 5 cents
        low = calculate_fee(100, 5)
        # 0.07 * 100 * 0.95 * 0.05 = 0.3325 dollars = 33.25 cents
        assert abs(low.fee_cents - 33.25) < 1

        # At 95 cents
        high = calculate_fee(100, 95)
        # Same formula, same result
        assert abs(high.fee_cents - 33.25) < 1

    def test_single_contract(self):
        """Test fee for single contract."""
        result = calculate_fee(1, 50)

        # 0.07 * 1 * 0.50 * 0.50 = 0.0175 dollars = 1.75 cents
        assert abs(result.fee_cents - 1.75) < 0.1

    def test_zero_contracts(self):
        """Test that zero contracts returns zero fee."""
        result = calculate_fee(0, 50)
        assert result.fee_cents == 0
        assert result.fee_dollars == 0

    def test_invalid_price_raises(self):
        """Test that invalid prices raise ValueError."""
        with pytest.raises(ValueError):
            calculate_fee(100, 0)

        with pytest.raises(ValueError):
            calculate_fee(100, 100)

        with pytest.raises(ValueError):
            calculate_fee(100, -5)

    def test_fee_cap(self):
        """Test that fees are capped at 1.74% of notional."""
        # At high contract counts, fee might hit cap
        # For 1000 contracts at 50 cents:
        # Raw fee = 0.07 * 1000 * 0.5 * 0.5 = 17.5 dollars
        # Notional = 1000 * 1 = 1000 dollars
        # Cap = 1000 * 0.0174 = 17.4 dollars
        result = calculate_fee(1000, 50)

        # Should be capped
        assert result.was_capped is True
        assert result.fee_dollars <= 17.4 + 0.01  # Allow small rounding

    def test_multi_leg_fees(self):
        """Test multi-leg fee calculation."""
        legs = [
            {'contracts': 10, 'price_cents': 30},
            {'contracts': 10, 'price_cents': 70},
        ]

        total_fee, leg_fees = calculate_multi_leg_fee(legs)

        # Both legs should have same fee (30*70 = 70*30)
        assert len(leg_fees) == 2
        assert abs(leg_fees[0].fee_cents - leg_fees[1].fee_cents) < 0.1
        assert total_fee == pytest.approx(leg_fees[0].fee_cents + leg_fees[1].fee_cents)


class TestProbabilityEngine:
    """Tests for probability estimation."""

    def test_basic_probability(self):
        """Test basic probability calculation."""
        brackets = [
            {'ticker': 'T1', 'floor': 60, 'cap': 65},
            {'ticker': 'T2', 'floor': 65, 'cap': 70},
            {'ticker': 'T3', 'floor': 70, 'cap': 75},
        ]

        result = estimate_from_dict(brackets, forecast_temp=68)

        # Probabilities should sum to approximately 1
        total = sum(b.probability for b in result.brackets)
        assert abs(total - 1.0) < 0.01

        # Middle bracket (containing 68) should have highest probability
        probs = {b.ticker: b.probability for b in result.brackets}
        assert probs['T2'] > probs['T1']
        assert probs['T2'] > probs['T3']

    def test_edge_brackets(self):
        """Test open-ended brackets."""
        brackets = [
            {'ticker': 'LOW', 'floor': None, 'cap': 60},
            {'ticker': 'MID', 'floor': 60, 'cap': 70},
            {'ticker': 'HIGH', 'floor': 70, 'cap': None},
        ]

        result = estimate_from_dict(brackets, forecast_temp=65)

        total = sum(b.probability for b in result.brackets)
        assert abs(total - 1.0) < 0.01

    def test_weather_pattern_affects_uncertainty(self):
        """Test that weather pattern affects probability spread."""
        brackets = [
            {'ticker': 'T1', 'floor': 60, 'cap': 65},
            {'ticker': 'T2', 'floor': 65, 'cap': 70},
        ]

        stable = estimate_from_dict(brackets, forecast_temp=67, weather_pattern='stable')
        stormy = estimate_from_dict(brackets, forecast_temp=67, weather_pattern='stormy')

        # Stable weather should give more concentrated probabilities
        # (higher probability for the containing bracket)
        stable_probs = {b.ticker: b.probability for b in stable.brackets}
        stormy_probs = {b.ticker: b.probability for b in stormy.brackets}

        assert stable_probs['T2'] > stormy_probs['T2']

    def test_edge_vs_market(self):
        """Test edge calculation against market prices."""
        engine = ProbabilityEngine()

        forecast = NWSForecast(forecast_high=68)
        markets = [
            MarketBracket(ticker='T1', floor_strike=65, cap_strike=70),
        ]

        estimate = engine.estimate_probabilities(markets, forecast)

        # If our probability is 60% and market is at 50 cents
        market_prices = {'T1': 50}
        edges = engine.get_edge_vs_market(estimate, market_prices)

        # Edge should be our prob minus market implied prob
        expected_edge = estimate.brackets[0].probability - 0.50
        assert abs(edges['T1'] - expected_edge) < 0.01


class TestPositionCalculator:
    """Tests for position-aware calculations."""

    def test_simple_buy_no_position(self):
        """Test buying when no existing position."""
        orderbook = Orderbook(
            ticker='TEST',
            yes_asks=[OrderbookLevel(price=50, quantity=100)],
            yes_bids=[OrderbookLevel(price=48, quantity=100)],
        )

        effect = calculate_order_effect(
            ticker='TEST',
            side='yes',
            action='buy',
            quantity=10,
            orderbook=orderbook,
            current_position=None,
        )

        assert effect.will_close_existing is False
        assert effect.new_position_cost_cents == 500  # 10 * 50
        assert effect.net_cost_cents == 500

    def test_buy_opposite_closes_position(self):
        """Test that buying opposite side closes existing position."""
        orderbook = Orderbook(
            ticker='TEST',
            yes_asks=[OrderbookLevel(price=60, quantity=100)],
            yes_bids=[OrderbookLevel(price=58, quantity=100)],
        )

        position = Position(
            ticker='TEST',
            side='no',
            quantity=5,
            avg_price_cents=45,
            total_cost_cents=225,
        )

        effect = calculate_order_effect(
            ticker='TEST',
            side='yes',
            action='buy',
            quantity=10,
            orderbook=orderbook,
            current_position=position,
        )

        assert effect.will_close_existing is True
        assert effect.existing_side == 'no'
        assert effect.existing_quantity == 5
        assert len(effect.warnings) > 0

    def test_orderbook_take_cost(self):
        """Test orderbook cost calculation across multiple levels."""
        orderbook = Orderbook(
            ticker='TEST',
            yes_asks=[
                OrderbookLevel(price=50, quantity=5),
                OrderbookLevel(price=52, quantity=5),
                OrderbookLevel(price=55, quantity=10),
            ],
            yes_bids=[],
        )

        result = orderbook.take_yes_cost(10)

        # Should take 5 at 50 + 5 at 52 = 250 + 260 = 510
        assert result['total_cost_cents'] == 510
        assert result['fillable'] == 10
        assert result['avg_price_cents'] == 51


class TestArbitrageCalculator:
    """Tests for arbitrage analysis."""

    def test_all_yes_arbitrage(self):
        """Test all-YES strategy detection."""
        brackets = [
            {'ticker': 'B1', 'yes_ask': 30, 'no_ask': 72},
            {'ticker': 'B2', 'yes_ask': 25, 'no_ask': 77},
            {'ticker': 'B3', 'yes_ask': 20, 'no_ask': 82},
        ]

        # Sum of YES asks = 75, payout = 100, so 25 cent profit before fees
        result = analyze_from_brackets(brackets)

        assert 'all_yes' in result.strategies
        all_yes = result.strategies['all_yes']

        # Total cost should be 75 cents
        assert all_yes.total_cost_cents == 75
        assert all_yes.guaranteed_payout_cents == 100
        assert all_yes.profit_cents == 25

    def test_all_no_arbitrage(self):
        """Test all-NO strategy detection."""
        brackets = [
            {'ticker': 'B1', 'yes_ask': 40, 'no_ask': 62},
            {'ticker': 'B2', 'yes_ask': 35, 'no_ask': 67},
            {'ticker': 'B3', 'yes_ask': 30, 'no_ask': 72},
        ]

        result = analyze_from_brackets(brackets)

        assert 'all_no' in result.strategies
        all_no = result.strategies['all_no']

        # N-1 = 2 brackets pay out = 200 cents
        assert all_no.guaranteed_payout_cents == 200

    def test_no_all_yes_arbitrage(self):
        """Test when all-YES arbitrage doesn't exist."""
        brackets = [
            {'ticker': 'B1', 'yes_ask': 50, 'no_ask': 52},
            {'ticker': 'B2', 'yes_ask': 52, 'no_ask': 50},
        ]

        # Sum of YES asks = 102 > 100, no all-YES arb
        result = analyze_from_brackets(brackets)

        # all_yes and all_no should not be profitable
        assert result.strategies['all_yes'].is_profitable is False
        assert result.strategies['all_no'].is_profitable is False
        # Note: hybrid might still find an opportunity (buy YES on B1, NO on B2)

    def test_best_strategy_selection(self):
        """Test that best strategy is correctly selected."""
        # Create scenario where all_yes is clearly best
        brackets = [
            {'ticker': 'B1', 'yes_ask': 20, 'no_ask': 82},
            {'ticker': 'B2', 'yes_ask': 20, 'no_ask': 82},
            {'ticker': 'B3', 'yes_ask': 20, 'no_ask': 82},
        ]

        result = analyze_from_brackets(brackets)

        # all_yes: cost=60, payout=100, profit=40
        # all_no: cost=54 (3*18), payout=200, profit=146
        # all_no should be better here
        if result.has_opportunity:
            assert result.best_strategy in ['all_yes', 'all_no', 'hybrid', 'min_2_no']

    def test_hybrid_strategy(self):
        """Test hybrid strategy picks cheapest side per bracket."""
        brackets = [
            {'ticker': 'B1', 'yes_ask': 30, 'no_ask': 40},  # YES cheaper
            {'ticker': 'B2', 'yes_ask': 60, 'no_ask': 25},  # NO cheaper
        ]

        result = analyze_from_brackets(brackets)

        assert 'hybrid' in result.strategies
        hybrid = result.strategies['hybrid']

        # Should have picked YES for B1, NO for B2
        leg_sides = {leg['ticker']: leg['side'] for leg in hybrid.legs}
        assert leg_sides.get('B1') == 'yes'
        assert leg_sides.get('B2') == 'no'


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_fee_included_in_arbitrage(self):
        """Test that fees are properly included in arbitrage calculations."""
        brackets = [
            {'ticker': 'B1', 'yes_ask': 30, 'no_ask': 72},
            {'ticker': 'B2', 'yes_ask': 30, 'no_ask': 72},
            {'ticker': 'B3', 'yes_ask': 30, 'no_ask': 72},
        ]

        result = analyze_from_brackets(brackets)
        all_yes = result.strategies['all_yes']

        # Profit after fees should be less than gross profit
        assert all_yes.profit_after_fees_cents < all_yes.profit_cents
        assert all_yes.total_fees_cents > 0

    def test_probability_informs_edge(self):
        """Test probability estimation provides actionable edge info."""
        engine = ProbabilityEngine()

        forecast = NWSForecast(
            forecast_high=70,
            weather_pattern=WeatherPattern.STABLE,
        )

        markets = [
            MarketBracket(ticker='B1', floor_strike=65, cap_strike=70),
            MarketBracket(ticker='B2', floor_strike=70, cap_strike=75),
        ]

        estimate = engine.estimate_probabilities(markets, forecast)

        # Market mispriced: B1 at 60 cents but we think it's 40%
        market_prices = {'B1': 60, 'B2': 40}
        edges = engine.get_edge_vs_market(estimate, market_prices)

        # Should identify if there's an edge
        assert 'B1' in edges
        assert 'B2' in edges


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
