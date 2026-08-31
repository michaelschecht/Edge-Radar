"""S4 / Gate 2b (2026-08-26): cumulative open-exposure ceilings.

Every risk gate before this one measures either a **single order**
(`MAX_BET_SIZE`, `MAX_BET_RATIO`), a **single event** (`MAX_PER_EVENT`), a
**single batch** (`--budget`, the Kelly `/batch_size` divisor), or a **row
count** (`MAX_OPEN_POSITIONS`). None of them measures dollars standing across
the book, which is how 26 NFL positions reached 31% of a ~$92 bankroll across
roughly a dozen scans over three months with every gate passing the whole way.

Two ceilings, both fractions of **total equity** (cash + position value):
`MAX_OPEN_EXPOSURE_PCT` across everything, `MAX_SEGMENT_EXPOSURE_PCT` per sport.
The pair is the point -- a portfolio cap alone permits one sport to hold all of
it, and a segment cap alone permits N sports x the segment cap.
"""

import pytest
from opportunity import Opportunity

import kalshi_executor as ke
from kalshi_executor import (
    _exposure_rejection,
    exposure_from_positions,
    exposure_segment,
    size_order,
)


def _opp(ticker="KXMLBGAME-99AUG271900NYYBOS-NYY", category="game", price=0.50):
    return Opportunity(
        ticker=ticker, title="", category=category, side="yes",
        market_price=price, fair_value=price + 0.12, edge=0.12, edge_source="test",
        confidence="high", liquidity_score=9.0, composite_score=9.9,
        details={"bid_ask_spread": 0.01},
    )


@pytest.fixture
def caps(monkeypatch):
    """The live `.env` pair: 50% total, 33% per sport."""
    monkeypatch.setattr(ke, "MAX_OPEN_EXPOSURE_PCT", 0.50)
    monkeypatch.setattr(ke, "MAX_SEGMENT_EXPOSURE_PCT", 0.33)


class TestReadingPositions:
    """`market_exposure_dollars` arrives as a STRING from the v2 API."""

    def test_sums_string_dollars(self):
        total, by_seg = exposure_from_positions([
            {"ticker": "KXNFLSPREAD-26SEP13MIALV-MIA7", "market_exposure_dollars": "0.960000"},
            {"ticker": "KXNFLSPREAD-26SEP14DENKC-KC4", "market_exposure_dollars": "0.860000"},
        ])
        assert total == pytest.approx(1.82)
        assert by_seg == {"nfl": pytest.approx(1.82)}

    def test_splits_by_sport(self):
        total, by_seg = exposure_from_positions([
            {"ticker": "KXNFLSPREAD-26SEP13MIALV-MIA7", "market_exposure_dollars": "10.00"},
            {"ticker": "KXMLBGAME-99AUG271900NYYBOS-NYY", "market_exposure_dollars": "4.00"},
        ])
        assert total == pytest.approx(14.0)
        assert by_seg["nfl"] == pytest.approx(10.0)
        assert by_seg["mlb"] == pytest.approx(4.0)

    @pytest.mark.parametrize("bad", [None, "", "n/a", {}])
    def test_unparseable_exposure_is_skipped_not_zeroed(self, bad):
        """A silent `float("")` would raise; a silent 0 for the whole book would
        open every ceiling. Skip the row, keep the rest."""
        total, _ = exposure_from_positions([
            {"ticker": "KXNFLGAME-26SEP13MIALV-MIA", "market_exposure_dollars": bad},
            {"ticker": "KXMLBGAME-99AUG271900NYYBOS-NYY", "market_exposure_dollars": "4.00"},
        ])
        assert total == pytest.approx(4.0)

    def test_empty_book_is_zero_not_an_error(self):
        assert exposure_from_positions([]) == (0.0, {})
        assert exposure_from_positions(None) == (0.0, {})


