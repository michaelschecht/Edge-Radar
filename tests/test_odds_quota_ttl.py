"""A cached zero must expire, or a monthly quota reset is never discovered.

Regression test for 2026-09-09: `get_current_key()` returns the first key not
cached at zero, so one key with quota left kept the walk from ever reaching the
drained ones. 12 of 14 keys read 0 while a live probe found 5154 requests
actually available. The bug was that a zero was believed forever.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "shared"))
import odds_api


def _reload_from(tmp_path, payload):
    """Point the module at a scratch cache holding `payload` and reload it."""
    cache = tmp_path / "quota.json"
    cache.write_text(json.dumps(payload), encoding="utf-8")
    odds_api._QUOTA_CACHE_PATH = cache
    odds_api._remaining.clear()
    odds_api._checked_at.clear()
    odds_api._load_quota_cache()
    return cache


def _iso(hours_ago):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def test_fresh_zero_is_believed(tmp_path):
    _reload_from(tmp_path, {"k1": {"remaining": 0, "checked_at": _iso(1)}})
    assert odds_api._remaining.get("k1") == 0


def test_stale_zero_reads_as_unknown(tmp_path):
    _reload_from(tmp_path, {"k1": {"remaining": 0, "checked_at": _iso(48)}})
    assert "k1" not in odds_api._remaining, "a day-old zero must be re-probed"


def test_legacy_bare_int_zero_is_expired(tmp_path):
    """The old format carries no timestamp, so its zeros cannot be trusted."""
    _reload_from(tmp_path, {"k1": 0, "k2": 416})
    assert "k1" not in odds_api._remaining
    assert odds_api._remaining["k2"] == 416


def test_nonzero_never_expires(tmp_path):
    _reload_from(tmp_path, {"k1": {"remaining": 500, "checked_at": _iso(999)}})
    assert odds_api._remaining["k1"] == 500


def test_stale_zero_key_gets_selected_again(tmp_path):
    """The end-to-end point: a drained key comes back into rotation."""
    _reload_from(tmp_path, {"dead": {"remaining": 0, "checked_at": _iso(48)}})
    odds_api._keys = ["dead"]
    odds_api._current_index = 0
    assert odds_api.get_current_key() == "dead"


def test_roundtrip_writes_timestamps(tmp_path):
    _reload_from(tmp_path, {})
    odds_api.report_remaining("k1", 0)
    written = json.loads(odds_api._QUOTA_CACHE_PATH.read_text(encoding="utf-8"))
    assert written["k1"]["remaining"] == 0
    assert written["k1"]["checked_at"], "a zero without a stamp can never expire"
