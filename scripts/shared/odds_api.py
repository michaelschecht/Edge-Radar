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

**A cached zero expires after `_ZERO_TTL_HOURS`.** The Odds API resets
each key's quota on its own signup anniversary, not the 1st of the month,
so a zero is only ever a fact about the past. Without an expiry the cache
was self-perpetuating: `get_current_key()` returns the first key not
cached at zero, so as long as ONE key had quota left the walk stopped
there and every drained key was never contacted again -- their resets
came and went unobserved. The "if every key is exhausted, try anyway"
fallback below only fires when *all* keys read zero, which never happened.
Observed 2026-09-09: 12 of 14 keys cached at 0, one key carrying the
entire workload, while a live probe found 5154 requests actually
available (9 keys sitting at a full 500). Re-probing an expired zero
costs one request that either 401s or discovers the reset.
"""

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("odds_api")

from app.config import get_config

# Strip the Odds API key out of any string before it reaches a log/stdout.
# A `requests` HTTPError/ConnectionError/Timeout stringifies the full resolved
# URL, which carries `?apiKey=<secret>`; logging it verbatim leaks the key.
_APIKEY_QUERY_RE = re.compile(r"(apiKey=)[^&\s'\"]+", re.IGNORECASE)


def redact_secrets(text: object) -> str:
    """Return ``str(text)`` with any ``apiKey=<value>`` query param masked."""
    return _APIKEY_QUERY_RE.sub(r"\1***", str(text))

# ── Key Management ───────────────────────────────────────────────────────────

_keys: list[str] = []
_current_index: int = 0
_remaining: dict[str, int] = {}  # key -> requests remaining
_checked_at: dict[str, str] = {}  # key -> ISO-8601 UTC of that reading

# How long a cached ZERO is believed. Quota resets land on each key's own
# monthly anniversary, so the worst case is one wasted request per drained
# key per day -- cheap against never noticing a reset at all. Non-zero
# readings do not expire: they are refreshed on every use anyway.
_ZERO_TTL_HOURS = 24

# Persist _remaining across processes so we don't re-hit exhausted keys.
# Gitignored path (data/cache/…) so it stays out of the repo.
_QUOTA_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "cache" / "odds_api_quota.json"


def _load_quota_cache() -> None:
    """Populate `_remaining` from disk, dropping expired zeros. Silent on any error.

    Accepts both the current ``{key: {"remaining": N, "checked_at": iso}}``
    shape and the legacy bare ``{key: N}`` one. A legacy entry carries no
    timestamp, so a legacy zero is treated as expired -- that is the whole
    point of the migration.
    """
    if not _QUOTA_CACHE_PATH.exists():
        return
    try:
        raw = json.loads(_QUOTA_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError):
        return
    if not isinstance(raw, dict):
        return
    for key, val in raw.items():
        if isinstance(val, dict):
            rem, stamp = val.get("remaining"), val.get("checked_at")
        elif isinstance(val, (int, float)):
            rem, stamp = val, None
        else:
            continue
        if not isinstance(rem, (int, float)):
            continue
        rem = int(rem)
        if rem == 0 and _zero_expired(stamp):
            continue  # read as unknown so this key gets probed again
        _remaining[key] = rem
        if stamp:
            _checked_at[key] = stamp


def _zero_expired(stamp: str | None) -> bool:
    """True when a cached zero is older than `_ZERO_TTL_HOURS` (or undateable)."""
    if not stamp:
        return True
    try:
        when = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return True
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when < datetime.now(timezone.utc) - timedelta(hours=_ZERO_TTL_HOURS)


def _save_quota_cache() -> None:
    """Persist `_remaining` to disk. Silent on any error."""
    try:
        _QUOTA_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            k: {"remaining": v, "checked_at": _checked_at.get(k)}
            for k, v in _remaining.items()
        }
        _QUOTA_CACHE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def _load_keys() -> list[str]:
    """Load API keys from environment and hydrate the on-disk quota cache."""
    global _keys

    odds = get_config().odds

    # Try ODDS_API_KEYS first (comma-separated list)
    if odds.keys:
        _keys = list(odds.keys)

    # Fallback to single ODDS_API_KEY
    if not _keys and odds.single_key:
        _keys = [odds.single_key]

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
    _checked_at[key] = datetime.now(timezone.utc).isoformat()
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
    _checked_at[key] = datetime.now(timezone.utc).isoformat()
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