class TestSegmentKey:
    def test_sport_wins(self):
        assert exposure_segment(_opp("KXNFLSPREAD-26SEP13MIALV-MIA7")) == "nfl"

    def test_falls_back_to_category_then_unknown(self):
        assert exposure_segment(_opp("KXSB-26-KC", category="futures")) == "futures"
        assert exposure_segment(_opp("KXSB-26-KC", category="")) == "unknown"

    def test_is_not_the_event_key(self):
        """Gate 6 already binds one event -- and passed 26 times over 26 events."""
        a = exposure_segment(_opp("KXNFLSPREAD-26SEP13MIALV-MIA7"))
        b = exposure_segment(_opp("KXNFLSPREAD-26SEP14DENKC-KC4"))
        assert a == b == "nfl"


class TestTheCeilings:
    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.setattr(ke, "MAX_OPEN_EXPOSURE_PCT", 0.0)
        monkeypatch.setattr(ke, "MAX_SEGMENT_EXPOSURE_PCT", 0.0)
        assert _exposure_rejection(_opp(), 999.0, 999.0, 100.0) is None

    def test_under_both_ceilings_passes(self, caps):
        assert _exposure_rejection(_opp(), 40.0, 20.0, 100.0) is None

    def test_total_ceiling_rejects(self, caps):
        r = _exposure_rejection(_opp(), 55.0, 10.0, 100.0)
        assert r is not None and "max_open_exposure" in r

    def test_segment_ceiling_rejects_while_total_is_fine(self, caps):
        """The whole reason both exist: 35% in one sport is 35% of the book
        riding on one league's weekend, at a total the portfolio cap allows."""
        r = _exposure_rejection(_opp(), 40.0, 35.0, 100.0)
        assert r is not None and "max_segment_exposure" in r and "mlb" in r

    def test_ceiling_is_inclusive(self, caps):
        """Exactly at the cap is at the cap -- no new position."""
        assert _exposure_rejection(_opp(), 50.0, 0.0, 100.0) is not None

    def test_unknown_equity_fails_open(self, caps):
        """Mirrors gates 3.6/3.7: a balance call that returned nothing is
        'unknown', not 'over the limit'."""
        assert _exposure_rejection(_opp(), 999.0, 999.0, 0.0) is None
        assert _exposure_rejection(_opp(), 999.0, 999.0, -5.0) is None


class TestTheRealBook:
    """The 2026-08-26 numbers that motivated the gate, at the operator's caps."""

    LIVE_EQUITY = 107.04
    NFL_AT_RISK = 28.50
    TOTAL_AT_RISK = 33.71

    def test_current_book_passes_at_50_33(self, caps):
        """The operator chose 50/33 over the review's 20/10 knowing this: the
        gate binds on the NEXT pileup, not the one that prompted it."""
        assert _exposure_rejection(
            _opp("KXNFLGAME-26SEP13MIALV-MIA"),
            self.TOTAL_AT_RISK, self.NFL_AT_RISK, self.LIVE_EQUITY,
        ) is None

    def test_same_book_would_have_been_blocked_at_the_reviews_20_10(self, monkeypatch):
        monkeypatch.setattr(ke, "MAX_OPEN_EXPOSURE_PCT", 0.20)
        monkeypatch.setattr(ke, "MAX_SEGMENT_EXPOSURE_PCT", 0.10)
        assert _exposure_rejection(
            _opp("KXNFLGAME-26SEP13MIALV-MIA"),
            self.TOTAL_AT_RISK, self.NFL_AT_RISK, self.LIVE_EQUITY,
        ) is not None

    def test_other_sports_still_have_headroom(self, caps):
        """MLB carries $5.21 of the book, so a frozen NFL pile must not stop
        new betting elsewhere -- the reason the segment cap exists at all."""
        assert _exposure_rejection(
            _opp("KXMLBGAME-99AUG271900NYYBOS-NYY"),
            self.TOTAL_AT_RISK, 5.21, self.LIVE_EQUITY,
        ) is None


