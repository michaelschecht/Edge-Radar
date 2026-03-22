"""
trade_log.py
Centralized trade log and settlement log I/O.

Single source of truth for loading, saving, and querying trade history.
Used by kalshi_executor.py, kalshi_settler.py, and future prediction executor.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from paths import TRADE_LOG_PATH, SETTLEMENT_LOG_PATH


def load_trade_log() -> list[dict]:
    """Load the trade log from disk."""
    if TRADE_LOG_PATH.exists():
        with open(TRADE_LOG_PATH) as f:
            return json.load(f)
    return []


def save_trade_log(trades: list[dict]) -> None:
    """Save the trade log to disk."""
    TRADE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRADE_LOG_PATH, "w") as f:
        json.dump(trades, f, indent=2, default=str)


def load_settlement_log() -> list[dict]:
    """Load the settlement log from disk."""
    if SETTLEMENT_LOG_PATH.exists():
        with open(SETTLEMENT_LOG_PATH) as f:
            return json.load(f)
    return []


def save_settlement_log(settlements: list[dict]) -> None:
    """Save the settlement log to disk."""
    SETTLEMENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTLEMENT_LOG_PATH, "w") as f:
        json.dump(settlements, f, indent=2, default=str)


def get_today_pnl(trades: list[dict] | None = None) -> float:
    """Calculate today's realized P&L from the trade log."""
    if trades is None:
        trades = load_trade_log()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return sum(
        t.get("net_pnl", 0) for t in trades
        if (t.get("closed_at") or "").startswith(today)
    )


def get_open_trade_count(trades: list[dict] | None = None) -> int:
    """Count trades that haven't been settled yet."""
    if trades is None:
        trades = load_trade_log()
    return sum(1 for t in trades if not t.get("closed_at"))
