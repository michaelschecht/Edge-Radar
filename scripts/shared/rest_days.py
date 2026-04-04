"""
rest_days.py — Back-to-back and rest day detection for NBA/NHL.

Fetches the ESPN schedule to identify teams playing on consecutive days.
NBA back-to-backs are a 5-7 point swing (fatigue, travel, shorter prep).

Used by edge_detector to adjust stdev and confidence for affected teams.

The ESPN API is free and requires no API key.

Usage:
    from rest_days import prefetch_rest_data

    # Returns rest data for all NBA teams playing today
    rest = prefetch_rest_data("basketball_nba", "2026-04-05")
    info = rest.get("BOS")  # {'is_b2b': True, 'days_rest': 0, ...}
"""

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import requests

log = logging.getLogger("rest_days")
_TIMEOUT = 10

# ESPN sport/league mapping (same as line_movement.py)
_ESPN_SPORTS = {
    "basketball_nba": ("basketball", "nba"),
    "icehockey_nhl": ("hockey", "nhl"),
}

# Stdev adjustments for rest situations
# NBA back-to-back increases variance and lowers scoring slightly
REST_ADJUSTMENTS = {
    "basketball_nba": {
        "b2b_stdev_adj": 1.5,       # Add to margin/total stdev (more variance)
        "b2b_scoring_adj": -0.02,    # Lower over probability ~2% (fatigue = less scoring)
        "well_rested_stdev_adj": -0.5,  # Tighter games when well rested (3+ days)
    },
    "icehockey_nhl": {
        "b2b_stdev_adj": 0.3,
        "b2b_scoring_adj": -0.01,
        "well_rested_stdev_adj": -0.1,
    },
}


# ── ESPN Schedule Fetch ──────────────────────────────────────────────────────

@lru_cache(maxsize=16)
def _fetch_scoreboard(sport_path: str, league: str, date_str: str) -> list[dict]:
    """Fetch ESPN scoreboard for a date. Returns list of (away_abbr, home_abbr) game tuples."""
    try:
        url = f"http://site.api.espn.com/apis/site/v2/sports/{sport_path}/{league}/scoreboard"
        resp = requests.get(url, params={"dates": date_str}, timeout=_TIMEOUT)
        resp.raise_for_status()
        games = []
        for event in resp.json().get("events", []):
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            away = home = None
            for c in competitors:
                abbr = c.get("team", {}).get("abbreviation", "")
                if c.get("homeAway") == "home":
                    home = abbr
                else:
                    away = abbr
            if away and home:
                games.append({"away": away, "home": home})
        return games
    except Exception as e:
        log.debug("ESPN scoreboard fetch failed for %s/%s on %s: %s", sport_path, league, date_str, e)
        return []


def _teams_playing_on(sport_path: str, league: str, date_str: str) -> set[str]:
    """Get set of team abbreviations playing on a given date."""
    games = _fetch_scoreboard(sport_path, league, date_str)
    teams = set()
    for g in games:
        teams.add(g["away"])
        teams.add(g["home"])
    return teams


# ── Rest Day Calculation ─────────────────────────────────────────────────────

def _calculate_rest(sport_path: str, league: str, game_date: str, team_abbr: str) -> dict:
    """Calculate rest days for a team heading into a game.

    Checks the 3 days prior to game_date to determine:
    - Did they play yesterday? (back-to-back)
    - How many days since last game? (rest days)

    Returns:
        is_b2b: True if played yesterday
        days_rest: 0 = b2b, 1 = normal, 2 = one day off, 3+ = well rested
        last_game: date string of most recent game, or None
    """
    try:
        target = datetime.strptime(game_date, "%Y-%m-%d")
    except ValueError:
        return {"is_b2b": False, "days_rest": 1, "last_game": None}

    # Check 1-4 days back
    for days_back in range(1, 5):
        check_date = target - timedelta(days=days_back)
        check_str = check_date.strftime("%Y%m%d")
        teams = _teams_playing_on(sport_path, league, check_str)
        if team_abbr.upper() in teams:
            return {
                "is_b2b": days_back == 1,
                "days_rest": days_back - 1,  # 0 = b2b, 1 = normal rest, 2+ = extra rest
                "last_game": check_date.strftime("%Y-%m-%d"),
            }

    # No game found in last 4 days
    return {"is_b2b": False, "days_rest": 4, "last_game": None}


# ── Public API ───────────────────────────────────────────────────────────────

