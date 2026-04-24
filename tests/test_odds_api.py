"""Tests for `odds_api.py` key rotation + persistent quota cache.

The persistence layer matters because each scanner run is a fresh Python
process — without the on-disk cache we'd burn retry attempts rediscovering
exhausted keys every time.
"""

import json
from pathlib import Path

import pytest

import odds_api


@pytest.fixture
def clean_module(monkeypatch, tmp_path):
    """Reset odds_api module state between tests and point the quota cache
    at a throwaway tmpdir so we never touch the real cache file."""
    cache_path = tmp_path / "odds_api_quota.json"
    monkeypatch.setattr(odds_api, "_QUOTA_CACHE_PATH", cache_path)
    monkeypatch.setattr(odds_api, "_keys", [])
    monkeypatch.setattr(odds_api, "_current_index", 0)
    monkeypatch.setattr(odds_api, "_remaining", {})
    yield cache_path


class TestGetCurrentKey:
    """`get_current_key` must skip cached-exhausted keys."""

    def test_returns_first_key_when_no_cache(self, clean_module):
        odds_api._keys[:] = ["keyA", "keyB", "keyC"]
        assert odds_api.get_current_key() == "keyA"

    def test_skips_key_with_zero_remaining(self, clean_module):
        odds_api._keys[:] = ["keyA", "keyB", "keyC"]
        odds_api._remaining.update({"keyA": 0, "keyB": 250, "keyC": 500})
        assert odds_api.get_current_key() == "keyB"
        # Index should advance past the exhausted key so subsequent calls don't recheck it
        assert odds_api._current_index == 1

    def test_skips_multiple_exhausted_in_a_row(self, clean_module):
        # User's actual situation: first 5 keys exhausted, key 5 has quota
        odds_api._keys[:] = [f"k{i}" for i in range(10)]
        odds_api._remaining.update({f"k{i}": 0 for i in range(5)})
        odds_api._remaining.update({"k5": 174})
        assert odds_api.get_current_key() == "k5"
        assert odds_api._current_index == 5

    def test_returns_current_slot_when_all_exhausted(self, clean_module):
        # Fallback: if every key is cached exhausted, return current slot
        # so a monthly quota reset can be re-discovered instead of giving up.
        odds_api._keys[:] = ["keyA", "keyB"]
        odds_api._remaining.update({"keyA": 0, "keyB": 0})
        result = odds_api.get_current_key()
        assert result in ("keyA", "keyB")

    def test_unknown_remaining_treated_as_live(self, clean_module):
        # Key without a cache entry shouldn't be skipped — we assume it's live
        # until proven otherwise.
        odds_api._keys[:] = ["keyA", "keyB"]
        odds_api._remaining.update({"keyA": 0})  # keyB absent = unknown
        assert odds_api.get_current_key() == "keyB"

    def test_returns_empty_when_no_keys_configured(self, clean_module, monkeypatch):
        # Prevent the fallback _load_keys() inside get_current_key from
        # repopulating _keys from the developer's real env.
        monkeypatch.setattr(odds_api, "_load_keys", lambda: [])
        assert odds_api.get_current_key() == ""


class TestQuotaCachePersistence:
    """`report_remaining` and `mark_exhausted` must survive across processes."""

    def test_report_remaining_writes_cache(self, clean_module):
        odds_api._keys[:] = ["keyA"]
        odds_api.report_remaining("keyA", 250)
        assert clean_module.exists()
        saved = json.loads(clean_module.read_text())
        assert saved == {"keyA": 250}

    def test_mark_exhausted_writes_cache(self, clean_module):
        odds_api._keys[:] = ["keyA"]
        odds_api.mark_exhausted("keyA")
        saved = json.loads(clean_module.read_text())
        assert saved == {"keyA": 0}

    def test_cache_load_populates_remaining(self, clean_module):
        clean_module.parent.mkdir(parents=True, exist_ok=True)
        clean_module.write_text(json.dumps({"keyA": 0, "keyB": 174}))
        odds_api._load_quota_cache()
        assert odds_api._remaining["keyA"] == 0
        assert odds_api._remaining["keyB"] == 174

    def test_cache_load_tolerates_missing_file(self, clean_module):
        # Don't write anything — should not raise
        odds_api._load_quota_cache()
        assert odds_api._remaining == {}

    def test_cache_load_tolerates_corrupt_file(self, clean_module):
        clean_module.parent.mkdir(parents=True, exist_ok=True)
        clean_module.write_text("{not json")
        odds_api._load_quota_cache()
        assert odds_api._remaining == {}


class TestRotateKey:
    """`rotate_key` cycles to the next slot and returns None when no
    additional keys exist."""

    def test_rotate_with_single_key_returns_none(self, clean_module):
        odds_api._keys[:] = ["keyA"]
        assert odds_api.rotate_key("test") is None

    def test_rotate_cycles_forward(self, clean_module):
        odds_api._keys[:] = ["keyA", "keyB", "keyC"]
        new_key = odds_api.rotate_key("test")
        assert new_key == "keyB"
        assert odds_api._current_index == 1
