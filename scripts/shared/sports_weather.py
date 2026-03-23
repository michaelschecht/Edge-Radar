"""
sports_weather.py
Weather impact assessment for outdoor sports betting.

Fetches NWS forecasts for game venues and calculates a scoring adjustment
factor for totals markets. High wind, rain, and extreme cold reduce
expected scoring in outdoor sports (NFL, MLB).

NWS API is free with no key required.
"""

import re
import logging
from datetime import datetime, timezone
from functools import lru_cache

import requests

log = logging.getLogger("sports_weather")

_TIMEOUT = 15
_USER_AGENT = "Edge-Radar/1.0 (sports-weather)"

# ── Venue NWS Grid Points ────────────────────────────────────────────────────
# (NWS office, gridX, gridY, dome/outdoor)
# Only outdoor venues matter — dome venues are unaffected by weather.

NFL_VENUES = {
    # Outdoor stadiums
    "BUF": ("BUF", 81, 47, "outdoor"),    # Highmark Stadium, Buffalo
    "CHI": ("LOT", 76, 73, "outdoor"),     # Soldier Field, Chicago
    "CIN": ("ILN", 56, 73, "outdoor"),     # Paycor Stadium, Cincinnati
    "CLE": ("CLE", 82, 65, "outdoor"),     # Cleveland Browns Stadium
    "DEN": ("BOU", 62, 60, "outdoor"),     # Empower Field, Denver
    "GB":  ("GRB", 65, 50, "outdoor"),     # Lambeau Field, Green Bay
    "JAX": ("JAX", 74, 56, "outdoor"),     # EverBank Stadium, Jacksonville
    "KC":  ("EAX", 39, 32, "outdoor"),     # Arrowhead Stadium, Kansas City
    "LAC": ("SGX", 58, 68, "outdoor"),     # SoFi Stadium (open-air), LA
    "LAR": ("SGX", 58, 68, "outdoor"),     # SoFi Stadium, LA
    "MIA": ("MFL", 76, 50, "outdoor"),     # Hard Rock Stadium, Miami
    "NE":  ("BOX", 71, 90, "outdoor"),     # Gillette Stadium, Foxborough
    "NYG": ("OKX", 33, 37, "outdoor"),     # MetLife Stadium, East Rutherford
    "NYJ": ("OKX", 33, 37, "outdoor"),     # MetLife Stadium
    "PHI": ("PHI", 55, 76, "outdoor"),     # Lincoln Financial Field
    "PIT": ("PBZ", 77, 65, "outdoor"),     # Acrisure Stadium, Pittsburgh
    "SEA": ("SEW", 124, 67, "outdoor"),    # Lumen Field, Seattle
    "SF":  ("MTR", 85, 105, "outdoor"),    # Levi's Stadium, Santa Clara
    "TB":  ("TBW", 55, 79, "outdoor"),     # Raymond James Stadium, Tampa
    "TEN": ("OHX", 57, 46, "outdoor"),     # Nissan Stadium, Nashville
    "WAS": ("LWX", 97, 71, "outdoor"),     # Northwest Stadium, Landover
    # Dome / retractable roof — weather does not affect these
    "ARI": ("PSR", 159, 57, "dome"),
    "ATL": ("FFC", 50, 86, "dome"),
    "BAL": ("LWX", 97, 71, "dome"),        # retractable
    "DAL": ("FWD", 84, 108, "dome"),
    "DET": ("DTX", 65, 33, "dome"),
    "HOU": ("HGX", 65, 97, "dome"),        # retractable
    "IND": ("IND", 58, 68, "dome"),
    "LV":  ("VEF", 122, 37, "dome"),
    "MIN": ("MPX", 107, 71, "dome"),
    "NO":  ("LIX", 75, 76, "dome"),
}

