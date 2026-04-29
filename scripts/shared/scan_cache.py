"""
scan_cache.py
File-backed cache of the last preview's sized-order list (R26).

Solves the bug where a two-call workflow

    python scripts/scan.py sports --filter mlb --exclude-open       # preview
    python scripts/scan.py sports --filter mlb --pick '1,3' --execute   # execute

can place the wrong bets because the second call rescans live and reorders rows
on small price/composite-score drift. After every preview the displayed rows
(post-dedup, post-risk-gate, post-budget-cap) are persisted to
`data/cache/last_scan.json`. When `--pick` or `--ticker` is supplied with
`--execute`, the cache is replayed so row indices stay locked to what the user
saw, with a fingerprint check on the scanner type and filter args so a
mismatched second call rescans instead of executing the wrong universe.

Operations are silent-on-error: a corrupt or unreadable cache file is treated
as a miss, never an exception. Mirrors the precedent set by
`scripts/shared/odds_cache.py`.

Layout:
    data/cache/last_scan.json   (single file, latest preview only)

The serialized SizedOrder rehydrates back into the same dataclass on load,
including the embedded Opportunity, so the executor's existing order-placement
loop works without conditional branches.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from paths import DATA_DIR

log = logging.getLogger("scan_cache")

_CACHE_DIR = DATA_DIR / "cache"
_CACHE_FILE = _CACHE_DIR / "last_scan.json"
_VERSION = 1


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _opp_to_dict(opp) -> dict:
    return {
        "ticker": opp.ticker,
        "title": opp.title,
        "category": opp.category,
        "side": opp.side,
        "market_price": opp.market_price,
        "fair_value": opp.fair_value,
        "edge": opp.edge,
        "edge_source": opp.edge_source,
        "confidence": opp.confidence,
        "liquidity_score": opp.liquidity_score,
        "composite_score": opp.composite_score,
        "details": opp.details or {},
    }


def _dict_to_opp(d: dict):
    from opportunity import Opportunity
    return Opportunity(
        ticker=d.get("ticker", ""),
        title=d.get("title", ""),
        category=d.get("category", ""),
        side=d.get("side", "yes"),
        market_price=float(d.get("market_price", 0.0) or 0.0),
        fair_value=float(d.get("fair_value", 0.0) or 0.0),
        edge=float(d.get("edge", 0.0) or 0.0),
        edge_source=d.get("edge_source", ""),
        confidence=d.get("confidence", "medium"),
        liquidity_score=float(d.get("liquidity_score", 0.0) or 0.0),
        composite_score=float(d.get("composite_score", 0.0) or 0.0),
        details=d.get("details") or {},
    )


def _sized_to_dict(s) -> dict:
    return {
        **_opp_to_dict(s.opportunity),
        "contracts": int(s.contracts),
        "price_cents": int(s.price_cents),
        "cost_dollars": float(s.cost_dollars),
        "bankroll_pct": float(s.bankroll_pct),
        "risk_approval": s.risk_approval,
    }


def _dict_to_sized(d: dict):
    from kalshi_executor import SizedOrder
    return SizedOrder(
        opportunity=_dict_to_opp(d),
        contracts=int(d.get("contracts", 1) or 1),
        price_cents=int(d.get("price_cents", 0) or 0),
        cost_dollars=float(d.get("cost_dollars", 0.0) or 0.0),
        bankroll_pct=float(d.get("bankroll_pct", 0.0) or 0.0),
        risk_approval=d.get("risk_approval", "APPROVED"),
    )


def store(
    fingerprint: dict,
    sized_orders: list,
    bankroll: float | None = None,
) -> Path | None:
    """Write the displayed preview rows to the cache. Silent on I/O error.

    Returns the cache path on success, None on disabled or write failure.
    """
    from app.config import get_config

    cfg = get_config().scan_cache
    if not cfg.enabled:
        return None
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": _VERSION,
            "saved_at": _now().isoformat().replace("+00:00", "Z"),
            "fingerprint": fingerprint,
            "bankroll_at_scan": bankroll,
            "rows": [_sized_to_dict(s) for s in sized_orders],
        }
        _CACHE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return _CACHE_FILE
    except OSError as e:
        log.debug("scan_cache.store failed: %s", e)
        return None


def load() -> dict | None:
    """Return the cached preview if present, fresh, and valid; else None.

    Result keys:
        fingerprint        -- the dict stored at write time
        saved_at           -- aware UTC datetime of the write
        age_seconds        -- int seconds since saved_at (>= 0)
        bankroll_at_scan   -- float or None (informational)
        rows               -- list[SizedOrder] (rehydrated)
    """
    from app.config import get_config

    cfg = get_config().scan_cache
    if not cfg.enabled or cfg.ttl_seconds <= 0:
        return None
    if not _CACHE_FILE.exists():
        return None

    try:
        raw = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if raw.get("version") != _VERSION:
        return None
    saved_at_str = raw.get("saved_at")
    if not isinstance(saved_at_str, str):
        return None
    try:
        saved_at = datetime.fromisoformat(saved_at_str.replace("Z", "+00:00"))
    except ValueError:
        return None

    age_seconds = int((_now() - saved_at).total_seconds())
    if age_seconds < 0 or age_seconds > cfg.ttl_seconds:
        return None

    rows_raw = raw.get("rows")
    if not isinstance(rows_raw, list):
        return None
    try:
        rows = [_dict_to_sized(d) for d in rows_raw]
    except (TypeError, ValueError, KeyError):
        return None

    return {
        "fingerprint": raw.get("fingerprint") or {},
        "saved_at": saved_at,
        "age_seconds": age_seconds,
        "bankroll_at_scan": raw.get("bankroll_at_scan"),
        "rows": rows,
    }


def clear() -> bool:
    """Remove the cache file. Returns True if a file was deleted."""
    try:
        _CACHE_FILE.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def fingerprints_match(saved: dict, current: dict) -> tuple[bool, list[str]]:
    """Compare a saved fingerprint against the current invocation's args.

    Returns (match, diffs). `diffs` is a human-readable list of mismatched
    keys for the rescan-warning message. Keys present in only one side are
    treated as a mismatch.
    """
    diffs: list[str] = []
    keys = set(saved.keys()) | set(current.keys())
    for k in sorted(keys):
        cached_val = saved.get(k, "<unset>")
        current_val = current.get(k, "<unset>")
        if cached_val != current_val:
            diffs.append(f"{k}: cached={cached_val!r}, now={current_val!r}")
    return (len(diffs) == 0, diffs)
