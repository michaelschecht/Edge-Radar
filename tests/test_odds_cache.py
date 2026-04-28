"""Tests for `odds_cache.py` — file-backed Odds API response cache (R24b).

Covers the four contract guarantees in the module docstring:
- Hit within TTL returns the cached events with computed age
- Miss after TTL returns (None, None)
- Disabled cache (ttl_seconds <= 0) skips load
- Corrupted file silently misses, never raises
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import odds_cache


@pytest.fixture
def isolated_cache_dir(monkeypatch, tmp_path):
    """Point _CACHE_DIR at a tmpdir so the real cache is never touched."""
    cache_dir = tmp_path / "odds"
    monkeypatch.setattr(odds_cache, "_CACHE_DIR", cache_dir)
    yield cache_dir


def _write_cache_file(cache_dir: Path, sport_key: str, markets: str,
                     fetched_at: datetime, events: list) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    safe_markets = markets.replace(",", "_")
    path = cache_dir / f"{sport_key}__{safe_markets}.json"
    payload = {
        "fetched_at": fetched_at.isoformat().replace("+00:00", "Z"),
        "sport_key": sport_key,
        "markets": markets,
        "events": events,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestLoad:
    def test_hit_within_ttl(self, isolated_cache_dir):
        events = [{"home_team": "Yankees", "away_team": "Red Sox"}]
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=60)
        _write_cache_file(isolated_cache_dir, "baseball_mlb",
                          "h2h,spreads,totals", fetched_at, events)

        result, age = odds_cache.load(
            "baseball_mlb", "h2h,spreads,totals", ttl_seconds=300
        )

        assert result == events
        assert 55 <= age <= 70  # ~60s, allow timing wiggle

    def test_miss_after_ttl(self, isolated_cache_dir):
        events = [{"home_team": "Yankees"}]
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=600)
        _write_cache_file(isolated_cache_dir, "baseball_mlb",
                          "h2h,spreads,totals", fetched_at, events)

        result, age = odds_cache.load(
            "baseball_mlb", "h2h,spreads,totals", ttl_seconds=300
        )

        assert result is None
        assert age is None

    def test_disabled_via_zero_ttl(self, isolated_cache_dir):
        """ttl_seconds <= 0 must short-circuit the load with no I/O."""
        events = [{"home_team": "Yankees"}]
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=10)
        _write_cache_file(isolated_cache_dir, "baseball_mlb",
                          "h2h", fetched_at, events)

        result, age = odds_cache.load("baseball_mlb", "h2h", ttl_seconds=0)
        assert result is None and age is None

        result, age = odds_cache.load("baseball_mlb", "h2h", ttl_seconds=-1)
        assert result is None and age is None

    def test_corrupted_file_silently_misses(self, isolated_cache_dir):
        isolated_cache_dir.mkdir(parents=True, exist_ok=True)
        path = isolated_cache_dir / "baseball_mlb__h2h.json"
        path.write_text("{ this is not valid json", encoding="utf-8")

        # Must not raise
        result, age = odds_cache.load("baseball_mlb", "h2h", ttl_seconds=300)
        assert result is None and age is None

    def test_missing_file_returns_none(self, isolated_cache_dir):
        result, age = odds_cache.load(
            "baseball_mlb", "h2h", ttl_seconds=300
        )
        assert result is None and age is None

    def test_missing_required_fields_misses(self, isolated_cache_dir):
        """A file without `fetched_at` or `events` should not crash."""
        isolated_cache_dir.mkdir(parents=True, exist_ok=True)
        path = isolated_cache_dir / "baseball_mlb__h2h.json"
        path.write_text(json.dumps({"sport_key": "baseball_mlb"}), encoding="utf-8")

        result, age = odds_cache.load("baseball_mlb", "h2h", ttl_seconds=300)
        assert result is None and age is None


class TestStore:
    def test_round_trip(self, isolated_cache_dir):
        events = [{"home_team": "Yankees", "bookmakers": [{"key": "fanduel"}]}]
        odds_cache.store("baseball_mlb", "h2h,spreads,totals", events)

        # File exists with comma-sanitized name
        expected_path = isolated_cache_dir / "baseball_mlb__h2h_spreads_totals.json"
        assert expected_path.exists()

        # Round-trips via load()
        result, age = odds_cache.load(
            "baseball_mlb", "h2h,spreads,totals", ttl_seconds=300
        )
        assert result == events
        assert age is not None and age >= 0

    def test_store_creates_parent_dir(self, monkeypatch, tmp_path):
        # Cache dir doesn't exist yet
        deep = tmp_path / "nested" / "odds"
        monkeypatch.setattr(odds_cache, "_CACHE_DIR", deep)

        odds_cache.store("baseball_mlb", "outrights", [{"x": 1}])
        assert (deep / "baseball_mlb__outrights.json").exists()


class TestClear:
    def test_removes_all_files(self, isolated_cache_dir):
        for sport in ["baseball_mlb", "basketball_nba", "icehockey_nhl"]:
            odds_cache.store(sport, "h2h", [])
        assert len(list(isolated_cache_dir.glob("*.json"))) == 3

        removed = odds_cache.clear()
        assert removed == 3
        assert len(list(isolated_cache_dir.glob("*.json"))) == 0

    def test_clear_when_dir_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(odds_cache, "_CACHE_DIR", tmp_path / "does_not_exist")
        # Must not raise
        assert odds_cache.clear() == 0
