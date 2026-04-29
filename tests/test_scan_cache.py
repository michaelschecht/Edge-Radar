"""Tests for `scan_cache.py` — file-backed cache of the last preview's
sized-order list (R26).

Covers the R26 contract:
- Hit within TTL returns rehydrated SizedOrders + age + fingerprint
- Miss after TTL returns None
- Disabled cache (ttl_seconds <= 0 or enabled=False) returns None
- Corrupted file silently misses, never raises
- Round-trip preserves SizedOrder + Opportunity fields
- Fingerprint match / mismatch contract
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import scan_cache
from app import config as app_config
from kalshi_executor import SizedOrder
from opportunity import Opportunity


@pytest.fixture(autouse=True)
def isolated_cache_file(monkeypatch, tmp_path):
    """Redirect _CACHE_DIR / _CACHE_FILE so the real cache is never touched."""
    cache_dir = tmp_path / "cache"
    cache_file = cache_dir / "last_scan.json"
    monkeypatch.setattr(scan_cache, "_CACHE_DIR", cache_dir)
    monkeypatch.setattr(scan_cache, "_CACHE_FILE", cache_file)
    # Reset config so SCAN_CACHE_* env mutations are picked up.
    app_config.reset_config()
    yield cache_file
    app_config.reset_config()


@pytest.fixture
def sample_sized():
    opp = Opportunity(
        ticker="KXMLBGAME-26APR291840NYMLAD-NYM",
        title="NY Mets vs LA Dodgers",
        category="game",
        side="yes",
        market_price=0.42,
        fair_value=0.55,
        edge=0.13,
        edge_source="odds_consensus",
        confidence="high",
        liquidity_score=8.0,
        composite_score=7.8,
        details={"n_books": 9},
    )
    return SizedOrder(
        opportunity=opp,
        contracts=5,
        price_cents=42,
        cost_dollars=2.10,
        bankroll_pct=0.04,
        risk_approval="APPROVED",
    )


@pytest.fixture
def sample_fingerprint():
    return {
        "scanner": "sports",
        "filter": "mlb",
        "category": None,
        "date": "2026-04-29",
        "exclude_open": True,
        "min_edge": 0.03,
        "top": 20,
    }


class TestStoreLoadRoundTrip:
    def test_round_trip_preserves_fields(self, sample_sized, sample_fingerprint):
        path = scan_cache.store(sample_fingerprint, [sample_sized], bankroll=543.21)
        assert path is not None and path.exists()

        result = scan_cache.load()
        assert result is not None
        assert result["fingerprint"] == sample_fingerprint
        assert result["bankroll_at_scan"] == 543.21
        assert len(result["rows"]) == 1
        s = result["rows"][0]
        assert isinstance(s, SizedOrder)
        assert s.contracts == 5
        assert s.price_cents == 42
        assert s.cost_dollars == 2.10
        assert s.risk_approval == "APPROVED"
        # Opportunity round-trips
        assert s.opportunity.ticker == sample_sized.opportunity.ticker
        assert s.opportunity.edge == pytest.approx(0.13)
        assert s.opportunity.confidence == "high"
        assert s.opportunity.details == {"n_books": 9}

    def test_age_is_recent(self, sample_sized, sample_fingerprint):
        scan_cache.store(sample_fingerprint, [sample_sized])
        result = scan_cache.load()
        assert result is not None
        assert 0 <= result["age_seconds"] <= 5


class TestLoadFreshness:
    def test_miss_after_ttl(self, sample_sized, sample_fingerprint, isolated_cache_file):
        scan_cache.store(sample_fingerprint, [sample_sized])
        # Rewrite saved_at to far in the past
        raw = json.loads(isolated_cache_file.read_text(encoding="utf-8"))
        old = datetime.now(timezone.utc) - timedelta(seconds=3600)
        raw["saved_at"] = old.isoformat().replace("+00:00", "Z")
        isolated_cache_file.write_text(json.dumps(raw), encoding="utf-8")

        # Default TTL is 600s — 3600s old is past it
        assert scan_cache.load() is None

    def test_disabled_via_zero_ttl(self, monkeypatch, sample_sized, sample_fingerprint):
        scan_cache.store(sample_fingerprint, [sample_sized])
        monkeypatch.setenv("SCAN_CACHE_TTL_SECONDS", "0")
        app_config.reset_config()
        assert scan_cache.load() is None

    def test_disabled_via_env_flag(self, monkeypatch, sample_sized, sample_fingerprint):
        scan_cache.store(sample_fingerprint, [sample_sized])
        monkeypatch.setenv("SCAN_CACHE_ENABLED", "false")
        app_config.reset_config()
        assert scan_cache.load() is None


class TestLoadFailureModes:
    def test_corrupted_file_silently_misses(self, isolated_cache_file):
        isolated_cache_file.parent.mkdir(parents=True, exist_ok=True)
        isolated_cache_file.write_text("{ this is not valid json", encoding="utf-8")
        assert scan_cache.load() is None  # must not raise

    def test_missing_file_returns_none(self):
        assert scan_cache.load() is None

    def test_wrong_version_returns_none(self, isolated_cache_file):
        isolated_cache_file.parent.mkdir(parents=True, exist_ok=True)
        isolated_cache_file.write_text(
            json.dumps({"version": 999, "saved_at": "2026-04-29T00:00:00Z", "rows": []}),
            encoding="utf-8",
        )
        assert scan_cache.load() is None

    def test_missing_required_fields(self, isolated_cache_file):
        isolated_cache_file.parent.mkdir(parents=True, exist_ok=True)
        isolated_cache_file.write_text(json.dumps({"version": 1}), encoding="utf-8")
        assert scan_cache.load() is None


class TestStore:
    def test_disabled_via_env_does_not_write(
        self, monkeypatch, sample_sized, sample_fingerprint, isolated_cache_file
    ):
        monkeypatch.setenv("SCAN_CACHE_ENABLED", "false")
        app_config.reset_config()
        path = scan_cache.store(sample_fingerprint, [sample_sized])
        assert path is None
        assert not isolated_cache_file.exists()

    def test_creates_parent_dir(self, sample_sized, sample_fingerprint, isolated_cache_file):
        # cache dir doesn't exist initially
        assert not isolated_cache_file.parent.exists()
        scan_cache.store(sample_fingerprint, [sample_sized])
        assert isolated_cache_file.exists()


class TestClear:
    def test_clear_removes_file(self, sample_sized, sample_fingerprint, isolated_cache_file):
        scan_cache.store(sample_fingerprint, [sample_sized])
        assert isolated_cache_file.exists()
        assert scan_cache.clear() is True
        assert not isolated_cache_file.exists()

    def test_clear_when_missing(self):
        assert scan_cache.clear() is False  # no error


class TestFingerprintsMatch:
    def test_identical_match(self, sample_fingerprint):
        ok, diffs = scan_cache.fingerprints_match(sample_fingerprint, dict(sample_fingerprint))
        assert ok is True
        assert diffs == []

    def test_value_mismatch(self, sample_fingerprint):
        current = dict(sample_fingerprint)
        current["filter"] = "nhl"
        ok, diffs = scan_cache.fingerprints_match(sample_fingerprint, current)
        assert ok is False
        assert any("filter" in d for d in diffs)

    def test_extra_key_in_current(self, sample_fingerprint):
        current = dict(sample_fingerprint)
        current["new_arg"] = True
        ok, diffs = scan_cache.fingerprints_match(sample_fingerprint, current)
        assert ok is False
        assert any("new_arg" in d for d in diffs)

    def test_exclude_open_change_is_a_mismatch(self, sample_fingerprint):
        """The user's exact bug case: --exclude-open on preview, dropped on execute."""
        current = dict(sample_fingerprint)
        current["exclude_open"] = False
        ok, diffs = scan_cache.fingerprints_match(sample_fingerprint, current)
        assert ok is False
        assert any("exclude_open" in d for d in diffs)
