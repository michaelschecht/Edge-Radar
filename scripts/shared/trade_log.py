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


def get_filled_contracts(trade: dict) -> float:
    """Return the number of contracts actually filled for a trade record.

    Handles both old format (only ``contracts`` + ``fill_count``) and the new
    format (explicit ``filled_contracts`` field).  For old records that lack
    ``filled_contracts``, falls back to ``fill_count`` (from the Kalshi API
    response) then ``contracts`` (legacy requested value).
    """
    if "filled_contracts" in trade:
        return float(trade["filled_contracts"])
    fc = trade.get("fill_count")
    if fc is not None and str(fc) not in ("", "0"):
        return float(fc)
    # Legacy fallback: assume fully filled (pre-X5 records)
    return float(trade.get("contracts", 0))


def get_filled_cost(trade: dict) -> float:
    """Return the dollar cost of contracts actually filled.

    Uses ``filled_cost`` when present (new format).  For old records, derives
    cost from ``fill_count * market_price_at_entry`` if available, otherwise
    falls back to ``cost_dollars`` (legacy requested value).
    """
    if "filled_cost" in trade:
        return float(trade["filled_cost"])
    fc = trade.get("fill_count")
    price = trade.get("market_price_at_entry", 0)
    if fc is not None and str(fc) not in ("", "0") and price:
        return round(float(fc) * float(price), 4)
    # Legacy fallback
    return float(trade.get("cost_dollars", 0))


def get_open_trade_count(trades: list[dict] | None = None) -> int:
    """Count trades that haven't been settled yet."""
    if trades is None:
        trades = load_trade_log()
    return sum(1 for t in trades if not t.get("closed_at"))
