"""
spx_edge.py
Edge detection for Kalshi S&P 500 (KXINX) binary options.

Compares Kalshi strike prices against current SPX price and uses VIX-implied
volatility for probability estimation.
"""

import logging
from datetime import datetime, timezone

import requests

from probability import strike_probability, realized_volatility

log = logging.getLogger("spx_edge")

# ── Market Data Fetching ─────────────────────────────────────────────────────

_price_cache: dict[str, dict] = {}


def fetch_yahoo_quote(symbol: str) -> dict | None:
    """
    Fetch current quote from Yahoo Finance v8 API.
    Returns dict with 'price' and optionally 'history' or None on failure.
    No API key required.
    """
    if symbol in _price_cache:
        return _price_cache[symbol]

    try:
        # Use Yahoo Finance v8 chart endpoint (free, no key)
        resp = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"interval": "1h", "range": "5d"},
            headers={"User-Agent": "FinAgent/1.0"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        result = data.get("chart", {}).get("result", [{}])[0]
        meta = result.get("meta", {})
        price = meta.get("regularMarketPrice")

        if not price:
            return None

        # Extract hourly prices for volatility calculation
        closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
        history = [c for c in closes if c is not None]

        quote = {"price": float(price), "history": history}
        _price_cache[symbol] = quote
        log.info("Yahoo %s: $%.2f (%d history points)", symbol, price, len(history))
        return quote

    except Exception as e:
        log.warning("Yahoo Finance error for %s: %s", symbol, e)
        return None


def fetch_spx_data() -> tuple[float, float] | None:
    """
    Fetch current S&P 500 price and VIX for volatility estimation.

    Returns (spx_price, annual_volatility) or None.
    Uses VIX if available, falls back to realized vol from price history.
    """
    spx = fetch_yahoo_quote("%5EGSPC")  # ^GSPC
    if not spx:
        return None

    spx_price = spx["price"]

    # Try to get VIX for implied volatility
    vix = fetch_yahoo_quote("%5EVIX")  # ^VIX
    if vix and vix["price"] > 0:
        annual_vol = vix["price"] / 100.0  # VIX 20 = 20% annual vol
        log.info("Using VIX-implied vol: %.1f%%", annual_vol * 100)
        return spx_price, annual_vol

    # Fallback: compute realized vol from SPX history
    history = spx.get("history", [])
    if history and len(history) > 10:
        annual_vol = realized_volatility(history)
        if annual_vol > 0.01:
            log.info("Using realized vol: %.1f%%", annual_vol * 100)
            return spx_price, annual_vol

    # Last resort: use typical SPX vol
    log.info("Using default SPX vol: 18%%")
    return spx_price, 0.18


# ── Edge Detection ───────────────────────────────────────────────────────────

def parse_expiry_spx(market: dict) -> datetime | None:
    """Parse settlement time from an KXINX market."""
    exp_str = market.get("expected_expiration_time") or market.get("close_time")
    if not exp_str:
        return None
    try:
        return datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def detect_edge_spx(market: dict, spx_price: float, annual_vol: float) -> dict | None:
    """
    Detect edge on a Kalshi S&P 500 binary option.

    Args:
        market: Kalshi market dict
        spx_price: Current S&P 500 price
        annual_vol: Annualized volatility (from VIX or realized)

    Returns a dict with opportunity fields or None if no edge.
    """
    ticker = market.get("ticker", "")
    if not ticker.startswith("KXINX"):
        return None

    # Parse strike
    strike = market.get("floor_strike")
    if strike is None:
        return None
    strike = float(strike)
    if strike <= 0:
        return None

    # Parse market prices
    yes_ask = float(market.get("yes_ask_dollars") or 0)
    no_ask = float(market.get("no_ask_dollars") or 0)
    yes_bid = float(market.get("yes_bid_dollars") or 0)

    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    # Parse expiry
    expiry = parse_expiry_spx(market)
    if not expiry:
        return None

    now = datetime.now(timezone.utc)
    hours_to_expiry = max(0.01, (expiry - now).total_seconds() / 3600)

    # Skip if more than 14 days out (vol model less reliable)
    if hours_to_expiry > 14 * 24:
        return None

    # Determine market direction from title/strike_type
    strike_type = market.get("strike_type", "greater")
    title = market.get("title", "").lower()

    # Calculate fair probability (above strike)
    fair_above = strike_probability(spx_price, strike, annual_vol, hours_to_expiry)
    fair_below = 1.0 - fair_above

    if strike_type == "less" or "below" in title:
        fair_yes = fair_below
        fair_no = fair_above
    else:
        fair_yes = fair_above
        fair_no = fair_below

    # Pick better side
    yes_edge = fair_yes - yes_ask
    no_edge = (fair_no - no_ask) if 0 < no_ask < 1.0 else -1

    if yes_edge >= no_edge:
        side = "yes"
        fair_value = fair_yes
        market_price = yes_ask
        edge = yes_edge
    else:
        side = "no"
        fair_value = fair_no
        market_price = no_ask
        edge = no_edge

    if edge <= 0:
        return None

    # Confidence based on VIX and time horizon
    vix_level = annual_vol * 100
    if vix_level < 20 and hours_to_expiry < 8:
        confidence = "high"
    elif vix_level < 30 and hours_to_expiry < 48:
        confidence = "medium"
    else:
        confidence = "low"

    # Liquidity score
    spread = yes_ask - yes_bid if yes_bid > 0 else 1.0
    liquidity = max(0, 10 - spread * 20)

    # Composite score
    edge_score = min(10, edge * 20)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    time_score = min(10, 10 * (1 - hours_to_expiry / (14 * 24)))

    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * time_score

    return {
        "ticker": ticker,
        "title": market.get("title", ""),
        "category": "spx",
        "side": side,
        "market_price": market_price,
        "fair_value": round(fair_value, 4),
        "edge": round(edge, 4),
        "edge_source": "spx_vix_model" if vix_level > 0 else "spx_realized_vol",
        "confidence": confidence,
        "liquidity_score": round(liquidity, 1),
        "composite_score": round(composite, 1),
        "details": {
            "spx_price": spx_price,
            "strike": strike,
            "vix": round(vix_level, 1),
            "annual_vol": round(annual_vol, 4),
            "hours_to_expiry": round(hours_to_expiry, 1),
        },
    }
