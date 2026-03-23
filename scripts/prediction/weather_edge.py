"""
weather_edge.py
Edge detection for Kalshi weather/temperature markets.

Compares Kalshi temperature binary options against NWS forecast data.
NWS API is free with no API key required.
"""

import re
import logging
from datetime import datetime, timezone, timedelta

import requests

from probability import weather_probability

log = logging.getLogger("weather_edge")

# ── City-to-NWS grid mapping ────────────────────────────────────────────────

# (NWS office, gridX, gridY) for each Kalshi city prefix
CITY_NWS_MAP = {
    "NY":  ("OKX", 33, 37),    # New York City (Central Park)
    "CHI": ("LOT", 76, 73),    # Chicago (Midway area)
    "MIA": ("MFL", 76, 50),    # Miami
    "DEN": ("BOU", 62, 60),    # Denver
    "LA":  ("LOX", 154, 44),   # Los Angeles
    "DAL": ("FWD", 84, 108),   # Dallas
    "HOU": ("HGX", 65, 97),    # Houston
    "PHX": ("PSR", 159, 57),   # Phoenix
    "SF":  ("MTR", 85, 105),   # San Francisco
    "DC":  ("LWX", 97, 71),    # Washington DC
    "BOS": ("BOX", 71, 90),    # Boston
    "SEA": ("SEW", 124, 67),   # Seattle
    "ATL": ("FFC", 50, 86),    # Atlanta
}

# Map Kalshi ticker prefix suffix to city key
# KXHIGHNY -> "NY", KXHIGHCHI -> "CHI", etc.
TICKER_CITY_MAP = {
    "KXHIGHNY":  "NY",
    "KXHIGHCHI": "CHI",
    "KXHIGHMIA": "MIA",
    "KXHIGHDEN": "DEN",
    "KXHIGHLA":  "LA",
    "KXHIGHDAL": "DAL",
    "KXHIGHHOU": "HOU",
    "KXHIGHPHX": "PHX",
    "KXHIGHSF":  "SF",
    "KXHIGHDC":  "DC",
    "KXHIGHBOS": "BOS",
    "KXHIGHSEA": "SEA",
    "KXHIGHATL": "ATL",
}

# ── NWS API ──────────────────────────────────────────────────────────────────

_forecast_cache: dict[str, list[dict]] = {}


def fetch_nws_forecast(office: str, grid_x: int, grid_y: int) -> list[dict]:
    """
    Fetch forecast periods from NWS gridpoint API.
    Returns list of forecast periods with 'temperature', 'isDaytime', etc.
    Free, no API key required. Caches per grid point.
    """
    cache_key = f"{office}/{grid_x}/{grid_y}"
    if cache_key in _forecast_cache:
        return _forecast_cache[cache_key]

    try:
        resp = requests.get(
            f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast",
            headers={"User-Agent": "Edge-Radar/1.0 (weather-edge-detection)"},
            timeout=15,
        )
        resp.raise_for_status()
        periods = resp.json().get("properties", {}).get("periods", [])
        _forecast_cache[cache_key] = periods
        log.info("NWS forecast %s: %d periods", cache_key, len(periods))
        return periods
    except Exception as e:
        log.warning("NWS forecast error for %s: %s", cache_key, e)
        return []


def get_forecast_high(periods: list[dict], target_date: str) -> float | None:
    """
    Extract the forecast high temperature for a given date.

    Args:
        periods: NWS forecast periods
        target_date: Date string like "2026-03-23"

    Returns:
        Forecast high temperature (°F) or None
    """
    for period in periods:
        start = period.get("startTime", "")
        if target_date in start and period.get("isDaytime", False):
            return float(period.get("temperature", 0))
    return None


# ── Ticker Parsing ───────────────────────────────────────────────────────────

def get_city_from_ticker(ticker: str) -> str | None:
    """Map Kalshi ticker to city key."""
    for prefix, city in TICKER_CITY_MAP.items():
        if ticker.startswith(prefix):
            return city
    return None


