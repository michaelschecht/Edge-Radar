"""
trade_log.py
Centralized trade log and settlement log I/O.

Single source of truth for loading, saving, and querying trade history.
Used by kalshi_executor.py, kalshi_settler.py, and future prediction executor.
"""

import json
import logging
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from paths import TRADE_LOG_PATH, SETTLEMENT_LOG_PATH

log = logging.getLogger("trade_log")

# ── Cross-process lock (M2) ───────────────────────────────────────────────────
#
# `_atomic_write_json` prevents corruption from an interrupted write, but not a
# *lost update* when two processes both do load→mutate→save: the second save
# clobbers the first's change. For the trade log a lost append = an untracked
# live position, so every writer that mutates the log must hold this lock across
# its read-modify-write cycle, re-reading fresh *inside* the lock.
#
# One lock file guards BOTH logs (the settler mutates them together). We use the
# `filelock` library when present (robust cross-platform advisory lock); if it's
# somehow unavailable we degrade to a no-op so a missing dependency can never
# block a live trade write — the atomic-write guarantee still holds, only the
# lost-update protection is lost, and that's logged once.
_LOCK_TIMEOUT_SECONDS = 30.0

try:
    from filelock import FileLock, Timeout as _FileLockTimeout

    _HAVE_FILELOCK = True
except ImportError:  # pragma: no cover - defensive fallback
    _HAVE_FILELOCK = False
    _warned_no_filelock = False


def _lock_path() -> Path:
    """Lock file path, derived from the current ``TRADE_LOG_PATH`` at call time
    so it follows a monkeypatched log location in tests."""
    return TRADE_LOG_PATH.parent / ".trade_log.lock"


@contextmanager
def trade_log_lock(timeout: float = _LOCK_TIMEOUT_SECONDS):
    """Hold a cross-process lock guarding the trade + settlement logs.

    Wrap any load→mutate→save cycle in this and re-read the log *inside* the
    ``with`` block, so a concurrent writer's changes are merged rather than
    clobbered. On lock-acquire timeout the write still proceeds (falling back to
    atomic-write-only semantics) rather than dropping a trade — a blocked write
    is worse than a rare lost-update, and it's logged.
    """
    if not _HAVE_FILELOCK:
        global _warned_no_filelock
        if not _warned_no_filelock:
            log.warning(
                "filelock not installed — trade-log writes fall back to "
                "atomic-write-only (no cross-process lost-update protection)."
            )
            _warned_no_filelock = True
        yield
        return

    lock_path = _lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(str(lock_path), timeout=timeout)
    try:
        lock.acquire()
    except _FileLockTimeout:
        log.warning(
            "trade_log_lock: timed out after %ss waiting for %s; proceeding "
            "without the lock (atomic write only).", timeout, lock_path,
        )
        yield
        return
    try:
        yield
    finally:
        lock.release()


def _atomic_write_json(path: Path, data) -> None:
    """Serialize ``data`` to ``path`` atomically.

    Writes to a temp file in the same directory, flushes+fsyncs it, then
    ``os.replace``s it over the target. ``os.replace`` is atomic on both POSIX
    and Windows when source and destination share a filesystem, so a reader
    (or a crash) never observes a half-written trade/settlement log — the file
    is either the old contents or the complete new contents.

    NOTE: this closes the *corruption-on-interrupted-write* hole. Serializing
    concurrent read-modify-write cycles across processes is a separate concern
    handled by ``trade_log_lock`` (M2) — hold that lock and re-read inside it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        # Never leave a stray temp file behind on failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_trade_log() -> list[dict]:
    """Load the trade log from disk."""
    if TRADE_LOG_PATH.exists():
        with open(TRADE_LOG_PATH) as f:
            return json.load(f)
    return []


def save_trade_log(trades: list[dict]) -> None:
    """Save the trade log to disk (atomic write — see ``_atomic_write_json``).

    This overwrites the whole file. To append without clobbering a concurrent
    writer's records, use ``append_trades`` (which re-reads under the lock).
    """
    _atomic_write_json(TRADE_LOG_PATH, trades)


def append_trades(records: list[dict]) -> list[dict]:
    """Append ``records`` to the trade log without losing concurrent writes.

    Acquires the cross-process lock, re-reads the current log from disk, extends
    it with ``records``, and saves atomically — so a trade written by another
    process between our caller's load and this call is preserved instead of
    clobbered. Returns the full, freshly-persisted log.
    """
    if not records:
        return load_trade_log()
    with trade_log_lock():
        trades = load_trade_log()
        trades.extend(records)
        save_trade_log(trades)
        return trades


def load_settlement_log() -> list[dict]:
    """Load the settlement log from disk."""
    if SETTLEMENT_LOG_PATH.exists():
        with open(SETTLEMENT_LOG_PATH) as f:
            return json.load(f)
    return []


def save_settlement_log(settlements: list[dict]) -> None:
    """Save the settlement log to disk (atomic write — see ``_atomic_write_json``)."""
    _atomic_write_json(SETTLEMENT_LOG_PATH, settlements)


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


def settlement_revenue_dollars(raw) -> float:
    """Normalize a Kalshi settlement ``revenue`` field to dollars.

    Kalshi returns ``revenue`` as an integer number of **cents**, so any int is
    divided by 100. A non-int (already a float dollar value in some records) is
    passed through unchanged. Single source of truth so the settler report and
    ``risk_check`` agree — they previously disagreed on the 1-cent case (review
    #9: one used a ``> 1`` guard that mis-read 1¢ as $1.00).
    """
    return raw / 100 if isinstance(raw, int) else float(raw)


def get_open_trade_count(trades: list[dict] | None = None) -> int:
    """Count trades that haven't been settled yet."""
    if trades is None:
        trades = load_trade_log()
    return sum(1 for t in trades if not t.get("closed_at"))
