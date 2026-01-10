"""
Circuit breaker to prevent excessive losses.

Monitors trading activity and halts trading when limits are exceeded.
Implements multiple trigger conditions for comprehensive risk management.

This is an enhanced version with additional protections:
- Win rate monitoring
- Maximum drawdown tracking
- Position limit checking
- API error rate tracking
"""

import asyncio
from typing import Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from collections import deque
from enum import Enum

from backend.services.log_config import get_logger

logger = get_logger("circuit_breaker_v2")


class TripReason(str, Enum):
    DAILY_LOSS = "daily_loss"
    POSITION_LIMIT = "position_limit"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    WIN_RATE = "win_rate"
    DRAWDOWN = "drawdown"
    API_ERRORS = "api_errors"
    ORDER_REJECTIONS = "order_rejections"
    MANUAL = "manual"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""
    # Position limits
    max_position_per_market: int = 100
    max_total_position: int = 500
    max_event_exposure: int = 300

    # Daily limits
    max_daily_loss_cents: int = 5000  # $50
    max_daily_trades: int = 100

    # Performance limits
    max_consecutive_losses: int = 5
    min_win_rate_threshold: float = 0.35  # Over last 20 trades
    win_rate_lookback: int = 20
    max_drawdown_percent: float = 0.15  # 15%

    # Operational limits
    max_api_errors_per_hour: int = 10
    max_order_rejections: int = 5

    # Recovery
    cooldown_seconds: int = 300  # 5 minutes
    auto_reset_at_midnight: bool = True


@dataclass
class CircuitBreakerStatus:
    """Current circuit breaker status"""
    can_trade: bool
    tripped: bool
    trip_reason: Optional[TripReason]
    trip_time: Optional[datetime]
    cooldown_until: Optional[datetime]

    # Current metrics
    daily_pnl_cents: int
    total_position: int
    consecutive_losses: int
    win_rate: float
    drawdown_percent: float
    api_errors_hour: int

    # Warnings (approaching limits)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "can_trade": self.can_trade,
            "tripped": self.tripped,
            "trip_reason": self.trip_reason.value if self.trip_reason else None,
            "trip_time": self.trip_time.isoformat() if self.trip_time else None,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "daily_pnl_cents": self.daily_pnl_cents,
            "total_position": self.total_position,
            "consecutive_losses": self.consecutive_losses,
            "win_rate": self.win_rate,
            "drawdown_percent": self.drawdown_percent,
            "api_errors_hour": self.api_errors_hour,
            "warnings": self.warnings,
        }


