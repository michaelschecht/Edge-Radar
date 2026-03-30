"""Shared fixtures for Edge-Radar tests."""

import pytest
from opportunity import Opportunity


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
