"""
odds_api.py
Odds API key rotation and request management.

Loads multiple API keys from ODDS_API_KEYS env var (comma-separated).
Automatically rotates to the next key when one is exhausted or rate-limited.
Falls back to single ODDS_API_KEY for backwards compatibility.

Per-key remaining-request count is persisted to
`data/cache/odds_api_quota.json` so fresh Python processes don't burn
their retry budget rediscovering exhausted keys. `get_current_key()`
auto-advances past cached-exhausted keys (remaining == 0). If every
key is cached as exhausted the original slot is still returned so a
monthly quota reset can be re-discovered naturally.
"""

import json
import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("odds_api")

# ── Key Management ───────────────────────────────────────────────────────────

_keys: list[str] = []
_current_index: int = 0
_remaining: dict[str, int] = {}  # key -> requests remaining

# Persist _remaining across processes so we don't re-hit exhausted keys.
# Gitignored path (data/cache/…) so it stays out of the repo.
_QUOTA_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "odds_api_quota.json"


def _load_quota_cache() -> None:
    """Populate `_remaining` from disk. Silent on any error."""
    if not _QUOTA_CACHE_PATH.exists():
        return
    try:
        raw = json.loads(_QUOTA_CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            _remaining.update({k: int(v) for k, v in raw.items() if isinstance(v, (int, float))})
    except (OSError, json.JSONDecodeError, ValueError):
        pass


def _save_quota_cache() -> None:
    """Persist `_remaining` to disk. Silent on any error."""
    try:
        _QUOTA_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _QUOTA_CACHE_PATH.write_text(json.dumps(_remaining, indent=2), encoding="utf-8")
    except OSError:
        pass


def _load_keys() -> list[str]:
    """Load API keys from environment and hydrate the on-disk quota cache."""
    global _keys

    # Try ODDS_API_KEYS first (comma-separated list)
    keys_str = os.getenv("ODDS_API_KEYS", "")
    if keys_str:
        _keys = [k.strip() for k in keys_str.split(",") if k.strip()]

    # Fallback to single ODDS_API_KEY
    if not _keys:
        single = os.getenv("ODDS_API_KEY", "")
        if single:
            _keys = [single]

    if _keys:
        log.info("Loaded %d Odds API key(s)", len(_keys))
        _load_quota_cache()
    else:
        log.warning("No Odds API keys configured")

    return _keys


def get_current_key() -> str:
    """Get the current active API key.

    Auto-advances past keys whose cached quota is zero so fresh processes
    don't burn their retry budget on known-exhausted keys. If every key is
    cached as exhausted, returns the current slot anyway — lets a monthly
    quota reset be re-discovered instead of giving up permanently.
    """
    global _current_index
    if not _keys:
        _load_keys()
    if not _keys:
        return ""
    # Skip cached-exhausted keys, checking at most len(_keys) slots.
    for _ in range(len(_keys)):
        key = _keys[_current_index % len(_keys)]
        if _remaining.get(key, 1) != 0:
            return key
        _current_index = (_current_index + 1) % len(_keys)
    # All keys appear exhausted — return current anyway to let quota reset
    # be re-discovered naturally (request will 401 and caller can handle it).
    return _keys[_current_index % len(_keys)]


def rotate_key(reason: str = "exhausted") -> str | None:
    """Rotate to the next API key. Returns the new key, or None if all exhausted."""
    global _current_index
    if not _keys:
        _load_keys()
    if len(_keys) <= 1:
        log.warning("No additional Odds API keys to rotate to")
        return None

    old_index = _current_index
    _current_index = (_current_index + 1) % len(_keys)

    # If we've cycled back to the start, all keys are exhausted
    if _current_index == old_index:
        log.warning("All Odds API keys exhausted")
        return None

    new_key = _keys[_current_index]
    log.info("Rotated Odds API key (%s): ...%s -> ...%s",
             reason, _keys[old_index][-6:], new_key[-6:])
    return new_key


def report_remaining(key: str, remaining: int) -> None:
    """Track remaining requests for a key (from response headers).

    Also persists to disk so future processes skip exhausted keys at
    `get_current_key()` time instead of burning retry attempts on them.
    """
    _remaining[key] = remaining
    _save_quota_cache()
    if remaining <= 10:
        log.warning("Odds API key ...%s: only %d requests remaining", key[-6:], remaining)
    if remaining <= 0:
        log.warning("Odds API key ...%s exhausted, rotating", key[-6:])
        rotate_key("zero_remaining")


def mark_exhausted(key: str) -> None:
    """Mark a key as exhausted (remaining=0) when we get a 401 without a
    usable `x-requests-remaining` header. Persists to disk so the next
    process skips this key at `get_current_key()` time.
    """
    _remaining[key] = 0
    _save_quota_cache()


def get_status() -> dict:
    """Get status of all keys."""
    if not _keys:
        _load_keys()
    return {
        "total_keys": len(_keys),
        "current_index": _current_index,
        "remaining": {f"...{k[-6:]}": _remaining.get(k, "unknown") for k in _keys},
    }


# Initialize on import
_load_keys()