class CircuitBreaker:
    """
    Risk circuit breaker for trading system.

    Monitors:
    - Daily P&L
    - Position sizes
    - Consecutive losses
    - Win rate
    - Maximum drawdown
    - API errors

    Usage:
        cb = CircuitBreaker(config)

        # Before each trade
        status = cb.check()
        if not status.can_trade:
            print(f"Trading halted: {status.trip_reason}")
            return

        # After trade
        cb.record_trade(profit_cents=150)

        # After loss
        cb.record_trade(profit_cents=-200)
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._lock = asyncio.Lock()

        # State
        self._tripped = False
        self._trip_reason: Optional[TripReason] = None
        self._trip_time: Optional[datetime] = None

        # Metrics
        self._daily_pnl_cents = 0
        self._daily_trades = 0
        self._positions: dict = {}  # ticker -> position size

        # Trade history for win rate
        self._trade_results: deque = deque(maxlen=self.config.win_rate_lookback)
        self._consecutive_losses = 0

        # Peak for drawdown
        self._peak_balance_cents = 0
        self._current_balance_cents = 0

        # Error tracking
        self._api_errors: deque = deque(maxlen=100)  # (timestamp, error)
        self._order_rejections = 0

        # Day tracking
        self._current_day: Optional[datetime] = None

    def check(self) -> CircuitBreakerStatus:
        """
        Check if trading is allowed (synchronous version).

        Returns:
            CircuitBreakerStatus with current state and metrics
        """
        self._check_daily_reset()

        warnings = []

        # Check if in cooldown
        if self._tripped and self._trip_time:
            cooldown_until = self._trip_time + timedelta(seconds=self.config.cooldown_seconds)
            if datetime.now(timezone.utc) < cooldown_until:
                return CircuitBreakerStatus(
                    can_trade=False,
                    tripped=True,
                    trip_reason=self._trip_reason,
                    trip_time=self._trip_time,
                    cooldown_until=cooldown_until,
                    daily_pnl_cents=self._daily_pnl_cents,
                    total_position=self._total_position(),
                    consecutive_losses=self._consecutive_losses,
                    win_rate=self._calculate_win_rate(),
                    drawdown_percent=self._calculate_drawdown(),
                    api_errors_hour=self._count_recent_errors(),
                )
            else:
                # Cooldown expired, reset trip
                self._tripped = False
                self._trip_reason = None
                self._trip_time = None

        # Check all limits

        # 1. Daily loss
        if self._daily_pnl_cents < -self.config.max_daily_loss_cents:
            return self._trip(TripReason.DAILY_LOSS)
        elif self._daily_pnl_cents < -self.config.max_daily_loss_cents * 0.8:
            warnings.append(f"Approaching daily loss limit: ${-self._daily_pnl_cents/100:.2f}")

        # 2. Total position
        total_pos = self._total_position()
        if total_pos > self.config.max_total_position:
            return self._trip(TripReason.POSITION_LIMIT)
        elif total_pos > self.config.max_total_position * 0.8:
            warnings.append(f"High position: {total_pos}/{self.config.max_total_position}")

        # 3. Consecutive losses
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            return self._trip(TripReason.CONSECUTIVE_LOSSES)
        elif self._consecutive_losses >= self.config.max_consecutive_losses - 1:
            warnings.append(f"Consecutive losses: {self._consecutive_losses}")

        # 4. Win rate
        win_rate = self._calculate_win_rate()
        if len(self._trade_results) >= self.config.win_rate_lookback:
            if win_rate < self.config.min_win_rate_threshold:
                return self._trip(TripReason.WIN_RATE)
            elif win_rate < self.config.min_win_rate_threshold + 0.05:
                warnings.append(f"Low win rate: {win_rate:.1%}")

        # 5. Drawdown
        drawdown = self._calculate_drawdown()
        if drawdown > self.config.max_drawdown_percent:
            return self._trip(TripReason.DRAWDOWN)
        elif drawdown > self.config.max_drawdown_percent * 0.8:
            warnings.append(f"High drawdown: {drawdown:.1%}")

        # 6. API errors
        error_count = self._count_recent_errors()
        if error_count >= self.config.max_api_errors_per_hour:
            return self._trip(TripReason.API_ERRORS)

        # 7. Order rejections
        if self._order_rejections >= self.config.max_order_rejections:
            return self._trip(TripReason.ORDER_REJECTIONS)

        return CircuitBreakerStatus(
            can_trade=True,
            tripped=False,
            trip_reason=None,
            trip_time=None,
            cooldown_until=None,
            daily_pnl_cents=self._daily_pnl_cents,
            total_position=total_pos,
            consecutive_losses=self._consecutive_losses,
            win_rate=win_rate,
            drawdown_percent=drawdown,
            api_errors_hour=error_count,
            warnings=warnings,
        )

    async def check_async(self) -> CircuitBreakerStatus:
        """Check if trading is allowed (async version with lock)."""
        async with self._lock:
            return self.check()

    def _trip(self, reason: TripReason) -> CircuitBreakerStatus:
        """Trip the circuit breaker"""
        self._tripped = True
        self._trip_reason = reason
        self._trip_time = datetime.now(timezone.utc)
        cooldown_until = self._trip_time + timedelta(seconds=self.config.cooldown_seconds)

        logger.warning(f"CIRCUIT BREAKER TRIPPED: {reason.value}")

        return CircuitBreakerStatus(
            can_trade=False,
            tripped=True,
            trip_reason=reason,
            trip_time=self._trip_time,
            cooldown_until=cooldown_until,
            daily_pnl_cents=self._daily_pnl_cents,
            total_position=self._total_position(),
            consecutive_losses=self._consecutive_losses,
            win_rate=self._calculate_win_rate(),
            drawdown_percent=self._calculate_drawdown(),
            api_errors_hour=self._count_recent_errors(),
        )

    def record_trade(self, profit_cents: int, ticker: Optional[str] = None):
        """Record a completed trade"""
        self._daily_pnl_cents += profit_cents
        self._daily_trades += 1

        # Track win/loss
        is_win = profit_cents > 0
        self._trade_results.append(is_win)

        if is_win:
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1

        # Update balance for drawdown
        self._current_balance_cents += profit_cents
        if self._current_balance_cents > self._peak_balance_cents:
            self._peak_balance_cents = self._current_balance_cents

        logger.debug(
            f"Trade recorded: {profit_cents:+d}c, "
            f"daily={self._daily_pnl_cents}c, "
            f"consecutive_losses={self._consecutive_losses}"
        )

    async def record_trade_async(self, profit_cents: int, ticker: Optional[str] = None):
        """Record a completed trade (async version)"""
        async with self._lock:
            self.record_trade(profit_cents, ticker)

    def update_position(self, ticker: str, position: int):
        """Update position for a ticker"""
        if position == 0:
            self._positions.pop(ticker, None)
        else:
            self._positions[ticker] = position

    async def update_position_async(self, ticker: str, position: int):
        """Update position (async version)"""
        async with self._lock:
            self.update_position(ticker, position)

    def record_api_error(self, error: str):
        """Record an API error"""
        self._api_errors.append((datetime.now(timezone.utc), error))

    def record_order_rejection(self):
        """Record an order rejection"""
        self._order_rejections += 1

    def manual_trip(self, reason: str = "Manual"):
        """Manually trip the circuit breaker"""
        self._trip(TripReason.MANUAL)
        logger.warning(f"Manual circuit breaker trip: {reason}")

    def reset(self):
        """Reset the circuit breaker"""
        self._tripped = False
        self._trip_reason = None
        self._trip_time = None
        self._consecutive_losses = 0
        self._order_rejections = 0
        logger.info("Circuit breaker reset")

    async def reset_async(self):
        """Reset the circuit breaker (async version)"""
        async with self._lock:
            self.reset()

    def reset_daily(self):
        """Reset daily metrics"""
        self._daily_pnl_cents = 0
        self._daily_trades = 0
        self._order_rejections = 0
        self._current_day = datetime.now(timezone.utc).date()
        logger.info("Daily metrics reset")

    def set_initial_balance(self, balance_cents: int):
        """Set initial balance for drawdown calculation"""
        self._current_balance_cents = balance_cents
        self._peak_balance_cents = balance_cents

    def _check_daily_reset(self):
        """Reset daily metrics at midnight"""
        if not self.config.auto_reset_at_midnight:
            return

        today = datetime.now(timezone.utc).date()
        if self._current_day != today:
            self._daily_pnl_cents = 0
            self._daily_trades = 0
            self._order_rejections = 0
            self._current_day = today
            logger.info("Auto daily reset at midnight")

    def _total_position(self) -> int:
        """Calculate total position across all markets"""
        return sum(abs(p) for p in self._positions.values())

    def _calculate_win_rate(self) -> float:
        """Calculate win rate from recent trades"""
        if not self._trade_results:
            return 0.5  # Default to 50% if no history
        return sum(self._trade_results) / len(self._trade_results)

    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown from peak"""
        if self._peak_balance_cents <= 0:
            return 0.0

        drawdown = (self._peak_balance_cents - self._current_balance_cents) / self._peak_balance_cents
        return max(0.0, drawdown)

    def _count_recent_errors(self) -> int:
        """Count API errors in last hour"""
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        return sum(1 for ts, _ in self._api_errors if ts > one_hour_ago)

    def get_status(self) -> dict:
        """Get status as dictionary for API"""
        status = self.check()
        return status.to_dict()

    def get_detailed_status(self) -> dict:
        """Get detailed status including configuration"""
        status = self.check()
        return {
            **status.to_dict(),
            "config": {
                "max_position_per_market": self.config.max_position_per_market,
                "max_total_position": self.config.max_total_position,
                "max_daily_loss_cents": self.config.max_daily_loss_cents,
                "max_consecutive_losses": self.config.max_consecutive_losses,
                "min_win_rate_threshold": self.config.min_win_rate_threshold,
                "max_drawdown_percent": self.config.max_drawdown_percent,
                "cooldown_seconds": self.config.cooldown_seconds,
            },
            "metrics": {
                "trades_today": self._daily_trades,
                "trade_history_size": len(self._trade_results),
                "positions_count": len(self._positions),
                "peak_balance_cents": self._peak_balance_cents,
                "current_balance_cents": self._current_balance_cents,
            }
        }
