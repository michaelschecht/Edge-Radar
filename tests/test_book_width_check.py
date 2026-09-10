"""S20b — `scripts/backtest/book_width_check.py`.

S20 asked whether MLB's -6.4% ROI / 0.2917 Brier was caused by a book consensus
thinned by Odds-API quota exhaustion, and specified the check: *"log `n_books`
on every MLB edge and check whether the failure days coincide with the losing
trades."* It was never answerable — `n_books` was computed at scan time and
thrown away — so the 2026-09-10 pass had to proxy it with exhaustion days
scraped from logs.

What is worth testing here is the machinery that keeps that answer honest:
dating from the log LINE rather than the filename, the model-minus-market Brier
pair, and the per-month sign check that stops a pooled number being read as a
finding when it flips stratum to stratum (the mistake `correlation_check.py`
already caught once, at pooled rho +0.181).
"""

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def bw():
    sys.path.insert(0, str(ROOT / "scripts" / "shared"))
    sys.path.insert(0, str(ROOT / "scripts" / "backtest"))
    spec = importlib.util.spec_from_file_location(
        "_book_width_check", ROOT / "scripts" / "backtest" / "book_width_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(cost=1.0, net=0.0, fv=0.6, mp=0.5, y=1.0, n_books=None, date=None):
    return {"ticker": "KXMLBGAME-X", "date": date, "cost": cost, "net": net,
            "fv": fv, "mp": mp, "y": y, "n_books": n_books}


class TestGameDate:
    @pytest.mark.parametrize("ticker,expected", [
        ("KXMLBGAME-26MAR282140CLESEA-SEA", dt.date(2026, 3, 28)),
        ("KXMLBSPREAD-26SEP101215TBATL-TB3", dt.date(2026, 9, 10)),
        ("KXNFLGAME-26SEP09NESEA-NE", dt.date(2026, 9, 9)),
    ])
    def test_parses(self, bw, ticker, expected):
        assert bw.game_date(ticker) == expected

    @pytest.mark.parametrize("ticker", [
        "KXMLB-26-LAD",          # futures — no game date
        "KXMLBGAME-26XXX28-A",   # bad month
        "KXMLBGAME-26FEB302140-A",  # Feb 30 does not exist
        "", None, "garbage",
    ])
    def test_unparseable_is_none_not_a_crash(self, bw, ticker):
        assert bw.game_date(ticker) is None


class TestExhaustionDaysUsesTheLineNotTheFilename:
    """Log FILENAMES are UTC while the timestamps inside are local — an evening
    PDT run lands in tomorrow's file. Dating off the filename would misassign
    every late-day exhaustion by one day."""

    def test_reads_the_line_date(self, bw, tmp_path):
        (tmp_path / "edge_detector_2026-08-26.log").write_text(
            "2026-08-25 19:04:38 | odds_api | WARNING | "
            "All 4 Odds API keys returned 401/429 for baseball_mlb\n",
            encoding="utf-8")
        assert bw.exhaustion_days(tmp_path) == {"2026-08-25"}

    def test_ignores_unrelated_lines(self, bw, tmp_path):
        (tmp_path / "a_2026-08-25.log").write_text(
            "2026-08-25 10:00:00 | odds_api | INFO | cache hit\n"
            "2026-08-25 10:00:01 | x | INFO | mentions 401/429 but not the phrase\n",
            encoding="utf-8")
        assert bw.exhaustion_days(tmp_path) == set()

    def test_no_logs_is_empty_not_an_error(self, bw, tmp_path):
        assert bw.exhaustion_days(tmp_path) == set()


class TestBrierGapIsAPair:
    """S18: a bare 'Brier' is not a quantity. Positive = model worse."""

    def test_positive_when_model_is_worse(self, bw):
        # market called it right (0.9 on a win), model did not (0.4)
        assert bw.brier_gap([_row(fv=0.4, mp=0.9, y=1.0)]) > 0

    def test_negative_when_model_is_better(self, bw):
        assert bw.brier_gap([_row(fv=0.9, mp=0.4, y=1.0)]) < 0

    def test_zero_when_identical(self, bw):
        assert bw.brier_gap([_row(fv=0.7, mp=0.7, y=1.0)]) == pytest.approx(0.0)

    def test_rows_missing_inputs_are_skipped(self, bw):
        rows = [_row(fv=None), _row(mp=None), _row(y=None)]
        assert bw.brier_gap(rows) is None


class TestRoi:
    def test_basic(self, bw):
        assert bw.roi([_row(cost=10.0, net=2.0)]) == pytest.approx(0.2)

    def test_zero_stake_is_none_not_zero(self, bw):
        """A stake of $0 must not render as a clean 0.0% — the same trap that
        made nfl_week1_review print ROI +0.0% on every input."""
        assert bw.roi([_row(cost=0.0, net=-5.0)]) is None


class TestSplit:
    def test_proxy_uses_the_exhaustion_window(self, bw):
        rows = [_row(date=dt.date(2026, 8, 25)), _row(date=dt.date(2026, 7, 1))]
        lo, hi, skip = bw.split(rows, proxy=True, exh={"2026-08-25"},
                                days_before=0, thin=5)
        assert len(lo) == 1 and len(hi) == 1 and not skip

    def test_days_before_widens_the_window(self, bw):
        rows = [_row(date=dt.date(2026, 8, 26))]
        lo, _, _ = bw.split(rows, proxy=True, exh={"2026-08-25"},
                            days_before=0, thin=5)
        assert not lo
        lo, _, _ = bw.split(rows, proxy=True, exh={"2026-08-25"},
                            days_before=1, thin=5)
        assert len(lo) == 1

    def test_undatable_rows_are_excluded_not_counted_clean(self, bw):
        """A futures row with no game date must not silently pad the control
        arm — that would dilute the very effect under test."""
        _, hi, skip = bw.split([_row(date=None)], proxy=True, exh=set(),
                               days_before=1, thin=5)
        assert not hi and len(skip) == 1

    def test_n_books_mode_splits_on_width(self, bw):
        rows = [_row(n_books=3), _row(n_books=8)]
        lo, hi, skip = bw.split(rows, proxy=False, exh=set(),
                                days_before=0, thin=5)
        assert len(lo) == 1 and len(hi) == 1 and not skip

    def test_missing_n_books_is_unknown_not_zero(self, bw):
        """Pre-2026-09-10 rows carry no n_books. Treating that as 0 books would
        label the entire back-catalogue as thin."""
        lo, hi, skip = bw.split([_row(n_books=None)], proxy=False, exh=set(),
                                days_before=0, thin=5)
        assert not lo and not hi and len(skip) == 1


class TestBootstrap:
    def test_detects_a_real_gap(self, bw):
        a = [_row(cost=1.0, net=-0.9) for _ in range(60)]
        b = [_row(cost=1.0, net=+0.9) for _ in range(60)]
        lo, hi = bw.bootstrap_diff(a, b, bw.roi, n=400)
        assert hi < 0, "a clearly worse arm must produce a CI below zero"

    def test_straddles_zero_when_arms_match(self, bw):
        a = [_row(cost=1.0, net=0.1) for _ in range(40)]
        b = [_row(cost=1.0, net=0.1) for _ in range(40)]
        lo, hi = bw.bootstrap_diff(a, b, bw.roi, n=400)
        assert lo <= 0 <= hi

    def test_empty_arm_is_none(self, bw):
        assert bw.bootstrap_diff([], [_row()], bw.roi, n=50) is None

    def test_deterministic(self, bw):
        a = [_row(cost=1.0, net=-0.5) for _ in range(20)]
        b = [_row(cost=1.0, net=+0.5) for _ in range(20)]
        assert (bw.bootstrap_diff(a, b, bw.roi, n=300)
                == bw.bootstrap_diff(a, b, bw.roi, n=300))


class TestRunsEndToEnd:
    def test_proxy_mode_on_the_live_book(self, bw):
        assert bw.main(["--proxy", "--sport", "mlb"]) == 0

    def test_n_books_mode_on_the_live_book(self, bw):
        """Must not crash while every historical row still lacks n_books."""
        assert bw.main(["--sport", "mlb"]) == 0

    def test_unknown_sport_is_not_a_crash(self, bw):
        assert bw.main(["--proxy", "--sport", "quidditch"]) == 0
