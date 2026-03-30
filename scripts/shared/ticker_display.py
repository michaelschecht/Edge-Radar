"""
ticker_display.py
Parse Kalshi tickers into human-readable labels (matchup, date, team pick).

Used by all display/report functions across the project.
"""

import re

# ── Team abbreviation lookup ──────────────────────────────────────────────────

MLB_TEAMS = {
    "ARI": "Arizona", "ATL": "Atlanta", "BAL": "Baltimore", "BOS": "Boston",
    "CHC": "Cubs", "CWS": "White Sox", "CIN": "Cincinnati", "CLE": "Cleveland",
    "COL": "Colorado", "DET": "Detroit", "HOU": "Houston", "KC": "Kansas City",
    "LAA": "LA Angels", "LAD": "LA Dodgers", "MIA": "Miami", "MIL": "Milwaukee",
    "MIN": "Minnesota", "NYM": "NY Mets", "NYY": "NY Yankees", "OAK": "Oakland",
    "PHI": "Philadelphia", "PIT": "Pittsburgh", "SD": "San Diego", "SF": "San Francisco",
    "SEA": "Seattle", "STL": "St. Louis", "TB": "Tampa Bay", "TEX": "Texas",
    "TOR": "Toronto", "WSH": "Washington",
}

NBA_TEAMS = {
    "ATL": "Hawks", "BOS": "Celtics", "BKN": "Nets", "CHA": "Hornets",
    "CHI": "Bulls", "CLE": "Cavs", "DAL": "Mavs", "DEN": "Nuggets",
    "DET": "Pistons", "GS": "Warriors", "HOU": "Rockets", "IND": "Pacers",
    "LAC": "Clippers", "LAL": "Lakers", "MEM": "Grizzlies", "MIA": "Heat",
    "MIL": "Bucks", "MIN": "Wolves", "NO": "Pelicans", "NY": "Knicks",
    "OKC": "Thunder", "ORL": "Magic", "PHI": "76ers", "PHX": "Suns",
    "POR": "Blazers", "SAC": "Kings", "SA": "Spurs", "TOR": "Raptors",
    "UTA": "Jazz", "WAS": "Wizards",
}

NHL_TEAMS = {
    "ANA": "Ducks", "ARI": "Coyotes", "BOS": "Bruins", "BUF": "Sabres",
    "CGY": "Flames", "CAR": "Hurricanes", "CHI": "Blackhawks", "COL": "Avalanche",
    "CBJ": "Blue Jackets", "DAL": "Stars", "DET": "Red Wings", "EDM": "Oilers",
    "FLA": "Panthers", "LA": "Kings", "MIN": "Wild", "MTL": "Canadiens",
    "NSH": "Predators", "NJ": "Devils", "NYI": "Islanders", "NYR": "Rangers",
    "OTT": "Senators", "PHI": "Flyers", "PIT": "Penguins", "SJ": "Sharks",
    "SEA": "Kraken", "STL": "Blues", "TB": "Lightning", "TOR": "Maple Leafs",
    "VAN": "Canucks", "VGK": "Golden Knights", "WPG": "Jets", "WSH": "Capitals",
}

# Merged lookup — MLB takes priority for shared abbreviations since it uses
# full city names which are clearer in mixed-sport displays.
TEAM_NAMES: dict[str, str] = {}
TEAM_NAMES.update(NHL_TEAMS)
TEAM_NAMES.update(NBA_TEAMS)
TEAM_NAMES.update(MLB_TEAMS)

# ── Ticker prefix to sport mapping ────────────────────────────────────────────

_SPORT_PREFIXES = {
    "KXMLBGAME": "mlb", "KXMLB": "mlb",
    "KXNBAGAME": "nba", "KXNBA": "nba",
    "KXNHLGAME": "nhl", "KXNHL": "nhl",
    "KXNFLGAME": "nfl", "KXNFL": "nfl",
    "KXNCAAMB": "ncaab", "KXNCAAF": "ncaaf",
    "KXSOCCER": "soccer", "KXMLS": "mls",
    "KXUFC": "ufc", "KXBOX": "boxing",
    "KXGOLF": "golf", "KXPGA": "golf",
    "KXNASCAR": "nascar", "KXIPL": "ipl",
    "KXESPORT": "esports",
}


