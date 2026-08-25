"""F3 (2026-08-25): switching a sport off via an unreachable edge floor.

The calibration study found World Cup at -43.2% ROI over 43 settled bets, with
the model 9 points above a market price that was near-exact. Turning it off
revealed a second bug: `_SUPPORTED_SPORTS` in `app/config.py` listed only eight
sports, so `MIN_EDGE_THRESHOLD_WORLDCUP` (and seven other sports') was read by
nothing at all -- the override silently did nothing.

Edge is bounded by 1, so a floor >= 1.0 can never be cleared. That is the idiom
for "this sport is off" -- no separate kill switch, no new gate number.
"""

import pytest
from opportunity import Opportunity

from app.config import PerSportOverrides, _SUPPORTED_SPORTS
from kalshi_executor import min_edge_for, preflight_gate_status, size_order
from ticker_display import _detect_sport, _SPORT_PREFIXES


def _opp(ticker: str, price: float = 0.16, edge: float = 0.30) -> Opportunity:
    return Opportunity(
        ticker=ticker, title="", category="spread", side="yes",
        market_price=price, fair_value=price + edge, edge=edge,
        edge_source="test", confidence="high", liquidity_score=9.0,
        composite_score=9.9, details={"bid_ask_spread": 0.01},
    )


class TestEverySportCanBeOverridden:
    def test_no_detectable_sport_is_orphaned(self):
        """Every sport `_detect_sport` can return must be overridable.

        This is the actual bug: a name reachable from a ticker but missing from
        `_SUPPORTED_SPORTS` gets an env var that is never read -- a silent no-op
        rather than an error.
        """
        detectable = set(_SPORT_PREFIXES.values())
        missing = detectable - set(_SUPPORTED_SPORTS)
        assert not missing, f"orphaned sports (env override silently ignored): {missing}"

    def test_worldcup_specifically(self):
        assert _detect_sport("KXWCSPREAD-26JUN10ARGBRA-ARG2") == "worldcup"
        assert "worldcup" in _SUPPORTED_SPORTS

    def test_override_is_read_for_a_previously_orphaned_sport(self, monkeypatch):
        monkeypatch.setenv("MIN_EDGE_THRESHOLD_WORLDCUP", "1.0")
        assert PerSportOverrides.from_env().min_edge.get("worldcup") == 1.0


class TestUnreachableFloorDisablesTheSport:
    @pytest.fixture
    def wc_off(self, monkeypatch):
        import kalshi_executor as ke
        patched = dict(ke._PER_SPORT_MIN_EDGE)
        patched["worldcup"] = 1.0
        monkeypatch.setattr(ke, "_PER_SPORT_MIN_EDGE", patched)

    @pytest.mark.parametrize("ticker", [
        "KXWCSPREAD-26JUN10ARGBRA-ARG2",
        "KXWCGAME-26JUN10ARGBRA-ARG",
        "KXWCTOTAL-26JUN10ARGBRA-3",
    ])
    def test_every_wc_market_type_is_rejected(self, ticker, wc_off):
        result = size_order(_opp(ticker), bankroll=92.0, open_positions=0, daily_pnl=0.0)
        assert result.risk_approval.startswith("REJECTED")
        assert "sport_disabled" in result.risk_approval
        assert result.contracts == 0

    def test_rejection_names_the_sport_not_a_bogus_edge_comparison(self, wc_off):
        r = size_order(_opp("KXWCSPREAD-26JUN10ARGBRA-ARG2"),
                       bankroll=92.0, open_positions=0, daily_pnl=0.0)
        assert "worldcup" in r.risk_approval
        assert "edge_below_threshold" not in r.risk_approval

    def test_no_fee_is_added_to_the_disable_sentinel(self, wc_off):
        # Otherwise the message reads a confusing "101%".
        assert min_edge_for(_opp("KXWCSPREAD-26JUN10ARGBRA-ARG2")) == 1.0

    def test_preflight_agrees_and_says_off(self, wc_off):
        assert preflight_gate_status(_opp("KXWCSPREAD-26JUN10ARGBRA-ARG2")) == "off"

    def test_even_an_enormous_edge_cannot_clear_it(self, wc_off):
        r = size_order(_opp("KXWCGAME-26JUN10ARGBRA-ARG", price=0.05, edge=0.94),
                       bankroll=92.0, open_positions=0, daily_pnl=0.0)
        assert "sport_disabled" in r.risk_approval

    @pytest.mark.parametrize("ticker", [
        "KXMLSSPREAD-26AUG19TORCLT-CLT2",
        "KXNFLSPREAD-26SEP13BALIND-IND5",
        "KXMLBGAME-99APR171900NYYKAC-NYY",
    ])
    def test_other_sports_are_untouched(self, ticker, wc_off):
        r = size_order(_opp(ticker), bankroll=92.0, open_positions=0, daily_pnl=0.0)
        assert r.risk_approval.startswith("APPROVED"), r.risk_approval
        assert min_edge_for(_opp(ticker)) < 1.0
