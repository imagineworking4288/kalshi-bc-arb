"""
Execution services for Kalshi trading.

This package provides:
- Pre-trade validation
- Atomic multi-leg order execution
- Order lifecycle management
"""

from .validator import (
    PreTradeValidator,
    ValidatorConfig,
    ValidationResult,
    ValidationError,
)
from .atomic_executor import (
    AtomicExecutor,
    ExecutorConfig,
    ExecutionResult,
    ExecutionStatus,
    LegResult,
)
from .order_manager import (
    OrderManager,
    TrackedOrder,
)

__all__ = [
    # Validator
    'PreTradeValidator',
    'ValidatorConfig',
    'ValidationResult',
    'ValidationError',
    # Executor
    'AtomicExecutor',
    'ExecutorConfig',
    'ExecutionResult',
    'ExecutionStatus',
    'LegResult',
    # Order Manager
    'OrderManager',
    'TrackedOrder',
]
