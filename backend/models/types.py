"""
Shared type definitions used across ALL chats.
These are TypedDict for flexibility and Enums for safety.
"""

from typing import TypedDict, List, Optional, Literal
from datetime import datetime
from enum import Enum


class MarketStatus(str, Enum):
    """Market lifecycle states"""
    INITIALIZED = "initialized"
    UNOPENED = "unopened"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"
    SETTLED = "settled"


class OrderSide(str, Enum):
    YES = "yes"
    NO = "no"


class OrderAction(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TimeInForce(str, Enum):
    GTC = "good_till_canceled"
    FOK = "fill_or_kill"
    IOC = "immediate_or_cancel"


class ArbitrageStrategy(str, Enum):
    ALL_YES = "all_yes"
    ALL_NO = "all_no"
    HYBRID = "hybrid"
    MIN_2_NO = "min_2_no"


# TypedDict definitions for inter-chat communication
class OrderbookLevel(TypedDict):
    price_cents: int  # 1-99
    quantity: int


class MarketSnapshot(TypedDict):
    ticker: str
    event_ticker: str
    status: str
    yes_bid: Optional[int]
    yes_ask: Optional[int]
    no_bid: Optional[int]
    no_ask: Optional[int]
    floor_strike: Optional[int]
    cap_strike: Optional[int]
    volume_24h: int
    open_interest: int
    close_time: Optional[str]  # ISO format
    fetched_at: str  # ISO format


class OrderbookSnapshot(TypedDict):
    ticker: str
    yes_bids: List[OrderbookLevel]
    no_bids: List[OrderbookLevel]
    sequence: int
    timestamp: str  # ISO format


class PositionInfo(TypedDict):
    ticker: str
    side: str  # "yes" or "no"
    quantity: int
    avg_cost_cents: float
    unrealized_pnl_cents: int


class FeeResult(TypedDict):
    fee_cents: float
    is_maker: bool
    was_capped: bool


class ArbitrageLeg(TypedDict):
    ticker: str
    side: str
    action: str
    quantity: int
    price_cents: int
    fee_cents: float


class ArbitrageRecommendation(TypedDict):
    event_ticker: str
    strategy: str
    legs: List[ArbitrageLeg]
    total_cost_cents: int
    total_fees_cents: int
    expected_profit_cents: int
    profit_after_fees_cents: int
    confidence: float
    edge_percent: float
    warnings: List[str]
    stale: bool
    calculated_at: str  # ISO format


class ValidationResult(TypedDict):
    valid: bool
    errors: List[str]
    warnings: List[str]
    price_drift_detected: bool
    max_drift_cents: int


class ExecutionResult(TypedDict):
    success: bool
    fully_filled: bool
    orders_placed: int
    orders_filled: int
    partial_fills: List[dict]
    total_cost_cents: int
    actual_fees_cents: int
    slippage_cents: int
    error: Optional[str]
    execution_time_ms: int


class CircuitBreakerStatus(TypedDict):
    can_trade: bool
    reason: Optional[str]
    daily_pnl_cents: int
    total_position: int
    consecutive_losses: int
    win_rate: float
    drawdown_percent: float
    cooldown_until: Optional[str]  # ISO format
