"""
Circuit breaker for emergency trading halt.
Automatically stops trading when loss limits are hit.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from enum import Enum

from ..log_config import get_logger

logger = get_logger("circuit_breaker")


class TripReason(str, Enum):
    """Reasons for circuit breaker trip."""
    DAILY_LOSS = "daily_loss"
    POSITION_LIMIT = "position_limit"
    CONSECUTIVE_LOSSES = "consecutive_losses"
    WIN_RATE = "win_rate"
    DRAWDOWN = "drawdown"
    API_ERRORS = "api_errors"
    ORDER_REJECTIONS = "order_rejections"
    MANUAL = "manual"
    HOURLY_LOSSES = "hourly_losses"


@dataclass
class CBConfig:
    """Circuit breaker configuration."""
    max_consecutive_losses: int = 5  # Stop after N consecutive losses
    max_daily_loss_cents: int = 5000  # $50 daily loss limit
    max_hourly_losses: int = 3  # Max losses in an hour
    cooldown_seconds: int = 300  # 5 minute cooldown after trip
    auto_reset_hours: int = 24  # Auto-reset after 24 hours


# Backwards compatibility alias
CircuitBreakerConfig = CBConfig


@dataclass
class CircuitBreakerStatus:
    """Current circuit breaker status (backwards compatibility)."""
    can_trade: bool
    tripped: bool
    trip_reason: Optional[TripReason]
    trip_time: Optional[datetime]
    cooldown_until: Optional[datetime]
    daily_pnl_cents: int = 0
    total_position: int = 0
    consecutive_losses: int = 0
    win_rate: float = 0.0
    drawdown_percent: float = 0.0
    api_errors_hour: int = 0
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


@dataclass
class LossRecord:
    """Record of a loss event."""
    timestamp: datetime
    pnl_cents: int
    ticker: str = ""


class CircuitBreaker:
    """
    Emergency halt mechanism for trading.

    The circuit breaker trips when:
    - Too many consecutive losses
    - Daily loss limit exceeded
    - Too many losses in a short time period

    When tripped, all trading is halted until:
    - Manual reset
    - Cooldown period expires
    - Auto-reset after 24 hours
    """

    def __init__(self, config: CBConfig = None):
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config or CBConfig()

        # State tracking
        self._is_tripped: bool = False
        self._trip_reason: str = ""
        self._trip_time: datetime = None
        self._consecutive_losses: int = 0
        self._daily_loss_cents: int = 0
        self._hourly_losses: List[LossRecord] = []
        self._total_losses: int = 0
        self._total_wins: int = 0
        self._last_reset: datetime = datetime.utcnow()

        # Thread safety
        self._lock = asyncio.Lock()

    async def can_trade(self) -> Tuple[bool, str]:
        """
        Check if trading is allowed.

        Returns:
            Tuple of (can_trade, reason)
        """
        async with self._lock:
            # Check auto-reset
            await self._check_auto_reset()

            if self._is_tripped:
                # Check if cooldown has expired
                if self._trip_time:
                    elapsed = (datetime.utcnow() - self._trip_time).total_seconds()
                    if elapsed >= self.config.cooldown_seconds:
                        await self._do_reset("Cooldown expired")
                        return True, "Trading resumed after cooldown"

                return False, f"Circuit breaker tripped: {self._trip_reason}"

            return True, "Trading allowed"

    async def record_result(
        self,
        won: bool,
        pnl_cents: int,
        ticker: str = ""
    ) -> bool:
        """
        Record a trade result.

        Args:
            won: Whether the trade was profitable
            pnl_cents: P&L in cents (negative for loss)
            ticker: Market ticker (optional, for logging)

        Returns:
            True if circuit breaker tripped
        """
        async with self._lock:
            now = datetime.utcnow()

            if won:
                self._consecutive_losses = 0
                self._total_wins += 1
                logger.info(f"Win recorded: +{pnl_cents}¢ ({ticker})")
            else:
                self._consecutive_losses += 1
                self._total_losses += 1
                self._daily_loss_cents += abs(pnl_cents)
                self._hourly_losses.append(LossRecord(
                    timestamp=now,
                    pnl_cents=pnl_cents,
                    ticker=ticker
                ))
                logger.info(
                    f"Loss recorded: {pnl_cents}¢ ({ticker}) "
                    f"consecutive={self._consecutive_losses}"
                )

            # Clean up old hourly losses
            hour_ago = now - timedelta(hours=1)
            self._hourly_losses = [
                loss for loss in self._hourly_losses
                if loss.timestamp > hour_ago
            ]

            # Check trip conditions
            return await self._check_trip_conditions()

    async def _check_trip_conditions(self) -> bool:
        """Check if circuit breaker should trip. Returns True if tripped."""
        # Check consecutive losses
        if self._consecutive_losses >= self.config.max_consecutive_losses:
            await self._trip(
                f"Consecutive losses: {self._consecutive_losses} "
                f"(limit: {self.config.max_consecutive_losses})"
            )
            return True

        # Check daily loss
        if self._daily_loss_cents >= self.config.max_daily_loss_cents:
            await self._trip(
                f"Daily loss limit: {self._daily_loss_cents}¢ "
                f"(limit: {self.config.max_daily_loss_cents}¢)"
            )
            return True

        # Check hourly losses
        if len(self._hourly_losses) >= self.config.max_hourly_losses:
            await self._trip(
                f"Hourly losses: {len(self._hourly_losses)} "
                f"(limit: {self.config.max_hourly_losses})"
            )
            return True

        return False

    async def _trip(self, reason: str) -> None:
        """Trip the circuit breaker."""
        self._is_tripped = True
        self._trip_reason = reason
        self._trip_time = datetime.utcnow()
        logger.warning(f"CIRCUIT BREAKER TRIPPED: {reason}")

    async def reset(self) -> bool:
        """
        Manually reset the circuit breaker.

        Returns:
            True if reset was successful
        """
        async with self._lock:
            if self._is_tripped:
                await self._do_reset("Manual reset")
                return True
            return False

    async def _do_reset(self, reason: str) -> None:
        """Perform the actual reset."""
        self._is_tripped = False
        self._trip_reason = ""
        self._trip_time = None
        self._consecutive_losses = 0
        self._daily_loss_cents = 0
        self._hourly_losses.clear()
        self._last_reset = datetime.utcnow()
        logger.info(f"Circuit breaker reset: {reason}")

    async def _check_auto_reset(self) -> None:
        """Check for auto-reset condition."""
        if not self._is_tripped:
            return

        if self._trip_time:
            elapsed = datetime.utcnow() - self._trip_time
            if elapsed.total_seconds() >= self.config.auto_reset_hours * 3600:
                await self._do_reset("Auto-reset after 24 hours")

    async def force_trip(self, reason: str = "Manual trip") -> None:
        """Manually trip the circuit breaker."""
        async with self._lock:
            await self._trip(reason)

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        now = datetime.utcnow()

        remaining_cooldown = 0
        if self._is_tripped and self._trip_time:
            elapsed = (now - self._trip_time).total_seconds()
            remaining_cooldown = max(0, self.config.cooldown_seconds - elapsed)

        return {
            "is_tripped": self._is_tripped,
            "trip_reason": self._trip_reason,
            "trip_time": self._trip_time.isoformat() if self._trip_time else None,
            "cooldown_remaining_seconds": int(remaining_cooldown),
            "stats": {
                "consecutive_losses": self._consecutive_losses,
                "daily_loss_cents": self._daily_loss_cents,
                "hourly_loss_count": len(self._hourly_losses),
                "total_wins": self._total_wins,
                "total_losses": self._total_losses
            },
            "limits": {
                "max_consecutive_losses": self.config.max_consecutive_losses,
                "max_daily_loss_cents": self.config.max_daily_loss_cents,
                "max_hourly_losses": self.config.max_hourly_losses,
                "cooldown_seconds": self.config.cooldown_seconds,
                "auto_reset_hours": self.config.auto_reset_hours
            },
            "last_reset": self._last_reset.isoformat()
        }

    async def daily_reset(self) -> None:
        """Reset daily counters (call at start of trading day)."""
        async with self._lock:
            self._daily_loss_cents = 0
            logger.info("Daily loss counter reset")