MLB_VENUES = {
    # Outdoor stadiums (majority of MLB)
    "ARI": ("PSR", 159, 57, "dome"),        # Chase Field (retractable)
    "ATL": ("FFC", 50, 86, "outdoor"),      # Truist Park
    "BAL": ("LWX", 97, 71, "outdoor"),      # Camden Yards
    "BOS": ("BOX", 71, 90, "outdoor"),      # Fenway Park
    "CHC": ("LOT", 76, 73, "outdoor"),      # Wrigley Field
    "CWS": ("LOT", 76, 73, "outdoor"),      # Guaranteed Rate Field
    "CIN": ("ILN", 56, 73, "outdoor"),      # Great American Ball Park
    "CLE": ("CLE", 82, 65, "outdoor"),      # Progressive Field
    "COL": ("BOU", 62, 60, "outdoor"),      # Coors Field
    "DET": ("DTX", 65, 33, "outdoor"),      # Comerica Park
    "HOU": ("HGX", 65, 97, "dome"),         # Minute Maid Park (retractable)
    "KC":  ("EAX", 39, 32, "outdoor"),      # Kauffman Stadium
    "LAA": ("SGX", 58, 68, "outdoor"),      # Angel Stadium
    "LAD": ("LOX", 154, 44, "outdoor"),     # Dodger Stadium
    "MIA": ("MFL", 76, 50, "dome"),         # loanDepot park (retractable)
    "MIL": ("MKX", 89, 64, "dome"),         # American Family Field (retractable)
    "MIN": ("MPX", 107, 71, "outdoor"),     # Target Field
    "NYM": ("OKX", 33, 37, "outdoor"),      # Citi Field
    "NYY": ("OKX", 33, 37, "outdoor"),      # Yankee Stadium
    "OAK": ("MTR", 85, 105, "outdoor"),     # Oakland Coliseum
    "PHI": ("PHI", 55, 76, "outdoor"),      # Citizens Bank Park
    "PIT": ("PBZ", 77, 65, "outdoor"),      # PNC Park
    "SD":  ("SGX", 58, 68, "outdoor"),      # Petco Park
    "SEA": ("SEW", 124, 67, "dome"),        # T-Mobile Park (retractable)
    "SF":  ("MTR", 85, 105, "outdoor"),     # Oracle Park
    "STL": ("LSX", 88, 78, "outdoor"),      # Busch Stadium
    "TB":  ("TBW", 55, 79, "dome"),         # Tropicana Field
    "TEX": ("FWD", 84, 108, "dome"),        # Globe Life Field (retractable)
    "TOR": ("LOT", 76, 73, "dome"),         # Rogers Centre (retractable) — in Toronto but NWS doesn't cover Canada
    "WAS": ("LWX", 97, 71, "outdoor"),      # Nationals Park
}


# ── NWS Forecast Fetching ────────────────────────────────────────────────────

_hourly_cache: dict[str, list[dict]] = {}


