"""
Analysis services for Kalshi trading.

This module provides comprehensive analysis capabilities for:
- Fee calculation with proper non-linear handling
- Probability estimation for weather brackets
- Position-aware order calculations
- Multi-strategy arbitrage analysis
"""

from ..core.fee_calculator import (
    FeeCalculator,
    FeeResult,
    calculate_fee,
)

from .probability_engine import (
    ProbabilityEngine,
    BracketProbability,
    ProbabilityEstimate,
    MarketBracket,
    NWSForecast,
    WeatherPattern,
    estimate_probabilities,
    estimate_from_dict,
)

from .prediction_engine_v2 import (
    PredictionEngineV2,
    BracketAnalysis,
    PredictionResult,
    PositionInfo,
    RecommendationAction,
    get_engine as get_prediction_engine,
    analyze_brackets,
)

from .position_calculator import (
    PositionCalculator,
    Position,
    Orderbook,
    OrderbookLevel,
    OrderEffect,
    calculate_order_effect,
)

from .arbitrage_calculator import (
    ArbitrageCalculator,
    ArbitrageStrategy,
    Market,
    Event,
    ArbitrageLeg,
    StrategyResult,
    ArbitrageAnalysis,
    analyze_event,
    analyze_from_brackets,
)

__all__ = [
    # Fee calculation (from core)
    'FeeCalculator',
    'FeeResult',
    'calculate_fee',

    # Probability (v1)
    'ProbabilityEngine',
    'BracketProbability',
    'ProbabilityEstimate',
    'MarketBracket',
    'NWSForecast',
    'WeatherPattern',
    'estimate_probabilities',
    'estimate_from_dict',

    # Prediction Engine (v2 - fee-aware)
    'PredictionEngineV2',
    'BracketAnalysis',
    'PredictionResult',
    'PositionInfo',
    'RecommendationAction',
    'get_prediction_engine',
    'analyze_brackets',

    # Position
    'PositionCalculator',
    'Position',
    'Orderbook',
    'OrderbookLevel',
    'OrderEffect',
    'calculate_order_effect',

    # Arbitrage
    'ArbitrageCalculator',
    'ArbitrageStrategy',
    'Market',
    'Event',
    'ArbitrageLeg',
    'StrategyResult',
    'ArbitrageAnalysis',
    'analyze_event',
    'analyze_from_brackets',
]
