"""Tests for daily_summary.py — morning P&L digest.

Covers:
  - Empty-day proof-of-life: still produces sections, no crash.
  - Window filtering: settlements outside `hours` excluded.
  - Per-sport aggregation matches W/L/$/ROI math.
  - Open-exposure excludes resting + closed + zero-fill.
  - Pending-today filters by ticker game-date in PST.
  - 7-day rolling skipped when sample < 5.
  - Bankroll line renders with and without balance.
"""

from datetime import datetime, timedelta, timezone

import pytest

from daily_summary import (
    aggregate_exposure,
    aggregate_yesterday,
    build_report,
    filter_pending_today,
    load_open_positions,
    load_recent_settlements,
    rolling_7d_context,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

NOW = datetime(2026, 4, 30, 20, 0, tzinfo=timezone.utc)  # 12 PM PST Apr 30


def _settled(ts: datetime, **kw) -> dict:
    base = {
        "ticker": "KXNBAGAME-26APR29BOSNYK-BOS",
        "side": "yes",
        "won": True,
        "cost": 1.00,
        "revenue": 2.00,
        "fees": 0.05,
        "net_pnl": 0.95,
        "roi": 0.95,
        "category": "game",
        "settled_at": ts.isoformat().replace("+00:00", "Z"),
    }
    base.update(kw)
    return base


def _trade(**kw) -> dict:
    base = {
        "trade_id": "t1",
        "ticker": "KXMLBGAME-26MAY020100NYMLAD-NYM",
        "side": "yes",
        "filled_contracts": 5,
        "filled_cost": 2.50,
        "fill_status": "filled",
        "status": "executed",
        "closed_at": None,
    }
    base.update(kw)
    return base


# ── Window filtering ─────────────────────────────────────────────────────────

class TestLoadRecentSettlements:
    def test_within_window_included(self):
        rows = [_settled(NOW - timedelta(hours=12))]
        out = load_recent_settlements(rows, hours=24, now=NOW)
        assert len(out) == 1

    def test_outside_window_excluded(self):
        rows = [_settled(NOW - timedelta(hours=48))]
        out = load_recent_settlements(rows, hours=24, now=NOW)
        assert out == []

    def test_boundary_inclusive(self):
        # Exactly at the cutoff — should be included (>=)
        rows = [_settled(NOW - timedelta(hours=24))]
        out = load_recent_settlements(rows, hours=24, now=NOW)
        assert len(out) == 1

    def test_missing_settled_at_skipped(self):
        rows = [{"ticker": "X", "won": True}]  # no settled_at
        out = load_recent_settlements(rows, hours=24, now=NOW)
        assert out == []

    def test_malformed_timestamp_skipped(self):
        rows = [{"ticker": "X", "settled_at": "garbage"}]
        out = load_recent_settlements(rows, hours=24, now=NOW)
        assert out == []

    def test_sorted_ascending(self):
        rows = [
            _settled(NOW - timedelta(hours=2), ticker="A"),
            _settled(NOW - timedelta(hours=10), ticker="B"),
            _settled(NOW - timedelta(hours=5), ticker="C"),
        ]
        out = load_recent_settlements(rows, hours=24, now=NOW)
        assert [r["ticker"] for r in out] == ["B", "C", "A"]


# ── Open-position loader ─────────────────────────────────────────────────────

class TestLoadOpenPositions:
    def test_filled_kept(self):
        out = load_open_positions([_trade()])
        assert len(out) == 1

    def test_closed_excluded(self):
        out = load_open_positions([_trade(closed_at="2026-04-29T20:00:00Z")])
        assert out == []

    def test_resting_excluded(self):
        out = load_open_positions([_trade(fill_status="resting", filled_cost=0.0)])
        assert out == []

    def test_error_excluded(self):
        out = load_open_positions([_trade(status="error")])
        assert out == []

    def test_zero_fill_excluded(self):
        out = load_open_positions([_trade(filled_cost=0.0, filled_contracts=0)])
        assert out == []


# ── Aggregations ─────────────────────────────────────────────────────────────

class TestAggregateYesterday:
    def test_empty(self):
        overall, by_sport = aggregate_yesterday([])
        assert overall.n == 0
        assert by_sport == {}

    def test_wl_and_pnl(self):
        rows = [
            _settled(NOW, won=True, net_pnl=2.0, cost=1.0),
            _settled(NOW, won=False, net_pnl=-1.0, cost=1.0),
            _settled(NOW, won=True, net_pnl=1.0, cost=1.0),
        ]
        overall, _ = aggregate_yesterday(rows)
        assert overall.n == 3
        assert overall.wins == 2
        assert overall.losses == 1
        assert overall.pnl == pytest.approx(2.0)
        assert overall.cost == pytest.approx(3.0)

    def test_per_sport_split(self):
        rows = [
            _settled(NOW, ticker="KXNBAGAME-26APR29BOSNYK-BOS", won=True, net_pnl=1.0, cost=1.0),
            _settled(NOW, ticker="KXMLBGAME-26APR29NYMLAD-NYM", won=False, net_pnl=-1.0, cost=1.0),
        ]
        overall, by_sport = aggregate_yesterday(rows)
        assert by_sport["NBA"].wins == 1
        assert by_sport["NBA"].pnl == pytest.approx(1.0)
        assert by_sport["MLB"].wins == 0
        assert by_sport["MLB"].pnl == pytest.approx(-1.0)


class TestAggregateExposure:
    def test_sums_filled_cost(self):
        positions = [
            _trade(ticker="KXNBAGAME-26MAY01-BOS", filled_cost=2.50),
            _trade(ticker="KXMLBGAME-26MAY01-NYM", filled_cost=1.25),
            _trade(ticker="KXNBAGAME-26MAY01-LAL", filled_cost=3.00),
        ]
        overall, by_sport = aggregate_exposure(positions)
        assert overall.n == 3
        assert overall.cost == pytest.approx(6.75)
        assert by_sport["NBA"].n == 2
        assert by_sport["NBA"].cost == pytest.approx(5.50)
        assert by_sport["MLB"].n == 1
        assert by_sport["MLB"].cost == pytest.approx(1.25)


# ── Pending-today filter ─────────────────────────────────────────────────────

class TestFilterPendingToday:
    def test_today_match(self):
        # NOW = Apr 30 12 PM PST. A May 1 game (10 PM PST Apr 30 PST = May 1 in UTC)
        # should NOT match today's PST date. An Apr 30 PST ticker should.
        positions = [
            _trade(ticker="KXNBAGAME-26APR301900LALBOS-LAL"),    # Apr 30 7:00 PM
            _trade(ticker="KXMLBGAME-26MAY020100NYMLAD-NYM"),    # May 2
        ]
        out = filter_pending_today(positions, NOW)
        assert len(out) == 1
        assert "APR30" in out[0]["ticker"]

    def test_no_match_other_days(self):
        positions = [_trade(ticker="KXMLBGAME-26MAY020100NYMLAD-NYM")]
        out = filter_pending_today(positions, NOW)
        assert out == []

    def test_unparseable_ticker_skipped(self):
        positions = [_trade(ticker="GARBAGE-NOT-A-TICKER")]
        out = filter_pending_today(positions, NOW)
        assert out == []


# ── 7-day rolling context ────────────────────────────────────────────────────

class TestRolling7d:
    def test_under_5_returns_none(self):
        rows = [_settled(NOW - timedelta(hours=24)) for _ in range(4)]
        assert rolling_7d_context(rows, NOW) is None

    def test_at_5_returns_stats(self):
        rows = [
            _settled(NOW - timedelta(hours=24), market_price_at_entry=0.50, won=True, cost=1.0, net_pnl=1.0),
            _settled(NOW - timedelta(hours=48), market_price_at_entry=0.50, won=False, cost=1.0, net_pnl=-1.0),
            _settled(NOW - timedelta(hours=72), market_price_at_entry=0.50, won=True, cost=1.0, net_pnl=1.0),
            _settled(NOW - timedelta(hours=96), market_price_at_entry=0.50, won=False, cost=1.0, net_pnl=-1.0),
            _settled(NOW - timedelta(hours=120), market_price_at_entry=0.50, won=True, cost=1.0, net_pnl=1.0),
        ]
        out = rolling_7d_context(rows, NOW)
        assert out["n"] == 5
        assert out["wins"] == 3
        assert out["pnl"] == pytest.approx(1.0)
        # Brier with predicted=0.50 and 3W/2L → mean (0.5)^2 = 0.25
        assert out["brier"] == pytest.approx(0.25)

    def test_excludes_outside_7d(self):
        rows = [_settled(NOW - timedelta(days=8)) for _ in range(10)]
        assert rolling_7d_context(rows, NOW) is None


# ── End-to-end render ────────────────────────────────────────────────────────

class TestBuildReport:
    def test_empty_day_proof_of_life(self):
        report = build_report(NOW, hours=24, settlements=[], trades=[], balance=None)
        assert "Edge-Radar Daily Summary" in report
        assert "_No settlements in window._" in report
        assert "_No open positions._" in report
        assert "_No open positions on today's slate._" in report
        # Sections all present even on empty day
        assert "## Yesterday" in report
        assert "## Open Exposure" in report
        assert "## Pending Today" in report
        assert "## Context" in report

    def test_yesterday_section_renders(self):
        settlements = [
            _settled(NOW - timedelta(hours=12), ticker="KXNBAGAME-26APR29BOSNYK-BOS",
                     won=True, net_pnl=2.5, cost=1.0),
        ]
        report = build_report(NOW, hours=24, settlements=settlements, trades=[], balance=None)
        assert "1 settled" in report
        assert "1-0" in report
        assert "+$2.50" in report
        assert "| NBA |" in report

    def test_balance_line_renders_when_present(self):
        report = build_report(NOW, hours=24, settlements=[], trades=[], balance=125.50)
        assert "**Balance:** $125.50" in report

    def test_balance_line_falls_back_when_missing(self):
        report = build_report(NOW, hours=24, settlements=[], trades=[], balance=None)
        assert "_(balance unavailable)_" in report

    def test_pending_today_table_renders(self):
        trades = [_trade(ticker="KXNBAGAME-26APR301900LALBOS-LAL", filled_cost=3.00)]
        report = build_report(NOW, hours=24, settlements=[], trades=trades, balance=None)
        assert "**1 positions** scheduled for today" in report
        assert "$3.00" in report