def _detect_sport(ticker: str) -> str | None:
    """Return sport key from ticker prefix."""
    for prefix, sport in _SPORT_PREFIXES.items():
        if ticker.startswith(prefix):
            return sport
    return None


# ── Team code splitting ───────────────────────────────────────────────────────

def _split_team_codes(combined: str) -> tuple[str, str]:
    """Split a combined team code like CWSMIA into (CWS, MIA).

    Tries 3-char away first, then 2-char, matching against known abbreviations.
    """
    for away_len in (3, 2):
        away = combined[:away_len]
        home = combined[away_len:]
        if away in TEAM_NAMES and home in TEAM_NAMES:
            return away, home
    # Reverse: try home 3-char then 2-char
    for home_len in (3, 2):
        home = combined[-home_len:]
        away = combined[:-home_len]
        if away in TEAM_NAMES and home in TEAM_NAMES:
            return away, home
    return combined, ""


# ── Date/time extraction ─────────────────────────────────────────────────────

_MONTH_MAP = {
    "JAN": "Jan", "FEB": "Feb", "MAR": "Mar", "APR": "Apr",
    "MAY": "May", "JUN": "Jun", "JUL": "Jul", "AUG": "Aug",
    "SEP": "Sep", "OCT": "Oct", "NOV": "Nov", "DEC": "Dec",
}

# Pattern: KXPREFIX-YYMONDDHHMMTEAMS-PICK  (sports games)
_GAME_RE = re.compile(
    r"KX\w*GAME-(\d{2})([A-Z]{3})(\d{2})(\d{4})([A-Z]{4,8})-(.+)"
)

# Pattern for spreads/totals: KXPREFIX-YYMONDDHHMMTEAMS-STRIKE
_SPREAD_TOTAL_RE = re.compile(
    r"KX\w*(?:SPREAD|TOTAL)-(\d{2})([A-Z]{3})(\d{2})(\d{4})([A-Z]{4,8})-(.+)"
)

# Generic date pattern for non-sports (prediction markets, futures):
# KXPREFIX-YYMONDDHH... or KXPREFIX-YYMONDD...
_DATE_RE = re.compile(
    r"KX\w+-(\d{2})([A-Z]{3})(\d{2})"
)


def parse_game_datetime(ticker: str) -> str:
    """Extract a human-readable date/time string from a Kalshi ticker.

    Returns strings like:
      "Mar 30 6:40pm"   (sports games with time)
      "Mar 30"          (predictions/futures with date only)
      ""                (unparseable)
    """
    # Try game/spread/total pattern first (has time)
    m = _GAME_RE.match(ticker) or _SPREAD_TOTAL_RE.match(ticker)
    if m:
        _yy, mon, day, time_str = m.group(1), m.group(2), m.group(3), m.group(4)
        hh, mm = int(time_str[:2]), int(time_str[2:])
        ampm = "am" if hh < 12 else "pm"
        hh12 = hh if hh <= 12 else hh - 12
        if hh12 == 0:
            hh12 = 12
        mon_label = _MONTH_MAP.get(mon, mon.capitalize())
        return f"{mon_label} {int(day)} {hh12}:{mm:02d}{ampm}"

    # Fallback: just date
    m = _DATE_RE.match(ticker)
    if m:
        _yy, mon, day = m.group(1), m.group(2), m.group(3)
        mon_label = _MONTH_MAP.get(mon, mon.capitalize())
        return f"{mon_label} {int(day)}"

    return ""


def parse_matchup(ticker: str) -> str:
    """Parse a sports game ticker into a readable matchup.

    Example: KXMLBGAME-26MAR301840CWSMIA-MIA -> White Sox @ Miami
    Falls back to the raw ticker (trimmed) for non-game tickers.
    """
    m = _GAME_RE.match(ticker) or _SPREAD_TOTAL_RE.match(ticker)
    if not m:
        return ""

    teams_combined = m.group(5)
    away, home = _split_team_codes(teams_combined)
    if not home:
        return ""

    away_name = TEAM_NAMES.get(away, away)
    home_name = TEAM_NAMES.get(home, home)
    return f"{away_name} @ {home_name}"


