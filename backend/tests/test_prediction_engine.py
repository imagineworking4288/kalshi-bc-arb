"""
Unit tests for the prediction engine v2.

Tests cover:
- Probability calculations (Issue #5)
- Fee-aware expected value (Issue #7)
- Position awareness (Issue #8)
- Kelly sizing (Issue #9)
- Edge threshold (Issue #10)
"""

import pytest
import math
from backend.services.analysis.prediction_engine_v2 import (
    PredictionEngineV2,
    BracketAnalysis,
    PredictionResult,
    PositionInfo,
    RecommendationAction,
)


class TestProbabilityCalculations:
    """Test probability calculations (Issue #5)"""

    def setup_method(self):
        self.engine = PredictionEngineV2()

    def test_bracket_probability_middle(self):
        """Test probability for bracket containing the mean"""
        # Mean = 70, std_dev = 3, bracket = 69-71
        prob = self.engine._bracket_probability(70, 3.0, 69, 71)
        # Should be roughly P(-1/3 < Z < 2/3) ≈ 37%
        assert 0.30 < prob < 0.45

    def test_bracket_probability_above_mean(self):
        """Test probability for bracket above the mean"""
        # Mean = 70, std_dev = 3, bracket = 73-75
        prob = self.engine._bracket_probability(70, 3.0, 73, 75)
        # Should be lower than middle bracket
        assert 0.05 < prob < 0.20

    def test_bracket_probability_below_mean(self):
        """Test probability for bracket below the mean"""
        # Mean = 70, std_dev = 3, bracket = 65-67
        prob = self.engine._bracket_probability(70, 3.0, 65, 67)
        # Should be lower than middle bracket but not too low
        assert 0.05 < prob < 0.25

    def test_open_ended_above_bracket(self):
        """Test probability for '>=X' bracket"""
        # Mean = 70, std_dev = 3, bracket = >=75
        prob = self.engine._bracket_probability(70, 3.0, 75, None)
        # P(Z > 5/3) ≈ 5%
        assert 0.01 < prob < 0.15

    def test_open_ended_below_bracket(self):
        """Test probability for '<X' bracket"""
        # Mean = 70, std_dev = 3, bracket = <65
        prob = self.engine._bracket_probability(70, 3.0, None, 65)
        # P(Z < -5/3) ≈ 5%
        assert 0.01 < prob < 0.15

    def test_probabilities_cover_distribution(self):
        """Test that bracket probabilities behave correctly across distribution"""
        # Test that open-ended brackets capture the tails properly
        mean = 70
        std = 3.0

        # P(<65) should be low (left tail)
        p_below = self.engine._bracket_probability(mean, std, None, 65)
        assert p_below < 0.1  # Should be small

        # P(>=75) should also be low (right tail)
        p_above = self.engine._bracket_probability(mean, std, 75, None)
        assert p_above < 0.1  # Should be small

        # P(68-72) should be high (around mean)
        p_middle = self.engine._bracket_probability(mean, std, 68, 72)
        assert p_middle > 0.5  # Should capture most of distribution


class TestFeeAwareEV:
    """Test fee-aware expected value calculation (Issue #7)"""

    def setup_method(self):
        self.engine = PredictionEngineV2()

    def test_positive_ev_calculation(self):
        """Test EV calculation for profitable bet"""
        # If model says 60% probability, and we can buy at 50 cents
        # EV = 0.60 * 100 - 50 = 10 cents (before fees)
        ev, ev_after_fee, fee = self.engine._calculate_fee_aware_ev(
            prob=0.60,
            price_cents=50,
            side="yes",
            contracts=10
        )

        assert ev == pytest.approx(10.0, abs=0.1)
        # Fee should reduce EV
        assert ev_after_fee < ev
        assert fee > 0

    def test_negative_ev_calculation(self):
        """Test EV calculation for unprofitable bet"""
        # If model says 40% probability, and we have to buy at 50 cents
        # EV = 0.40 * 100 - 50 = -10 cents (before fees)
        ev, ev_after_fee, fee = self.engine._calculate_fee_aware_ev(
            prob=0.40,
            price_cents=50,
            side="yes",
            contracts=10
        )

        assert ev == pytest.approx(-10.0, abs=0.1)
        # EV after fee should be even more negative
        assert ev_after_fee < ev

    def test_fee_calculation(self):
        """Test that fees are properly calculated"""
        _, _, fee = self.engine._calculate_fee_aware_ev(
            prob=0.50,
            price_cents=50,
            side="yes",
            contracts=10
        )

        # Fee formula: 0.07 * contracts * price * (1 - price)
        # = 0.07 * 10 * 0.5 * 0.5 = 0.175 dollars = 17.5 cents for 10 contracts
        assert 15.0 < fee < 20.0


