"""
pitcher_stats.py — Starting pitcher data from MLB Stats API.

Fetches probable pitchers for today's/tomorrow's games and their season stats
(ERA, FIP, WHIP, K/9, days rest). Used by edge_detector to adjust stdev and
confidence for MLB markets.

The MLB Stats API is free and requires no API key.

Usage:
    from pitcher_stats import get_game_pitchers

    # Returns pitcher data for a matchup on a given date
    pitchers = get_game_pitchers("NYY", "BOS", "2026-04-05")
"""

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import requests

log = logging.getLogger("pitcher_stats")
_TIMEOUT = 10
_BASE = "https://statsapi.mlb.com/api/v1"


# ── MLB Team ID Mapping ─────────────────────────────────────────────────────

# Kalshi uses 2-3 char abbreviations; MLB API uses numeric team IDs.
# We fetch the schedule by date and match teams by abbreviation.

# Common Kalshi ticker abbreviations -> MLB team names (for matching)
_KALSHI_ABBR_TO_MLB = {
    "ARI": "Arizona Diamondbacks", "ATL": "Atlanta Braves",
    "BAL": "Baltimore Orioles", "BOS": "Boston Red Sox",
    "CHC": "Chicago Cubs", "CHW": "Chicago White Sox",
    "CIN": "Cincinnati Reds", "CLE": "Cleveland Guardians",
    "COL": "Colorado Rockies", "DET": "Detroit Tigers",
    "HOU": "Houston Astros", "KC": "Kansas City Royals",
    "KCR": "Kansas City Royals",
    "LAA": "Los Angeles Angels", "LAD": "Los Angeles Dodgers",
    "MIA": "Miami Marlins", "MIL": "Milwaukee Brewers",
    "MIN": "Minnesota Twins", "NYM": "New York Mets",
    "NYY": "New York Yankees", "OAK": "Oakland Athletics",
    "PHI": "Philadelphia Phillies", "PIT": "Pittsburgh Pirates",
    "SD": "San Diego Padres", "SDP": "San Diego Padres",
    "SF": "San Francisco Giants", "SFG": "San Francisco Giants",
    "SEA": "Seattle Mariners", "STL": "St. Louis Cardinals",
    "TB": "Tampa Bay Rays", "TBR": "Tampa Bay Rays",
    "TEX": "Texas Rangers", "TOR": "Toronto Blue Jays",
    "WAS": "Washington Nationals", "WSH": "Washington Nationals",
}


# ── Pitcher Season Stats ────────────────────────────────────────────────────

