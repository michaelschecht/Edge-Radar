"""
opportunity.py
Single source of truth for the Opportunity dataclass.

Used by both sports (kalshi/edge_detector.py) and prediction
(prediction/prediction_scanner.py) edge detection pipelines.
"""

from dataclasses import dataclass


@dataclass
class Opportunity:
    """A scored betting/trading opportunity on Kalshi."""
    ticker: str
    title: str
    category: str           # game, spread, total, player_prop, crypto, weather, spx, etc.
    side: str               # "yes" or "no"
    market_price: float     # current ask we'd pay
    fair_value: float       # our estimated probability
    edge: float             # fair_value - market_price (for the chosen side)
    edge_source: str        # how we estimated fair value
    confidence: str         # low / medium / high
    liquidity_score: float  # 0-10 based on spread + volume
    composite_score: float  # weighted overall score
    details: dict           # extra context (matched odds, vol, forecast, etc.)
