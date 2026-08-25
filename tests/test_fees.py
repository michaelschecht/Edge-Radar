"""Fee awareness (2026-08-25).

Until this change fees were invisible end to end: nothing subtracted one before
a bet, and `log_trade` read `taker_fees_dollars` from a v2 create-order response
that doesn't carry it -- so every trade recorded a fee of 0 and `calculate_pnl`
computed `net_pnl = revenue - cost - 0`. Measured over the 119 settled trades in
the log at that date: $5.14 of unrecorded fees on $140.97 of stake (3.6%), which
is 1.02c per contract against a 3.0-4.0c minimum-edge floor.
"""

import math

import pytest
from opportunity import Opportunity

import fees
from app.config import reset_config
from kalshi_executor import min_edge_for, size_order


def _opp(price=0.50, edge=0.10, side="yes",
         ticker="KXMLBGAME-99APR171900NYYKAC-NYY") -> Opportunity:
    return Opportunity(
        ticker=ticker, title="Test", category="game", side=side,
        market_price=price, fair_value=price + edge, edge=edge,
        edge_source="test", confidence="high",
        liquidity_score=8.0, composite_score=9.0, details={},
    )


@pytest.fixture
def fee_rate_7pct(monkeypatch):
    monkeypatch.setenv("KALSHI_FEE_RATE", "0.07")
    reset_config()
    yield
    monkeypatch.delenv("KALSHI_FEE_RATE", raising=False)
    reset_config()


class TestFeeModel:
    def test_matches_kalshi_published_formula(self, fee_rate_7pct):
        # fee = roundup(rate * C * P * (1-P)), rounded UP to the next cent.
        for contracts, price in [(7, 0.14), (1, 0.50), (100, 0.30), (3, 0.85)]:
            expected = math.ceil(0.07 * contracts * price * (1 - price) * 100) / 100
            assert fees.taker_fee(contracts, price) == expected

    def test_the_review_trade(self, fee_rate_7pct):
        # KXMLSSPREAD-26AUG19TORCLT-CLT2: 7 contracts @ 14c, claimed edge +4.67%.
        # 0.07 * 7 * 0.14 * 0.86 = $0.0590 -> $0.06, i.e. 6.1% of the $0.98 stake.
        assert fees.taker_fee(7, 0.14) == 0.06

    def test_roundup_is_per_order_not_per_contract(self, fee_rate_7pct):
        # A 1-contract order pays a full cent more than the linear term: this is
        # why small stakes are penalised disproportionately at this bankroll.
        assert fees.taker_fee(1, 0.50) == 0.02          # 0.0175 rounds up
        assert fees.fee_per_contract(0.50) < 0.02

    def test_peaks_at_fifty_cents_and_is_symmetric(self, fee_rate_7pct):
        assert fees.fee_per_contract(0.50) > fees.fee_per_contract(0.25)
        assert fees.fee_per_contract(0.25) == pytest.approx(fees.fee_per_contract(0.75))

    @pytest.mark.parametrize("price", [0.0, 1.0, -0.1, 1.5])
    def test_degenerate_prices_cost_nothing(self, price, fee_rate_7pct):
        assert fees.taker_fee(10, price) == 0.0
        assert fees.fee_per_contract(price) == 0.0

    def test_rate_zero_disables(self, monkeypatch):
        monkeypatch.setenv("KALSHI_FEE_RATE", "0")
        reset_config()
        try:
            assert fees.taker_fee(10, 0.5) == 0.0
            assert fees.fee_per_contract(0.5) == 0.0
        finally:
            monkeypatch.delenv("KALSHI_FEE_RATE", raising=False)
            reset_config()


