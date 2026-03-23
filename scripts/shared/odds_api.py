"""
odds_api.py
Odds API key rotation and request management.

Loads multiple API keys from ODDS_API_KEYS env var (comma-separated).
Automatically rotates to the next key when one is exhausted or rate-limited.
Falls back to single ODDS_API_KEY for backwards compatibility.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("odds_api")

# ── Key Management ───────────────────────────────────────────────────────────

_keys: list[str] = []
_current_index: int = 0
_remaining: dict[str, int] = {}  # key -> requests remaining


def _load_keys() -> list[str]:
    """Load API keys from environment."""
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
    else:
        log.warning("No Odds API keys configured")

    return _keys


def get_current_key() -> str:
    """Get the current active API key."""
    global _current_index
    if not _keys:
        _load_keys()
    if not _keys:
        return ""
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
    """Track remaining requests for a key (from response headers)."""
    _remaining[key] = remaining
    if remaining <= 10:
        log.warning("Odds API key ...%s: only %d requests remaining", key[-6:], remaining)
    if remaining <= 0:
        log.warning("Odds API key ...%s exhausted, rotating", key[-6:])
        rotate_key("zero_remaining")


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
