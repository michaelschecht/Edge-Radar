"""
logging_setup.py
Configures logging to both console and file for all FinAgent scripts.

Usage:
    from logging_setup import setup_logging
    setup_logging("kalshi_executor")  # creates logs/kalshi_executor.log
"""

import logging
from datetime import datetime, timezone

from config import LOG_DIR, LOG_LEVEL


def setup_logging(name: str) -> logging.Logger:
    """
    Configure logging for a script.

    - Console: INFO+ (or LOG_LEVEL from .env)
    - File: DEBUG+ (captures everything for post-run analysis)

    Args:
        name: Logger name and log file prefix (e.g., "kalshi_executor")

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers on re-import
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (daily rotating by name)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"{name}_{today}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger
