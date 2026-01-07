"""
Thread-safe logging configuration for Windows.
Uses QueueHandler pattern to avoid PermissionError on log rotation.

Usage:
    from backend.logging_config import setup_logging, get_logger

    setup_logging()  # Call once at app startup
    logger = get_logger("my_module")
    logger.info("Thread-safe logging!")
"""

import logging
import logging.handlers
import queue
import sys
import os
import atexit
from pathlib import Path
from typing import Optional

_queue_listener: Optional[logging.handlers.QueueListener] = None
_is_initialized = False


def setup_logging(
    log_dir: str = "logs",
    log_level: int = logging.INFO,
    max_bytes: int = 10_000_000,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    Initialize thread-safe logging with queue-based rotation.
    Call this ONCE at application startup, before creating any scanners.
    """
    global _queue_listener, _is_initialized

    if _is_initialized:
        return logging.getLogger()

    # Create log directory
    Path(log_dir).mkdir(exist_ok=True)
    log_file = os.path.join(log_dir, "kalshi.log")

    # Queue for thread-safe logging
    log_queue: queue.Queue = queue.Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)

    handlers = []

    # File handler - only accessed by the queue listener thread
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)-5s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    handlers.append(file_handler)

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)-5s] [%(name)s] %(message)s',
            datefmt='%H:%M:%S'
        ))
        handlers.append(console_handler)

    # Queue listener - single thread handles all file I/O
    _queue_listener = logging.handlers.QueueListener(
        log_queue,
        *handlers,
        respect_handler_level=True
    )
    _queue_listener.start()

    # Configure root logger
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

    root_logger.info(f"Logging initialized: {log_file}")
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
