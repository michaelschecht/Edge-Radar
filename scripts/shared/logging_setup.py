"""
logging_setup.py
Configures logging to both console and file for all Edge-Radar scripts.

Usage:
    from logging_setup import setup_logging
    setup_logging("kalshi_executor")  # creates logs/kalshi_executor.log
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Imported after load_dotenv so the config picks up `.env` values on first
# call. Safe even if get_config() was already cached by an earlier import —
# load_dotenv is idempotent (default `override=False`).
from app.config import get_config

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_LEVEL = get_config().system.log_level


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
