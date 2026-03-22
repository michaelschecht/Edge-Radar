"""
mentions_edge.py
Edge detection for Kalshi TV mention markets.

Covers:
- KXLASTWORDCOUNT: "How many times will X say Y?" (numeric strike)
- KXPOLITICSMENTION: "Will speaker say word on show?" (binary yes/no)
- KXFOXNEWSMENTION: Same as above, Fox News broadcasts
- KXNBAMENTION: "Will announcer say word during game?"

Edge approach:
- LASTWORDCOUNT: Build historical average from settled markets, model as
  Poisson distribution, compare P(count >= strike) to market price.
- Binary mention markets: Use historical settlement rate (% of similar
  words that settle YES) as fair value estimate.
"""

import re
import math
import logging
from datetime import datetime, timezone

from probability import weather_probability  # reuse normal CDF for count distribution

log = logging.getLogger("mentions_edge")

# ── Ticker Classification ────────────────────────────────────────────────────

MENTION_PREFIXES = {
    "KXLASTWORDCOUNT": "lastword",
    "KXPOLITICSMENTION": "politics",
    "KXFOXNEWSMENTION": "foxnews",
    "KXNBAMENTION": "nbamention",
}

# ── Historical Data ──────────────────────────────────────────────────────────

_historical_cache: dict[str, list[int]] = {}


def fetch_historical_counts(client, series_ticker: str, max_pages: int = 5) -> list[int]:
    """
    Fetch settlement values from settled markets to build a historical baseline.
    Returns list of actual count values from past episodes.
    """
    cache_key = series_ticker
    if cache_key in _historical_cache:
        return _historical_cache[cache_key]

    counts = []
    events_seen = {}
    cursor = None

    for _ in range(max_pages):
        resp = client.get_markets(
            limit=200, status="settled", series_ticker=series_ticker, cursor=cursor
        )
        for m in resp.get("markets", []):
            event = m.get("event_ticker", "")
            val = m.get("expiration_value", "")
            if event and val and event not in events_seen:
                try:
                    events_seen[event] = int(val)
                except ValueError:
                    pass
        cursor = resp.get("cursor", "")
        if not cursor:
            break

    counts = list(events_seen.values())
    _historical_cache[cache_key] = counts
    log.info("Historical %s: %d episodes, counts=%s", series_ticker, len(counts),
             counts[:10] if len(counts) > 10 else counts)
    return counts


def fetch_historical_mention_rate(client, series_ticker: str, max_pages: int = 5) -> float | None:
    """
    For binary mention markets (POLITICSMENTION, FOXNEWSMENTION, NBAMENTION),
    calculate the historical YES settlement rate across all words/markets.
    Returns rate between 0 and 1, or None if insufficient data.
    """
    cache_key = f"{series_ticker}_rate"
    if cache_key in _historical_cache:
        stored = _historical_cache[cache_key]
        return stored[0] / stored[1] if stored[1] > 0 else None

    yes_count = 0
    total_count = 0
    cursor = None

    for _ in range(max_pages):
        resp = client.get_markets(
            limit=200, status="settled", series_ticker=series_ticker, cursor=cursor
        )
        for m in resp.get("markets", []):
            result = m.get("result", "")
            if result in ("yes", "no"):
                total_count += 1
                if result == "yes":
                    yes_count += 1
        cursor = resp.get("cursor", "")
        if not cursor:
            break

    _historical_cache[cache_key] = [yes_count, total_count]
    if total_count < 10:
        log.info("Historical %s: only %d settled, insufficient data", series_ticker, total_count)
        return None

    rate = yes_count / total_count
    log.info("Historical %s: %d/%d YES (%.1f%%)", series_ticker, yes_count, total_count, rate * 100)
    return rate


# ── Poisson Probability ──────────────────────────────────────────────────────

def poisson_above(mean: float, strike: int) -> float:
    """P(X >= strike) where X ~ Poisson(mean). Uses normal approximation for large mean."""
    if mean <= 0:
        return 0.0
    if strike <= 0:
        return 1.0

    # For mean > 10, normal approximation is good
    if mean > 10:
        std = math.sqrt(mean)
        z = (strike - 0.5 - mean) / std  # continuity correction
        from scipy.stats import norm
        return float(1.0 - norm.cdf(z))

    # Exact Poisson CDF for small means
    cdf = 0.0
    for k in range(strike):
        cdf += math.exp(-mean + k * math.log(mean) - math.lgamma(k + 1))
    return max(0.0, 1.0 - cdf)


# ── Edge Detection ───────────────────────────────────────────────────────────

def get_mention_type(ticker: str) -> str | None:
    """Classify a mention market ticker."""
    for prefix, mtype in MENTION_PREFIXES.items():
        if ticker.startswith(prefix):
            return mtype
    return None


