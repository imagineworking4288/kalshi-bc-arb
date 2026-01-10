"""
Weather probability estimation engine.

Estimates the probability that temperature will fall into each bracket
based on NWS forecasts, weather patterns, and historical biases.
"""

import math
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class WeatherPattern(str, Enum):
    """Weather pattern affecting forecast uncertainty."""
    STABLE = "stable"
    TRANSITIONAL = "transitional"
    STORMY = "stormy"
    FRONTAL = "frontal"


@dataclass
class BracketProbability:
    """Probability estimate for a single bracket"""
    ticker: str
    floor_strike: Optional[int]
    cap_strike: Optional[int]
    probability: float  # 0.0 to 1.0
    confidence: float   # How confident we are in this estimate
    label: str          # Human-readable label


@dataclass
class ProbabilityEstimate:
    """Complete probability estimate for an event"""
    event_ticker: str
    forecast_temp: int  # High or low depending on market type
    forecast_std_dev: float
    brackets: List[BracketProbability]
    total_probability: float  # Should be ~1.0
    generated_at: datetime
    forecast_source: str
    warnings: List[str] = field(default_factory=list)


@dataclass
class MarketBracket:
    """Simple bracket representation for probability calculations."""
    ticker: str
    floor_strike: Optional[int] = None
    cap_strike: Optional[int] = None
    event_ticker: str = ""

    def is_tradeable(self) -> bool:
        """Check if bracket has valid strike prices."""
        return self.floor_strike is not None or self.cap_strike is not None


@dataclass
class NWSForecast:
    """Forecast data from NWS."""
    forecast_high: int
    forecast_low: Optional[int] = None
    weather_pattern: WeatherPattern = WeatherPattern.TRANSITIONAL
    confidence_level: float = 0.7
    temperature_range_low: Optional[int] = None
    temperature_range_high: Optional[int] = None


