"""
Centralized Logging Configuration

Thread-safe logging using QueueHandler pattern to avoid Windows PermissionError.

All services log to:
1. Console (their own terminal)
2. Shared log files (for log viewer terminal)
"""

import logging
import logging.handlers
import queue
import sys
import atexit
from pathlib import Path
from datetime import datetime
from typing import Optional

# Log directory
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True)

# Log files
MAIN_LOG = LOG_DIR / "kalshi.log"
API_LOG = LOG_DIR / "api.log"
SCANNER_LOG = LOG_DIR / "scanners.log"
TRADE_LOG = LOG_DIR / "trades.log"
ERROR_LOG = LOG_DIR / "errors.log"

# Global queue listener
_queue_listener: Optional[logging.handlers.QueueListener] = None
_is_initialized = False

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
    """
    Setup thread-safe logging for a service using QueueHandler pattern.
    Call this ONCE at application startup.
    """
    global _queue_listener, _is_initialized

    if _is_initialized:
        return logging.getLogger()

    # Queue for thread-safe logging
    log_queue: queue.Queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    # All handlers that will write to files/console (accessed only by queue listener thread)
    handlers = []

    # Console handler with colors
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(ColoredFormatter())
    handlers.append(console_handler)

    # Main log file
    main_handler = logging.handlers.RotatingFileHandler(
        MAIN_LOG, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8'
    )
    main_handler.setLevel(log_level)
    main_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
    handlers.append(main_handler)

    # Service-specific log
    service_log = {"api": API_LOG, "scanner": SCANNER_LOG}.get(service_name, LOG_DIR / f"{service_name}.log")
    service_handler = logging.handlers.RotatingFileHandler(
        service_log, maxBytes=10*1024*1024, backupCount=3, encoding='utf-8'
    )
    service_handler.setLevel(log_level)
    service_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
    handlers.append(service_handler)

    # Error log
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_LOG, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s\n%(pathname)s:%(lineno)d'))
    handlers.append(error_handler)

    # Queue listener - single thread handles all file I/O
    _queue_listener = logging.handlers.QueueListener(
        log_queue,
        *handlers,
        respect_handler_level=True
    )
    _queue_listener.start()

    # Configure root logger to use queue
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(queue_handler)

    # Reduce noise from HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    # Auto-cleanup on exit
    atexit.register(shutdown_logging)
    _is_initialized = True

    root_logger.info(f"Thread-safe logging initialized for {service_name}")
    return root_logger


def shutdown_logging() -> None:
    """Clean shutdown of logging system. Called automatically via atexit."""
    global _queue_listener, _is_initialized
    if _queue_listener:
        _queue_listener.stop()
        _queue_listener = None
    _is_initialized = False


def get_logger(name: str) -> logging.Logger:
    """Get a named logger. Use this in all modules instead of logging.getLogger()."""
    return logging.getLogger(name)
