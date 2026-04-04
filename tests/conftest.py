"""Shared fixtures for Edge-Radar tests.

Adds script directories to sys.path so tests work with any Python
interpreter, not just the project venv (which has an edge_radar.pth
file that does this automatically via site-packages).
"""

import sys
from pathlib import Path

# Add the same directories that edge_radar.pth adds in the project venv.
_project_root = Path(__file__).resolve().parent.parent
for _subdir in [
    "scripts/shared",
    "scripts/kalshi",
    "scripts/prediction",
    "scripts/polymarket",
    "scripts/schedulers",
    "scripts",
]:
    _path = str(_project_root / _subdir)
    if _path not in sys.path:
        sys.path.insert(0, _path)


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