def parse_target_date(market: dict) -> str | None:
    """
    Parse the target date from the market's expiration time.
    Returns date string like "2026-03-23".
    """
    exp_str = market.get("expected_expiration_time") or market.get("close_time")
    if not exp_str:
        return None
    try:
        # Weather markets settle the day before the expiration
        # The ticker contains the date: KXHIGHNY-26MAR23-T61 -> March 23
        ticker = market.get("ticker", "")
        # Extract date portion from ticker
        match = re.search(r'-(\d{2})([A-Z]{3})(\d{2})-', ticker)
        if match:
            year = int("20" + match.group(1))
            month_map = {
                "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
                "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
            }
            month = month_map.get(match.group(2), 0)
            day = int(match.group(3))
            if month > 0:
                return f"{year}-{month:02d}-{day:02d}"

        # Fallback: use expiration time
        dt = datetime.fromisoformat(exp_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return None


# ── Edge Detection ───────────────────────────────────────────────────────────

def detect_edge_weather(market: dict) -> dict | None:
    """
    Detect edge on a Kalshi weather/temperature binary market.

    Returns a dict with opportunity fields or None if no edge / can't analyze.
    """
    ticker = market.get("ticker", "")
    city_key = get_city_from_ticker(ticker)
    if not city_key:
        return None

    nws_info = CITY_NWS_MAP.get(city_key)
    if not nws_info:
        return None

    # Parse strike (temperature threshold)
    strike = market.get("floor_strike")
    if strike is None:
        return None
    strike = float(strike)

    # Parse market prices
    yes_ask = float(market.get("yes_ask_dollars") or 0)
    no_ask = float(market.get("no_ask_dollars") or 0)
    yes_bid = float(market.get("yes_bid_dollars") or 0)

    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    # Parse target date and calculate forecast horizon
    target_date = parse_target_date(market)
    if not target_date:
        return None

    now = datetime.now(timezone.utc)
    try:
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    days_out = max(0, (target_dt - now).days)
    if days_out > 7:
        return None  # NWS forecasts unreliable beyond ~7 days

    # Fetch NWS forecast
    office, grid_x, grid_y = nws_info
    periods = fetch_nws_forecast(office, grid_x, grid_y)
    if not periods:
        return None

    forecast_high = get_forecast_high(periods, target_date)
    if forecast_high is None:
        return None

    # Uncertainty increases with forecast horizon
    # NWS typical errors: ~2-3°F day 1, ~3-4°F day 2, ~4-5°F day 3, etc.
    uncertainty = 2.5 + days_out * 1.0

    # Calculate fair probability
    fair_above = weather_probability(forecast_high, strike, uncertainty)
    fair_below = 1.0 - fair_above

    # Determine if this is a "greater than" or "less than" market
    strike_type = market.get("strike_type", "greater")
    title = market.get("title", "").lower()

    if strike_type == "less" or "<" in title or "below" in title:
        # Market asks: will temp be BELOW strike?
        fair_yes = fair_below
        fair_no = fair_above
    else:
        # Market asks: will temp be ABOVE strike?
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

    # Confidence based on forecast horizon
    if days_out <= 1:
        confidence = "high"
    elif days_out <= 3:
        confidence = "medium"
    else:
        confidence = "low"

    # Liquidity score
    spread = yes_ask - yes_bid if yes_bid > 0 else 1.0
    liquidity = max(0, 10 - spread * 20)

    # Composite score
    edge_score = min(10, edge * 20)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    time_score = max(0, 10 - days_out * 2)

    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * time_score

    return {
        "ticker": ticker,
        "title": market.get("title", ""),
        "category": "weather",
        "side": side,
        "market_price": market_price,
        "fair_value": round(fair_value, 4),
        "edge": round(edge, 4),
        "edge_source": f"nws_forecast_{city_key.lower()}",
        "confidence": confidence,
        "liquidity_score": round(liquidity, 1),
        "composite_score": round(composite, 1),
        "details": {
            "city": city_key,
            "forecast_high": forecast_high,
            "strike": strike,
            "uncertainty": round(uncertainty, 1),
            "days_out": days_out,
            "target_date": target_date,
        },
    }
