"""F4 (2026-08-25): NO-side Kelly damping at the EXPENSIVE end.

Over 380 settled bets the NO side runs -7.7% ROI against YES's +22.4%, and YES
beats NO *within every shared price band* -- so it is the side, not merely that
NO bets sit at expensive prices. The bleed is concentrated at/above 50c
(n=68, $90 staked, -11.3%), which is precisely where R1's existing rule did
nothing: `NO_SIDE_KELLY_PRICE_FLOOR` damps NO *below* 35c and leaves the
expensive end at full Kelly.

`NO_SIDE_KELLY_PRICE_CEILING` mirrors the floor, reusing the same multiplier.
Damped rather than gated on purpose: that population is +4.8% Mar-May vs -16.0%
Jun-Aug, too uneven to justify a hard reject.
"""

import pytest
from opportunity import Opportunity

import kalshi_executor as ke
from kalshi_executor import size_order


def _opp(side: str, price: float, edge: float = 0.12) -> Opportunity:
    return Opportunity(
        ticker="KXMLBTOTAL-26APR14LAAANYY-9", title="", category="total",
        side=side, market_price=price, fair_value=min(0.99, price + edge),
        edge=edge, edge_source="test", confidence="high",
        liquidity_score=9.0, composite_score=9.9,
        details={"bid_ask_spread": 0.01},
    )


def _size(side: str, price: float, **kw) -> int:
    return size_order(_opp(side, price), bankroll=92.0, open_positions=0,
                      daily_pnl=0.0, batch_size=5, **kw).contracts


@pytest.fixture
def ceiling_at_50(monkeypatch):
    monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_CEILING", 0.50)
    monkeypatch.setattr(ke, "NO_SIDE_KELLY_MULTIPLIER", 0.5)
    monkeypatch.setattr(ke, "NO_SIDE_KELLY_MULTIPLIER_GLOBAL", 1.0)
    monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_FLOOR", 0.35)
    monkeypatch.setattr(ke, "NO_SIDE_FAVORITE_THRESHOLD", 0.10)  # not under test
    monkeypatch.setattr(ke, "MIN_COMPOSITE_SCORE", 0.0)


@pytest.fixture
def ceiling_off(monkeypatch):
    monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_CEILING", 0.0)
    monkeypatch.setattr(ke, "NO_SIDE_KELLY_MULTIPLIER", 0.5)
    monkeypatch.setattr(ke, "NO_SIDE_KELLY_MULTIPLIER_GLOBAL", 1.0)
    monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_FLOOR", 0.35)
    monkeypatch.setattr(ke, "NO_SIDE_FAVORITE_THRESHOLD", 0.10)
    monkeypatch.setattr(ke, "MIN_COMPOSITE_SCORE", 0.0)


class TestExpensiveNoIsDamped:
    @pytest.mark.parametrize("price", [0.50, 0.60, 0.75, 0.85])
    def test_damped_relative_to_the_same_price_on_yes(self, price, ceiling_at_50):
        assert _size("no", price) < _size("yes", price)

    @pytest.mark.parametrize("price", [0.60, 0.75, 0.85])
    def test_damped_relative_to_the_ceiling_being_off(self, price, ceiling_at_50,
                                                      monkeypatch):
        damped = _size("no", price)
        monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_CEILING", 0.0)
        assert damped < _size("no", price)

    def test_boundary_is_inclusive(self, ceiling_at_50, monkeypatch):
        """At exactly the ceiling price the damping applies."""
        at = _size("no", 0.50)
        monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_CEILING", 0.0)
        assert at < _size("no", 0.50)


class TestProfitablePocketIsUntouched:
    @pytest.mark.parametrize("price", [0.35, 0.40, 0.45, 0.49])
    def test_no_between_floor_and_ceiling_sizes_like_yes(self, price, ceiling_at_50):
        # NO at 30-50c is the one profitable NO pocket (+5.3% ROI, n=55).
        # Neither R1's floor nor F4's ceiling should touch it.
        assert _size("no", price) == _size("yes", price)


class TestDefaultIsOff:
    @pytest.mark.parametrize("price", [0.50, 0.75, 0.85])
    def test_ceiling_zero_changes_nothing(self, price, ceiling_off):
        assert _size("no", price) == _size("yes", price)

    def test_shipped_code_default_is_zero(self):
        from app.config import KellyConfig
        assert KellyConfig().no_side_kelly_price_ceiling == 0.0


class TestInteractionWithTheExistingFloorRule:
    def test_cheap_no_still_uses_the_r1_floor_rule(self, ceiling_at_50):
        # R1's floor and F4's ceiling are mutually exclusive by construction
        # (floor 0.35 < ceiling 0.50), so a cheap NO bet takes the floor branch.
        assert _size("no", 0.20) < _size("yes", 0.20)

    def test_multiplier_is_not_applied_twice(self, ceiling_at_50, monkeypatch):
        """A price can be below the floor OR above the ceiling, never both."""
        monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_FLOOR", 0.35)
        monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_CEILING", 0.50)
        cheap = _size("no", 0.20)
        monkeypatch.setattr(ke, "NO_SIDE_KELLY_MULTIPLIER", 0.25)
        assert _size("no", 0.20) <= cheap  # one application, monotone in mult

    def test_yes_side_is_never_damped(self, ceiling_at_50, monkeypatch):
        baseline = _size("yes", 0.85)
        monkeypatch.setattr(ke, "NO_SIDE_KELLY_PRICE_CEILING", 0.01)
        assert _size("yes", 0.85) == baseline


class TestReloadPicksItUp:
    def test_config_layer_reads_the_env_var(self, monkeypatch):
        from app.config import KellyConfig
        monkeypatch.setenv("NO_SIDE_KELLY_PRICE_CEILING", "0.42")
        assert KellyConfig.from_env().no_side_kelly_price_ceiling == 0.42

    def test_reload_risk_config_refreshes_the_ceiling(self, monkeypatch):
        """The module snapshots globals at import; a long-running host picks up
        a changed value via reload_risk_config().

        `load_dotenv` is stubbed out here because reload_risk_config calls it
        with `override=True` -- which is correct behaviour (re-read .env from
        disk) but would clobber the monkeypatched var straight back to whatever
        the developer's own .env says, making the test non-hermetic.
        """
        from app.config import reset_config
        # reload_risk_config rebinds a module global, so restore it explicitly --
        # monkeypatch cannot undo an assignment made inside the call.
        saved = ke.NO_SIDE_KELLY_PRICE_CEILING
        monkeypatch.setattr(ke, "load_dotenv", lambda *a, **k: None)
        monkeypatch.setenv("NO_SIDE_KELLY_PRICE_CEILING", "0.42")
        reset_config()
        ke.reload_risk_config()
        try:
            assert ke.NO_SIDE_KELLY_PRICE_CEILING == 0.42
        finally:
            ke.NO_SIDE_KELLY_PRICE_CEILING = saved
            monkeypatch.delenv("NO_SIDE_KELLY_PRICE_CEILING", raising=False)
            reset_config()
