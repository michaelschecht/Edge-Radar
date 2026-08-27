"""S5 / Gate 3.7 (2026-08-26): a days-to-event cap on game markets.

The NFL book that reached 31% of a $92 bankroll was not one bad bet. It was 26
positions bought **25 to 112 days before kickoff** (median 35), 20 of them by the
one scheduled task that runs with no date filter. Nothing settled for months, so
no feedback ever arrived, while `MAX_OPEN_POSITIONS` and `MAX_PER_EVENT` passed
the whole way -- neither measures a standing total, and `MAX_BET_RATIO` /
`--budget` each bound only a single batch.

The cap targets **lead time, not sports**: near-dated college football (3-4 days
out) is unaffected, and championship futures are exempt by category because their
event is a whole season.
"""

from datetime import datetime, timedelta, timezone

import pytest
from opportunity import Opportunity

import kalshi_executor as ke
from kalshi_executor import _time_to_event_rejection, preflight_gate_status, size_order
from ticker_display import days_to_event

_MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
        "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _ticker(days_out: int, prefix: str = "KXNFLSPREAD", suffix: str = "BALIND-IND5") -> str:
    """A game ticker whose embedded date is `days_out` days from today."""
    d = datetime.now(timezone.utc) + timedelta(days=days_out)
    return f"{prefix}-{d:%y}{_MON[d.month - 1]}{d:%d}{suffix}"


def _opp(ticker: str, category: str = "spread") -> Opportunity:
    return Opportunity(
        ticker=ticker, title="", category=category, side="yes",
        market_price=0.50, fair_value=0.62, edge=0.12, edge_source="test",
        confidence="high", liquidity_score=9.0, composite_score=9.9,
        details={"bid_ask_spread": 0.01},
    )


@pytest.fixture
def cap_14(monkeypatch):
    monkeypatch.setattr(ke, "MAX_DAYS_TO_EVENT", 14)


class TestTheCapItself:
    def test_disabled_by_default(self, monkeypatch):
        """Ships at 0 so a fresh clone's behaviour is unchanged."""
        monkeypatch.setattr(ke, "MAX_DAYS_TO_EVENT", 0)
        assert _time_to_event_rejection(_opp(_ticker(112))) is None

    @pytest.mark.parametrize("days", [0, 1, 3, 13, 14])
    def test_near_dated_games_pass(self, days, cap_14):
        assert _time_to_event_rejection(_opp(_ticker(days))) is None

    @pytest.mark.parametrize("days", [15, 25, 35, 112])
    def test_far_dated_games_reject(self, days, cap_14):
        r = _time_to_event_rejection(_opp(_ticker(days)))
        assert r is not None and "event_too_far_out" in r

    def test_the_actual_nfl_book_would_have_been_blocked(self, cap_14):
        """25 days was the *closest* of the 26; the median was 35."""
        for days in (25, 35, 112):
            assert _time_to_event_rejection(_opp(_ticker(days))) is not None

    def test_college_football_week_one_is_unaffected(self, cap_14):
        """The point of the cap: it limits lead time, not sports."""
        opp = _opp(_ticker(3, prefix="KXNCAAFBGAME", suffix="ALAUGA-ALA"))
        assert _time_to_event_rejection(opp) is None
        assert preflight_gate_status(opp) == "ok"

    def test_a_game_already_in_the_past_is_not_rejected_by_this_gate(self, cap_14):
        """Negative lead time is Gate 4.8's business (live betting), not ours."""
        assert _time_to_event_rejection(_opp(_ticker(-2))) is None


class TestFuturesAreExempt:
    """A championship future is *supposed* to be months out."""

    @pytest.mark.parametrize("category", ["futures", "outrights", "championship", "FUTURES"])
    def test_long_dated_categories_pass_at_any_distance(self, category, cap_14):
        opp = _opp(_ticker(300, prefix="KXSB", suffix="-KC"), category=category)
        assert _time_to_event_rejection(opp) is None

    def test_exemption_is_by_category_not_ticker_prefix(self, cap_14):
        """`KXMLB-26-LAD` (World Series) and `KXMLBGAME-26AUG26...` share a
        prefix, so only the scanner's category separates them. A far-dated MLB
        *game* must still reject even though `KXMLB` is also a futures prefix."""
        game = _opp(_ticker(40, prefix="KXMLBGAME", suffix="1915LADATL-LAD"), category="game")
        assert _time_to_event_rejection(game) is not None

    def test_undated_futures_ticker_is_unmeasurable_not_rejected(self, cap_14):
        assert days_to_event("KXSB-26-KC") is None
        assert _time_to_event_rejection(_opp("KXSB-26-KC", category="futures")) is None


class TestFailsOpenLikeGate36:
    def test_unparseable_date_is_unknown_not_too_far(self, cap_14):
        """Mirrors Gate 3.6: reject on evidence, never on a missing field."""
        assert _time_to_event_rejection(_opp("KXNFLSPREAD-GARBAGE-IND5")) is None

    def test_impossible_calendar_date_does_not_raise(self, cap_14):
        assert days_to_event("KXNFLSPREAD-26FEB30BALIND-IND5") is None


class TestWiring:
    def test_size_order_rejects_and_names_the_gate(self, cap_14):
        r = size_order(_opp(_ticker(35)), bankroll=107.0, open_positions=0, daily_pnl=0.0)
        assert r.risk_approval.startswith("REJECTED")
        assert "event_too_far_out" in r.risk_approval
        assert r.contracts == 0

    def test_preflight_agrees_and_says_far(self, cap_14):
        assert preflight_gate_status(_opp(_ticker(35))) == "far"

    def test_reload_risk_config_picks_up_the_env_value(self, monkeypatch):
        monkeypatch.setenv("MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS", "7")
        monkeypatch.setattr("kalshi_executor.load_dotenv", lambda *a, **k: None)
        ke.reload_risk_config()
        try:
            assert ke.MAX_DAYS_TO_EVENT == 7
            assert _time_to_event_rejection(_opp(_ticker(10))) is not None
        finally:
            monkeypatch.delenv("MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS", raising=False)
            ke.reload_risk_config()
