"""
Reconciliation module for detecting discrepancies between local state and Kalshi.

Provides:
- ReconciliationService: Main service for position and balance reconciliation
- ReconciliationConfig: Configuration for reconciliation behavior
- Discrepancy: Data class representing a detected discrepancy
- DiscrepancyType: Types of discrepancies
- Severity: Severity levels for discrepancies
"""

from .reconciler import (
    ReconciliationService,
    ReconciliationConfig,
    Discrepancy,
    DiscrepancyType,
    Severity,
)

__all__ = [
    "ReconciliationService",
    "ReconciliationConfig",
    "Discrepancy",
    "DiscrepancyType",
    "Severity",
]
