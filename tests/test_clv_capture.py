"""S8 — `scripts/kalshi/clv_capture.py`, closing-book capture for CLV.

CLV had never once been computed. `kalshi_settler.py` derived `closing_price`
from the *settlement-time* market snapshot; a settled Kalshi market returns
nothing meaningful for `last_price`, so it read `0.0`, `0.0` is falsy, and
`if closing_price and entry_price` short-circuited `clv` to `None` — silently,
on every settle, for five months. **426 settlements, 0 CLV**, `closing_price`
split `{None: 259, 0.0: 167}`.

The bug was not arithmetic. By settlement the closing book no longer exists, so
nothing at that point could have recovered it; capture has to happen before the
event starts. What these tests guard is the handful of ways that same class of
mistake can recur:

- a missing price must be **NULL, never 0.0** — a falsy sentinel absorbed by a
  truthiness guard is exactly how D1 hid, and a zero close would drag every mean
  CLV toward a fictitious `-entry_price`;
- CLV must be computed in **bet-side probability space**, or the sign inverts
  for every NO bet (a third of the book) — the S18 mistake;
- "never captured", "captured", and "capture ran and missed" are three different
  facts and must stay distinguishable.
"""

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)


@pytest.fixture(scope="module")
def clv():
    sys.path.insert(0, str(ROOT / "scripts" / "shared"))
    sys.path.insert(0, str(ROOT / "scripts" / "kalshi"))
    spec = importlib.util.spec_from_file_location(
        "_clv_capture", ROOT / "scripts" / "kalshi" / "clv_capture.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _trade(**kw):
    t = {"ticker": "KXMLBGAME-26SEP101800NYYBOS-NYY", "side": "yes",
         "filled_contracts": 3, "dry_run": False, "closed_at": None,
         "entry_price_bet_side": 0.55, "market_price_at_entry": 0.55,
         "event_start_time": NOW.isoformat(), "close_capture_reason": None}
    t.update(kw)
    return t


class FakeClient:
    def __init__(self, market=None, raises=False):
        self._m = market or {}
        self._raises = raises
        self.calls = []

    def get_market(self, ticker):
        self.calls.append(ticker)
        if self._raises:
            raise RuntimeError("venue down")
        return {"market": self._m}


# ── the D1 trap: missing must be NULL, never 0.0 ────────────────────────────

class TestMissingPriceIsNullNotZero:
    def test_absent_field_is_none(self, clv):
        assert clv._price(None) is None
        assert clv._price("") is None

    def test_unparseable_is_none(self, clv):
        assert clv._price("n/a") is None
        assert clv._price({}) is None

    def test_a_real_zero_survives(self, clv):
        """0.0 is a legitimate close on a collapsed market. It must not be
        conflated with 'missing' — that conflation is the whole of D1."""
        assert clv._price("0.0") == 0.0
        assert clv._price(0) == 0.0

    def test_empty_book_yields_null_mid_not_zero(self, clv):
        book = clv.closing_book({}, "yes")
        assert book["close_mid_bet_side"] is None
        assert all(v is None for v in book.values())

    def test_missed_capture_writes_nulls(self, clv, monkeypatch):
        """A miss must not write a zero that later averages in as real."""
        t = _trade(event_start_time=(NOW - timedelta(minutes=60)).isoformat())
        monkeypatch.setattr(clv, "load_trade_log", lambda: [t])
        monkeypatch.setattr(clv, "save_trade_log", lambda rows: None)
        clv.run(client=FakeClient(), now=NOW)
        assert t["close_capture_reason"] == "missed"
        assert t["close_mid_bet_side"] is None
        assert t["clv"] is None


class TestComputeClvUsesIsNoneNotTruthiness:
    def test_basic(self, clv):
        assert clv.compute_clv(0.55, 0.62) == pytest.approx(0.07)

    def test_negative_clv(self, clv):
        assert clv.compute_clv(0.60, 0.52) == pytest.approx(-0.08)

    def test_zero_close_is_computed_not_discarded(self, clv):
        """`if close and entry` would drop this — the D1 shape one level down."""
        assert clv.compute_clv(0.55, 0.0) == pytest.approx(-0.55)

    def test_zero_entry_is_computed_not_discarded(self, clv):
        assert clv.compute_clv(0.0, 0.4) == pytest.approx(0.4)

    @pytest.mark.parametrize("entry,close", [(None, 0.5), (0.5, None), (None, None)])
    def test_missing_leg_is_none(self, clv, entry, close):
        assert clv.compute_clv(entry, close) is None


# ── bet-side space: the S18 trap ────────────────────────────────────────────

class TestBetSideProbabilitySpace:
    MARKET = {"yes_bid_dollars": "0.60", "yes_ask_dollars": "0.64",
              "no_bid_dollars": "0.36", "no_ask_dollars": "0.40"}

    def test_yes_midpoint(self, clv):
        assert clv.closing_book(self.MARKET, "yes")["close_mid_bet_side"] == pytest.approx(0.62)

    def test_no_midpoint_is_the_no_price(self, clv):
        """A NO bet's close is the NO price — NOT 1 - yes_mid dressed up."""
        assert clv.closing_book(self.MARKET, "no")["close_mid_bet_side"] == pytest.approx(0.38)

    def test_no_side_clv_sign_is_not_inverted(self, clv):
        """A NO bought at 0.35 whose NO price closes at 0.38 moved the bettor's
        way: CLV must be POSITIVE. Reading the close as a YES probability would
        report -0.27 and invert the sign on a third of the book (S18)."""
        mid = clv.closing_book(self.MARKET, "no")["close_mid_bet_side"]
        assert clv.compute_clv(0.35, mid) == pytest.approx(+0.03)

    def test_whole_book_is_persisted(self, clv):
        """A lone midpoint makes the S14 maker/taker A/B unreadable."""
        book = clv.closing_book(self.MARKET, "yes")
        for k in ("close_yes_bid", "close_yes_ask", "close_no_bid", "close_no_ask"):
            assert book[k] is not None

    def test_no_side_derived_when_venue_omits_it(self, clv):
        book = clv.closing_book(
            {"yes_bid_dollars": "0.60", "yes_ask_dollars": "0.64"}, "no")
        assert book["close_no_bid"] == pytest.approx(0.36)
        assert book["close_no_ask"] == pytest.approx(0.40)
        assert book["close_mid_bet_side"] == pytest.approx(0.38)


# ── window logic ────────────────────────────────────────────────────────────

class TestCaptureWindow:
    @pytest.mark.parametrize("minutes_out,expected", [
        (60, None), (6, None),               # too early
        (5, "t_minus_5"), (1, "t_minus_5"), (0, "t_minus_5"),
        (-1, "t_zero_fallback"), (-10, "t_zero_fallback"),
        (-11, "missed"), (-600, "missed"),   # in-play too long to call a close
    ])
    def test_reason_by_offset(self, clv, minutes_out, expected):
        t = _trade(event_start_time=(NOW + timedelta(minutes=minutes_out)).isoformat())
        assert clv.capture_due(t, NOW, 5) == expected

    def test_no_start_time_is_never_due(self, clv):
        """Futures have no start; guessing one would invent a closing line."""
        assert clv.capture_due(_trade(event_start_time=None), NOW, 5) is None

    def test_unparseable_start_is_never_due(self, clv):
        assert clv.capture_due(_trade(event_start_time="not a date"), NOW, 5) is None


class TestEligibility:
    def test_settled_rows_are_skipped(self, clv):
        assert not clv.is_open(_trade(closed_at="2026-09-10T00:00:00Z"))

    def test_dry_run_rows_are_skipped(self, clv):
        """A dry run never reached the venue — no position, no closing line."""
        assert not clv.is_open(_trade(dry_run=True))

    def test_zero_fill_rows_are_skipped(self, clv):
        assert not clv.is_open(_trade(filled_contracts=0, fill_count=0))

    def test_open_filled_row_qualifies(self, clv):
        assert clv.is_open(_trade())

    def test_already_captured_is_not_recaptured(self, clv):
        assert not clv.needs_capture(_trade(close_capture_reason="t_minus_5"))

    def test_a_recorded_miss_is_not_retried(self, clv):
        """Retrying later samples an in-play book and calls it a close."""
        assert not clv.needs_capture(_trade(close_capture_reason="missed"))


# ── the pass itself ─────────────────────────────────────────────────────────

class TestRun:
    def test_captures_and_computes(self, clv, monkeypatch):
        t = _trade()
        monkeypatch.setattr(clv, "load_trade_log", lambda: [t])
        saved = []
        monkeypatch.setattr(clv, "save_trade_log", lambda rows: saved.append(rows))
        c = FakeClient({"yes_bid_dollars": "0.60", "yes_ask_dollars": "0.64"})
        s = clv.run(client=c, now=NOW)
        assert s["captured"] == 1
        assert t["close_capture_reason"] == "t_minus_5"
        assert t["close_mid_bet_side"] == pytest.approx(0.62)
        assert t["clv"] == pytest.approx(0.07)
        assert t["close_capture_at"] == NOW.isoformat()
        assert saved, "a real run must persist"

    def test_nothing_due_makes_no_api_calls(self, clv, monkeypatch):
        """A pass with nothing due must be free — it runs every few minutes."""
        t = _trade(event_start_time=(NOW + timedelta(hours=6)).isoformat())
        monkeypatch.setattr(clv, "load_trade_log", lambda: [t])
        monkeypatch.setattr(clv, "save_trade_log", lambda rows: None)
        c = FakeClient()
        assert clv.run(client=c, now=NOW)["due"] == 0
        assert c.calls == []

    def test_venue_error_is_a_miss_not_a_crash(self, clv, monkeypatch):
        """One unreachable ticker must not abandon a window that will not
        come round again."""
        a, b = _trade(ticker="A"), _trade(ticker="B")
        monkeypatch.setattr(clv, "load_trade_log", lambda: [a, b])
        monkeypatch.setattr(clv, "save_trade_log", lambda rows: None)
        s = clv.run(client=FakeClient(raises=True), now=NOW)
        assert s["errors"] == 2
        assert a["close_capture_reason"] == "missed"
        assert a["clv"] is None

    def test_one_bad_ticker_does_not_stop_the_others(self, clv, monkeypatch):
        class Mixed(FakeClient):
            def get_market(self, ticker):
                if ticker == "BAD":
                    raise RuntimeError("nope")
                return {"market": {"yes_bid_dollars": "0.60",
                                   "yes_ask_dollars": "0.64"}}

        bad, good = _trade(ticker="BAD"), _trade(ticker="GOOD")
        monkeypatch.setattr(clv, "load_trade_log", lambda: [bad, good])
        monkeypatch.setattr(clv, "save_trade_log", lambda rows: None)
        s = clv.run(client=Mixed(), now=NOW)
        assert s["captured"] == 1 and s["errors"] == 1
        assert good["clv"] == pytest.approx(0.07)

    def test_dry_run_writes_nothing(self, clv, monkeypatch):
        t = _trade()
        monkeypatch.setattr(clv, "load_trade_log", lambda: [t])
        saved = []
        monkeypatch.setattr(clv, "save_trade_log", lambda rows: saved.append(rows))
        clv.run(client=FakeClient({"yes_bid_dollars": "0.60",
                                   "yes_ask_dollars": "0.64"}),
                now=NOW, dry_run=True)
        assert saved == []

    def test_falls_back_to_market_price_at_entry(self, clv, monkeypatch):
        """Rows written before `entry_price_bet_side` existed still resolve —
        `market_price_at_entry` is already bet-side-relative (S18)."""
        t = _trade(market_price_at_entry=0.55)
        del t["entry_price_bet_side"]
        monkeypatch.setattr(clv, "load_trade_log", lambda: [t])
        monkeypatch.setattr(clv, "save_trade_log", lambda rows: None)
        clv.run(client=FakeClient({"yes_bid_dollars": "0.60",
                                   "yes_ask_dollars": "0.64"}), now=NOW)
        assert t["clv"] == pytest.approx(0.07)


class TestReportRuns:
    def test_report_on_the_live_book(self, clv):
        out = clv.report()
        assert out["captured"] <= out["settled"]

    def test_main_report(self, clv):
        assert clv.main(["--report"]) == 0


class TestConcurrentWriteSafety:
    """M2: `save_trade_log` overwrites the WHOLE file.

    This job runs every few minutes alongside ~10 scheduled execute tasks, so a
    bare load -> mutate -> save would eventually clobber a row appended in
    between — and what it would lose is a live position record. The captures are
    re-applied by `trade_id` against a fresh read taken inside the lock.
    """

    def test_a_concurrent_append_survives(self, clv, monkeypatch):
        target = _trade(trade_id="A")
        newcomer = _trade(trade_id="B", ticker="APPENDED-MID-RUN")

        reads = [[target]]           # first read: only A exists
        saved = {}

        def fake_load():
            # second read (inside the lock) sees B, appended by another process
            return reads.pop(0) if reads else [dict(target), newcomer]

        monkeypatch.setattr(clv, "load_trade_log", fake_load)
        monkeypatch.setattr(clv, "save_trade_log",
                            lambda rows: saved.update(rows=rows))
        monkeypatch.setattr(clv, "trade_log_lock", lambda *a, **k: __import__(
            "contextlib").nullcontext())

        clv.run(client=FakeClient({"yes_bid_dollars": "0.60",
                                   "yes_ask_dollars": "0.64"}), now=NOW)

        ids = [r.get("trade_id") for r in saved["rows"]]
        assert "B" in ids, "a row appended mid-run must not be clobbered"
        written = next(r for r in saved["rows"] if r["trade_id"] == "A")
        assert written["clv"] == pytest.approx(0.07), "the capture must land"

    def test_capture_applies_to_the_fresh_row_not_the_stale_one(self, clv, monkeypatch):
        """The fresh read is authoritative for everything except the capture
        fields — another process may have updated the row meanwhile."""
        stale = _trade(trade_id="A", filled_contracts=3)
        fresh = _trade(trade_id="A", filled_contracts=9)  # updated concurrently

        reads = [[stale]]
        saved = {}
        monkeypatch.setattr(clv, "load_trade_log",
                            lambda: reads.pop(0) if reads else [fresh])
        monkeypatch.setattr(clv, "save_trade_log",
                            lambda rows: saved.update(rows=rows))
        monkeypatch.setattr(clv, "trade_log_lock", lambda *a, **k: __import__(
            "contextlib").nullcontext())

        clv.run(client=FakeClient({"yes_bid_dollars": "0.60",
                                   "yes_ask_dollars": "0.64"}), now=NOW)

        row = saved["rows"][0]
        assert row["filled_contracts"] == 9, "must not revert a concurrent update"
        assert row["clv"] == pytest.approx(0.07), "but must carry the capture"

    def test_venue_reads_happen_outside_the_lock(self, clv, monkeypatch):
        """Holding a cross-process lock across N network calls would block
        execution writes for as long as Kalshi takes to answer."""
        order = []
        monkeypatch.setattr(clv, "load_trade_log", lambda: [_trade(trade_id="A")])
        monkeypatch.setattr(clv, "save_trade_log", lambda rows: None)

        import contextlib

        @contextlib.contextmanager
        def tracking_lock(*a, **k):
            order.append("lock")
            yield
            order.append("unlock")

        monkeypatch.setattr(clv, "trade_log_lock", tracking_lock)

        class Tracking(FakeClient):
            def get_market(self, ticker):
                order.append("api")
                return {"market": {"yes_bid_dollars": "0.60",
                                   "yes_ask_dollars": "0.64"}}

        clv.run(client=Tracking(), now=NOW)
        assert order.index("api") < order.index("lock"), \
            "the venue read must complete before the lock is taken"
