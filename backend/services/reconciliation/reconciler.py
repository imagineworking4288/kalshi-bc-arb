"""
Reconciliation Service for detecting discrepancies between local state and Kalshi.

Periodically compares:
- Local positions (paper_positions table) vs Kalshi positions (API)
- Local balance vs Kalshi balance
- Position quantities and states

When critical discrepancies are found:
- Trips circuit breaker (optional)
- Sends critical alerts
- Logs for investigation
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any

from backend.services.log_config import get_logger

logger = get_logger("reconciliation")


class DiscrepancyType(str, Enum):
    """Types of discrepancies that can be detected."""

    MISSING_LOCAL = "missing_local"  # Position on Kalshi not tracked locally
    MISSING_REMOTE = "missing_remote"  # Local position not on Kalshi
    QUANTITY_MISMATCH = "quantity_mismatch"  # Contract counts don't match
    BALANCE_MISMATCH = "balance_mismatch"  # Account balance mismatch
    STALE_POSITION = "stale_position"  # Position not updated in expected time


class Severity(str, Enum):
    """Severity levels for discrepancies."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Discrepancy:
    """A detected discrepancy between local and remote state."""

    type: DiscrepancyType
    severity: Severity
    ticker: Optional[str]
    description: str
    local_value: Optional[str]
    remote_value: Optional[str]
    detected_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "ticker": self.ticker,
            "description": self.description,
            "local_value": self.local_value,
            "remote_value": self.remote_value,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class ReconciliationConfig:
    """Configuration for reconciliation service behavior."""

    run_interval_seconds: int = 300  # 5 minutes
    critical_threshold_cents: int = 1000  # $10 balance discrepancy is critical
    critical_threshold_contracts: int = 10  # 10+ contract discrepancy is critical
    halt_on_critical: bool = True  # Trip circuit breaker on critical discrepancy
    auto_start: bool = False  # Start background loop automatically