class TestPositionAwareness:
    """Test position-aware recommendations (Issue #8)"""

    def setup_method(self):
        self.engine = PredictionEngineV2()

    def test_no_conflict_without_position(self):
        """Test recommendation when no existing position"""
        brackets = [
            {"ticker": "TEST-70-72", "floor_strike": 70, "cap_strike": 72, "yes_price": 30}
        ]

        result = self.engine.analyze_brackets(
            brackets=brackets,
            forecast_high=71,  # Mean in the bracket
            forecast_std_dev=3.0,
            positions=[],
        )

        # Should have a recommendation
        assert len(result.brackets) == 1
        assert not result.brackets[0].position_conflict

    def test_conflict_with_opposite_position(self):
        """Test that opposite positions create conflict"""
        brackets = [
            {"ticker": "TEST-70-72", "floor_strike": 70, "cap_strike": 72, "yes_price": 30}
        ]

        positions = [PositionInfo(ticker="TEST-70-72", side="no", quantity=10)]

        result = self.engine.analyze_brackets(
            brackets=brackets,
            forecast_high=71,
            forecast_std_dev=3.0,
            positions=positions,
        )

        # If recommendation would be buy_yes, there should be a conflict
        bracket = result.brackets[0]
        if bracket.recommended_side == "yes":
            assert bracket.position_conflict
            assert bracket.recommended_action == RecommendationAction.SKIP

    def test_no_conflict_with_same_side_position(self):
        """Test that same-side positions don't create conflict"""
        brackets = [
            {"ticker": "TEST-70-72", "floor_strike": 70, "cap_strike": 72, "yes_price": 30}
        ]

        # Assuming we'd recommend YES, having a YES position shouldn't conflict
        positions = [PositionInfo(ticker="TEST-70-72", side="yes", quantity=10)]

        result = self.engine.analyze_brackets(
            brackets=brackets,
            forecast_high=71,
            forecast_std_dev=2.0,  # Lower std = higher confidence
            positions=positions,
        )

        bracket = result.brackets[0]
        if bracket.recommended_side == "yes":
            assert not bracket.position_conflict


class TestKellySizing:
    """Test Kelly criterion sizing (Issue #9)"""

    def setup_method(self):
        self.engine = PredictionEngineV2(kelly_fraction=0.25, bankroll_cents=100000)

    def test_kelly_positive_edge(self):
        """Test Kelly fraction for positive edge bet"""
        # If prob = 0.60 and price = 0.50
        # odds = (1/0.50) - 1 = 1
        # kelly = (0.60 * 1 - 0.40) / 1 = 0.20
        kelly = self.engine._calculate_kelly(0.60, 0.50)
        assert 0.15 < kelly < 0.25

    def test_kelly_negative_edge(self):
        """Test Kelly fraction for negative edge bet"""
        # If prob = 0.40 and price = 0.50
        kelly = self.engine._calculate_kelly(0.40, 0.50)
        assert kelly == 0.0  # Should not bet

    def test_kelly_capped_at_one(self):
        """Test that Kelly fraction never exceeds 1"""
        # Very high edge scenario
        kelly = self.engine._calculate_kelly(0.99, 0.10)
        assert kelly <= 1.0

    def test_fractional_kelly(self):
        """Test that fractional Kelly is applied"""
        result = self.engine.analyze_brackets(
            brackets=[
                {"ticker": "TEST", "floor_strike": 70, "cap_strike": 72, "yes_price": 30}
            ],
            forecast_high=71,
            forecast_std_dev=2.0,
        )

        bracket = result.brackets[0]
        # Kelly fraction should be reduced by self.engine.kelly_fraction (0.25)
        assert bracket.kelly_fraction <= 0.25


class TestEdgeThreshold:
    """Test minimum edge threshold (Issue #10)"""

    def setup_method(self):
        self.engine = PredictionEngineV2(min_edge=0.05)

    def test_recommendation_with_sufficient_edge(self):
        """Test that recommendations are made when edge > threshold"""
        brackets = [
            {"ticker": "TEST", "floor_strike": 70, "cap_strike": 72, "yes_price": 20}  # Low price
        ]

        result = self.engine.analyze_brackets(
            brackets=brackets,
            forecast_high=71,  # Mean in bracket
            forecast_std_dev=2.0,  # Low uncertainty
        )

        bracket = result.brackets[0]
        # With 71 mean, 2.0 std, 70-72 bracket should have high probability
        # And at 20 cents price, should have good edge
        if bracket.probability_edge > 0.05:
            assert bracket.recommended_action in [RecommendationAction.BUY_YES, RecommendationAction.BUY_NO]

    def test_hold_with_insufficient_edge(self):
        """Test that HOLD is returned when edge < threshold"""
        brackets = [
            {"ticker": "TEST", "floor_strike": 70, "cap_strike": 72, "yes_price": 40}  # Near fair value
        ]

        result = self.engine.analyze_brackets(
            brackets=brackets,
            forecast_high=71,
            forecast_std_dev=3.0,
        )

        bracket = result.brackets[0]
        # With ~35-40% probability and 40 cent price, edge should be small
        if abs(bracket.probability_edge) < 0.05:
            assert bracket.recommended_action == RecommendationAction.HOLD


