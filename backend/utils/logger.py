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
    Set up a logger with optional activity buffer.

    NOTE: File and console handlers are managed by the centralized log_config.py
    using QueueHandler pattern. This function only adds the ActivityBuffer handler.

    Args:
        name: Logger name
        activity_buffer: Optional ActivityBuffer to also log to

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Check if we already added the activity buffer handler
    for handler in logger.handlers:
        if isinstance(handler, ActivityHandler):
            return logger

    logger.setLevel(logging.DEBUG)

    # Activity buffer handler (for UI) - this is in-memory only, no file I/O
    if activity_buffer:
        activity_handler = ActivityHandler(activity_buffer)
        activity_handler.setLevel(logging.INFO)
        activity_handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(activity_handler)

    return logger


# Module-level exports for BTC arbitrage scanner
btc_arb_activity = ActivityBuffer(maxlen=100)
btc_arb_logger = setup_logger('btc_arb', btc_arb_activity)
