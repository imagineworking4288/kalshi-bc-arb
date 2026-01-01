"""
Logging utilities for BTC Arbitrage Scanner.
Provides console logging + in-memory activity buffer for UI display.
"""

import logging
import os
from collections import deque
from datetime import datetime
from threading import Lock
from typing import List, Dict


class ActivityBuffer:
    """Thread-safe circular buffer for storing recent log messages."""

    def __init__(self, maxlen: int = 50):
        self._buffer: deque = deque(maxlen=maxlen)
        self._lock = Lock()

    def add(self, level: str, message: str, emoji: str = ""):
        """Add a message to the buffer."""
        with self._lock:
            self._buffer.append({
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'level': level,
                'message': message,
                'emoji': emoji
            })

    def get_all(self) -> List[Dict]:
        """Get all messages in the buffer (newest first)."""
        with self._lock:
            return list(reversed(self._buffer))

    def clear(self):
        """Clear the buffer."""
        with self._lock:
            self._buffer.clear()


class ActivityHandler(logging.Handler):
    """Custom logging handler that writes to an ActivityBuffer."""

    def __init__(self, buffer: ActivityBuffer):
        super().__init__()
        self.buffer = buffer

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            # Extract emoji from message if present
            emoji = ""
            for e in ["[SCAN]", "[OK]", "[HOT]", "[X]", "[WARN]", "[SEARCH]", "[$]", "[UP]", "[DOWN]", "[TARGET]", "[TIME]"]:
                if e in msg:
                    emoji = e
                    break
            self.buffer.add(record.levelname, msg, emoji)
        except Exception:
            self.handleError(record)


def setup_logger(name: str, activity_buffer: ActivityBuffer = None) -> logging.Logger:
    """
    Set up a logger with console and optional file handlers.

    Args:
        name: Logger name
        activity_buffer: Optional ActivityBuffer to also log to

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only add handlers if none exist
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '[%(name)s] %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (create logs directory if needed)
    logs_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
    os.makedirs(logs_dir, exist_ok=True)

    file_handler = logging.FileHandler(
        os.path.join(logs_dir, f'{name}.log'),
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    # Activity buffer handler (for UI)
    if activity_buffer:
        activity_handler = ActivityHandler(activity_buffer)
        activity_handler.setLevel(logging.INFO)
        activity_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(activity_handler)

    return logger


# Module-level exports for BTC arbitrage scanner
btc_arb_activity = ActivityBuffer(maxlen=100)
btc_arb_logger = setup_logger('btc_arb', btc_arb_activity)
