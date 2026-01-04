"""
Core trading infrastructure module.

Provides reusable components for all trading strategies:
- Strategy base class and signal management
- Position sizing (Kelly Criterion)
- Risk management and circuit breakers
- Atomic order execution
- Performance tracking
- Alerting and notifications
- Backtesting
"""

from .base_strategy import (
    StrategyType,
    SignalType,
    SignalStatus,
    SignalLeg,
    TradingSignal,
    BaseStrategy
)

from .signal_manager import SignalManager

from .kelly_sizing import (
    KellyConfig,
    KellyResult,
    KellySizing
)

from .risk_manager import (
    RiskLimits,
    RiskCheck,
    RiskManager
)

from .circuit_breaker import (
    CBConfig,
    CircuitBreaker
)

from .batch_executor import (
    OrderSide,
    OrderAction,
    OrderStatus,
    OrderLeg,
    BatchResult,
    BatchExecutor
)

from .performance_tracker import (
    Metrics,
    PerformanceTracker
)

from .alert_service import (
    AlertType,
    AlertPriority,
    Alert,
    AlertService
)

from .strategy_orchestrator import StrategyOrchestrator

from .backtest_engine import (
    BacktestConfig,
    BacktestTrade,
    BacktestResult,
    BacktestEngine
)

__all__ = [
    # Strategy types and signals
    "StrategyType",
    "SignalType",
    "SignalStatus",
    "SignalLeg",
    "TradingSignal",
    "BaseStrategy",

    # Signal management
    "SignalManager",

    # Kelly sizing
    "KellyConfig",
    "KellyResult",
    "KellySizing",

    # Risk management
    "RiskLimits",
    "RiskCheck",
    "RiskManager",

    # Circuit breaker
    "CBConfig",
    "CircuitBreaker",

    # Order execution
    "OrderSide",
    "OrderAction",
    "OrderStatus",
    "OrderLeg",
    "BatchResult",
    "BatchExecutor",

    # Performance tracking
    "Metrics",
    "PerformanceTracker",

    # Alerts
    "AlertType",
    "AlertPriority",
    "Alert",
    "AlertService",

    # Main orchestrator
    "StrategyOrchestrator",

    # Backtesting
    "BacktestConfig",
    "BacktestTrade",
    "BacktestResult",
    "BacktestEngine"
]
