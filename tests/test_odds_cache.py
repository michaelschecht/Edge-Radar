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
    """Point _CACHE_DIR and _EVENT_CACHE_DIR at a tmpdir so the real cache is never touched."""
    cache_dir = tmp_path / "odds"
    event_dir = tmp_path / "odds_events"
    monkeypatch.setattr(odds_cache, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(odds_cache, "_EVENT_CACHE_DIR", event_dir)
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


class TestLiveAwareTtl:
    """L1: a response containing an in-play event expires on the shorter live
    TTL, so in-progress games refetch on a seconds-fresh cadence."""

    NOW = datetime(2026, 6, 20, 18, 0, 0, tzinfo=timezone.utc)

    def _event(self, offset_seconds: int) -> dict:
        """Event commencing `offset_seconds` relative to NOW (negative = live)."""
        commence = self.NOW + timedelta(seconds=offset_seconds)
        return {"commence_time": commence.isoformat().replace("+00:00", "Z")}

    def test_response_has_live_event_detects_started_game(self):
        events = [self._event(+3600), self._event(-120)]  # one upcoming, one live
        assert odds_cache.response_has_live_event(events, now=self.NOW) is True

    def test_response_has_live_event_false_for_all_upcoming(self):
        events = [self._event(+3600), self._event(+7200)]
        assert odds_cache.response_has_live_event(events, now=self.NOW) is False

    def test_response_has_live_event_handles_garbage(self):
        assert odds_cache.response_has_live_event([{"commence_time": "nope"}],
                                                  now=self.NOW) is False
        assert odds_cache.response_has_live_event([{}], now=self.NOW) is False
        assert odds_cache.response_has_live_event("not a list") is False

    def test_effective_ttl_picks_live_for_inplay(self):
        live = [self._event(-30)]
        upcoming = [self._event(+3600)]
        assert odds_cache.effective_ttl(live, 300, 45, now=self.NOW) == 45
        assert odds_cache.effective_ttl(upcoming, 300, 45, now=self.NOW) == 300

    def test_load_misses_live_response_past_live_ttl(self, isolated_cache_dir):
        """A live response 90s old is a miss at live_ttl=45 even though it's
        well within the 300s pre-game TTL."""
        events = [{"commence_time": "2020-01-01T00:00:00Z"}]  # long since started
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=90)
        _write_cache_file(isolated_cache_dir, "baseball_mlb", "h2h",
                          fetched_at, events)

        result, age = odds_cache.load(
            "baseball_mlb", "h2h", ttl_seconds=300, live_ttl_seconds=45
        )
        assert result is None and age is None

    def test_load_hits_live_response_within_live_ttl(self, isolated_cache_dir):
        events = [{"commence_time": "2020-01-01T00:00:00Z"}]
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=20)
        _write_cache_file(isolated_cache_dir, "baseball_mlb", "h2h",
                          fetched_at, events)

        result, age = odds_cache.load(
            "baseball_mlb", "h2h", ttl_seconds=300, live_ttl_seconds=45
        )
        assert result == events
        assert age is not None and 15 <= age <= 30

    def test_load_pregame_unaffected_by_live_ttl(self, isolated_cache_dir):
        """An all-upcoming response 90s old still hits — live TTL doesn't apply."""
        events = [{"commence_time": "2099-01-01T00:00:00Z"}]  # far future
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=90)
        _write_cache_file(isolated_cache_dir, "baseball_mlb", "h2h",
                          fetched_at, events)

        result, age = odds_cache.load(
            "baseball_mlb", "h2h", ttl_seconds=300, live_ttl_seconds=45
        )
        assert result == events

    def test_load_without_live_ttl_is_backward_compatible(self, isolated_cache_dir):
        """Omitting live_ttl_seconds preserves the pre-L1 3-arg behavior."""
        events = [{"commence_time": "2020-01-01T00:00:00Z"}]
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=90)
        _write_cache_file(isolated_cache_dir, "baseball_mlb", "h2h",
                          fetched_at, events)

        result, age = odds_cache.load("baseball_mlb", "h2h", ttl_seconds=300)
        assert result == events  # live not considered → 300s TTL → hit


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
            odds_cache.store_event(sport, "ev1", {})
        
        # Check files in main and event directories
        assert len(list(odds_cache._CACHE_DIR.glob("*.json"))) == 3
        assert len(list(odds_cache._EVENT_CACHE_DIR.glob("*.json"))) == 3

        removed = odds_cache.clear()
        assert removed == 6
        assert len(list(odds_cache._CACHE_DIR.glob("*.json"))) == 0
        assert len(list(odds_cache._EVENT_CACHE_DIR.glob("*.json"))) == 0

    def test_clear_when_dir_missing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(odds_cache, "_CACHE_DIR", tmp_path / "does_not_exist")
        monkeypatch.setattr(odds_cache, "_EVENT_CACHE_DIR", tmp_path / "does_not_exist_events")
        # Must not raise
        assert odds_cache.clear() == 0


class TestEventCache:
    def test_event_hit_within_ttl(self, isolated_cache_dir):
        event = {"id": "ev1", "home_team": "Lakers"}
        odds_cache.store_event("basketball_nba", "ev1", event)

        result, age = odds_cache.load_event("basketball_nba", "ev1", live_ttl_seconds=45)
        assert result == event
        assert age is not None and age >= 0

    def test_event_miss_after_ttl(self, isolated_cache_dir, monkeypatch):
        event = {"id": "ev1", "home_team": "Lakers"}
        odds_cache.store_event("basketball_nba", "ev1", event)

        future_time = odds_cache._now() + timedelta(seconds=50)
        monkeypatch.setattr(odds_cache, "_now", lambda: future_time)

        result, age = odds_cache.load_event("basketball_nba", "ev1", live_ttl_seconds=45)
        assert result is None
        assert age is None

    def test_event_disabled_via_zero_ttl(self, isolated_cache_dir):
        event = {"id": "ev1", "home_team": "Lakers"}
        odds_cache.store_event("basketball_nba", "ev1", event)

        result, age = odds_cache.load_event("basketball_nba", "ev1", live_ttl_seconds=0)
        assert result is None and age is None

    def test_corrupted_event_file_silently_misses(self, isolated_cache_dir):
        odds_cache._EVENT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = odds_cache._EVENT_CACHE_DIR / "basketball_nba__ev1.json"
        path.write_text("{ corrupt }", encoding="utf-8")

        result, age = odds_cache.load_event("basketball_nba", "ev1", live_ttl_seconds=45)
        assert result is None and age is None