class TestGateThreeIsFeeAware:
    def test_floor_includes_the_fee(self, fee_rate_7pct):
        import kalshi_executor as ke
        orig = dict(ke._PER_SPORT_MIN_EDGE)
        try:
            ke._PER_SPORT_MIN_EDGE.clear()
            opp = _opp(price=0.50)
            assert min_edge_for(opp) == pytest.approx(
                ke.MIN_EDGE_THRESHOLD + 0.07 * 0.5 * 0.5
            )
        finally:
            ke._PER_SPORT_MIN_EDGE.clear()
            ke._PER_SPORT_MIN_EDGE.update(orig)

    def test_floor_is_price_dependent(self, fee_rate_7pct):
        # The fee peaks at mid-price, so the floor must too -- a flat haircut
        # would over-penalise longshots and under-penalise 50c bets.
        assert min_edge_for(_opp(price=0.50)) > min_edge_for(_opp(price=0.10))

    def test_bet_clearing_gross_but_not_net_is_rejected(self, fee_rate_7pct):
        import kalshi_executor as ke
        orig = dict(ke._PER_SPORT_MIN_EDGE)
        try:
            ke._PER_SPORT_MIN_EDGE.clear()
            # 3.5% edge at 50c: clears a 3% gross floor, fails the 4.75% net one.
            opp = _opp(price=0.50, edge=0.035)
            result = size_order(opp, bankroll=1000.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval.startswith("REJECTED")
            assert "edge_below_threshold" in result.risk_approval
            assert "fee" in result.risk_approval
        finally:
            ke._PER_SPORT_MIN_EDGE.clear()
            ke._PER_SPORT_MIN_EDGE.update(orig)

    def test_preflight_agrees_with_the_gate(self, fee_rate_7pct):
        # R18's scan preview must not promise "ok" on a row the executor rejects.
        import kalshi_executor as ke
        orig = dict(ke._PER_SPORT_MIN_EDGE)
        try:
            ke._PER_SPORT_MIN_EDGE.clear()
            opp = _opp(price=0.50, edge=0.035)
            assert ke.preflight_gate_status(opp) == "edge"
        finally:
            ke._PER_SPORT_MIN_EDGE.clear()
            ke._PER_SPORT_MIN_EDGE.update(orig)


class TestKellySizesOffNetEdge:
    def test_fee_reduces_contract_count(self, monkeypatch):
        import kalshi_executor as ke
        monkeypatch.setattr(ke, "KELLY_FRACTION", 0.50)
        monkeypatch.setattr(ke, "MAX_BET_SIZE", 100000.0)
        monkeypatch.setattr(ke, "MIN_COMPOSITE_SCORE", 0.0)
        opp = _opp(price=0.50, edge=0.10)

        monkeypatch.setenv("KALSHI_FEE_RATE", "0")
        reset_config()
        free = size_order(opp, bankroll=100000.0, open_positions=0, daily_pnl=0.0)

        monkeypatch.setenv("KALSHI_FEE_RATE", "0.07")
        reset_config()
        charged = size_order(opp, bankroll=100000.0, open_positions=0, daily_pnl=0.0)

        monkeypatch.delenv("KALSHI_FEE_RATE", raising=False)
        reset_config()

        # Net edge is 0.10 - 0.0175 = 0.0825, so sizing drops by that ratio.
        assert charged.contracts < free.contracts
        assert charged.contracts == pytest.approx(free.contracts * 0.825, rel=0.02)


class TestSettlerFeeBackfill:
    def test_recorded_fee_wins_over_the_model(self):
        trade = {"taker_fees": "0.09", "maker_fees": "0",
                 "filled_contracts": 7, "market_price_at_entry": 0.14}
        import kalshi_settler
        assert kalshi_settler.trade_fees(trade) == 0.09

    def test_falls_back_to_the_model_not_to_zero(self, fee_rate_7pct):
        # This is the whole point: a missing fee field used to mean "free".
        trade = {"taker_fees": "0", "maker_fees": "0",
                 "filled_contracts": 7, "market_price_at_entry": 0.14}
        import kalshi_settler
        assert kalshi_settler.trade_fees(trade) == 0.06

    def test_pnl_subtracts_the_modelled_fee(self, fee_rate_7pct):
        import kalshi_settler
        trade = {"side": "yes", "taker_fees": "0", "maker_fees": "0",
                 "filled_contracts": 7, "filled_cost": 0.98,
                 "market_price_at_entry": 0.14}
        pnl = kalshi_settler.calculate_pnl(trade, {"market_result": "no"})
        assert pnl["fees"] == 0.06
        assert pnl["net_pnl"] == pytest.approx(-1.04)  # -0.98 stake - 0.06 fee

    def test_fetch_fill_fees_sums_partial_fills_per_order(self):
        import kalshi_settler

        class _Client:
            def get_fills(self, limit=200, cursor=None):
                return {"fills": [
                    {"order_id": "a", "fee_dollars": "0.02"},
                    {"order_id": "a", "fee_dollars": "0.03"},
                    {"order_id": "b", "fee_dollars": "0.07"},
                    {"order_id": None, "fee_dollars": "0.99"},  # ignored
                ], "cursor": ""}

        assert kalshi_settler.fetch_fill_fees(_Client()) == {"a": 0.05, "b": 0.07}

    def test_fetch_fill_fees_returns_empty_on_api_failure(self):
        import kalshi_settler

        class _Broken:
            def get_fills(self, limit=200, cursor=None):
                raise RuntimeError("boom")

        assert kalshi_settler.fetch_fill_fees(_Broken()) == {}
