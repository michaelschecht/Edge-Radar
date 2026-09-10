"""S1b — the NFL Week 1 freeze review (`scripts/backtest/nfl_week1_review.py`).

This script runs **once, unattended, on 2026-09-15, with `--apply`**, and it may
rewrite `MIN_EDGE_THRESHOLD_NFL` in the live `.env`. That makes every number and
claim in its report an input to a live-money decision, so the reporting is worth
testing even though it "votes on nothing".

Three defects fixed 2026-09-10, all found by running the script rather than
reading it:

1. `roi_context()` summed `cost_dollars`, which the settlement log has **never**
   written (426/426 rows carry `cost`). `staked` was therefore always `$0.00`,
   and `roi` fell through its own `if staked else 0.0` guard to a clean-looking
   `+0.0%` — on every possible input, since the script was written.
2. The report asserted `MAX_SEGMENT_EXPOSURE_PCT` "does not exist", a string
   literal written before S4 shipped on 2026-08-26. It had been telling the
   operator that nothing caps NFL exposure for two weeks while a 33% cap ran.
3. Branch C said "only N settled NFL bets" when N counts only rows carrying a
   model probability — so dropped rows read as bets that were never placed.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def rev():
    """Import the review script as a module."""
    sys.path.insert(0, str(ROOT / "scripts" / "shared"))
    sys.path.insert(0, str(ROOT / "scripts" / "backtest"))
    spec = importlib.util.spec_from_file_location(
        "_nfl_week1_review", ROOT / "scripts" / "backtest" / "nfl_week1_review.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── 1. The stake field ──────────────────────────────────────────────────────

class TestRoiReadsTheRealStakeField:
    """`cost` is the settler's field. `cost_dollars` is the trade log's."""

    ROWS = [
        {"ticker": "KXNFLGAME-26SEP09NESEA-NE", "cost": 1.02,
         "net_pnl": -1.0672, "won": False},
        {"ticker": "KXNFLSPREAD-26SEP09NESEA-NE5", "cost": 1.10,
         "net_pnl": -1.17, "won": False},
        {"ticker": "KXMLBGAME-26SEP09NYYBOS-NYY", "cost": 5.00,
         "net_pnl": 2.0, "won": True},  # not NFL — must be excluded
    ]

    def test_stake_is_summed_from_cost(self, rev, monkeypatch):
        monkeypatch.setattr(rev, "load_settlement_log", lambda: self.ROWS)
        r = rev.roi_context()
        assert r["n"] == 2
        assert r["staked"] == pytest.approx(2.12)
        assert r["net"] == pytest.approx(-2.2372)
        assert r["roi"] == pytest.approx(-2.2372 / 2.12)

    def test_regression_cost_dollars_is_never_present(self, rev, monkeypatch):
        """The exact shape that produced `staked $0.00 / ROI +0.0%`."""
        monkeypatch.setattr(rev, "load_settlement_log", lambda: self.ROWS)
        assert all("cost_dollars" not in r for r in self.ROWS)
        r = rev.roi_context()
        assert r["staked"] > 0, "the old code read cost_dollars and got 0.00"
        assert r["roi"] != 0.0, "a real loss must not print as +0.0%"

    def test_trade_log_shape_still_reads(self, rev, monkeypatch):
        """A row using the other field name must not be silently worth $0."""
        rows = [{"ticker": "KXNFLGAME-X", "cost_dollars": 3.0,
                 "net_pnl": -3.0, "won": False}]
        monkeypatch.setattr(rev, "load_settlement_log", lambda: rows)
        assert rev.roi_context()["staked"] == pytest.approx(3.0)


class TestUnreadableStakeIsNotZero:
    """A zero indistinguishable from a real result is worse than no result."""

    def test_roi_is_none_when_no_row_has_a_stake(self, rev, monkeypatch):
        rows = [{"ticker": "KXNFLGAME-X", "net_pnl": -1.0, "won": False}]
        monkeypatch.setattr(rev, "load_settlement_log", lambda: rows)
        r = rev.roi_context()
        assert r["roi"] is None, "must not fall through to a plausible 0.0%"
        assert r["missing_cost"] == 1

    def test_partial_stakes_are_counted_and_flagged(self, rev, monkeypatch):
        rows = [
            {"ticker": "KXNFLGAME-A", "cost": 2.0, "net_pnl": 1.0, "won": True},
            {"ticker": "KXNFLGAME-B", "net_pnl": -1.0, "won": False},
        ]
        monkeypatch.setattr(rev, "load_settlement_log", lambda: rows)
        r = rev.roi_context()
        assert r["staked"] == pytest.approx(2.0)
        assert r["missing_cost"] == 1, "the shortfall must be reportable"

    def test_report_prints_na_not_a_number(self, rev, monkeypatch):
        rows = [{"ticker": "KXNFLGAME-X", "net_pnl": -1.0, "won": False}]
        monkeypatch.setattr(rev, "load_settlement_log", lambda: rows)
        monkeypatch.setattr(rev, "load_rows", lambda: [])
        text = rev.render(rev.decide([]), rev.roi_context(), applied=None)
        assert "ROI n/a" in text
        assert "ROI +0.0%" not in text


# ── 2. The S4 claim ─────────────────────────────────────────────────────────

class TestSegmentCapIsReadNotHardcoded:
    """The old text was a literal written before S4 shipped."""

    def test_live_value_is_reported(self, rev, monkeypatch):
        monkeypatch.setattr(rev, "_segment_cap", lambda: 0.33)
        para = rev._segment_cap_paragraph()
        assert "33%" in para
        assert "does not exist" not in para

    def test_off_is_reported_as_off(self, rev, monkeypatch):
        """If the cap really is 0, the warning must come back — not vanish."""
        monkeypatch.setattr(rev, "_segment_cap", lambda: 0.0)
        para = rev._segment_cap_paragraph()
        assert "OFF" in para
        assert "nothing mechanically stops" in para

    def test_unreadable_says_so(self, rev, monkeypatch):
        monkeypatch.setattr(rev, "_segment_cap", lambda: None)
        para = rev._segment_cap_paragraph()
        assert "could not be read" in para
        assert "Check" in para

    def test_never_claims_a_cap_that_is_off(self, rev, monkeypatch):
        """The contradiction caught in review: 'live 0 — OFF' followed by
        'that is a real cap on total NFL money at risk'."""
        for pct in (0.0, None):
            monkeypatch.setattr(rev, "_segment_cap", lambda p=pct: p)
            para = rev._segment_cap_paragraph()
            assert "could not repeat silently" not in para

    def test_entry_only_caveat_survives_every_branch(self, rev, monkeypatch):
        """Gate 2b runs at entry only — true whatever the cap is set to."""
        for pct in (0.33, 0.0, None):
            monkeypatch.setattr(rev, "_segment_cap", lambda p=pct: p)
            assert "only at entry" in rev._segment_cap_paragraph()


# ── 3. Usable vs settled ────────────────────────────────────────────────────

class TestBranchCDistinguishesDroppedRows:
    def test_dropped_rows_are_named(self, rev, monkeypatch):
        monkeypatch.setattr(rev, "_settled_nfl_count", lambda: 31)
        d = rev.decide([])
        assert d["branch"] == "C"
        assert "31 settled" in d["reason"]
        assert "31 dropped" in d["reason"]

    def test_no_confusing_clause_when_nothing_dropped(self, rev, monkeypatch):
        monkeypatch.setattr(rev, "_settled_nfl_count", lambda: 0)
        assert "dropped" not in rev.decide([])["reason"]

    def test_still_stays_frozen(self, rev, monkeypatch):
        """Reporting changed; the pre-declared branch logic did not."""
        monkeypatch.setattr(rev, "_settled_nfl_count", lambda: 31)
        d = rev.decide([])
        assert d["action"] == "stay_frozen"


class TestPreDeclaredLogicUnchanged:
    def test_self_check_passes(self, rev):
        assert rev.main(["--self-check"]) == 0

    def test_threshold_is_still_twenty(self, rev):
        assert rev.MIN_SETTLEMENTS == 20

    def test_pilot_floor_is_still_capped(self, rev):
        """Branch A unfreezes to a pilot floor, never to normal sizing."""
        assert rev.PILOT_FLOOR == 0.08

    def test_report_only_by_default(self, rev, monkeypatch):
        """No `--apply` must never write `.env`."""
        written = []
        monkeypatch.setattr(rev, "apply_pilot",
                            lambda *a, **k: written.append(a))
        rev.main([])
        assert written == []
