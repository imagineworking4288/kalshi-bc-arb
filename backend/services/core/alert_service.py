"""
Alert and notification service.
Sends alerts via console logging and WebSocket.
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertType(str, Enum):
    """Types of alerts."""
    OPPORTUNITY = "opportunity"
    TRADE_EXECUTED = "trade_executed"
    TRADE_FAILED = "trade_failed"
    CIRCUIT_BREAKER = "circuit_breaker"
    RISK_WARNING = "risk_warning"
    ERROR = "error"
    INFO = "info"


class AlertPriority(str, Enum):
    """Alert priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Alert:
    """An alert notification."""
    id: str
    type: AlertType
    title: str
    message: str
    priority: AlertPriority
    timestamp: datetime
    data: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "acknowledged": self.acknowledged
        }


class AlertService:
    """
    Sends alerts via console and WebSocket.

    Maintains a history of recent alerts for dashboard display.
    Integrates with the WebSocket connection manager for real-time updates.
    """

    def __init__(self, websocket_manager=None, max_history: int = 100):
        """
        Initialize alert service.

        Args:
            websocket_manager: WebSocket ConnectionManager for real-time alerts
            max_history: Maximum alerts to keep in history
        """
        self.ws_manager = websocket_manager
        self._history: deque = deque(maxlen=max_history)
        self._alert_count = 0

    async def send(
        self,
        alert_type: AlertType,
        title: str,
        message: str,
        priority: AlertPriority = AlertPriority.MEDIUM,
        data: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """
        Send an alert notification.

        Args:
            alert_type: Type of alert
            title: Short title
            message: Detailed message
            priority: Alert priority
            data: Additional data to include

        Returns:
            The created Alert object
        """
        self._alert_count += 1
        alert = Alert(
            id=f"alert-{self._alert_count}",
            type=alert_type,
            title=title,
            message=message,
            priority=priority,
            timestamp=datetime.utcnow(),
            data=data or {}
        )

        # Log based on priority
        log_message = f"[{alert_type.value.upper()}] {title}: {message}"

        if priority == AlertPriority.CRITICAL:
            logger.critical(log_message)
        elif priority == AlertPriority.HIGH:
            logger.warning(log_message)
        elif priority == AlertPriority.MEDIUM:
            logger.info(log_message)
        else:
            logger.debug(log_message)

        # Add to history
        self._history.appendleft(alert)

        # Send via WebSocket
        if self.ws_manager:
            try:
                await self.ws_manager.broadcast({
                    "type": "alert",
                    "alert": alert.to_dict()
                })
            except Exception as e:
                logger.error(f"Failed to broadcast alert: {e}")

        return alert

    # Convenience methods for common alert types

    async def opportunity(
        self,
        ticker: str,
        edge_percent: float,
        strategy: str,
        data: Optional[Dict] = None
    ) -> Alert:
        """Send opportunity found alert."""
        return await self.send(
            AlertType.OPPORTUNITY,
            f"Opportunity: {ticker}",
            f"{strategy} found {edge_percent:.1f}% edge",
            AlertPriority.MEDIUM,
            {"ticker": ticker, "edge_percent": edge_percent, "strategy": strategy, **(data or {})}
        )

    async def trade_executed(
        self,
        ticker: str,
        contracts: int,
        price_cents: int,
        pnl_cents: int,
        mode: str = "paper",
        data: Optional[Dict] = None
    ) -> Alert:
        """Send trade executed alert."""
        return await self.send(
            AlertType.TRADE_EXECUTED,
            f"Trade: {ticker}",
            f"Executed {contracts} @ {price_cents}¢ ({mode})",
            AlertPriority.MEDIUM,
            {
                "ticker": ticker,
                "contracts": contracts,
                "price_cents": price_cents,
                "pnl_cents": pnl_cents,
                "mode": mode,
                **(data or {})
            }
        )

    async def trade_failed(
        self,
        ticker: str,
        reason: str,
        data: Optional[Dict] = None
    ) -> Alert:
        """Send trade failed alert."""
        return await self.send(
            AlertType.TRADE_FAILED,
            f"Trade Failed: {ticker}",
            reason,
            AlertPriority.HIGH,
            {"ticker": ticker, "reason": reason, **(data or {})}
        )

    async def circuit_breaker(
        self,
        tripped: bool,
        reason: str,
        data: Optional[Dict] = None
    ) -> Alert:
        """Send circuit breaker alert."""
        if tripped:
            return await self.send(
                AlertType.CIRCUIT_BREAKER,
                "Circuit Breaker TRIPPED",
                reason,
                AlertPriority.CRITICAL,
                {"tripped": True, "reason": reason, **(data or {})}
            )
        else:
            return await self.send(
                AlertType.CIRCUIT_BREAKER,
                "Circuit Breaker Reset",
                reason,
                AlertPriority.MEDIUM,
                {"tripped": False, "reason": reason, **(data or {})}
            )

    async def risk_warning(
        self,
        warning_type: str,
        message: str,
        data: Optional[Dict] = None
    ) -> Alert:
        """Send risk warning alert."""
        return await self.send(
            AlertType.RISK_WARNING,
            f"Risk: {warning_type}",
            message,
            AlertPriority.HIGH,
            {"warning_type": warning_type, **(data or {})}
        )

    async def error(
        self,
        error_type: str,
        message: str,
        data: Optional[Dict] = None
    ) -> Alert:
        """Send error alert."""
        return await self.send(
            AlertType.ERROR,
            f"Error: {error_type}",
            message,
            AlertPriority.HIGH,
            {"error_type": error_type, **(data or {})}
        )

    async def info(
        self,
        title: str,
        message: str,
        data: Optional[Dict] = None
    ) -> Alert:
        """Send info alert."""
        return await self.send(
            AlertType.INFO,
            title,
            message,
            AlertPriority.LOW,
            data
        )

    def get_recent(self, limit: int = 20) -> List[Dict]:
        """
        Get recent alerts.

        Args:
            limit: Maximum alerts to return

        Returns:
            List of alert dictionaries
        """
        alerts = list(self._history)[:limit]
        return [alert.to_dict() for alert in alerts]

    def get_unacknowledged(self, limit: int = 50) -> List[Dict]:
        """
        Get unacknowledged alerts.

        Args:
            limit: Maximum alerts to return

        Returns:
            List of unacknowledged alert dictionaries
        """
        alerts = [a for a in self._history if not a.acknowledged][:limit]
        return [alert.to_dict() for alert in alerts]

    def acknowledge(self, alert_id: str) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_id: ID of alert to acknowledge

        Returns:
            True if found and acknowledged
        """
        for alert in self._history:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def acknowledge_all(self) -> int:
        """
        Acknowledge all alerts.

        Returns:
            Number of alerts acknowledged
        """
        count = 0
        for alert in self._history:
            if not alert.acknowledged:
                alert.acknowledged = True
                count += 1
        return count

    def clear_history(self) -> int:
        """
        Clear alert history.

        Returns:
            Number of alerts cleared
        """
        count = len(self._history)
        self._history.clear()
        return count

    def get_stats(self) -> Dict[str, Any]:
        """Get alert statistics."""
        type_counts = {}
        priority_counts = {}

        for alert in self._history:
            type_counts[alert.type.value] = type_counts.get(alert.type.value, 0) + 1
            priority_counts[alert.priority.value] = priority_counts.get(alert.priority.value, 0) + 1

        return {
            "total_alerts": self._alert_count,
            "history_size": len(self._history),
            "unacknowledged": sum(1 for a in self._history if not a.acknowledged),
            "by_type": type_counts,
            "by_priority": priority_counts
        }