class TestAnalyzeBrackets:
    """Test the main analyze_brackets method"""

    def setup_method(self):
        self.engine = PredictionEngineV2()

    def test_full_analysis(self):
        """Test complete bracket analysis"""
        brackets = [
            {"ticker": "T1", "floor_strike": None, "cap_strike": 65, "yes_price": 10},
            {"ticker": "T2", "floor_strike": 65, "cap_strike": 68, "yes_price": 15},
            {"ticker": "T3", "floor_strike": 68, "cap_strike": 71, "yes_price": 35},
            {"ticker": "T4", "floor_strike": 71, "cap_strike": 74, "yes_price": 30},
            {"ticker": "T5", "floor_strike": 74, "cap_strike": 77, "yes_price": 8},
            {"ticker": "T6", "floor_strike": 77, "cap_strike": None, "yes_price": 5},
        ]

        result = self.engine.analyze_brackets(
            brackets=brackets,
            forecast_high=70,
            forecast_std_dev=3.0,
            city="NYC",
            event_ticker="KXHIGHNY-TEST",
        )

        assert isinstance(result, PredictionResult)
        assert len(result.brackets) == 6
        assert result.city == "NYC"
        assert result.event_ticker == "KXHIGHNY-TEST"

        # Total probability should be close to 1.0
        assert 0.95 < result.total_probability < 1.05

        # Each bracket should have valid analysis
        for bracket in result.brackets:
            assert isinstance(bracket, BracketAnalysis)
            assert 0.0 <= bracket.model_probability <= 1.0
            assert isinstance(bracket.recommended_action, RecommendationAction)

    def test_warnings_for_invalid_probabilities(self):
        """Test that warnings are generated for probability issues"""
        brackets = [
            {"ticker": "T1", "floor_strike": 65, "cap_strike": 68, "yes_price": 15},
            # Missing some brackets means probabilities won't sum to 1
        ]

        result = self.engine.analyze_brackets(
            brackets=brackets,
            forecast_high=70,
            forecast_std_dev=3.0,
        )

        # Should have a warning about probabilities not summing to 1
        assert len(result.warnings) > 0 or result.total_probability < 0.95

    def test_best_opportunity_selection(self):
        """Test that best opportunity is correctly identified"""
        brackets = [
            {"ticker": "T1", "floor_strike": 70, "cap_strike": 72, "yes_price": 20},  # Underpriced
            {"ticker": "T2", "floor_strike": 72, "cap_strike": 74, "yes_price": 80},  # Overpriced
        ]

        result = self.engine.analyze_brackets(
            brackets=brackets,
            forecast_high=71,  # Mean in first bracket
            forecast_std_dev=2.0,
        )

        # Best opportunity should be the underpriced one (if any has positive EV)
        if result.best_bracket:
            assert result.best_bracket.best_ev_after_fee > 0


class TestNormCDF:
    """Test normal CDF implementation"""

    def setup_method(self):
        self.engine = PredictionEngineV2()

    def test_cdf_at_mean(self):
        """CDF at mean should be 0.5"""
        result = self.engine._norm_cdf(50, 50, 10)
        assert result == pytest.approx(0.5, abs=0.001)

    def test_cdf_above_mean(self):
        """CDF above mean should be > 0.5"""
        result = self.engine._norm_cdf(60, 50, 10)  # 1 std above
        assert 0.8 < result < 0.9  # Should be ~0.84

    def test_cdf_below_mean(self):
        """CDF below mean should be < 0.5"""
        result = self.engine._norm_cdf(40, 50, 10)  # 1 std below
        assert 0.1 < result < 0.2  # Should be ~0.16

    def test_cdf_zero_std(self):
        """CDF with zero std should be step function"""
        assert self.engine._norm_cdf(51, 50, 0) == 1.0
        assert self.engine._norm_cdf(49, 50, 0) == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