def prefetch_rest_data(sport_key: str, game_date: str) -> dict[str, dict]:
    """Pre-fetch rest day data for all teams playing on a given date.

    Args:
        sport_key: e.g., "basketball_nba", "icehockey_nhl"
        game_date: YYYY-MM-DD format

    Returns dict keyed by team abbreviation -> rest info:
        is_b2b: bool
        days_rest: int (0=b2b, 1=normal, 2+=extra rest)
        last_game: str or None
        opponent_is_b2b: bool
        rest_advantage: int (our rest - opponent rest, positive = we're more rested)
        stdev_adjustment: float (to add to base sport stdev)
        confidence_signal: "supports_under" | "supports_over" | "neutral"
    """
    espn = _ESPN_SPORTS.get(sport_key)
    if not espn:
        return {}

    sport_path, league = espn
    adjustments = REST_ADJUSTMENTS.get(sport_key, {})

    # Get today's games
    date_fmt = game_date.replace("-", "")
    games = _fetch_scoreboard(sport_path, league, date_fmt)
    if not games:
        return {}

    # Calculate rest for each team
    team_rest: dict[str, dict] = {}
    for g in games:
        for abbr in [g["away"], g["home"]]:
            rest = _calculate_rest(sport_path, league, game_date, abbr)
            team_rest[abbr] = rest

    # Now enrich with opponent context and adjustments
    result: dict[str, dict] = {}
    for g in games:
        away_rest = team_rest.get(g["away"], {})
        home_rest = team_rest.get(g["home"], {})

        for abbr, my_rest, opp_rest, opp_abbr in [
            (g["away"], away_rest, home_rest, g["home"]),
            (g["home"], home_rest, away_rest, g["away"]),
        ]:
            my_days = my_rest.get("days_rest", 1)
            opp_days = opp_rest.get("days_rest", 1)
            rest_adv = my_days - opp_days

            # Stdev adjustment
            stdev_adj = 0.0
            if my_rest.get("is_b2b") or opp_rest.get("is_b2b"):
                stdev_adj += adjustments.get("b2b_stdev_adj", 0)
            if my_days >= 3 and opp_days >= 3:
                stdev_adj += adjustments.get("well_rested_stdev_adj", 0)

            # Confidence signal for totals
            # Both teams on b2b = lean under (fatigue)
            # One team b2b = slight lean under
            # Both well rested = neutral (standard game)
            conf_signal = "neutral"
            if my_rest.get("is_b2b") and opp_rest.get("is_b2b"):
                conf_signal = "supports_under"
            elif my_rest.get("is_b2b") or opp_rest.get("is_b2b"):
                conf_signal = "supports_under"

            result[abbr.upper()] = {
                "is_b2b": my_rest.get("is_b2b", False),
                "days_rest": my_days,
                "last_game": my_rest.get("last_game"),
                "opponent": opp_abbr,
                "opponent_is_b2b": opp_rest.get("is_b2b", False),
                "rest_advantage": rest_adv,
                "stdev_adjustment": round(stdev_adj, 2),
                "confidence_signal": conf_signal,
            }

    return result


def get_team_rest(sport_key: str, team_abbr: str, game_date: str) -> dict | None:
    """Get rest data for a single team. Convenience wrapper."""
    data = prefetch_rest_data(sport_key, game_date)
    return data.get(team_abbr.upper())


# ── CLI for testing ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from rich import print as rprint
    from rich.table import Table
    from rich.console import Console

    sport = sys.argv[1] if len(sys.argv) > 1 else "basketball_nba"
    date = sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    rprint(f"\n[bold]Rest Day Report — {sport} — {date}[/bold]\n")

    data = prefetch_rest_data(sport, date)
    if not data:
        rprint("[yellow]No games found.[/yellow]")
        sys.exit(0)

    table = Table(show_lines=True)
    table.add_column("Team", style="cyan")
    table.add_column("B2B?", justify="center")
    table.add_column("Days Rest", justify="right")
    table.add_column("Last Game")
    table.add_column("vs", style="dim")
    table.add_column("Opp B2B?", justify="center")
    table.add_column("Rest Adv", justify="right")
    table.add_column("Stdev Adj", justify="right", style="bold")
    table.add_column("Signal", style="magenta")

    seen = set()
    for abbr, info in sorted(data.items()):
        if abbr in seen:
            continue
        seen.add(abbr)

        b2b = "[red]YES[/red]" if info["is_b2b"] else "no"
        opp_b2b = "[red]YES[/red]" if info["opponent_is_b2b"] else "no"
        adv = info["rest_advantage"]
        adv_style = "green" if adv > 0 else ("red" if adv < 0 else "dim")

        table.add_row(
            abbr,
            b2b,
            str(info["days_rest"]),
            info["last_game"] or "-",
            info["opponent"],
            opp_b2b,
            f"[{adv_style}]{adv:+d}[/{adv_style}]",
            f"{info['stdev_adjustment']:+.1f}",
            info["confidence_signal"],
        )

    Console().print(table)
