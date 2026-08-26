"""Shared fixtures for Edge-Radar tests.

Path setup is handled by [tool.pytest.ini_options] pythonpath in
pyproject.toml.  This file only provides shared fixtures.
"""

import pytest
import trade_log
from opportunity import Opportunity


@pytest.fixture(autouse=True)
def _isolate_data_logs(tmp_path, monkeypatch):
    """Defense-in-depth: never let a test read or write the real trade /
    settlement logs under data/history/.

    ``log_trade()`` persists via ``save_trade_log()`` as a side effect, so a
    test that calls it with an ad-hoc list (e.g. test_fill_accounting) would
    otherwise overwrite the live ``kalshi_trades.json`` with test records.
    Redirecting the module-level path constants to a per-test tmp dir makes
    every test hermetic regardless of how it exercises the I/O helpers.
    """
    monkeypatch.setattr(trade_log, "TRADE_LOG_PATH",
                        tmp_path / "kalshi_trades.json")
    monkeypatch.setattr(trade_log, "SETTLEMENT_LOG_PATH",
                        tmp_path / "kalshi_settlements.json")


@pytest.fixture(autouse=True)
def _ignore_operator_sport_freezes(monkeypatch):
    """Never let the operator's live `.env` switch a sport off underneath a test.

    `MIN_EDGE_THRESHOLD_<SPORT> >= 1.0` is the "this sport is off" idiom (F3),
    and `_PER_SPORT_MIN_EDGE` is populated from the environment at import. So
    freezing a sport in `.env` makes `size_order` reject on `sport_disabled`
    *before* reaching whatever gate a test is actually exercising -- which broke
    four tests the day NFL was frozen (S1, 2026-08-26), none of which were about
    per-sport floors: TestLiquidityGate deliberately uses the real
    `KXNFLTOTAL-26SEP13CLEJAC-20` book from the L2 audit, and test_sport_disable
    uses an NFL ticker as its "other sports are untouched" control.

    Dropping disabled sports here makes the suite hermetic against operator
    config, permanently. A test that *wants* a sport off sets it explicitly
    (see `wc_off` in test_sport_disable.py).
    """
    import kalshi_executor as ke
    live = {k: v for k, v in ke._PER_SPORT_MIN_EDGE.items() if v < 1.0}
    monkeypatch.setattr(ke, "_PER_SPORT_MIN_EDGE", live)


@pytest.fixture
def no_fees(monkeypatch):
    """Zero the exchange fee rate for tests that pin exact pre-fee arithmetic.

    Gate 3 and Kelly sizing became fee-aware on 2026-08-25. Tests written to pin
    the *price-complement* (C11) or *per-sport floor* mechanics are testing
    something orthogonal to fees, so they opt out here rather than re-deriving
    every expected number with a fee term folded in. Tests of the fee behaviour
    itself do not use this fixture.
    """
    from app.config import reset_config
    monkeypatch.setenv("KALSHI_FEE_RATE", "0")
    reset_config()
    yield
    monkeypatch.delenv("KALSHI_FEE_RATE", raising=False)
    reset_config()


@pytest.fixture
def sample_opportunity():
    """A basic approved-worthy Opportunity."""
    return Opportunity(
        ticker="KXMLBGAME-26MAR301840CWSMIA-MIA",
        title="Chicago WS vs Miami Winner? (vs Miami)",
        category="game",
        side="yes",
        market_price=0.45,
        fair_value=0.56,
        edge=0.11,
        edge_source="odds_consensus",
        confidence="high",
        liquidity_score=8.0,
        composite_score=8.5,
        details={"n_books": 8},
    )


@pytest.fixture
def low_edge_opportunity():
    """An Opportunity below typical edge threshold."""
    return Opportunity(
        ticker="KXMLBGAME-26MAR301840PITCIN-PIT",
        title="Pittsburgh vs Cincinnati Winner?",
        category="game",
        side="yes",
        market_price=0.50,
        fair_value=0.51,
        edge=0.01,
        edge_source="odds_consensus",
        confidence="low",
        liquidity_score=5.0,
        composite_score=3.0,
        details={},
    )