def parse_pick_team(ticker: str) -> str:
    """Extract the picked team name from the ticker suffix.

    Example: KXMLBGAME-26MAR301840CWSMIA-MIA -> Miami
    """
    if "-" not in ticker:
        return ""
    pick_abbr = ticker.rsplit("-", 1)[-1]
    return TEAM_NAMES.get(pick_abbr, pick_abbr)


def format_bet_label(ticker: str, title: str) -> str:
    """Best-effort human-readable bet label.

    Tries matchup parsing first, falls back to the Kalshi title.
    """
    matchup = parse_matchup(ticker)
    if matchup:
        return matchup
    # Strip common Kalshi title suffixes for brevity
    label = title.replace(" Winner?", "").replace(" (vs ", " | ").rstrip(")")
    return label[:45]


# ── Date filtering ────────────────────────────────────────────────────────────

_MONTH_NUM = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def extract_ticker_date(ticker: str) -> str | None:
    """Extract the date from a ticker as YYYY-MM-DD string.

    Example: KXMLBGAME-26MAR301840CWSMIA-MIA -> 2026-03-30
    Returns None if no date can be parsed.
    """
    m = _DATE_RE.match(ticker)
    if not m:
        return None
    yy, mon, day = m.group(1), m.group(2), m.group(3)
    mon_num = _MONTH_NUM.get(mon)
    if not mon_num:
        return None
    return f"20{yy}-{mon_num:02d}-{int(day):02d}"


def resolve_date_arg(date_str: str) -> str:
    """Resolve a user-provided date argument to YYYY-MM-DD.

    Accepts:
      "today", "tomorrow"
      "YYYY-MM-DD" (e.g., "2026-03-31")
      "MM-DD" (e.g., "03-31", assumes current year)
      "MonDD" (e.g., "mar31", "Apr02")
    """
    from datetime import date, timedelta

    low = date_str.strip().lower()

    if low == "today":
        return date.today().isoformat()
    if low == "tomorrow":
        return (date.today() + timedelta(days=1)).isoformat()

    # YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # MM-DD
    m = re.match(r"^(\d{1,2})-(\d{1,2})$", date_str)
    if m:
        mon, day = int(m.group(1)), int(m.group(2))
        return f"{date.today().year}-{mon:02d}-{day:02d}"

    # MonDD (e.g., mar31, Apr02)
    m = re.match(r"^([a-zA-Z]{3})(\d{1,2})$", low)
    if m:
        mon_name, day = m.group(1).upper(), int(m.group(2))
        mon_num = _MONTH_NUM.get(mon_name)
        if mon_num:
            return f"{date.today().year}-{mon_num:02d}-{day:02d}"

    return date_str  # pass through as-is


def filter_by_date(opportunities: list, target_date: str) -> list:
    """Filter opportunities to only those matching a specific date.

    Args:
        opportunities: list of Opportunity objects (must have .ticker attr)
        target_date: YYYY-MM-DD string (already resolved via resolve_date_arg)

    Returns filtered list.
    """
    result = []
    for opp in opportunities:
        ticker = opp.ticker if hasattr(opp, "ticker") else opp.get("ticker", "")
        opp_date = extract_ticker_date(ticker)
        if opp_date == target_date:
            result.append(opp)
    return result


def filter_exclude_tickers(opportunities: list, exclude_tickers: set[str]) -> list:
    """Remove opportunities whose ticker is in the exclude set.

    For --exclude-open: pass in the set of tickers with open positions.
    Matches on the event portion of the ticker (before the last hyphen)
    so that betting YES on a game also excludes the NO side of the same game.
    """
    # Build a set of event keys (ticker without the pick suffix)
    exclude_events = set()
    for t in exclude_tickers:
        # KXMLBGAME-26MAR301840CWSMIA-MIA -> KXMLBGAME-26MAR301840CWSMIA
        parts = t.rsplit("-", 1)
        exclude_events.add(parts[0] if len(parts) > 1 else t)

    result = []
    for opp in opportunities:
        ticker = opp.ticker if hasattr(opp, "ticker") else opp.get("ticker", "")
        parts = ticker.rsplit("-", 1)
        event_key = parts[0] if len(parts) > 1 else ticker
        if event_key not in exclude_events:
            result.append(opp)
    return result