def _fetch_pitcher_season_stats(person_id: int) -> dict | None:
    """Fetch a pitcher's current season stats from MLB Stats API."""
    try:
        resp = requests.get(
            f"{_BASE}/people/{person_id}",
            params={"hydrate": "currentTeam,stats(type=season,group=pitching)"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()

        person = data.get("people", [{}])[0]
        name = person.get("fullName", "Unknown")

        # Extract season pitching stats
        stats_groups = person.get("stats", [])
        season_stats = None
        for sg in stats_groups:
            if sg.get("type", {}).get("displayName") == "season":
                splits = sg.get("splits", [])
                if splits:
                    season_stats = splits[-1].get("stat", {})
                    break

        if not season_stats:
            return {"name": name, "person_id": person_id, "has_stats": False}

        era = float(season_stats.get("era", "99.99") or "99.99")
        whip = float(season_stats.get("whip", "9.99") or "9.99")
        innings = float(season_stats.get("inningsPitched", "0") or "0")
        strikeouts = int(season_stats.get("strikeOuts", 0) or 0)
        k_per_9 = (strikeouts / innings * 9) if innings > 0 else 0.0

        # FIP approximation: (13*HR + 3*BB - 2*K) / IP + constant (~3.10)
        hr = int(season_stats.get("homeRuns", 0) or 0)
        bb = int(season_stats.get("baseOnBalls", 0) or 0)
        hbp = int(season_stats.get("hitByPitch", 0) or 0)
        fip = ((13 * hr + 3 * (bb + hbp) - 2 * strikeouts) / innings + 3.10) if innings > 0 else 99.99

        games_started = int(season_stats.get("gamesStarted", 0) or 0)
        wins = int(season_stats.get("wins", 0) or 0)
        losses = int(season_stats.get("losses", 0) or 0)

        return {
            "name": name,
            "person_id": person_id,
            "has_stats": True,
            "era": round(era, 2),
            "fip": round(fip, 2),
            "whip": round(whip, 2),
            "k_per_9": round(k_per_9, 1),
            "innings_pitched": round(innings, 1),
            "games_started": games_started,
            "record": f"{wins}-{losses}",
        }
    except Exception as e:
        log.debug("Failed to fetch stats for pitcher %d: %s", person_id, e)
        return None


def _calculate_days_rest(person_id: int, game_date: str) -> int | None:
    """Calculate days since pitcher's last start."""
    try:
        # Look back 10 days for last start
        end_dt = datetime.strptime(game_date, "%Y-%m-%d")
        start_dt = end_dt - timedelta(days=10)
        resp = requests.get(
            f"{_BASE}/people/{person_id}/stats",
            params={
                "stats": "gameLog",
                "group": "pitching",
                "startDate": start_dt.strftime("%Y-%m-%d"),
                "endDate": (end_dt - timedelta(days=1)).strftime("%Y-%m-%d"),
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        splits = resp.json().get("stats", [{}])[0].get("splits", [])

        # Find most recent game where they were the starter
        for split in reversed(splits):
            stat = split.get("stat", {})
            if int(stat.get("gamesStarted", 0) or 0) > 0:
                game_dt_str = split.get("date", "")
                if game_dt_str:
                    last_start = datetime.strptime(game_dt_str, "%Y-%m-%d")
                    return (end_dt - last_start).days
        return None
    except Exception as e:
        log.debug("Failed to fetch game log for pitcher %d: %s", person_id, e)
        return None


# ── Schedule + Probable Pitchers ─────────────────────────────────────────────

@lru_cache(maxsize=4)
def _fetch_schedule(date: str) -> list[dict]:
    """Fetch MLB schedule with probable pitchers for a given date.

    Returns list of game dicts with away/home team info and probable pitchers.
    """
    try:
        resp = requests.get(
            f"{_BASE}/schedule",
            params={
                "date": date,
                "sportId": 1,
                "hydrate": "probablePitcher,team",
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        games = []
        for date_entry in resp.json().get("dates", []):
            for game in date_entry.get("games", []):
                away = game.get("teams", {}).get("away", {})
                home = game.get("teams", {}).get("home", {})
                games.append({
                    "game_pk": game.get("gamePk"),
                    "away_team": away.get("team", {}).get("name", ""),
                    "away_abbr": away.get("team", {}).get("abbreviation", ""),
                    "home_team": home.get("team", {}).get("name", ""),
                    "home_abbr": home.get("team", {}).get("abbreviation", ""),
                    "away_pitcher_id": away.get("probablePitcher", {}).get("id"),
                    "away_pitcher_name": away.get("probablePitcher", {}).get("fullName"),
                    "home_pitcher_id": home.get("probablePitcher", {}).get("id"),
                    "home_pitcher_name": home.get("probablePitcher", {}).get("fullName"),
                })
        return games
    except Exception as e:
        log.warning("MLB schedule fetch failed for %s: %s", date, e)
        return []


def _match_game(games: list[dict], team_abbr: str) -> dict | None:
    """Find a game involving the given team abbreviation."""
    abbr_upper = team_abbr.upper()
    for g in games:
        if g["away_abbr"].upper() == abbr_upper or g["home_abbr"].upper() == abbr_upper:
            return g
    # Fuzzy: try Kalshi abbreviation mapping
    mlb_name = _KALSHI_ABBR_TO_MLB.get(abbr_upper, "")
    if mlb_name:
        for g in games:
            if mlb_name in (g["away_team"], g["home_team"]):
                return g
    return None


# ── Public API ───────────────────────────────────────────────────────────────

def get_game_pitchers(team_abbr: str, game_date: str) -> dict | None:
    """Get starting pitcher data for a game involving the given team.

    Args:
        team_abbr: Team abbreviation (Kalshi-style, e.g., "NYY", "BOS")
        game_date: Game date as YYYY-MM-DD

    Returns dict with:
        away_pitcher: dict with name, ERA, FIP, WHIP, K/9, days_rest (or None)
        home_pitcher: dict with name, ERA, FIP, WHIP, K/9, days_rest (or None)
        matchup_quality: "ace_vs_ace" | "ace_vs_mid" | "mid_vs_mid" | "bullpen_day" | "unknown"
        stdev_adjustment: float (-0.3 to +0.5) to add to base MLB stdev
        confidence_signal: "supports_under" | "supports_over" | "neutral"
    """
    games = _fetch_schedule(game_date)
    if not games:
        return None

    game = _match_game(games, team_abbr)
    if not game:
        return None

    # Fetch stats for both probable pitchers
    away_stats = None
    home_stats = None

    if game.get("away_pitcher_id"):
        away_stats = _fetch_pitcher_season_stats(game["away_pitcher_id"])
        if away_stats and away_stats.get("has_stats"):
            away_stats["days_rest"] = _calculate_days_rest(
                game["away_pitcher_id"], game_date
            )
    if game.get("home_pitcher_id"):
        home_stats = _fetch_pitcher_season_stats(game["home_pitcher_id"])
        if home_stats and home_stats.get("has_stats"):
            home_stats["days_rest"] = _calculate_days_rest(
                game["home_pitcher_id"], game_date
            )

    # Classify matchup quality and compute adjustments
    matchup_quality, stdev_adj, confidence_signal = _classify_matchup(
        away_stats, home_stats
    )

    return {
        "away_pitcher": away_stats,
        "home_pitcher": home_stats,
        "away_team": game["away_abbr"],
        "home_team": game["home_abbr"],
        "matchup_quality": matchup_quality,
        "stdev_adjustment": stdev_adj,
        "confidence_signal": confidence_signal,
    }


def _pitcher_tier(stats: dict | None) -> str:
    """Classify a pitcher as 'ace', 'mid', or 'back'.

    Tiers based on ERA (primary) with FIP as tiebreaker:
        ace:  ERA <= 3.20 (or FIP <= 3.00 with ERA <= 3.50)
        mid:  ERA <= 4.50
        back: ERA > 4.50, or no stats / bullpen day
    """
    if not stats or not stats.get("has_stats"):
        return "back"
    era = stats.get("era", 99)
    fip = stats.get("fip", 99)
    ip = stats.get("innings_pitched", 0)

    # Need at least ~10 IP to trust the stats at all
    if ip < 10:
        return "back"
    if era <= 3.20 or (fip <= 3.00 and era <= 3.50):
        return "ace"
    if era <= 4.50:
        return "mid"
    return "back"


def _classify_matchup(
    away: dict | None, home: dict | None
) -> tuple[str, float, str]:
    """Classify the pitcher matchup and return adjustments.

    Returns:
        matchup_quality: descriptive label
        stdev_adjustment: float to add to base MLB total stdev
            negative = tighter game (aces), positive = higher variance (bad pitching)
        confidence_signal: for totals direction
    """
    away_tier = _pitcher_tier(away)
    home_tier = _pitcher_tier(home)

    tiers = sorted([away_tier, home_tier])  # alphabetical: ace < back < mid

    # Both aces: lower-scoring, tighter game -> reduce stdev, lean under
    if tiers == ["ace", "ace"]:
        return "ace_vs_ace", -0.3, "supports_under"

    # One ace, one mid: slightly below average scoring
    if tiers == ["ace", "mid"]:
        return "ace_vs_mid", -0.15, "supports_under"

    # Both mid-tier: average game, no adjustment
    if tiers == ["mid", "mid"]:
        return "mid_vs_mid", 0.0, "neutral"

    # One ace vs back-end: mixed, slight lean under from ace side
    if tiers == ["ace", "back"]:
        return "ace_vs_back", 0.1, "neutral"

    # One mid vs back-end: slightly elevated scoring
    if tiers == ["back", "mid"]:
        return "mid_vs_back", 0.2, "supports_over"

    # Both back-end / bullpen day: high-scoring, lean over
    if tiers == ["back", "back"]:
        return "bullpen_day", 0.5, "supports_over"

    # Fallback
    return "unknown", 0.0, "neutral"


# ── Bulk Pre-fetch ───────────────────────────────────────────────────────────

def prefetch_mlb_pitchers(game_date: str) -> dict[str, dict]:
    """Pre-fetch pitcher data for all MLB games on a date.

    Returns dict keyed by team abbreviation (both teams per game) -> pitcher data.
    This avoids redundant API calls when scanning many MLB markets.
    """
    games = _fetch_schedule(game_date)
    if not games:
        return {}

    result: dict[str, dict] = {}
    for game in games:
        # Fetch both pitchers
        away_stats = None
        home_stats = None

        if game.get("away_pitcher_id"):
            away_stats = _fetch_pitcher_season_stats(game["away_pitcher_id"])
            if away_stats and away_stats.get("has_stats"):
                away_stats["days_rest"] = _calculate_days_rest(
                    game["away_pitcher_id"], game_date
                )
        if game.get("home_pitcher_id"):
            home_stats = _fetch_pitcher_season_stats(game["home_pitcher_id"])
            if home_stats and home_stats.get("has_stats"):
                home_stats["days_rest"] = _calculate_days_rest(
                    game["home_pitcher_id"], game_date
                )

        matchup_quality, stdev_adj, confidence_signal = _classify_matchup(
            away_stats, home_stats
        )

        pitcher_data = {
            "away_pitcher": away_stats,
            "home_pitcher": home_stats,
            "away_team": game["away_abbr"],
            "home_team": game["home_abbr"],
            "matchup_quality": matchup_quality,
            "stdev_adjustment": stdev_adj,
            "confidence_signal": confidence_signal,
        }

        # Index by both team abbreviations
        result[game["away_abbr"].upper()] = pitcher_data
        result[game["home_abbr"].upper()] = pitcher_data

    return result


# ── CLI for testing ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from rich import print as rprint
    from rich.table import Table

    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rprint(f"\n[bold]MLB Probable Pitchers — {date}[/bold]\n")

    games = _fetch_schedule(date)
    if not games:
        rprint("[yellow]No games found.[/yellow]")
        sys.exit(0)

    table = Table(show_lines=True)
    table.add_column("Matchup", style="cyan")
    table.add_column("Away Pitcher")
    table.add_column("ERA", justify="right")
    table.add_column("FIP", justify="right")
    table.add_column("WHIP", justify="right")
    table.add_column("K/9", justify="right")
    table.add_column("Home Pitcher")
    table.add_column("ERA", justify="right")
    table.add_column("FIP", justify="right")
    table.add_column("WHIP", justify="right")
    table.add_column("K/9", justify="right")
    table.add_column("Matchup Type", style="magenta")
    table.add_column("Stdev Adj", justify="right", style="bold")

    pitchers = prefetch_mlb_pitchers(date)
    seen = set()
    for game in games:
        key = f"{game['away_abbr']}@{game['home_abbr']}"
        if key in seen:
            continue
        seen.add(key)

        data = pitchers.get(game["away_abbr"].upper())
        if not data:
            continue

        ap = data.get("away_pitcher") or {}
        hp = data.get("home_pitcher") or {}

        table.add_row(
            f"{game['away_abbr']} @ {game['home_abbr']}",
            ap.get("name", "TBD"),
            str(ap.get("era", "-")),
            str(ap.get("fip", "-")),
            str(ap.get("whip", "-")),
            str(ap.get("k_per_9", "-")),
            hp.get("name", "TBD"),
            str(hp.get("era", "-")),
            str(hp.get("fip", "-")),
            str(hp.get("whip", "-")),
            str(hp.get("k_per_9", "-")),
            data["matchup_quality"],
            f"{data['stdev_adjustment']:+.2f}",
        )

    from rich.console import Console
    Console().print(table)