def detect_edge_lastword(market: dict, historical_counts: list[int]) -> dict | None:
    """
    Detect edge on KXLASTWORDCOUNT markets using historical count distribution.
    """
    ticker = market.get("ticker", "")
    strike = market.get("floor_strike")
    if strike is None:
        return None
    strike = int(float(strike))

    yes_ask = float(market.get("yes_ask_dollars") or 0)
    no_ask = float(market.get("no_ask_dollars") or 0)
    yes_bid = float(market.get("yes_bid_dollars") or 0)

    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    if not historical_counts:
        return None

    # Calculate historical mean and use Poisson model
    mean_count = sum(historical_counts) / len(historical_counts)
    fair_above = poisson_above(mean_count, strike)
    fair_below = 1.0 - fair_above

    # Determine direction from strike_type
    strike_type = market.get("strike_type", "greater_or_equal")
    if "less" in str(strike_type):
        fair_yes = fair_below
        fair_no = fair_above
    else:
        fair_yes = fair_above
        fair_no = fair_below

    # Pick better side
    yes_edge = fair_yes - yes_ask
    no_edge = (fair_no - no_ask) if 0 < no_ask < 1.0 else -1

    if yes_edge >= no_edge:
        side, fair_value, market_price, edge = "yes", fair_yes, yes_ask, yes_edge
    else:
        side, fair_value, market_price, edge = "no", fair_no, no_ask, no_edge

    if edge <= 0:
        return None

    # Confidence based on sample size
    n = len(historical_counts)
    confidence = "high" if n >= 20 else "medium" if n >= 5 else "low"

    spread = yes_ask - yes_bid if yes_bid > 0 else 1.0
    liquidity = max(0, 10 - spread * 20)
    edge_score = min(10, edge * 20)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * 5

    return {
        "ticker": ticker,
        "title": market.get("title", ""),
        "category": "mentions",
        "side": side,
        "market_price": market_price,
        "fair_value": round(fair_value, 4),
        "edge": round(edge, 4),
        "edge_source": "historical_count_poisson",
        "confidence": confidence,
        "liquidity_score": round(liquidity, 1),
        "composite_score": round(composite, 1),
        "details": {
            "strike": strike,
            "historical_mean": round(mean_count, 1),
            "historical_n": n,
            "historical_counts": historical_counts[-10:],
        },
    }


def detect_edge_binary_mention(market: dict, historical_yes_rate: float) -> dict | None:
    """
    Detect edge on binary mention markets (will speaker say word X?).
    Uses overall historical YES rate as a baseline fair value.
    """
    ticker = market.get("ticker", "")

    yes_ask = float(market.get("yes_ask_dollars") or 0)
    no_ask = float(market.get("no_ask_dollars") or 0)
    yes_bid = float(market.get("yes_bid_dollars") or 0)

    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    # Use historical rate as fair value for YES
    fair_yes = historical_yes_rate
    fair_no = 1.0 - fair_yes

    # Adjust for common vs rare words based on the word itself
    word = market.get("custom_strike", {}).get("Word", "")
    subtitle = market.get("yes_sub_title", "") or market.get("subtitle", "")
    display_word = word or subtitle

    # Common political words are almost always said -- boost fair value
    common_words = {"trump", "republican", "democrat", "congress", "president", "america"}
    if display_word.lower() in common_words:
        fair_yes = min(0.98, fair_yes * 1.3)
        fair_no = 1.0 - fair_yes

    yes_edge = fair_yes - yes_ask
    no_edge = (fair_no - no_ask) if 0 < no_ask < 1.0 else -1

    if yes_edge >= no_edge:
        side, fair_value, market_price, edge = "yes", fair_yes, yes_ask, yes_edge
    else:
        side, fair_value, market_price, edge = "no", fair_no, no_ask, no_edge

    if edge <= 0:
        return None

    confidence = "medium"  # historical rate is a rough baseline
    spread = yes_ask - yes_bid if yes_bid > 0 else 1.0
    liquidity = max(0, 10 - spread * 20)
    edge_score = min(10, edge * 20)
    conf_score = 6
    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * 5

    return {
        "ticker": ticker,
        "title": market.get("title", ""),
        "category": "mentions",
        "side": side,
        "market_price": market_price,
        "fair_value": round(fair_value, 4),
        "edge": round(edge, 4),
        "edge_source": f"historical_mention_rate",
        "confidence": confidence,
        "liquidity_score": round(liquidity, 1),
        "composite_score": round(composite, 1),
        "details": {
            "word": display_word,
            "historical_yes_rate": round(historical_yes_rate, 3),
        },
    }
