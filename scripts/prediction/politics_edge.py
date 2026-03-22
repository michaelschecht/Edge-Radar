"""
politics_edge.py
Edge detection for Kalshi political event markets.

Covers:
- KXIMPEACH: "Will the President be impeached before date X?"
- KXQUANTUM: "When will useful quantum computing be developed?"
- KXFUSION: "When will nuclear fusion be achieved?"

These are long-dated event markets with no clean external data source.
Edge approach: time-decay model based on the assumption that events
with no strong catalysts have a roughly constant hazard rate per unit time.

The model uses historical base rates for similar event types and
adjusts for time remaining until the strike date.
"""

import re
import math
import logging
from datetime import datetime, timezone

from scipy.stats import norm

log = logging.getLogger("politics_edge")

# ── Event Base Rates ─────────────────────────────────────────────────────────

# Annual probability estimates for rare political/tech events
# Based on prediction market consensus and historical data
EVENT_BASE_RATES = {
    "KXIMPEACH": {
        "annual_prob": 0.12,  # ~12% annual chance of impeachment proceedings
        "description": "Presidential impeachment",
    },
    "KXQUANTUM": {
        "annual_prob": 0.05,  # ~5% chance per year of "useful" quantum computer
        "description": "Useful quantum computing",
    },
    "KXFUSION": {
        "annual_prob": 0.03,  # ~3% chance per year of commercial fusion
        "description": "Commercial nuclear fusion",
    },
}


# ── Time-Decay Model ────────────────────────────────────────────────────────

def event_probability_by_date(annual_prob: float, years_until_deadline: float) -> float:
    """
    P(event occurs before deadline) given a constant annual hazard rate.

    Uses exponential survival model:
        P(event by time T) = 1 - exp(-lambda * T)
    where lambda = -ln(1 - annual_prob)
    """
    if annual_prob <= 0:
        return 0.0
    if annual_prob >= 1:
        return 1.0
    if years_until_deadline <= 0:
        return 0.0

    hazard_rate = -math.log(1 - annual_prob)
    return 1.0 - math.exp(-hazard_rate * years_until_deadline)


# ── Ticker Parsing ───────────────────────────────────────────────────────────

def parse_deadline(market: dict) -> datetime | None:
    """Parse the deadline/expiration from a political event market."""
    exp_str = market.get("expected_expiration_time") or market.get("close_time")
    if not exp_str:
        return None
    try:
        return datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def get_event_type(ticker: str) -> str | None:
    """Map ticker to event type."""
    for prefix in EVENT_BASE_RATES:
        if ticker.startswith(prefix):
            return prefix
    return None


# ── Edge Detection ───────────────────────────────────────────────────────────

def detect_edge_political_event(market: dict) -> dict | None:
    """
    Detect edge on long-dated political/tech event markets
    using time-decay probability model.
    """
    ticker = market.get("ticker", "")
    event_type = get_event_type(ticker)
    if not event_type:
        return None

    base_rate = EVENT_BASE_RATES[event_type]
    annual_prob = base_rate["annual_prob"]

    yes_ask = float(market.get("yes_ask_dollars") or 0)
    no_ask = float(market.get("no_ask_dollars") or 0)
    yes_bid = float(market.get("yes_bid_dollars") or 0)

    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    # Parse deadline
    deadline = parse_deadline(market)
    if not deadline:
        return None

    now = datetime.now(timezone.utc)
    years_until = max(0.01, (deadline - now).total_seconds() / (365.25 * 86400))

    # Calculate fair probability
    fair_yes = event_probability_by_date(annual_prob, years_until)
    fair_no = 1.0 - fair_yes

    # Pick better side
    yes_edge = fair_yes - yes_ask
    no_edge = (fair_no - no_ask) if 0 < no_ask < 1.0 else -1

    if yes_edge >= no_edge:
        side, fair_value, market_price, edge = "yes", fair_yes, yes_ask, yes_edge
    else:
        side, fair_value, market_price, edge = "no", fair_no, no_ask, no_edge

    if edge <= 0:
        return None

    # Confidence is always low for these speculative models
    confidence = "low"

    spread = yes_ask - yes_bid if yes_bid > 0 else 1.0
    liquidity = max(0, 10 - spread * 20)
    edge_score = min(10, edge * 20)
    conf_score = 3
    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * 5

    return {
        "ticker": ticker,
        "title": market.get("title", ""),
        "category": "politics",
        "side": side,
        "market_price": market_price,
        "fair_value": round(fair_value, 4),
        "edge": round(edge, 4),
        "edge_source": f"time_decay_{event_type.lower()}",
        "confidence": confidence,
        "liquidity_score": round(liquidity, 1),
        "composite_score": round(composite, 1),
        "details": {
            "event_type": base_rate["description"],
            "annual_prob": annual_prob,
            "years_until_deadline": round(years_until, 2),
            "deadline": deadline.isoformat(),
        },
    }
