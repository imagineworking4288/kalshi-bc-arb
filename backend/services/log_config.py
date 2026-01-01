"""
Centralized Logging Configuration

All services log to:
1. Console (their own terminal)
2. Shared log files (for log viewer terminal)
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
import json

# Log directory
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

# Log files
MAIN_LOG = LOG_DIR / "kalshi.log"
API_LOG = LOG_DIR / "api.log"
SCANNER_LOG = LOG_DIR / "scanners.log"
TRADE_LOG = LOG_DIR / "trades.log"
ERROR_LOG = LOG_DIR / "errors.log"

class ColoredFormatter(logging.Formatter):
    """Colored console formatter."""

    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    SOURCE_COLORS = {
        'btc_arb': '\033[93m',      # Bright Yellow
        'weather_arb': '\033[96m',  # Bright Cyan
        'api': '\033[95m',          # Bright Magenta
        'trade': '\033[92m',        # Bright Green
        'scanner': '\033[94m',      # Bright Blue
        'nws': '\033[36m',          # Cyan
    }

    def format(self, record):
        level_color = self.COLORS.get(record.levelname, '')

        source_color = ''
        for key, color in self.SOURCE_COLORS.items():
            if key in record.name.lower():
                source_color = color
                break

        timestamp = datetime.now().strftime('%H:%M:%S')

        formatted = (
            f"\033[90m{timestamp}\033[0m "
            f"{level_color}[{record.levelname:^7}]{self.RESET} "
            f"{source_color}[{record.name}]{self.RESET} "
            f"{record.getMessage()}"
        )

        return formatted


def setup_logging(service_name: str, log_level: int = logging.INFO):
    """Setup logging for a service."""
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers = []

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredFormatter())
    root_logger.addHandler(console_handler)

    # Main log file
    main_handler = RotatingFileHandler(MAIN_LOG, maxBytes=10*1024*1024, backupCount=5)
    main_handler.setLevel(log_level)
    main_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
    root_logger.addHandler(main_handler)

    # Service-specific log
    service_log = {"api": API_LOG, "scanner": SCANNER_LOG}.get(service_name, LOG_DIR / f"{service_name}.log")
    service_handler = RotatingFileHandler(service_log, maxBytes=10*1024*1024, backupCount=3)
    service_handler.setLevel(log_level)
    service_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
    root_logger.addHandler(service_handler)

    # Error log
    error_handler = RotatingFileHandler(ERROR_LOG, maxBytes=5*1024*1024, backupCount=3)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s\n%(pathname)s:%(lineno)d'))
    root_logger.addHandler(error_handler)

    return root_logger
