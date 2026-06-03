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
