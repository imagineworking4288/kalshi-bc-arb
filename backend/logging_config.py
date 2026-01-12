"""
Logging configuration - re-exports from services.log_config.

This module exists for backwards compatibility.
Use backend.services.log_config directly for new code.
"""

from backend.services.log_config import (
    setup_logging,
    shutdown_logging,
    get_logger,
    LOG_DIR,
    MAIN_LOG,
    API_LOG,
    SCANNER_LOG,
    TRADE_LOG,
    ERROR_LOG,
    ColoredFormatter,
)

__all__ = [
    'setup_logging',
    'shutdown_logging',
    'get_logger',
    'LOG_DIR',
    'MAIN_LOG',
    'API_LOG',
    'SCANNER_LOG',
    'TRADE_LOG',
    'ERROR_LOG',
    'ColoredFormatter',
]
