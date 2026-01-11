"""
Strategy Registry and Implementations.

This module provides:
- Strategy registry with @register_strategy decorator
- Three BaseStrategy implementations:
  - WeatherStrategy: Weather bracket arbitrage and directional trading
  - BTCArbitrageStrategy: BTC range vs threshold arbitrage
  - BTCDirectionalStrategy: BTC threshold directional using logistic probability

Note: BTCArbitrageStrategy and BTCDirectionalStrategy both use StrategyType.BTC.
The registry maps one class per type (last registered wins), but all strategies
are accessible via direct import or get_all_strategy_classes().

Usage:
    from backend.services.strategies import (
        WeatherStrategy, BTCArbitrageStrategy, BTCDirectionalStrategy,
        get_all_strategies, get_strategy_class, get_registered_types,
        get_all_strategy_classes
    )

    # Get all strategy classes (regardless of type overlap)
    all_classes = get_all_strategy_classes()
    # Returns: [WeatherStrategy, BTCArbitrageStrategy, BTCDirectionalStrategy]

    # Get strategy class by type (returns one per type)
    from backend.services.core import StrategyType
    cls = get_strategy_class(StrategyType.BTC)

    # Direct instantiation
    btc_arb = BTCArbitrageStrategy(kalshi_client=client)
    btc_dir = BTCDirectionalStrategy(kalshi_client=client)
"""

from typing import Dict, Type, List, Optional

from backend.services.core.base_strategy import BaseStrategy, StrategyType


# Strategy registry - populated by @register_strategy decorator
_STRATEGY_REGISTRY: Dict[StrategyType, Type[BaseStrategy]] = {}


def register_strategy(cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
    """
    Decorator to register a strategy class in the global registry.

    The strategy class must have a 'strategy_type' class attribute or instance
    attribute set during __init__.

    Example:
        @register_strategy
        class MyStrategy(BaseStrategy):
            strategy_type = StrategyType.BTC
            ...
    """
    # Check for class-level strategy_type
    if hasattr(cls, 'strategy_type'):
        strategy_type = getattr(cls, 'strategy_type')
        if isinstance(strategy_type, StrategyType):
            _STRATEGY_REGISTRY[strategy_type] = cls
    return cls


def get_strategy_class(strategy_type: StrategyType) -> Optional[Type[BaseStrategy]]:
    """
    Get a strategy class by its type.

    Args:
        strategy_type: The StrategyType enum value

    Returns:
        The strategy class if registered, None otherwise
    """
    return _STRATEGY_REGISTRY.get(strategy_type)


def get_all_strategies() -> Dict[StrategyType, Type[BaseStrategy]]:
    """
    Get all registered strategy classes.

    Returns:
        Dict mapping StrategyType to strategy class
    """
    return _STRATEGY_REGISTRY.copy()


def get_registered_types() -> List[StrategyType]:
    """
    Get list of all registered strategy types.

    Returns:
        List of StrategyType enum values that have registered strategies
    """
    return list(_STRATEGY_REGISTRY.keys())


def get_all_strategy_classes() -> List[Type[BaseStrategy]]:
    """
    Get all strategy classes regardless of type overlap.

    Unlike get_all_strategies() which maps one class per type,
    this returns ALL strategy classes including multiple classes
    that share the same StrategyType.

    Returns:
        List of all strategy classes
    """
    # Import here to avoid issues during module initialization
    from .weather_strategy import WeatherStrategy
    from .btc_arb_strategy import BTCArbitrageStrategy
    from .btc_directional_strategy import BTCDirectionalStrategy

    return [WeatherStrategy, BTCArbitrageStrategy, BTCDirectionalStrategy]


# Import strategies AFTER defining the decorator to avoid circular imports
# Each strategy module uses @register_strategy which requires the decorator to exist
from .weather_strategy import WeatherStrategy
from .btc_arb_strategy import BTCArbitrageStrategy
from .btc_directional_strategy import BTCDirectionalStrategy


__all__ = [
    # Registry functions
    "register_strategy",
    "get_strategy_class",
    "get_all_strategies",
    "get_registered_types",
    "get_all_strategy_classes",
    # Strategy implementations
    "WeatherStrategy",
    "BTCArbitrageStrategy",
    "BTCDirectionalStrategy",
]
