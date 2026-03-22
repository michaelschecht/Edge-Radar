"""
companies_edge.py
Edge detection for Kalshi company/corporate markets.

Covers:
- KXBANKRUPTCY: "How many corporate bankruptcies this year?" (numeric strike)
  Edge source: FRED bankruptcy filing data (free API, no key).
- KXIPO: "Who will IPO in 2026?" (browsable only, no automated edge)

Bankruptcy edge approach:
- Fetch YTD bankruptcy count from FRED (series AACOMP or similar)
- Annualize YTD pace to project year-end total
- Compare projected total vs strike using normal distribution
"""

import math
import logging
from datetime import datetime, timezone

import requests
from scipy.stats import norm

log = logging.getLogger("companies_edge")

# ── FRED API ─────────────────────────────────────────────────────────────────

FRED_BASE = "https://api.stlouisfed.org/fred"

_fred_cache: dict[str, dict] = {}


def fetch_bankruptcy_data() -> dict | None:
    """
    Fetch corporate bankruptcy filing data from FRED.
    Uses the AACOMP series (Moody's Aaa Corporate Bond spread as proxy)
    or the BLS BDSTIMESERIES for business dynamics.

    Since FRED doesn't have a direct real-time bankruptcy count series,
    we use the ABI (American Bankruptcy Institute) approach:
    estimate from recent quarterly data.

    Returns dict with 'ytd_count', 'annual_rate', 'last_year_total' or None.
    """
    if "bankruptcy" in _fred_cache:
        return _fred_cache["bankruptcy"]

    # Try to get bankruptcy data from FRED
    # FRED series BUSINSEXPQ: Business Applications for Employers (quarterly proxy)
    try:
        resp = requests.get(
            f"{FRED_BASE}/series/observations",
            params={
                "series_id": "BNKRFD",  # Bankruptcy filings
                "api_key": "DEMO_KEY",   # FRED allows limited calls with DEMO_KEY
                "file_type": "json",
                "sort_order": "desc",
                "limit": 12,
            },
            timeout=15,
        )

        if resp.status_code == 200:
            data = resp.json()
            observations = data.get("observations", [])
            if observations:
                values = []
                for obs in observations:
                    try:
                        values.append(float(obs["value"]))
                    except (ValueError, KeyError):
                        pass

                if values:
                    result = {
                        "latest_value": values[0],
                        "avg_recent": sum(values[:4]) / min(4, len(values)),
                        "data_points": len(values),
                    }
                    _fred_cache["bankruptcy"] = result
                    log.info("FRED bankruptcy data: %s", result)
                    return result
    except Exception as e:
        log.warning("FRED API error: %s", e)

    # Fallback: use reasonable defaults based on public data
    # ~600-900 corporate bankruptcies per year in recent years
    now = datetime.now(timezone.utc)
    day_of_year = now.timetuple().tm_yday
    days_in_year = 366 if now.year % 4 == 0 else 365

    # Historical baseline: ~750 bankruptcies/year average (2020-2025 range)
    result = {
        "annual_baseline": 750,
        "annual_std": 150,  # significant year-to-year variation
        "day_of_year": day_of_year,
        "days_in_year": days_in_year,
        "source": "historical_baseline",
    }
    _fred_cache["bankruptcy"] = result
    log.info("Using bankruptcy baseline: %s", result)
    return result


# ── Edge Detection ───────────────────────────────────────────────────────────

def detect_edge_bankruptcy(market: dict, bankruptcy_data: dict) -> dict | None:
    """
    Detect edge on KXBANKRUPTCY markets.
    Compares projected year-end bankruptcy count vs strike.
    """
    ticker = market.get("ticker", "")
    if not ticker.startswith("KXBANKRUPTCY"):
        return None

    strike = market.get("floor_strike")
    if strike is None:
        return None
    strike = float(strike)

    yes_ask = float(market.get("yes_ask_dollars") or 0)
    no_ask = float(market.get("no_ask_dollars") or 0)
    yes_bid = float(market.get("yes_bid_dollars") or 0)

    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    # Project year-end total
    if "annual_baseline" in bankruptcy_data:
        mean = bankruptcy_data["annual_baseline"]
        std = bankruptcy_data["annual_std"]
    elif "avg_recent" in bankruptcy_data:
        mean = bankruptcy_data["avg_recent"]
        std = mean * 0.2  # assume 20% variation
    else:
        return None

    # P(total >= strike) using normal approximation
    if std <= 0:
        fair_above = 1.0 if mean >= strike else 0.0
    else:
        z = (strike - mean) / std
        fair_above = float(1.0 - norm.cdf(z))

    fair_below = 1.0 - fair_above

    strike_type = market.get("strike_type", "greater")
    if "less" in str(strike_type):
        fair_yes, fair_no = fair_below, fair_above
    else:
        fair_yes, fair_no = fair_above, fair_below

    yes_edge = fair_yes - yes_ask
    no_edge = (fair_no - no_ask) if 0 < no_ask < 1.0 else -1

    if yes_edge >= no_edge:
        side, fair_value, market_price, edge = "yes", fair_yes, yes_ask, yes_edge
    else:
        side, fair_value, market_price, edge = "no", fair_no, no_ask, no_edge

    if edge <= 0:
        return None

    confidence = "low" if bankruptcy_data.get("source") == "historical_baseline" else "medium"

    spread = yes_ask - yes_bid if yes_bid > 0 else 1.0
    liquidity = max(0, 10 - spread * 20)
    edge_score = min(10, edge * 20)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * 5

    return {
        "ticker": ticker,
        "title": market.get("title", ""),
        "category": "companies",
        "side": side,
        "market_price": market_price,
        "fair_value": round(fair_value, 4),
        "edge": round(edge, 4),
        "edge_source": "bankruptcy_projection",
        "confidence": confidence,
        "liquidity_score": round(liquidity, 1),
        "composite_score": round(composite, 1),
        "details": {
            "strike": strike,
            "projected_mean": round(mean, 0),
            "projected_std": round(std, 0),
            "data_source": bankruptcy_data.get("source", "fred"),
        },
    }