def _fetch_hourly_forecast(office: str, grid_x: int, grid_y: int) -> list[dict]:
    """Fetch hourly forecast from NWS. Cached per grid point."""
    cache_key = f"{office}/{grid_x}/{grid_y}"
    if cache_key in _hourly_cache:
        return _hourly_cache[cache_key]

    try:
        resp = requests.get(
            f"https://api.weather.gov/gridpoints/{office}/{grid_x},{grid_y}/forecast/hourly",
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        periods = resp.json().get("properties", {}).get("periods", [])
        _hourly_cache[cache_key] = periods
        return periods
    except Exception as e:
        log.warning("NWS hourly forecast error for %s: %s", cache_key, e)
        return []


def _get_game_time_weather(office: str, grid_x: int, grid_y: int,
                           game_date: str) -> dict | None:
    """
    Get weather conditions around game time for a given date.

    Returns dict with: temperature, wind_speed_mph, precip_pct, forecast
    Averages across the typical game window (afternoon/evening hours).
    """
    periods = _fetch_hourly_forecast(office, grid_x, grid_y)
    if not periods:
        return None

    # Find periods matching the game date (focus on 12:00-23:00 local)
    game_periods = []
    for p in periods:
        start = p.get("startTime", "")
        if game_date in start:
            # Parse hour from ISO timestamp
            try:
                hour = int(start[11:13])
                if 12 <= hour <= 23:  # typical game window
                    game_periods.append(p)
            except (ValueError, IndexError):
                continue

    if not game_periods:
        return None

    # Average the conditions
    temps = [p.get("temperature", 60) for p in game_periods]
    precips = [p.get("probabilityOfPrecipitation", {}).get("value", 0) or 0 for p in game_periods]

    wind_speeds = []
    for p in game_periods:
        ws = p.get("windSpeed", "0 mph")
        match = re.search(r"(\d+)", str(ws))
        if match:
            wind_speeds.append(int(match.group(1)))

    avg_temp = sum(temps) / len(temps) if temps else 60
    avg_wind = sum(wind_speeds) / len(wind_speeds) if wind_speeds else 0
    max_precip = max(precips) if precips else 0
    forecast = game_periods[0].get("shortForecast", "") if game_periods else ""

    return {
        "temperature_f": round(avg_temp, 1),
        "wind_speed_mph": round(avg_wind, 1),
        "precip_pct": round(max_precip, 0),
        "forecast": forecast,
        "periods_sampled": len(game_periods),
    }


# ── Scoring Impact ───────────────────────────────────────────────────────────

def weather_scoring_adjustment(weather: dict, sport: str) -> dict:
    """
    Calculate a scoring adjustment factor based on weather conditions.

    Returns dict with:
        - "adjustment": float (-0.15 to 0.0, negative = expect fewer points)
        - "reason": str (human-readable explanation)
        - "severity": "none" | "mild" | "moderate" | "severe"

    Factors:
        - Wind > 15 mph: reduces passing/kicking accuracy (NFL), fly balls (MLB)
        - Rain/precip > 40%: reduces scoring in both sports
        - Cold < 32F: reduces grip, ball flight (mainly NFL)
    """
    temp = weather.get("temperature_f", 60)
    wind = weather.get("wind_speed_mph", 0)
    precip = weather.get("precip_pct", 0)

    adjustment = 0.0
    reasons = []

    if sport in ("americanfootball_nfl", "americanfootball_ncaaf"):
        # NFL: wind affects passing game, cold affects grip
        if wind >= 25:
            adjustment -= 0.08
            reasons.append(f"high wind ({wind:.0f} mph)")
        elif wind >= 15:
            adjustment -= 0.04
            reasons.append(f"moderate wind ({wind:.0f} mph)")

        if precip >= 60:
            adjustment -= 0.06
            reasons.append(f"likely rain ({precip:.0f}%)")
        elif precip >= 40:
            adjustment -= 0.03
            reasons.append(f"possible rain ({precip:.0f}%)")

        if temp <= 20:
            adjustment -= 0.05
            reasons.append(f"extreme cold ({temp:.0f}F)")
        elif temp <= 32:
            adjustment -= 0.02
            reasons.append(f"cold ({temp:.0f}F)")

    elif sport in ("baseball_mlb",):
        # MLB: wind affects fly balls, rain delays/affects pitching
        if wind >= 20:
            adjustment -= 0.06
            reasons.append(f"high wind ({wind:.0f} mph)")
        elif wind >= 12:
            adjustment -= 0.03
            reasons.append(f"moderate wind ({wind:.0f} mph)")

        if precip >= 50:
            adjustment -= 0.05
            reasons.append(f"likely rain ({precip:.0f}%)")
        elif precip >= 30:
            adjustment -= 0.02
            reasons.append(f"possible rain ({precip:.0f}%)")

        if temp <= 45:
            adjustment -= 0.03
            reasons.append(f"cold ({temp:.0f}F)")

    # Severity classification
    if adjustment <= -0.10:
        severity = "severe"
    elif adjustment <= -0.05:
        severity = "moderate"
    elif adjustment < 0:
        severity = "mild"
    else:
        severity = "none"

    return {
        "adjustment": round(adjustment, 3),
        "reason": ", ".join(reasons) if reasons else "no weather impact",
        "severity": severity,
    }


# ── Public API ───────────────────────────────────────────────────────────────

def get_game_weather(team_abbr: str, sport: str, game_date: str) -> dict | None:
    """
    Get weather conditions and scoring impact for an outdoor game.

    Args:
        team_abbr: Home team abbreviation (e.g., "KC", "NYY")
        sport: Sport key (e.g., "americanfootball_nfl", "baseball_mlb")
        game_date: Date string "YYYY-MM-DD"

    Returns dict with weather conditions and scoring adjustment, or None
    if venue is a dome or team/sport not found.
    """
    if sport in ("americanfootball_nfl", "americanfootball_ncaaf"):
        venues = NFL_VENUES
    elif sport == "baseball_mlb":
        venues = MLB_VENUES
    else:
        return None  # other sports not supported yet

    venue = venues.get(team_abbr.upper())
    if not venue:
        return None

    office, grid_x, grid_y, venue_type = venue

    if venue_type == "dome":
        return {
            "venue_type": "dome",
            "weather": None,
            "scoring_impact": {"adjustment": 0.0, "reason": "dome stadium", "severity": "none"},
        }

    weather = _get_game_time_weather(office, grid_x, grid_y, game_date)
    if not weather:
        return None

    impact = weather_scoring_adjustment(weather, sport)

    return {
        "venue_type": "outdoor",
        "team": team_abbr.upper(),
        "game_date": game_date,
        "weather": weather,
        "scoring_impact": impact,
    }