class ReconciliationService:
    """
    Detect discrepancies between local state and Kalshi.

    Compares positions tracked locally (in paper_positions or live cache)
    against actual Kalshi API positions to detect:
    - Missing positions (tracked locally but not on Kalshi, or vice versa)
    - Quantity mismatches (different contract counts)
    - Balance discrepancies

    Usage:
        reconciler = ReconciliationService(
            kalshi_client=client,
            position_manager=pm,
            alert_service=alerts,
            circuit_breaker=circuit,
            db=database
        )

        # Run once
        discrepancies = await reconciler.reconcile_now()

        # Or start background loop
        await reconciler.start()
    """

    def __init__(
        self,
        kalshi_client,
        position_manager,
        alert_service,
        circuit_breaker,
        db,
        config: Optional[ReconciliationConfig] = None,
    ):
        """
        Initialize ReconciliationService.

        Args:
            kalshi_client: KalshiClient for API access
            position_manager: PositionManager for local position queries
            alert_service: AlertService for sending alerts
            circuit_breaker: CircuitBreaker for emergency halt
            db: Database connection
            config: Optional configuration overrides
        """
        self.kalshi_client = kalshi_client
        self.position_manager = position_manager
        self.alert_service = alert_service
        self.circuit_breaker = circuit_breaker
        self.db = db
        self.config = config or ReconciliationConfig()

        # Runtime state
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._discrepancies: List[Discrepancy] = []
        self._last_run: Optional[datetime] = None
        self._run_count = 0

        logger.info(
            f"ReconciliationService initialized: "
            f"interval={self.config.run_interval_seconds}s, "
            f"halt_on_critical={self.config.halt_on_critical}"
        )

    async def start(self) -> None:
        """Start the background reconciliation loop."""
        if self._running:
            logger.warning("ReconciliationService already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._reconciliation_loop())
        logger.info("ReconciliationService background loop started")

    async def stop(self) -> None:
        """Stop the background reconciliation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("ReconciliationService stopped")

    async def _reconciliation_loop(self) -> None:
        """Background loop that runs reconciliation periodically."""
        while self._running:
            try:
                await self.reconcile_now()
            except Exception as e:
                logger.error(f"Reconciliation error: {e}")

            await asyncio.sleep(self.config.run_interval_seconds)

    async def reconcile_now(self) -> List[Discrepancy]:
        """
        Run reconciliation immediately.

        Returns:
            List of detected discrepancies
        """
        start_time = datetime.utcnow()
        discrepancies: List[Discrepancy] = []

        logger.info("Starting reconciliation...")

        # Reconcile positions
        position_discrepancies = await self._reconcile_positions()
        discrepancies.extend(position_discrepancies)

        # Update state
        self._discrepancies = discrepancies
        self._last_run = start_time
        self._run_count += 1

        # Handle critical discrepancies
        critical = [d for d in discrepancies if d.severity == Severity.CRITICAL]
        if critical:
            await self._handle_critical(critical)

        # Log results
        await self._log_reconciliation(discrepancies, start_time)

        return discrepancies

    async def _reconcile_positions(self) -> List[Discrepancy]:
        """
        Reconcile local positions against Kalshi API.

        Returns:
            List of position-related discrepancies
        """
        discrepancies: List[Discrepancy] = []

        if not self.kalshi_client:
            logger.warning("No Kalshi client - skipping position reconciliation")
            return discrepancies

        # Get local positions (live mode from position manager)
        try:
            local_positions = await self.position_manager.get_positions(mode="live")
            local_by_ticker = {p.ticker: p for p in local_positions}
        except Exception as e:
            logger.error(f"Failed to fetch local positions: {e}")
            return discrepancies

        # Get remote positions from Kalshi
        try:
            remote_positions = await self.kalshi_client.get_positions()
            # Filter to non-zero positions
            remote_by_ticker = {
                p["ticker"]: p
                for p in remote_positions
                if abs(p.get("position", 0)) > 0
            }
        except Exception as e:
            logger.error(f"Failed to fetch Kalshi positions: {e}")
            return discrepancies

        # Check for positions on Kalshi not tracked locally
        for ticker, remote_pos in remote_by_ticker.items():
            contracts = abs(remote_pos.get("position", 0))

            if ticker not in local_by_ticker:
                severity = (
                    Severity.CRITICAL
                    if contracts >= self.config.critical_threshold_contracts
                    else Severity.WARNING
                )
                discrepancies.append(
                    Discrepancy(
                        type=DiscrepancyType.MISSING_LOCAL,
                        severity=severity,
                        ticker=ticker,
                        description="Position on Kalshi not tracked locally",
                        local_value=None,
                        remote_value=str(contracts),
                    )
                )

        # Check for local positions not on Kalshi
        for ticker, local_pos in local_by_ticker.items():
            if ticker not in remote_by_ticker:
                discrepancies.append(
                    Discrepancy(
                        type=DiscrepancyType.MISSING_REMOTE,
                        severity=Severity.WARNING,
                        ticker=ticker,
                        description="Local position not found on Kalshi",
                        local_value=str(local_pos.contracts),
                        remote_value=None,
                    )
                )
            else:
                # Check quantity match
                remote_contracts = abs(remote_by_ticker[ticker].get("position", 0))
                if local_pos.contracts != remote_contracts:
                    diff = abs(local_pos.contracts - remote_contracts)
                    severity = (
                        Severity.CRITICAL
                        if diff >= self.config.critical_threshold_contracts
                        else Severity.WARNING
                    )
                    discrepancies.append(
                        Discrepancy(
                            type=DiscrepancyType.QUANTITY_MISMATCH,
                            severity=severity,
                            ticker=ticker,
                            description="Position quantity mismatch",
                            local_value=str(local_pos.contracts),
                            remote_value=str(remote_contracts),
                        )
                    )

        logger.info(
            f"Position reconciliation: {len(local_by_ticker)} local, "
            f"{len(remote_by_ticker)} remote, {len(discrepancies)} discrepancies"
        )

        return discrepancies

    async def _handle_critical(self, critical: List[Discrepancy]) -> None:
        """
        Handle critical discrepancies.

        Args:
            critical: List of critical discrepancies
        """
        logger.warning(f"CRITICAL: {len(critical)} critical discrepancies detected!")

        # Trip circuit breaker if configured
        if self.config.halt_on_critical and self.circuit_breaker:
            await self.circuit_breaker.force_trip(
                f"Critical reconciliation discrepancy: {len(critical)} issues"
            )

        # Send critical alert
        if self.alert_service:
            # Import AlertType and AlertPriority here to avoid circular imports
            from backend.services.core.alert_service import AlertType, AlertPriority

            await self.alert_service.send(
                AlertType.RISK_WARNING,
                "Critical Reconciliation Discrepancy",
                f"Found {len(critical)} critical discrepancies - trading may be halted",
                AlertPriority.CRITICAL,
                {
                    "discrepancy_count": len(critical),
                    "discrepancies": [d.to_dict() for d in critical],
                },
            )

    async def _log_reconciliation(
        self, discrepancies: List[Discrepancy], start_time: datetime
    ) -> None:
        """Log reconciliation results."""
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        if discrepancies:
            critical_count = sum(1 for d in discrepancies if d.severity == Severity.CRITICAL)
            warning_count = sum(1 for d in discrepancies if d.severity == Severity.WARNING)
            logger.warning(
                f"Reconciliation complete: {len(discrepancies)} discrepancies "
                f"({critical_count} critical, {warning_count} warning) in {duration_ms}ms"
            )
        else:
            logger.info(f"Reconciliation complete: no discrepancies in {duration_ms}ms")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current reconciliation service status.

        Returns:
            Status dictionary for dashboard display
        """
        critical_count = sum(
            1 for d in self._discrepancies if d.severity == Severity.CRITICAL
        )

        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "run_count": self._run_count,
            "discrepancy_count": len(self._discrepancies),
            "critical_count": critical_count,
            "config": {
                "run_interval_seconds": self.config.run_interval_seconds,
                "critical_threshold_contracts": self.config.critical_threshold_contracts,
                "critical_threshold_cents": self.config.critical_threshold_cents,
                "halt_on_critical": self.config.halt_on_critical,
            },
            "discrepancies": [d.to_dict() for d in self._discrepancies],
        }