class TestSizingHalf:
    """Rejecting only when a ceiling is already breached would let one order
    step over it. The trim is what makes the ceiling a ceiling."""

    def test_order_is_trimmed_to_remaining_headroom(self, caps, no_fees):
        # 49% deployed of $100 equity -> $1 of total headroom left.
        r = size_order(_opp(price=0.10), bankroll=100.0, open_positions=0,
                       daily_pnl=0.0, unit_size=50.0,
                       open_exposure=49.0, segment_exposure=0.0, equity=100.0)
        assert r.risk_approval == "APPROVED_CAPPED_EXPOSURE"
        assert r.cost_dollars <= 1.0

    def test_the_tighter_of_the_two_headrooms_wins(self, caps, no_fees):
        # total headroom $10, segment headroom $3 -> $3 binds.
        r = size_order(_opp(price=0.10), bankroll=100.0, open_positions=0,
                       daily_pnl=0.0, unit_size=50.0,
                       open_exposure=40.0, segment_exposure=30.0, equity=100.0)
        assert r.risk_approval == "APPROVED_CAPPED_EXPOSURE"
        assert r.cost_dollars <= 3.0

    def test_a_trimmed_order_is_never_zero_contracts(self, caps, no_fees):
        """A cap that can emit an unfillable 0-contract order is worse than a
        cent of overshoot -- same `max(1, ...)` rule as the MAX_BET_SIZE cap."""
        r = size_order(_opp(price=0.99), bankroll=100.0, open_positions=0,
                       daily_pnl=0.0, open_exposure=49.99,
                       segment_exposure=0.0, equity=100.0)
        assert r.contracts >= 1

    def test_an_order_that_fits_is_left_alone(self, caps, no_fees):
        """(It may still be capped by MAX_BET_SIZE -- that is a different cap,
        and this asserts only that the exposure trim kept its hands off.)"""
        r = size_order(_opp(price=0.50), bankroll=100.0, open_positions=0,
                       daily_pnl=0.0, open_exposure=1.0,
                       segment_exposure=1.0, equity=100.0)
        assert r.risk_approval.startswith("APPROVED")
        assert "EXPOSURE" not in r.risk_approval


class TestWiring:
    def test_size_order_rejects_and_names_the_gate(self, caps):
        r = size_order(_opp(), bankroll=100.0, open_positions=0, daily_pnl=0.0,
                       open_exposure=60.0, segment_exposure=0.0, equity=100.0)
        assert r.risk_approval.startswith("REJECTED")
        assert "max_open_exposure" in r.risk_approval
        assert r.contracts == 0

    def test_equity_defaults_to_bankroll_when_not_passed(self, caps):
        """Callers that don't track equity still get a coherent ratio rather
        than a divide-by-nothing."""
        r = size_order(_opp(), bankroll=100.0, open_positions=0, daily_pnl=0.0,
                       open_exposure=60.0, segment_exposure=0.0)
        assert "max_open_exposure" in r.risk_approval

    def test_default_callers_are_unaffected(self, caps):
        """No exposure args -> 0 standing -> the gate cannot fire. Keeps every
        existing call site and test working."""
        r = size_order(_opp(), bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert r.risk_approval.startswith("APPROVED")

    def test_reload_risk_config_picks_up_the_env_values(self, monkeypatch):
        monkeypatch.setenv("MAX_OPEN_EXPOSURE_PCT", "0.25")
        monkeypatch.setenv("MAX_SEGMENT_EXPOSURE_PCT", "0.15")
        monkeypatch.setattr("kalshi_executor.load_dotenv", lambda *a, **k: None)
        ke.reload_risk_config()
        try:
            assert ke.MAX_OPEN_EXPOSURE_PCT == 0.25
            assert ke.MAX_SEGMENT_EXPOSURE_PCT == 0.15
        finally:
            monkeypatch.delenv("MAX_OPEN_EXPOSURE_PCT", raising=False)
            monkeypatch.delenv("MAX_SEGMENT_EXPOSURE_PCT", raising=False)
            ke.reload_risk_config()

    def test_a_percentage_instead_of_a_fraction_is_rejected_at_config(self, monkeypatch):
        """`MAX_OPEN_EXPOSURE_PCT=50` would otherwise read as 5000% -- a cap
        silently switched off, which is the same class of bug as D1's 0.0."""
        from app.config import get_config, reset_config
        monkeypatch.setenv("MAX_OPEN_EXPOSURE_PCT", "50")
        reset_config()
        try:
            with pytest.raises(ValueError, match="MAX_OPEN_EXPOSURE_PCT"):
                get_config()
        finally:
            monkeypatch.delenv("MAX_OPEN_EXPOSURE_PCT", raising=False)
            reset_config()