class ProbabilityEngine:
    """
    Estimate bracket probabilities from weather forecasts.

    Uses cumulative normal distribution to estimate probability
    that actual temperature falls in each bracket.

    Key insight: We're predicting what the NWS CLI report will say,
    NOT trying to predict the actual temperature independently.
    """

    # Standard deviation adjustments by weather pattern
    PATTERN_STD_DEV = {
        WeatherPattern.STABLE: 1.5,
        WeatherPattern.TRANSITIONAL: 3.0,
        WeatherPattern.STORMY: 4.5,
        WeatherPattern.FRONTAL: 5.0,
        'stable': 1.5,
        'transitional': 3.0,
        'stormy': 4.5,
        'frontal': 5.0,
    }

    # Confidence adjustments
    MIN_CONFIDENCE = 0.5
    MAX_CONFIDENCE = 0.95

    def estimate_probabilities(
        self,
        markets: List[MarketBracket],
        forecast: NWSForecast,
        current_temp: Optional[int] = None,
        hours_to_settlement: Optional[float] = None,
    ) -> ProbabilityEstimate:
        """
        Estimate probability for each bracket.

        Args:
            markets: List of bracket markets for the event
            forecast: NWS forecast data
            current_temp: Current observed temperature (if available)
            hours_to_settlement: Hours until market settles

        Returns:
            ProbabilityEstimate with probability for each bracket
        """
        warnings = []

        # Get forecast parameters
        mean = forecast.forecast_high
        std_dev = self._calculate_std_dev(forecast, hours_to_settlement)

        # Adjust for current observations if close to settlement
        if current_temp is not None and hours_to_settlement is not None:
            if hours_to_settlement < 2:
                # Near settlement, current temp is highly informative
                # Blend forecast with current observation
                weight = max(0.3, 1 - (hours_to_settlement / 2))
                mean = int(mean * (1 - weight) + current_temp * weight)
                std_dev *= (1 - weight * 0.5)  # Reduce uncertainty
                warnings.append(f"Adjusted for current temp {current_temp}F")

        # Calculate probability for each bracket
        brackets = []
        total_prob = 0.0

        for market in markets:
            prob = self._bracket_probability(
                mean, std_dev,
                market.floor_strike,
                market.cap_strike
            )

            confidence = self._calculate_confidence(
                prob, std_dev, hours_to_settlement
            )

            brackets.append(BracketProbability(
                ticker=market.ticker,
                floor_strike=market.floor_strike,
                cap_strike=market.cap_strike,
                probability=prob,
                confidence=confidence,
                label=self._bracket_label(market.floor_strike, market.cap_strike),
            ))

            total_prob += prob

        # Normalize if total significantly different from 1.0
        if abs(total_prob - 1.0) > 0.01:
            warnings.append(f"Probabilities summed to {total_prob:.3f}, normalized")
            for b in brackets:
                b.probability /= total_prob
            total_prob = 1.0

        return ProbabilityEstimate(
            event_ticker=markets[0].event_ticker if markets else "",
            forecast_temp=mean,
            forecast_std_dev=std_dev,
            brackets=brackets,
            total_probability=total_prob,
            generated_at=datetime.now(timezone.utc),
            forecast_source="NWS",
            warnings=warnings,
        )

    def estimate_from_dict(
        self,
        brackets: List[Dict[str, Any]],
        forecast_temp: int,
        weather_pattern: str = "transitional",
        hours_to_settlement: Optional[float] = None,
    ) -> ProbabilityEstimate:
        """
        Convenience method to estimate probabilities from dict-based brackets.

        Args:
            brackets: List of bracket dicts with 'ticker', 'floor', 'cap' keys
            forecast_temp: Forecasted temperature
            weather_pattern: One of 'stable', 'transitional', 'stormy', 'frontal'
            hours_to_settlement: Hours until market settles

        Returns:
            ProbabilityEstimate with probability for each bracket
        """
        # Convert dicts to MarketBracket objects
        markets = []
        for b in brackets:
            markets.append(MarketBracket(
                ticker=b.get('ticker', ''),
                floor_strike=b.get('floor') or b.get('floor_strike'),
                cap_strike=b.get('cap') or b.get('cap_strike'),
                event_ticker=b.get('event_ticker', ''),
            ))

        # Create forecast object
        forecast = NWSForecast(
            forecast_high=forecast_temp,
            weather_pattern=WeatherPattern(weather_pattern) if weather_pattern in [p.value for p in WeatherPattern] else WeatherPattern.TRANSITIONAL,
        )

        return self.estimate_probabilities(
            markets, forecast, hours_to_settlement=hours_to_settlement
        )

    def _calculate_std_dev(
        self,
        forecast: NWSForecast,
        hours_to_settlement: Optional[float] = None,
    ) -> float:
        """
        Calculate standard deviation based on conditions.

        Factors:
        1. Weather pattern (stable, transitional, stormy)
        2. NWS-provided range (if available)
        3. Confidence level
        4. Time to settlement (less uncertainty closer to settlement)
        """
        # Base std dev from weather pattern
        pattern = forecast.weather_pattern
        if isinstance(pattern, WeatherPattern):
            base_std = self.PATTERN_STD_DEV.get(pattern, 3.0)
        else:
            base_std = self.PATTERN_STD_DEV.get(pattern, 3.0)

        # If NWS provides a range, use it
        if forecast.temperature_range_low and forecast.temperature_range_high:
            range_width = forecast.temperature_range_high - forecast.temperature_range_low
            # Range typically covers ~2 std devs (95%)
            range_std = range_width / 4.0
            # Average with pattern-based estimate
            base_std = (base_std + range_std) / 2.0

        # Adjust for confidence
        confidence = forecast.confidence_level
        confidence_multiplier = 1.0 + (1.0 - confidence) * 0.5
        base_std *= confidence_multiplier

        # Adjust for time to settlement
        if hours_to_settlement is not None:
            if hours_to_settlement < 2:
                # Very close to settlement - much less uncertainty
                base_std *= 0.6
            elif hours_to_settlement < 6:
                # Moderately close
                base_std *= 0.8

        return base_std

    def _bracket_probability(
        self,
        mean: float,
        std_dev: float,
        floor_strike: Optional[int],
        cap_strike: Optional[int],
    ) -> float:
        """
        Calculate probability that temperature falls in bracket.
        Uses cumulative normal distribution.
        """
        if floor_strike is None and cap_strike is None:
            return 0.0

        # Handle edge brackets (open-ended)
        if floor_strike is None:
            # "Below X" bracket
            return self._norm_cdf(cap_strike, mean, std_dev)

        if cap_strike is None:
            # "X or above" bracket
            return 1.0 - self._norm_cdf(floor_strike, mean, std_dev)

        # Normal bracket: floor <= temp < cap
        # But Kalshi brackets are typically "62-63F" meaning 62 <= temp <= 63
        # Since temps are integers, P(62 <= T <= 63) = P(T < 64) - P(T < 62)
        prob_below_cap = self._norm_cdf(cap_strike + 1, mean, std_dev)  # Include cap
        prob_below_floor = self._norm_cdf(floor_strike, mean, std_dev)  # Exclude floor

        return max(0.0, prob_below_cap - prob_below_floor)

    def _norm_cdf(self, x: float, mean: float, std_dev: float) -> float:
        """Cumulative distribution function for normal distribution"""
        if std_dev <= 0:
            return 1.0 if x >= mean else 0.0

        z = (x - mean) / std_dev
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def _calculate_confidence(
        self,
        probability: float,
        std_dev: float,
        hours_to_settlement: Optional[float],
    ) -> float:
        """
        Calculate confidence in probability estimate.
        Higher confidence for:
        - More certain forecasts (lower std_dev)
        - Closer to settlement
        - Probabilities near 0 or 1 (clearer outcomes)
        """
        # Base confidence from std_dev
        # Lower std_dev = higher confidence
        std_confidence = max(0.5, 1.0 - (std_dev - 1.5) / 10.0)

        # Time-based confidence
        time_confidence = 0.7
        if hours_to_settlement is not None:
            if hours_to_settlement < 2:
                time_confidence = 0.9
            elif hours_to_settlement < 6:
                time_confidence = 0.8

        # Probability-based confidence
        # More confident when probability is extreme
        prob_distance = abs(probability - 0.5)
        prob_confidence = 0.5 + prob_distance

        # Combine (geometric mean)
        confidence = (std_confidence * time_confidence * prob_confidence) ** (1/3)

        return max(self.MIN_CONFIDENCE, min(self.MAX_CONFIDENCE, confidence))

    def _bracket_label(
        self,
        floor_strike: Optional[int],
        cap_strike: Optional[int],
    ) -> str:
        """Generate human-readable bracket label"""
        if floor_strike is None and cap_strike is not None:
            return f"<{cap_strike}F"
        if cap_strike is None and floor_strike is not None:
            return f">={floor_strike}F"
        if floor_strike is not None and cap_strike is not None:
            return f"{floor_strike}-{cap_strike}F"
        return "Unknown"

    def get_most_likely_bracket(
        self,
        estimate: ProbabilityEstimate
    ) -> Optional[BracketProbability]:
        """Get the bracket with highest probability"""
        if not estimate.brackets:
            return None
        return max(estimate.brackets, key=lambda b: b.probability)

    def get_edge_vs_market(
        self,
        estimate: ProbabilityEstimate,
        market_prices: Dict[str, int],  # ticker -> price_cents
    ) -> Dict[str, float]:
        """
        Calculate edge (estimated prob - market implied prob) for each bracket.

        Returns: Dict of ticker -> edge (positive = underpriced by market)
        """
        edges = {}

        for bracket in estimate.brackets:
            market_price = market_prices.get(bracket.ticker)
            if market_price is None:
                continue

            # Market implied probability
            implied_prob = market_price / 100.0

            # Our edge
            edge = bracket.probability - implied_prob
            edges[bracket.ticker] = edge

        return edges


# Singleton
_probability_engine = ProbabilityEngine()

def estimate_probabilities(
    markets: List[MarketBracket],
    forecast: NWSForecast,
    **kwargs
) -> ProbabilityEstimate:
    """Convenience function"""
    return _probability_engine.estimate_probabilities(markets, forecast, **kwargs)

def estimate_from_dict(
    brackets: List[Dict[str, Any]],
    forecast_temp: int,
    **kwargs
) -> ProbabilityEstimate:
    """Convenience function for dict-based brackets"""
    return _probability_engine.estimate_from_dict(brackets, forecast_temp, **kwargs)
