"""
line_movement.py
Detect line movement and reverse line movement using ESPN odds data.

ESPN's scoreboard API provides opening and current (closing) odds from
DraftKings for every game. By comparing open vs close, we can detect:

1. **Line movement magnitude** — how much the spread/total shifted
2. **Reverse line movement** — when the line moves opposite to where
   public money would push it, indicating sharp action on the other side

This is a free proxy for public betting percentages. No API key required.

Usage:
    from line_movement import get_line_movement

    movements = get_line_movement("nba")
    for m in movements:
        print(f"{m['matchup']}: spread moved {m['spread_move']:+.1f} pts")
"""

import re
import logging
from datetime import datetime, timezone

import requests

log = logging.getLogger("line_movement")

_TIMEOUT = 10

# ESPN sport/league mapping
_ESPN_SPORTS = {
    "nba": ("basketball", "nba"),
    "basketball_nba": ("basketball", "nba"),
    "ncaab": ("basketball", "mens-college-basketball"),
    "basketball_ncaab": ("basketball", "mens-college-basketball"),
    "nfl": ("football", "nfl"),
    "americanfootball_nfl": ("football", "nfl"),
    "ncaaf": ("football", "college-football"),
    "americanfootball_ncaaf": ("football", "college-football"),
    "nhl": ("hockey", "nhl"),
    "icehockey_nhl": ("hockey", "nhl"),
    "mlb": ("baseball", "mlb"),
    "baseball_mlb": ("baseball", "mlb"),
}


def _parse_american_odds(odds_str: str) -> float | None:
    """Convert American odds string to implied probability."""
    if not odds_str or odds_str == "EVEN":
        return 0.50
    try:
        odds = int(odds_str.replace("+", ""))
        if odds > 0:
            return 100.0 / (odds + 100)
        else:
            return abs(odds) / (abs(odds) + 100)
    except (ValueError, TypeError):
        return None


def _parse_line(line_str: str) -> float | None:
    """Parse a spread/total line string like '+3.5' or 'o226.5'."""
    if not line_str:
        return None
    try:
        cleaned = re.sub(r"[oOuU]", "", str(line_str))
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def get_line_movement(sport: str, date: str | None = None) -> list[dict]:
    """
    Fetch today's games and calculate line movement from ESPN odds data.

    Args:
        sport: Sport key (e.g., 'nba', 'nfl', 'mlb', 'nhl')
        date: Optional date string 'YYYYMMDD' (defaults to today)

    Returns list of dicts with:
        - matchup: "LAL @ DET"
        - home_team, away_team (abbreviation)
        - spread_open, spread_close, spread_move
        - total_open, total_close, total_move
        - ml_home_open, ml_home_close (implied probability)
        - sharp_signal: "home" | "away" | "over" | "under" | None
        - signal_reason: human-readable explanation
    """
    espn = _ESPN_SPORTS.get(sport.lower())
    if not espn:
        return []

    sport_path, league = espn
    url = f"http://site.api.espn.com/apis/site/v2/sports/{sport_path}/{league}/scoreboard"
    params = {}
    if date:
        params["dates"] = date

    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
    except Exception as e:
        log.warning("ESPN scoreboard error for %s: %s", sport, e)
        return []

    results = []
    for event in resp.json().get("events", []):
        comp = event.get("competitions", [{}])[0]
        odds_list = comp.get("odds", [])
        if not odds_list:
            continue

        odds = odds_list[0]  # Primary provider (usually DraftKings)

        # Teams
        competitors = comp.get("competitors", [])
        home = away = None
        for c in competitors:
            if c.get("homeAway") == "home":
                home = c.get("team", {}).get("abbreviation", "?")
            else:
                away = c.get("team", {}).get("abbreviation", "?")

        if not home or not away:
            continue

        # Spread movement
        spread_data = odds.get("pointSpread", {})
        home_spread = spread_data.get("home", {})
        spread_open = _parse_line(home_spread.get("open", {}).get("line"))
        spread_close = _parse_line(home_spread.get("close", {}).get("line"))
        spread_move = (spread_close - spread_open) if (spread_open is not None and spread_close is not None) else None

        # Total movement
        total_data = odds.get("total", {})
        over_data = total_data.get("over", {})
        total_open = _parse_line(over_data.get("open", {}).get("line"))
        total_close = _parse_line(over_data.get("close", {}).get("line"))
        total_move = (total_close - total_open) if (total_open is not None and total_close is not None) else None

        # Moneyline movement (implied probability)
        ml_data = odds.get("moneyline", {})
        ml_home_open = _parse_american_odds(
            ml_data.get("home", {}).get("open", {}).get("odds", "")
        )
        ml_home_close = _parse_american_odds(
            ml_data.get("home", {}).get("close", {}).get("odds", "")
        )

        # Detect sharp signals (reverse line movement)
        sharp_signal = None
        signal_reason = None

        if spread_move is not None and abs(spread_move) >= 1.5:
            # Spread moved significantly
            # In a "normal" market, public money on the favorite pushes the
            # spread up (more negative). If the spread moves toward the
            # underdog instead, sharp money is likely on the underdog.
            fav_is_home = (spread_close or 0) < 0
            moved_toward_home = spread_move < 0  # line got more negative = more home-favorable

            if fav_is_home and not moved_toward_home:
                # Home is favorite but line moved away from home = sharp on away
                sharp_signal = "away"
                signal_reason = f"Spread moved {spread_move:+.1f} away from home favorite {home}"
            elif not fav_is_home and moved_toward_home:
                # Away is favorite but line moved toward home = sharp on home
                sharp_signal = "home"
                signal_reason = f"Spread moved {spread_move:+.1f} toward home underdog {home}"

        if total_move is not None and abs(total_move) >= 2.0:
            # Total moved significantly
            if total_move < -2.0 and sharp_signal is None:
                sharp_signal = "under"
                signal_reason = f"Total dropped {total_move:+.1f} pts (sharp under)"
            elif total_move > 2.0 and sharp_signal is None:
                sharp_signal = "over"
                signal_reason = f"Total rose {total_move:+.1f} pts (sharp over)"

        results.append({
            "matchup": f"{away} @ {home}",
            "home_team": home,
            "away_team": away,
            "spread_open": spread_open,
            "spread_close": spread_close,
            "spread_move": round(spread_move, 1) if spread_move is not None else None,
            "total_open": total_open,
            "total_close": total_close,
            "total_move": round(total_move, 1) if total_move is not None else None,
            "ml_home_open_prob": round(ml_home_open, 3) if ml_home_open is not None else None,
            "ml_home_close_prob": round(ml_home_close, 3) if ml_home_close is not None else None,
            "sharp_signal": sharp_signal,
            "signal_reason": signal_reason,
        })

    return results


def get_sharp_signals(sport: str) -> list[dict]:
    """Return only games with detected sharp/reverse line movement."""
    return [m for m in get_line_movement(sport) if m.get("sharp_signal")]
