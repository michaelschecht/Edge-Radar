"""
odds_cache.py
File-backed cache for The Odds API responses (R24b).

Each in-process scanner already maintains a module-level dict so repeated
calls within one Python process are O(1). What this module adds is a
**cross-process** layer: back-to-back CLI invocations within the TTL window
read the cached file instead of refetching, which materially cuts quota burn
on scheduler bursts and dashboard re-renders.

Layout:
    data/cache/odds/<sport_key>__<markets>.json

`<markets>` has commas replaced with underscores so filenames are portable;
the original markets string is preserved in the file body for round-trip
clarity.

Operations are silent-on-error: a corrupt or unreadable cache file is
treated as a miss, never an exception. This mirrors the precedent set by
`odds_api._save_quota_cache()` for `data/cache/odds_api_quota.json`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from paths import DATA_DIR

log = logging.getLogger("odds_cache")

_CACHE_DIR = DATA_DIR / "cache" / "odds"


def _filename(sport_key: str, markets: str) -> Path:
    safe_markets = markets.replace(",", "_")
    return _CACHE_DIR / f"{sport_key}__{safe_markets}.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load(
    sport_key: str,
    markets: str,
    ttl_seconds: int,
) -> tuple[list, int] | tuple[None, None]:
    """Return (events, age_seconds) on hit within TTL, else (None, None).

    A negative or zero `ttl_seconds` always misses — callers can treat that
    as "cache disabled" without a separate code path.
    """
    if ttl_seconds <= 0:
        return None, None

    path = _filename(sport_key, markets)
    if not path.exists():
        return None, None

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, None

    fetched_at_str = raw.get("fetched_at")
    events = raw.get("events")
    if not isinstance(fetched_at_str, str) or not isinstance(events, list):
        return None, None

    try:
        fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
    except ValueError:
        return None, None

    age_seconds = int((_now() - fetched_at).total_seconds())
    if age_seconds < 0 or age_seconds > ttl_seconds:
        return None, None

    return events, age_seconds


def store(sport_key: str, markets: str, events: list) -> None:
    """Write events to the on-disk cache. Silent on any I/O error."""
    path = _filename(sport_key, markets)
    payload = {
        "fetched_at": _now().isoformat().replace("+00:00", "Z"),
        "sport_key": sport_key,
        "markets": markets,
        "events": events,
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
    except OSError as e:
        log.debug("odds_cache.store failed for %s/%s: %s", sport_key, markets, e)


def clear() -> int:
    """Delete every cached odds file. Returns count of files removed.

    Used by tests and as a manual purge knob. Silent on per-file errors.
    """
    if not _CACHE_DIR.exists():
        return 0
    removed = 0
    for path in _CACHE_DIR.glob("*.json"):
        try:
            path.unlink()
            removed += 1
        except OSError:
            pass
    return removed
