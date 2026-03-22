"""
crypto_edge.py
Edge detection for Kalshi crypto markets (BTC, ETH, XRP, DOGE).

Compares Kalshi binary option prices against fair probabilities derived from
current exchange prices (CoinGecko) and realized volatility.
"""

import re
import logging
from datetime import datetime, timezone

import requests

from probability import strike_probability, realized_volatility

log = logging.getLogger("crypto_edge")

# ── Ticker-to-coin mapping ───────────────────────────────────────────────────

CRYPTO_PREFIX_MAP = {
    "KXBTC":  "bitcoin",
    "KXETH":  "ethereum",
    "KXXRP":  "ripple",
    "KXDOGE": "dogecoin",
    "KXSOL":  "solana",
}

# Default annual volatility fallbacks if history fetch fails
DEFAULT_VOL = {
    "bitcoin":  0.55,
    "ethereum":  0.70,
    "ripple":   0.85,
    "dogecoin": 1.00,
    "solana":   0.90,
}

# ── CoinGecko API ────────────────────────────────────────────────────────────

_price_cache: dict[str, float] = {}
_history_cache: dict[str, list[float]] = {}


def fetch_crypto_price(coin_id: str) -> float | None:
    """Fetch current USD price from CoinGecko with retry on rate limit."""
    if coin_id in _price_cache:
        return _price_cache[coin_id]

    import time
    for attempt in range(3):
        try:
            resp = requests.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": coin_id, "vs_currencies": "usd"},
                timeout=10,
            )
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log.info("CoinGecko rate limited, waiting %ds...", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            price = resp.json().get(coin_id, {}).get("usd")
            if price:
                _price_cache[coin_id] = float(price)
                log.info("CoinGecko %s: $%.2f", coin_id, price)
                return float(price)
        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                wait = 10 * (attempt + 1)
                log.info("CoinGecko rate limited, waiting %ds...", wait)
                time.sleep(wait)
                continue
            log.warning("CoinGecko price error for %s: %s", coin_id, e)
            return None
        except Exception as e:
            log.warning("CoinGecko price error for %s: %s", coin_id, e)
            return None
    log.warning("CoinGecko: gave up fetching %s after retries", coin_id)
    return None


def fetch_crypto_history(coin_id: str, days: int = 7) -> list[float]:
    """Fetch hourly price history from CoinGecko for volatility calculation."""
    cache_key = f"{coin_id}:{days}"
    if cache_key in _history_cache:
        return _history_cache[cache_key]

    import time
    for attempt in range(3):
        try:
            resp = requests.get(
                f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart",
                params={"vs_currency": "usd", "days": days},
                timeout=15,
            )
            if resp.status_code == 429:
                wait = 10 * (attempt + 1)
                log.info("CoinGecko rate limited (history), waiting %ds...", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            prices = [p[1] for p in resp.json().get("prices", [])]
            if prices:
                _history_cache[cache_key] = prices
                log.info("CoinGecko history %s: %d data points", coin_id, len(prices))
            return prices
        except requests.exceptions.HTTPError as e:
            if "429" in str(e):
                wait = 10 * (attempt + 1)
                log.info("CoinGecko rate limited (history), waiting %ds...", wait)
                time.sleep(wait)
                continue
            log.warning("CoinGecko history error for %s: %s", coin_id, e)
            return []
        except Exception as e:
            log.warning("CoinGecko history error for %s: %s", coin_id, e)
            return []
    return []


# ── Edge Detection ───────────────────────────────────────────────────────────

def get_coin_from_ticker(ticker: str) -> str | None:
    """Map Kalshi ticker to CoinGecko coin_id."""
    for prefix, coin_id in CRYPTO_PREFIX_MAP.items():
        if ticker.startswith(prefix):
            return coin_id
    return None


def parse_expiry(market: dict) -> datetime | None:
    """Parse settlement time from market."""
    exp_str = market.get("expected_expiration_time") or market.get("close_time")
    if not exp_str:
        return None
    try:
        return datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def detect_edge_crypto(market: dict) -> dict | None:
    """
    Detect edge on a Kalshi crypto binary market.

    Returns a dict with opportunity fields or None if no edge / can't analyze.
    """
    ticker = market.get("ticker", "")
    coin_id = get_coin_from_ticker(ticker)
    if not coin_id:
        return None

    # Parse strike price
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
    expiry = parse_expiry(market)
    if not expiry:
        return None

    now = datetime.now(timezone.utc)
    hours_to_expiry = max(0.01, (expiry - now).total_seconds() / 3600)

    # Fetch current price and volatility
    current_price = fetch_crypto_price(coin_id)
    if not current_price:
        return None

    history = fetch_crypto_history(coin_id, days=7)
    if history and len(history) > 10:
        vol = realized_volatility(history)
        if vol < 0.05:
            vol = DEFAULT_VOL.get(coin_id, 0.60)
    else:
        vol = DEFAULT_VOL.get(coin_id, 0.60)

    # Calculate fair probability (above strike)
    fair_above = strike_probability(current_price, strike, vol, hours_to_expiry)
    fair_below = 1.0 - fair_above

    # Pick better side
    yes_edge = fair_above - yes_ask
    no_edge = (fair_below - no_ask) if 0 < no_ask < 1.0 else -1

    if yes_edge >= no_edge:
        side = "yes"
        fair_value = fair_above
        market_price = yes_ask
        edge = yes_edge
    else:
        side = "no"
        fair_value = fair_below
        market_price = no_ask
        edge = no_edge

    if edge <= 0:
        return None

    # Confidence based on distance from strike
    price_distance = abs(current_price - strike) / current_price
    if price_distance > 0.10 and hours_to_expiry < 24:
        confidence = "high"
    elif price_distance > 0.03:
        confidence = "medium"
    else:
        confidence = "low"

    # Liquidity score
    spread = yes_ask - yes_bid if yes_bid > 0 else 1.0
    liquidity = max(0, 10 - spread * 20)

    # Composite score (same weights as sports edge detector)
    edge_score = min(10, edge * 20)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    time_score = min(10, 10 * (1 - hours_to_expiry / 168)) if hours_to_expiry < 168 else 0

    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * time_score

    return {
        "ticker": ticker,
        "title": market.get("title", ""),
        "category": "crypto",
        "side": side,
        "market_price": market_price,
        "fair_value": round(fair_value, 4),
        "edge": round(edge, 4),
        "edge_source": f"coingecko_{coin_id}_vol_model",
        "confidence": confidence,
        "liquidity_score": round(liquidity, 1),
        "composite_score": round(composite, 1),
        "details": {
            "coin": coin_id,
            "current_price": current_price,
            "strike": strike,
            "volatility": round(vol, 4),
            "hours_to_expiry": round(hours_to_expiry, 1),
        },
    }
