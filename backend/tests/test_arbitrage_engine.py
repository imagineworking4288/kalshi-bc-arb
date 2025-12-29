"""Tests for arbitrage engine"""

import pytest
from datetime import datetime, timedelta

from services.arbitrage_engine import ArbitrageEngine
from services.market_service import MarketGroup, ThresholdMarket, BracketMarket


def create_threshold(
    strike: float,
    yes_price: float,
    direction: str = "above",
    volume: int = 100
) -> ThresholdMarket:
    """Helper to create threshold market"""
    settlement = datetime.utcnow() + timedelta(hours=1)
    return ThresholdMarket(
        ticker=f"BTC-{direction.upper()}-{int(strike/1000)}K",
        title=f"BTC {direction} ${strike:,.0f}",
        asset="BTC",
        strike=strike,
        direction=direction,
        yes_price=yes_price,
        no_price=1 - yes_price,
        yes_ask=yes_price + 0.01,
        no_ask=1 - yes_price + 0.01,
        yes_bid=yes_price - 0.01,
        no_bid=1 - yes_price - 0.01,
        volume=volume,
        settlement_time=settlement
    )


def create_bracket(
    low: float,
    high: float,
    yes_price: float,
    volume: int = 100
) -> BracketMarket:
    """Helper to create bracket market"""
    settlement = datetime.utcnow() + timedelta(hours=1)
    return BracketMarket(
        ticker=f"BTC-{int(low/1000)}K-{int(high/1000)}K",
        title=f"BTC ${low:,.0f} - ${high:,.0f}",
        asset="BTC",
        low_bound=low,
        high_bound=high,
        yes_price=yes_price,
        no_price=1 - yes_price,
        yes_ask=yes_price + 0.01,
        no_ask=1 - yes_price + 0.01,
        yes_bid=yes_price - 0.01,
        no_bid=1 - yes_price - 0.01,
        volume=volume,
        settlement_time=settlement
    )


class TestArbitrageEngine:
    def test_finds_opportunity_when_threshold_overpriced(self):
        """Test finding arb when threshold is overpriced"""
        engine = ArbitrageEngine(min_profit_pct=1.0)

        settlement = datetime.utcnow() + timedelta(hours=1)
        group = MarketGroup(
            asset="BTC",
            settlement_time=settlement,
            thresholds=[
                create_threshold(95000, 0.70)  # 70c for "above 95K"
            ],
            brackets=[
                create_bracket(90000, 95000, 0.10),
                create_bracket(95000, 97500, 0.40),  # Should sum to 60c
                create_bracket(97500, 100000, 0.20), # for "above 95K"
            ],
            spot_price=96000
        )

        opportunities = engine.find_opportunities([group])

        # Should find opportunity: threshold 70c vs implied 60c (40+20)
        assert len(opportunities) > 0

        opp = opportunities[0]
        assert opp.threshold_strike == 95000
        assert opp.threshold_yes_price == 0.70
        assert opp.implied_price == 0.60  # 40c + 20c
        assert opp.divergence == 0.10  # 70c - 60c
        assert opp.trade_direction == "buy_brackets"

    def test_finds_opportunity_when_threshold_underpriced(self):
        """Test finding arb when threshold is underpriced"""
        engine = ArbitrageEngine(min_profit_pct=1.0)

        settlement = datetime.utcnow() + timedelta(hours=1)
        group = MarketGroup(
            asset="BTC",
            settlement_time=settlement,
            thresholds=[
                create_threshold(95000, 0.50)  # 50c for "above 95K"
            ],
            brackets=[
                create_bracket(90000, 95000, 0.10),
                create_bracket(95000, 97500, 0.40),  # Should sum to 60c
                create_bracket(97500, 100000, 0.20),
            ],
            spot_price=96000
        )

        opportunities = engine.find_opportunities([group])

        # Should find opportunity: threshold 50c vs implied 60c
        assert len(opportunities) > 0

        opp = opportunities[0]
        assert opp.divergence == -0.10  # 50c - 60c

    def test_no_opportunity_when_prices_aligned(self):
        """Test no arb when prices are properly aligned"""
        engine = ArbitrageEngine(min_profit_pct=1.0)

        settlement = datetime.utcnow() + timedelta(hours=1)
        group = MarketGroup(
            asset="BTC",
            settlement_time=settlement,
            thresholds=[
                create_threshold(95000, 0.60)  # 60c matches implied
            ],
            brackets=[
                create_bracket(90000, 95000, 0.10),
                create_bracket(95000, 97500, 0.40),
                create_bracket(97500, 100000, 0.20),
            ],
            spot_price=96000
        )

        opportunities = engine.find_opportunities([group])

        # Should find no profitable opportunity
        assert len(opportunities) == 0

    def test_respects_min_profit_threshold(self):
        """Test minimum profit threshold is respected"""
        engine = ArbitrageEngine(min_profit_pct=5.0)

        settlement = datetime.utcnow() + timedelta(hours=1)
        group = MarketGroup(
            asset="BTC",
            settlement_time=settlement,
            thresholds=[
                create_threshold(95000, 0.62)  # Small divergence (2c)
            ],
            brackets=[
                create_bracket(90000, 95000, 0.10),
                create_bracket(95000, 97500, 0.40),
                create_bracket(97500, 100000, 0.20),
            ],
            spot_price=96000
        )

        opportunities = engine.find_opportunities([group])

        # Should not find opportunity with 5% min threshold
        assert len(opportunities) == 0

    def test_empty_group(self):
        """Test with empty market group"""
        engine = ArbitrageEngine()

        settlement = datetime.utcnow() + timedelta(hours=1)
        group = MarketGroup(
            asset="BTC",
            settlement_time=settlement,
            thresholds=[],
            brackets=[],
        )

        opportunities = engine.find_opportunities([group])
        assert len(opportunities) == 0

    def test_opportunity_scoring(self):
        """Test that opportunities are sorted by score"""
        engine = ArbitrageEngine(min_profit_pct=1.0)

        settlement = datetime.utcnow() + timedelta(hours=1)

        # Create two groups with different profit levels
        group1 = MarketGroup(
            asset="BTC",
            settlement_time=settlement,
            thresholds=[create_threshold(95000, 0.75)],  # 15c divergence
            brackets=[
                create_bracket(90000, 95000, 0.10),
                create_bracket(95000, 97500, 0.40),
                create_bracket(97500, 100000, 0.20),
            ],
        )

        group2 = MarketGroup(
            asset="ETH",
            settlement_time=settlement,
            thresholds=[create_threshold(3000, 0.62)],  # 2c divergence
            brackets=[
                create_bracket(2800, 3000, 0.20),
                create_bracket(3000, 3200, 0.35),
                create_bracket(3200, 3400, 0.25),
            ],
        )

        opportunities = engine.find_opportunities([group1, group2])

        # Higher profit opportunity should be first
        if len(opportunities) >= 2:
            assert opportunities[0].net_profit_pct >= opportunities[1].net_profit_pct
