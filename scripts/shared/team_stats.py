"""
team_stats.py
Fetch team performance stats from free public APIs.

Provides recent form, win-loss records, and strength metrics for
NBA, NHL, and MLB teams. Used as a secondary signal alongside
sportsbook consensus odds.

All APIs are free with no key required.

Sources:
    - NBA/NCAAB: ESPN API (site.api.espn.com)
    - NHL: NHL Stats API (api-web.nhle.com)
    - MLB: MLB Stats API (statsapi.mlb.com)
"""

import logging
import requests
from functools import lru_cache

log = logging.getLogger("team_stats")

_CACHE_TTL = 300  # seconds — stats don't change mid-game
_TIMEOUT = 10


# ── ESPN (NBA, NCAAB) ───────────────────────────────────────────────────────

@lru_cache(maxsize=32)
def _espn_standings(sport: str, league: str) -> list[dict]:
    """Fetch ESPN standings for a sport/league."""
    try:
        url = f"http://site.api.espn.com/apis/v2/sports/{sport}/{league}/standings"
        resp = requests.get(url, timeout=_TIMEOUT)
        resp.raise_for_status()
        teams = []
        for group in resp.json().get("children", []):
            for entry in group.get("standings", {}).get("entries", []):
                team = entry.get("team", {})
                stats_map = {}
                for s in entry.get("stats", []):
                    stats_map[s.get("name", "")] = s.get("value", 0)
                teams.append({
                    "name": team.get("displayName", ""),
                    "abbr": team.get("abbreviation", ""),
                    "wins": int(stats_map.get("wins", 0)),
                    "losses": int(stats_map.get("losses", 0)),
                    "win_pct": stats_map.get("winPercent", 0),
                    "streak": stats_map.get("streak", 0),
                    "points_for": stats_map.get("pointsFor", 0),
                    "points_against": stats_map.get("pointsAgainst", 0),
                })
        return teams
    except Exception as e:
        log.warning("ESPN standings error for %s/%s: %s", sport, league, e)
        return []


def get_nba_team_stats(team_name: str) -> dict | None:
    """Get NBA team stats by name or abbreviation."""
    teams = _espn_standings("basketball", "nba")
    return _find_team(teams, team_name)


def get_ncaab_team_stats(team_name: str) -> dict | None:
    """Get NCAAB team stats by name or abbreviation."""
    teams = _espn_standings("basketball", "mens-college-basketball")
    return _find_team(teams, team_name)


def get_nfl_team_stats(team_name: str) -> dict | None:
    """Get NFL team stats by name or abbreviation."""
    teams = _espn_standings("football", "nfl")
    return _find_team(teams, team_name)


def get_ncaaf_team_stats(team_name: str) -> dict | None:
    """Get NCAAF team stats by name or abbreviation."""
    teams = _espn_standings("football", "college-football")
    return _find_team(teams, team_name)


# ── NHL API ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def _nhl_standings() -> list[dict]:
    """Fetch NHL standings from the official API."""
    try:
        resp = requests.get("https://api-web.nhle.com/v1/standings/now", timeout=_TIMEOUT)
        resp.raise_for_status()
        teams = []
        for t in resp.json().get("standings", []):
            teams.append({
                "name": t.get("teamName", {}).get("default", ""),
                "abbr": t.get("teamAbbrev", {}).get("default", ""),
                "wins": t.get("wins", 0),
                "losses": t.get("losses", 0),
                "ot_losses": t.get("otLosses", 0),
                "win_pct": t.get("pointPctg", 0),
                "goals_for": t.get("goalFor", 0),
                "goals_against": t.get("goalAgainst", 0),
                "goal_diff": t.get("goalDifferential", 0),
                "streak": t.get("streakCode", ""),
                "l10_wins": t.get("l10Wins", 0),
                "l10_losses": t.get("l10Losses", 0),
            })
        return teams
    except Exception as e:
        log.warning("NHL standings error: %s", e)
        return []


def get_nhl_team_stats(team_name: str) -> dict | None:
    """Get NHL team stats by name or abbreviation."""
    teams = _nhl_standings()
    return _find_team(teams, team_name)


# ── MLB API ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=4)
def _mlb_standings() -> list[dict]:
    """Fetch MLB standings from the official API."""
    try:
        resp = requests.get(
            "https://statsapi.mlb.com/api/v1/standings",
            params={"leagueId": "103,104", "hydrate": "team"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        teams = []
        for record in resp.json().get("records", []):
            for tr in record.get("teamRecords", []):
                team = tr.get("team", {})
                teams.append({
                    "name": team.get("name", ""),
                    "abbr": team.get("abbreviation", ""),
                    "wins": tr.get("wins", 0),
                    "losses": tr.get("losses", 0),
                    "win_pct": float(tr.get("winningPercentage", "0") or "0"),
                    "runs_scored": tr.get("runsScored", 0),
                    "runs_allowed": tr.get("runsAllowed", 0),
                    "run_diff": tr.get("runDifferential", 0),
                    "streak": tr.get("streak", {}).get("streakCode", ""),
                    "l10_wins": tr.get("records", {}).get("splitRecords", [{}])[0].get("wins", 0) if tr.get("records") else 0,
                })
        return teams
    except Exception as e:
        log.warning("MLB standings error: %s", e)
        return []


def get_mlb_team_stats(team_name: str) -> dict | None:
    """Get MLB team stats by name or abbreviation."""
    teams = _mlb_standings()
    return _find_team(teams, team_name)


# ── Lookup ───────────────────────────────────────────────────────────────────

def _find_team(teams: list[dict], query: str) -> dict | None:
    """Find a team by name or abbreviation (case-insensitive substring)."""
    q = query.lower().strip()
    for t in teams:
        if q == t.get("abbr", "").lower():
            return t
        if q in t.get("name", "").lower():
            return t
        if t.get("name", "").lower() in q:
            return t
    return None


def get_team_stats(team_name: str, sport: str) -> dict | None:
    """
    Unified lookup: get team stats for any supported sport.

    Args:
        team_name: Team name or abbreviation
        sport: 'nba', 'ncaab', 'nhl', 'mlb'
    """
    dispatch = {
        "nba": get_nba_team_stats,
        "basketball_nba": get_nba_team_stats,
        "ncaab": get_ncaab_team_stats,
        "basketball_ncaab": get_ncaab_team_stats,
        "nfl": get_nfl_team_stats,
        "americanfootball_nfl": get_nfl_team_stats,
        "ncaaf": get_ncaaf_team_stats,
        "americanfootball_ncaaf": get_ncaaf_team_stats,
        "nhl": get_nhl_team_stats,
        "icehockey_nhl": get_nhl_team_stats,
        "mlb": get_mlb_team_stats,
        "baseball_mlb": get_mlb_team_stats,
    }
    fn = dispatch.get(sport.lower())
    if fn:
        return fn(team_name)
    return None
