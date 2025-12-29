"""Logging configuration"""

import logging
import sys
from typing import Optional

from ..config import get_settings


def setup_logging(level: Optional[str] = None) -> logging.Logger:
    """
    Configure application logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR). Uses config if not specified.

    Returns:
        Configured logger instance
    """
    settings = get_settings()
    log_level = level or settings.log_level

    # Create logger
    logger = logging.getLogger("kalshi_arb")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level.upper()))

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)

    # Add handler if not already added
    if not logger.handlers:
        logger.addHandler(handler)

    return logger


def get_logger(name: str = "kalshi_arb") -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)
