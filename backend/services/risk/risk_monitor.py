"""
Real-time risk monitoring dashboard data.

Aggregates data from circuit breaker and positions
to provide dashboard-ready risk metrics.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

from .circuit_breaker import CircuitBreaker, CircuitBreakerStatus
from backend.services.log_config import get_logger

logger = get_logger("risk_monitor")


@dataclass
class RiskMetrics:
    """Current risk metrics snapshot"""
    timestamp: datetime

    # P&L
    daily_pnl_cents: int
    total_pnl_cents: int
    unrealized_pnl_cents: int

    # Positions
    total_position: int
    positions_by_ticker: Dict[str, int]

    # Performance
    trades_today: int
    wins_today: int
    losses_today: int
    win_rate: float

    # Risk indicators
    drawdown_percent: float
    consecutive_losses: int

    # Circuit breaker
    circuit_breaker_status: CircuitBreakerStatus

    # Warnings
    risk_warnings: List[str]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "pnl": {
                "daily_cents": self.daily_pnl_cents,
                "total_cents": self.total_pnl_cents,
                "unrealized_cents": self.unrealized_pnl_cents,
                "daily_dollars": self.daily_pnl_cents / 100,
                "total_dollars": self.total_pnl_cents / 100,
            },
            "positions": {
                "total_contracts": self.total_position,
                "by_ticker": self.positions_by_ticker,
                "open_count": len([v for v in self.positions_by_ticker.values() if v != 0]),
            },
            "performance": {
                "trades_today": self.trades_today,
                "wins_today": self.wins_today,
                "losses_today": self.losses_today,
                "win_rate": self.win_rate,
                "win_rate_percent": f"{self.win_rate * 100:.1f}%",
            },
            "risk": {
                "drawdown_percent": self.drawdown_percent,
                "consecutive_losses": self.consecutive_losses,
                "warnings": self.risk_warnings,
                "warning_count": len(self.risk_warnings),
            },
            "circuit_breaker": self.circuit_breaker_status.to_dict(),
        }


class RiskMonitor:
    """
    Real-time risk monitoring.

    Aggregates data from circuit breaker and positions
    to provide dashboard-ready risk metrics.

    Usage:
        cb = CircuitBreaker(config)
        monitor = RiskMonitor(cb)

        # Get current metrics
        metrics = monitor.get_metrics()

        # Record activity
        monitor.record_trade(profit_cents=150)
        monitor.update_position("TICKER", 10)

        # Get API-ready response
        data = metrics.to_dict()
    """

    def __init__(self, circuit_breaker: CircuitBreaker):
        self.cb = circuit_breaker
        self._total_pnl_cents = 0
        self._unrealized_pnl_cents = 0
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
        self._positions: Dict[str, int] = {}
        self._last_daily_reset: Optional[datetime] = None

    def get_metrics(self) -> RiskMetrics:
        """Get current risk metrics"""
        self._check_daily_reset()

        cb_status = self.cb.check()

        return RiskMetrics(
            timestamp=datetime.now(timezone.utc),
            daily_pnl_cents=cb_status.daily_pnl_cents,
            total_pnl_cents=self._total_pnl_cents,
            unrealized_pnl_cents=self._unrealized_pnl_cents,
            total_position=cb_status.total_position,
            positions_by_ticker=dict(self._positions),
            trades_today=self._trades_today,
            wins_today=self._wins_today,
            losses_today=self._losses_today,
            win_rate=cb_status.win_rate,
            drawdown_percent=cb_status.drawdown_percent,
            consecutive_losses=cb_status.consecutive_losses,
            circuit_breaker_status=cb_status,
            risk_warnings=cb_status.warnings,
        )

    def record_trade(self, profit_cents: int, ticker: Optional[str] = None):
        """Record a trade result"""
        self._total_pnl_cents += profit_cents
        self._trades_today += 1

        if profit_cents > 0:
            self._wins_today += 1
        else:
            self._losses_today += 1

        self.cb.record_trade(profit_cents, ticker)

        logger.debug(
            f"Trade recorded: {profit_cents:+d}c, "
            f"today: {self._wins_today}W/{self._losses_today}L"
        )

    def update_position(self, ticker: str, position: int):
        """Update position"""
        if position == 0:
            self._positions.pop(ticker, None)
        else:
            self._positions[ticker] = position

        self.cb.update_position(ticker, position)

    def update_unrealized_pnl(self, pnl_cents: int):
        """Update unrealized P&L"""
        self._unrealized_pnl_cents = pnl_cents

    def calculate_unrealized_pnl(self, current_prices: Dict[str, int]) -> int:
        """
        Calculate unrealized P&L based on current prices.

        Args:
            current_prices: Dict of ticker -> current price in cents

        Returns:
            Total unrealized P&L in cents
        """
        # This is a simplified calculation
        # In practice, you'd need cost basis for each position
        total = 0
        for ticker, position in self._positions.items():
            if ticker in current_prices:
                # Assume buying at current price for simplicity
                # Real implementation would track cost basis
                pass
        return total

    def sync_positions(self, positions: List[dict]):
        """
        Sync positions from external source (e.g., Kalshi API).

        Args:
            positions: List of position dicts with ticker, position fields
        """
        self._positions.clear()
        for pos in positions:
            ticker = pos.get('ticker', '')
            contracts = pos.get('position', pos.get('contracts', 0))
            if ticker and contracts != 0:
                self._positions[ticker] = contracts
                self.cb.update_position(ticker, contracts)

        logger.info(f"Synced {len(self._positions)} positions")

    def reset_daily(self):
        """Reset daily counters"""
        self._trades_today = 0
        self._wins_today = 0
        self._losses_today = 0
        self._last_daily_reset = datetime.now(timezone.utc)
        self.cb.reset_daily()

    def _check_daily_reset(self):
        """Check if we need to reset daily counters"""
        now = datetime.now(timezone.utc)
        if self._last_daily_reset is None:
            self._last_daily_reset = now
            return

        if self._last_daily_reset.date() != now.date():
            self.reset_daily()

    def get_summary(self) -> dict:
        """Get a quick summary for logging/alerts"""
        metrics = self.get_metrics()
        return {
            "daily_pnl": f"${metrics.daily_pnl_cents / 100:.2f}",
            "total_pnl": f"${metrics.total_pnl_cents / 100:.2f}",
            "win_rate": f"{metrics.win_rate * 100:.1f}%",
            "positions": len([v for v in self._positions.values() if v != 0]),
            "can_trade": metrics.circuit_breaker_status.can_trade,
            "warnings": len(metrics.risk_warnings),
        }

    def get_position_summary(self) -> dict:
        """Get position summary"""
        total_long = sum(p for p in self._positions.values() if p > 0)
        total_short = sum(abs(p) for p in self._positions.values() if p < 0)

        return {
            "total_positions": len(self._positions),
            "total_long_contracts": total_long,
            "total_short_contracts": total_short,
            "net_contracts": total_long - total_short,
            "positions": dict(self._positions),
        }


class RiskAlertManager:
    """
    Manages risk alerts and notifications.

    Integrates with RiskMonitor to detect risk conditions
    and trigger appropriate alerts.
    """

    def __init__(self, monitor: RiskMonitor, alert_service=None):
        self.monitor = monitor
        self.alert_service = alert_service
        self._last_alert_time: Dict[str, datetime] = {}
        self._alert_cooldown_seconds = 60  # Don't repeat same alert within 1 minute

    async def check_and_alert(self) -> List[str]:
        """
        Check risk conditions and send alerts if needed.

        Returns:
            List of alerts that were triggered
        """
        alerts_sent = []
        metrics = self.monitor.get_metrics()
        now = datetime.now(timezone.utc)

        # Circuit breaker tripped
        if metrics.circuit_breaker_status.tripped:
            alert_key = f"cb_trip_{metrics.circuit_breaker_status.trip_reason}"
            if self._should_alert(alert_key, now):
                await self._send_alert(
                    "Circuit Breaker Tripped",
                    f"Reason: {metrics.circuit_breaker_status.trip_reason.value}",
                    "critical"
                )
                alerts_sent.append(alert_key)
                self._last_alert_time[alert_key] = now

        # High drawdown warning
        if metrics.drawdown_percent > 0.10:  # 10%
            alert_key = "high_drawdown"
            if self._should_alert(alert_key, now):
                await self._send_alert(
                    "High Drawdown Warning",
                    f"Current drawdown: {metrics.drawdown_percent * 100:.1f}%",
                    "warning"
                )
                alerts_sent.append(alert_key)
                self._last_alert_time[alert_key] = now

        # Low win rate warning
        if metrics.win_rate < 0.40 and metrics.trades_today >= 10:
            alert_key = "low_win_rate"
            if self._should_alert(alert_key, now):
                await self._send_alert(
                    "Low Win Rate Warning",
                    f"Win rate: {metrics.win_rate * 100:.1f}% over {metrics.trades_today} trades",
                    "warning"
                )
                alerts_sent.append(alert_key)
                self._last_alert_time[alert_key] = now

        # Consecutive losses
        if metrics.consecutive_losses >= 3:
            alert_key = f"consecutive_losses_{metrics.consecutive_losses}"
            if self._should_alert(alert_key, now):
                await self._send_alert(
                    "Consecutive Losses",
                    f"{metrics.consecutive_losses} losses in a row",
                    "warning"
                )
                alerts_sent.append(alert_key)
                self._last_alert_time[alert_key] = now

        return alerts_sent

    def _should_alert(self, alert_key: str, now: datetime) -> bool:
        """Check if we should send this alert (cooldown check)"""
        if alert_key not in self._last_alert_time:
            return True

        elapsed = (now - self._last_alert_time[alert_key]).total_seconds()
        return elapsed >= self._alert_cooldown_seconds

    async def _send_alert(self, title: str, message: str, level: str):
        """Send an alert via the alert service"""
        if self.alert_service:
            try:
                await self.alert_service.send_alert(title, message, level)
            except Exception as e:
                logger.error(f"Failed to send alert: {e}")
        else:
            logger.warning(f"[{level.upper()}] {title}: {message}")
