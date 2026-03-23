"""
edge_detector.py
Scans Kalshi markets for +EV opportunities by comparing market prices
against estimated fair probabilities from external data sources.

Usage:
    python scripts/edge_detector.py scan
    python scripts/edge_detector.py scan --min-edge 0.05 --category game
    python scripts/edge_detector.py scan --top 10
    python scripts/edge_detector.py detail KXMLBGAME-26MAR261315PITNYM-PIT

Edge sources:
    - Sports game outcomes: cross-reference sportsbook consensus odds via The Odds API
    - Spreads/totals: compare Kalshi strike to sportsbook lines
    - Player props: base-rate analysis from sportsbook prop odds
    - Other markets: simple liquidity/spread analysis

Requires: ODDS_API_KEY in .env for sports edge detection.
"""

import os
import re
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import asdict

# Shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401 -- configures sys.path
from opportunity import Opportunity

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from kalshi_client import KalshiClient

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
log = logging.getLogger("edge_detector")
console = Console()

from odds_api import get_current_key, rotate_key, report_remaining
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

MIN_EDGE = float(os.getenv("MIN_EDGE_THRESHOLD", "0.03"))
OPPORTUNITIES_PATH = paths.SPORTS_OPPORTUNITIES_PATH


# ── Market Categorization ────────────────────────────────────────────────────

# Map Kalshi ticker prefixes to categories
CATEGORY_MAP = {
    "KXMLBGAME":     "game",
    "KXNHLGAME":     "game",
    "KXNBAGAME":     "game",
    "KXNCAABBGAME":  "game",
    "KXNCAAMBGAME":  "game",
    "KXNCAAFBGAME":  "game",
    "KXNBASPREAD":   "spread",
    "KXNHLSPREAD":   "spread",
    "KXNCAAMBSPREAD":"spread",
    "KXNHLTOTAL":    "total",
    "KXNBATOTAL":    "total",
    "KXNCAAMBTOTAL": "total",
    "KXNHLGOAL":     "player_prop",
    "KXNHLPTS":      "player_prop",
    "KXNHLAST":      "player_prop",
    "KXNHLFIRSTGOAL":"player_prop",
    "KXNBABLK":      "player_prop",
    "KXNBAMENTION":  "mention",
    "KXFOXNEWSMENTION": "mention",
    "KXPOLITICSMENTION":"mention",
    "KXLASTWORDCOUNT":"mention",
    "KXCS2MAP":      "esports",
    "KXCS2GAME":     "esports",
    "KXLOLMAP":      "esports",
    "KXLOLGAME":     "esports",
}

# Map Kalshi ticker prefixes to Odds API sport keys
KALSHI_TO_ODDS_SPORT = {
    "KXMLBGAME":    "baseball_mlb",
    "KXNHLGAME":    "icehockey_nhl",
    "KXNBAGAME":    "basketball_nba",
    "KXNBASPREAD":  "basketball_nba",
    "KXNBATOTAL":   "basketball_nba",
    "KXNCAABBGAME": "basketball_ncaab",
    "KXNCAAMBGAME": "basketball_ncaab",
    "KXNCAAMBSPREAD":"basketball_ncaab",
    "KXNCAAMBTOTAL": "basketball_ncaab",
    "KXNHLTOTAL":   "icehockey_nhl",
    "KXNHLSPREAD":  "icehockey_nhl",
}


def categorize_market(ticker: str) -> str:
    """Determine market category from ticker prefix."""
    for prefix, cat in CATEGORY_MAP.items():
        if ticker.startswith(prefix):
            return cat
    return "other"


# ── Odds API Integration ─────────────────────────────────────────────────────

_odds_cache: dict[str, list] = {}


def fetch_odds_api(sport_key: str, markets: str = "h2h") -> list:
    """Fetch odds from The Odds API with caching and key rotation."""
    api_key = get_current_key()
    if not api_key:
        return []

    cache_key = f"{sport_key}:{markets}"
    if cache_key in _odds_cache:
        return _odds_cache[cache_key]

    # Try current key, rotate on failure
    for attempt in range(3):
        try:
            resp = requests.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "us",
                    "markets": markets,
                    "oddsFormat": "decimal",
                    "dateFormat": "iso",
                },
                timeout=15,
            )
            if resp.status_code == 401 or resp.status_code == 429:
                # Key exhausted or invalid -- try rotating
                new_key = rotate_key("http_" + str(resp.status_code))
                if new_key:
                    api_key = new_key
                    continue
                else:
                    log.warning("All Odds API keys exhausted")
                    return []

            resp.raise_for_status()
            remaining = resp.headers.get("x-requests-remaining", "?")
            log.info("Odds API: %s events, %s requests remaining", len(resp.json()), remaining)

            # Track remaining for this key
            try:
                report_remaining(api_key, int(remaining))
            except (ValueError, TypeError):
                pass

            _odds_cache[cache_key] = resp.json()
            return resp.json()
        except Exception as e:
            log.warning("Odds API error for %s: %s", sport_key, e)
            return []

    return []


def implied_prob(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    if decimal_odds <= 1.0:
        return 1.0
    return 1.0 / decimal_odds


def devig_two_way(prob_a: float, prob_b: float) -> tuple[float, float]:
    """Remove vig from two-outcome market (power method)."""
    total = prob_a + prob_b
    if total == 0:
        return 0.5, 0.5
    return prob_a / total, prob_b / total


def consensus_fair_value(events: list, team_name: str) -> tuple[float, dict] | None:
    """
    Calculate consensus fair probability for a team across all bookmakers.
    Uses median of de-vigged probabilities for robustness.
    """
    fair_probs = []
    book_details = {}

    for event in events:
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market["key"] != "h2h":
                    continue
                outcomes = market.get("outcomes", [])
                if len(outcomes) != 2:
                    continue

                # Find if this team matches
                matched_idx = None
                for i, o in enumerate(outcomes):
                    if _team_match(o["name"], team_name):
                        matched_idx = i
                        break

                if matched_idx is None:
                    continue

                other_idx = 1 - matched_idx
                prob_team = implied_prob(outcomes[matched_idx]["price"])
                prob_other = implied_prob(outcomes[other_idx]["price"])
                fair_team, _ = devig_two_way(prob_team, prob_other)
                fair_probs.append(fair_team)
                book_details[bookmaker["key"]] = {
                    "raw_odds": outcomes[matched_idx]["price"],
                    "implied": round(prob_team, 4),
                    "devigged": round(fair_team, 4),
                }

    if not fair_probs:
        return None

    # Use median for robustness against outlier books
    fair_probs.sort()
    n = len(fair_probs)
    median_fair = fair_probs[n // 2] if n % 2 else (fair_probs[n // 2 - 1] + fair_probs[n // 2]) / 2

    return median_fair, {
        "n_books": len(fair_probs),
        "median_fair": round(median_fair, 4),
        "min_fair": round(min(fair_probs), 4),
        "max_fair": round(max(fair_probs), 4),
        "books": book_details,
    }


def consensus_spread_prob(events: list, team_name: str, strike: float) -> tuple[float, dict] | None:
    """Estimate probability of a team winning by > strike points using sportsbook spreads."""
    spread_data = []

    for event in events:
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market["key"] != "spreads":
                    continue
                for o in market.get("outcomes", []):
                    if _team_match(o["name"], team_name):
                        book_spread = o.get("point", 0)
                        book_odds = o.get("price", 2.0)
                        spread_data.append({
                            "book": bookmaker["key"],
                            "spread": book_spread,
                            "odds": book_odds,
                            "implied": round(implied_prob(book_odds), 4),
                        })

    if not spread_data:
        return None

    # If Kalshi strike is different from book spread, adjust probability
    # Simple linear adjustment: ~3% per point of spread difference (sport-dependent)
    adj_per_point = 0.03  # reasonable for NBA/NFL
    median_spread = sorted(s["spread"] for s in spread_data)[len(spread_data) // 2]
    median_implied = sorted(s["implied"] for s in spread_data)[len(spread_data) // 2]

    # Kalshi asks "wins by > strike" which is equivalent to spread of -strike
    # If book spread is -5.5 and Kalshi asks "wins by > 1.5", team covers more easily
    spread_diff = abs(median_spread) - strike  # positive = Kalshi is easier to cover
    adjusted_prob = median_implied + (spread_diff * adj_per_point)
    adjusted_prob = max(0.01, min(0.99, adjusted_prob))

    return adjusted_prob, {
        "n_books": len(spread_data),
        "median_book_spread": median_spread,
        "kalshi_strike": strike,
        "spread_diff": round(spread_diff, 1),
        "raw_median_implied": round(median_implied, 4),
        "adjusted_prob": round(adjusted_prob, 4),
        "books": spread_data[:5],  # top 5 for brevity
    }


def consensus_total_prob(events: list, strike: float) -> tuple[float, dict] | None:
    """Estimate probability of total going over strike using sportsbook totals."""
    total_data = []

    for event in events:
        for bookmaker in event.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market["key"] != "totals":
                    continue
                for o in market.get("outcomes", []):
                    if o["name"] == "Over":
                        total_data.append({
                            "book": bookmaker["key"],
                            "line": o.get("point", 0),
                            "odds": o.get("price", 2.0),
                            "implied": round(implied_prob(o["price"]), 4),
                        })

    if not total_data:
        return None

    median_line = sorted(t["line"] for t in total_data)[len(total_data) // 2]
    median_implied = sorted(t["implied"] for t in total_data)[len(total_data) // 2]

    # Adjust for Kalshi strike vs book total line
    adj_per_point = 0.04  # goals/runs are lower-scoring, each point matters more
    line_diff = median_line - strike  # positive = Kalshi strike is lower (easier over)
    adjusted_prob = median_implied + (line_diff * adj_per_point)
    adjusted_prob = max(0.01, min(0.99, adjusted_prob))

    return adjusted_prob, {
        "n_books": len(total_data),
        "median_book_line": median_line,
        "kalshi_strike": strike,
        "line_diff": round(line_diff, 1),
        "adjusted_prob": round(adjusted_prob, 4),
        "books": total_data[:5],
    }


# ── Team Name Matching ────────────────────────────────────────────────────────

# Common mappings between Kalshi team names and Odds API team names
TEAM_ALIASES = {
    "new york y": ["new york yankees", "ny yankees", "yankees"],
    "new york m": ["new york mets", "ny mets", "mets"],
    "la kings": ["los angeles kings", "la kings"],
    "la lakers": ["los angeles lakers", "la lakers"],
    "la clippers": ["los angeles clippers", "la clippers"],
    "la dodgers": ["los angeles dodgers", "la dodgers"],
    "los angeles a": ["los angeles angels", "la angels", "anaheim angels"],
    "sf": ["san francisco giants", "san francisco"],
    "okc": ["oklahoma city thunder", "oklahoma city"],
    "oklahoma city": ["oklahoma city thunder"],
    "brooklyn": ["brooklyn nets"],
    "pittsburgh": ["pittsburgh pirates"],
    "houston": ["houston astros", "houston rockets", "houston texans"],
    "dallas": ["dallas stars", "dallas mavericks", "dallas cowboys"],
    "colorado": ["colorado avalanche"],
    "buffalo": ["buffalo sabres"],
    "los angeles": ["los angeles kings", "la kings", "los angeles lakers"],
    "atlanta": ["atlanta hawks", "atlanta braves"],
    "st. louis": ["st louis blues", "st. louis blues"],
    "calgary": ["calgary flames"],
    "navy": ["navy midshipmen"],
}


def _team_match(odds_api_name: str, kalshi_name: str) -> bool:
    """Fuzzy match between Odds API team name and Kalshi team reference."""
    odds_lower = odds_api_name.lower().strip()
    kalshi_lower = kalshi_name.lower().strip()

    # Direct substring match
    if kalshi_lower in odds_lower or odds_lower in kalshi_lower:
        return True

    # Check aliases
    for alias_key, alias_list in TEAM_ALIASES.items():
        if kalshi_lower.startswith(alias_key) or alias_key.startswith(kalshi_lower):
            if any(a in odds_lower or odds_lower in a for a in alias_list):
                return True

    # Last-word match (city name to full name)
    kalshi_words = kalshi_lower.split()
    odds_words = odds_lower.split()
    if kalshi_words and odds_words:
        if kalshi_words[0] in odds_words or kalshi_words[-1] in odds_words:
            return True

    return False


# ── Extract Info from Kalshi Market ───────────────────────────────────────────

def extract_team_from_market(market: dict) -> str | None:
    """Extract the team name this market resolves YES for."""
    # Try subtitle fields
    for field in ["subtitle", "yes_sub_title", "no_sub_title", "title"]:
        val = market.get(field, "")
        if val and len(val) > 1 and val.lower() not in ("yes", "no"):
            return val

    # Try rules
    rules = market.get("rules_primary", "")
    match = re.search(r"If (.+?) wins", rules)
    if match:
        return match.group(1)

    return None


def extract_event_teams(market: dict) -> tuple[str, str] | None:
    """Extract both team names from the event ticker or rules."""
    rules = market.get("rules_primary", "")
    # Pattern: "Team A vs Team B" or "Team A at Team B" (multiple context words)
    match = re.search(
        r"the (.+?) (?:vs\.?|at) (.+?) (?:professional|college|men's college|women's college|NCAA|MLB|NBA|NHL|NFL|MLS)",
        rules, re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(), match.group(2).strip()
    # Fallback: simpler pattern
    match = re.search(r"in the (.+?) (?:vs\.?|at) (.+?) (?:game|match)", rules, re.IGNORECASE)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None


def get_display_title(market: dict) -> str:
    """Build a display-friendly title that always includes both teams.

    For spreads/totals where the title only shows one team,
    extracts the matchup from rules_primary or event_ticker.
    """
    title = market.get("title", "")

    # Game markets already show the matchup ("Team A at Team B Winner?")
    if " at " in title and "Winner" in title:
        return title

    # Total markets usually show matchup ("Team A at Team B: Total Points")
    if "Total Points" in title and " at " in title:
        return title

    # Spread markets need the opponent added
    teams = extract_event_teams(market)
    if teams:
        team_a, team_b = teams
        # title is like "UCLA wins by over 11.5 Points?"
        # Make it: "UCLA wins by over 11.5 Pts? (vs UConn)"
        # Figure out which team is in the title
        title_lower = title.lower()
        if team_a.lower() in title_lower:
            opponent = team_b
        elif team_b.lower() in title_lower:
            opponent = team_a
        else:
            opponent = f"{team_a} vs {team_b}"
        return f"{title} (vs {opponent})"

    return title


def extract_strike(market: dict) -> float | None:
    """Extract the strike/threshold from spread or total markets."""
    strike = market.get("floor_strike")
    if strike is not None:
        return float(strike)

    # Try parsing from title/rules
    rules = market.get("rules_primary", "")
    match = re.search(r"(?:over|by more than) ([\d.]+)", rules, re.IGNORECASE)
    if match:
        return float(match.group(1))

    return None


# ── Core Edge Detection ──────────────────────────────────────────────────────

def detect_edge_game(market: dict, odds_events: list) -> Opportunity | None:
    """Detect edge on game outcome markets (moneyline)."""
    ticker = market["ticker"]
    team = extract_team_from_market(market)
    if not team:
        return None

    yes_ask = float(market.get("yes_ask_dollars", "0"))
    no_ask = float(market.get("no_ask_dollars", "0"))
    yes_bid = float(market.get("yes_bid_dollars", "0"))

    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    result = consensus_fair_value(odds_events, team)
    if result is None:
        return None

    fair_value, details = result
    edge = fair_value - yes_ask

    # Also check the NO side
    no_fair = 1.0 - fair_value
    no_edge = no_fair - no_ask if no_ask > 0 and no_ask < 1.0 else -1

    # Pick the better side
    if no_edge > edge and no_edge > 0:
        side = "no"
        market_price = no_ask
        fair = no_fair
        edge = no_edge
    else:
        side = "yes"
        market_price = yes_ask
        fair = fair_value

    spread = yes_ask - yes_bid
    liquidity = max(0, 10 - (spread * 20))  # tighter spread = higher score

    confidence = "low"
    if details["n_books"] >= 5:
        confidence = "medium"
    if details["n_books"] >= 8 and (details["max_fair"] - details["min_fair"]) < 0.05:
        confidence = "high"

    composite = (
        min(edge / 0.01, 10) * 0.40 +      # edge strength (40%)
        {"low": 3, "medium": 6, "high": 9}[confidence] * 0.30 +  # confidence (30%)
        liquidity * 0.20 +                   # liquidity (20%)
        5 * 0.10                             # time sensitivity placeholder (10%)
    )

    return Opportunity(
        ticker=ticker,
        title=get_display_title(market) or f"{team} to win",
        category="game",
        side=side,
        market_price=round(market_price, 4),
        fair_value=round(fair, 4),
        edge=round(edge, 4),
        edge_source="odds_api_consensus",
        confidence=confidence,
        liquidity_score=round(liquidity, 1),
        composite_score=round(composite, 1),
        details=details,
    )


def detect_edge_spread(market: dict, odds_events: list) -> Opportunity | None:
    """Detect edge on spread markets."""
    ticker = market["ticker"]
    team = extract_team_from_market(market)
    strike = extract_strike(market)
    if not team or strike is None:
        return None

    yes_ask = float(market.get("yes_ask_dollars", "0"))
    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    result = consensus_spread_prob(odds_events, team, strike)
    if result is None:
        return None

    fair_value, details = result
    edge = fair_value - yes_ask

    # Check NO side too
    no_ask = float(market.get("no_ask_dollars", "0"))
    no_fair = 1.0 - fair_value
    no_edge = no_fair - no_ask if 0 < no_ask < 1.0 else -1

    if no_edge > edge and no_edge > 0:
        side = "no"
        market_price = no_ask
        fair = no_fair
        edge = no_edge
    else:
        side = "yes"
        market_price = yes_ask
        fair = fair_value

    yes_bid = float(market.get("yes_bid_dollars", "0"))
    spread = yes_ask - yes_bid
    liquidity = max(0, 10 - (spread * 20))

    confidence = "low" if details["n_books"] < 3 else "medium" if details["n_books"] < 6 else "high"

    composite = (
        min(edge / 0.01, 10) * 0.40 +
        {"low": 3, "medium": 6, "high": 9}[confidence] * 0.30 +
        liquidity * 0.20 +
        5 * 0.10
    )

    return Opportunity(
        ticker=ticker,
        title=get_display_title(market) or f"{team} ({strike})",
        category="spread",
        side=side,
        market_price=round(market_price, 4),
        fair_value=round(fair, 4),
        edge=round(edge, 4),
        edge_source="odds_api_spread_adjusted",
        confidence=confidence,
        liquidity_score=round(liquidity, 1),
        composite_score=round(composite, 1),
        details=details,
    )


def detect_edge_total(market: dict, odds_events: list) -> Opportunity | None:
    """Detect edge on over/under total markets."""
    ticker = market["ticker"]
    strike = extract_strike(market)
    if strike is None:
        return None

    yes_ask = float(market.get("yes_ask_dollars", "0"))
    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    result = consensus_total_prob(odds_events, strike)
    if result is None:
        return None

    fair_value, details = result
    edge = fair_value - yes_ask

    no_ask = float(market.get("no_ask_dollars", "0"))
    no_fair = 1.0 - fair_value
    no_edge = no_fair - no_ask if 0 < no_ask < 1.0 else -1

    if no_edge > edge and no_edge > 0:
        side = "no"
        market_price = no_ask
        fair = no_fair
        edge = no_edge
    else:
        side = "yes"
        market_price = yes_ask
        fair = fair_value

    yes_bid = float(market.get("yes_bid_dollars", "0"))
    spread = yes_ask - yes_bid
    liquidity = max(0, 10 - (spread * 20))

    confidence = "low" if details["n_books"] < 3 else "medium"

    composite = (
        min(edge / 0.01, 10) * 0.40 +
        {"low": 3, "medium": 6, "high": 9}[confidence] * 0.30 +
        liquidity * 0.20 +
        5 * 0.10
    )

    return Opportunity(
        ticker=ticker,
        title=get_display_title(market) or f"O/U {strike}",
        category="total",
        side=side,
        market_price=round(market_price, 4),
        fair_value=round(fair, 4),
        edge=round(edge, 4),
        edge_source="odds_api_total_adjusted",
        confidence=confidence,
        liquidity_score=round(liquidity, 1),
        composite_score=round(composite, 1),
        details=details,
    )


def detect_edge_spread_analysis(market: dict) -> Opportunity | None:
    """
    Fallback edge detection based purely on market microstructure.
    No external data needed -- flags markets where bid/ask spread
    suggests mispricing (e.g., wide spreads with prices far from 0.50).
    """
    yes_ask = float(market.get("yes_ask_dollars", "0"))
    yes_bid = float(market.get("yes_bid_dollars", "0"))
    no_ask = float(market.get("no_ask_dollars", "0"))

    if yes_ask <= 0 or yes_ask >= 1.0 or yes_bid <= 0:
        return None

    spread = yes_ask - yes_bid
    midpoint = (yes_ask + yes_bid) / 2

    # Only flag if spread is tight (< $0.05) — indicates some price discovery
    if spread > 0.05:
        return None

    # Markets priced near extremes with tight spreads may indicate strong consensus
    # Not really an "edge" but useful for monitoring
    return None  # Disabled for now — only activate with external data


# ── Main Scanner ──────────────────────────────────────────────────────────────

# Named ticker prefix shortcuts for --filter
FILTER_SHORTCUTS = {
    # --- US Major Leagues ---
    "nba":     ["KXNBAGAME", "KXNBASPREAD", "KXNBATOTAL", "KXNBABLK", "KXNBA3PT", "KXNBAREB", "KXNBAAST", "KXNBASTL", "KXNBAPTS", "KXNBAMVP", "KXNBAROY", "KXNBADPOY"],
    "nhl":     ["KXNHLGAME", "KXNHLSPREAD", "KXNHLTOTAL", "KXNHLGOAL", "KXNHLPTS", "KXNHLAST", "KXNHLFIRSTGOAL", "KXNHLHART", "KXNHLNORRIS", "KXNHLCALDER"],
    "mlb":     ["KXMLBGAME", "KXMLBPLAYOFFS"],
    "nfl":     ["KXNFLGAME", "KXNFLSPREAD", "KXNFLTOTAL", "KXNFLDRAFT"],
    # --- College Sports ---
    "ncaamb":  ["KXNCAAMBGAME", "KXNCAAMBSPREAD", "KXNCAAMBTOTAL", "KXNCAAMBMOP"],
    "ncaabb":  ["KXNCAABBGAME"],
    "ncaawb":  ["KXNCAAWBGAME"],
    "ncaafb":  ["KXNCAAFBGAME"],
    # --- Soccer / Football ---
    "mls":     ["KXMLSGAME", "KXMLSSPREAD", "KXMLSTOTAL"],
    "ucl":     ["KXUCL"],
    "epl":     ["KXEPL"],
    "laliga":  ["KXLALIGA"],
    "seriea":  ["KXSERIEA"],
    "bundesliga": ["KXBUNDESLIGA"],
    "ligue1":  ["KXLIGUE1"],
    "soccer":  ["KXMLSGAME", "KXMLSSPREAD", "KXMLSTOTAL", "KXUCL", "KXEPL", "KXLALIGA", "KXSERIEA", "KXBUNDESLIGA", "KXLIGUE1"],
    # --- Combat Sports ---
    "ufc":     ["KXUFCFIGHT"],
    "boxing":  ["KXBOXING"],
    # --- Motorsports ---
    "f1":      ["KXF1", "KXF1CONSTRUCTORS"],
    "nascar":  ["KXNASCARRACE"],
    # --- Golf ---
    "pga":     ["KXPGATOUR"],
    # --- Cricket ---
    "ipl":     ["KXIPL"],
    # --- Esports ---
    "cs2":     ["KXCS2MAP", "KXCS2GAME"],
    "lol":     ["KXLOLMAP", "KXLOLGAME"],
    "esports": ["KXCS2MAP", "KXCS2GAME", "KXLOLMAP", "KXLOLGAME"],
    # --- Futures (routed to futures_edge.py) ---
    "futures":       ["__FUTURES__"],
    "nfl-futures":   ["__FUTURES__nfl-futures"],
    "superbowl":     ["__FUTURES__nfl-futures"],
    "nba-futures":   ["__FUTURES__nba-futures"],
    "nhl-futures":   ["__FUTURES__nhl-futures"],
    "mlb-futures":   ["__FUTURES__mlb-futures"],
    "ncaab-futures": ["__FUTURES__ncaab-futures"],
    "golf-futures":  ["__FUTURES__golf-futures"],
}


def scan_all_markets(
    client: KalshiClient,
    min_edge: float = MIN_EDGE,
    category_filter: str | None = None,
    ticker_filter: str | None = None,
    top_n: int = 20,
) -> list[Opportunity]:
    """
    Scan all open Kalshi markets and score them for edge.

    Args:
        ticker_filter: Filter markets by ticker prefix. Can be a shortcut name
                       (ncaamb, nba, nhl, mlb, esports) or a raw prefix like "KXNCAAMB".

    Returns list of Opportunity objects sorted by composite score.
    """
    # Resolve ticker filter
    filter_prefixes = None
    if ticker_filter:
        shortcut = ticker_filter.lower()

        # Route futures filters to the dedicated futures scanner
        if shortcut in FILTER_SHORTCUTS and FILTER_SHORTCUTS[shortcut][0].startswith("__FUTURES__"):
            from futures_edge import scan_futures_markets
            futures_filter = shortcut if shortcut != "futures" else None
            return scan_futures_markets(client, min_edge=min_edge,
                                        ticker_filter=futures_filter, top_n=top_n)

        if shortcut in FILTER_SHORTCUTS:
            filter_prefixes = FILTER_SHORTCUTS[shortcut]
            rprint(f"[bold]Filter: {shortcut} -> {', '.join(filter_prefixes)}[/bold]")
        else:
            filter_prefixes = [ticker_filter.upper()]
            rprint(f"[bold]Filter: ticker prefix {filter_prefixes[0]}[/bold]")

    # 1. Fetch markets from Kalshi
    rprint("[bold]Fetching Kalshi markets...[/bold]")

    if filter_prefixes:
        # Fetch directly by series ticker -- much faster and finds markets
        # that would be buried beyond page 5 of a full scan
        all_markets = []
        for prefix in filter_prefixes:
            cursor = None
            for _ in range(5):
                resp = client.get_markets(limit=1000, status="open", series_ticker=prefix, cursor=cursor)
                batch = resp.get("markets", [])
                all_markets.extend(batch)
                cursor = resp.get("cursor", "")
                if not cursor:
                    break
        rprint(f"  Found {len(all_markets)} markets for {', '.join(filter_prefixes)}")
    else:
        # No filter: scan all known sport prefixes that have edge detection support.
        # A generic scan returns 5000+ multi-event markets that bury the actual sports.
        all_sport_prefixes = set()
        for prefix in KALSHI_TO_ODDS_SPORT:
            all_sport_prefixes.add(prefix)
        rprint("[bold]No filter -- scanning all supported sport prefixes...[/bold]")
        all_markets = []
        for prefix in sorted(all_sport_prefixes):
            cursor = None
            for _ in range(3):
                resp = client.get_markets(limit=1000, status="open", series_ticker=prefix, cursor=cursor)
                batch = resp.get("markets", [])
                all_markets.extend(batch)
                cursor = resp.get("cursor", "")
                if not cursor:
                    break
        rprint(f"  Found {len(all_markets)} markets across {len(all_sport_prefixes)} sport prefixes")

    # Remove markets past their expected expiration (game already started/ended)
    now = datetime.now(timezone.utc).isoformat()
    before = len(all_markets)
    all_markets = [m for m in all_markets
                   if (m.get("expected_expiration_time") or "") > now
                   or not m.get("expected_expiration_time")]
    expired = before - len(all_markets)
    if expired:
        rprint(f"  Skipped {expired} expired/in-progress markets")

    # 2. Categorize
    categorized: dict[str, list] = {}
    for m in all_markets:
        cat = categorize_market(m["ticker"])
        if category_filter and cat != category_filter:
            continue
        categorized.setdefault(cat, []).append(m)

    rprint(f"  Categories: { {k: len(v) for k, v in categorized.items()} }")

    # 3. Fetch external odds data for supported sports
    odds_data: dict[str, list] = {}
    sports_needed = set()
    for m in all_markets:
        for prefix, sport_key in KALSHI_TO_ODDS_SPORT.items():
            if m["ticker"].startswith(prefix):
                sports_needed.add(sport_key)

    if get_current_key() and sports_needed:
        rprint(f"\n[bold]Fetching odds for: {', '.join(sports_needed)}[/bold]")
        for sport_key in sports_needed:
            # Fetch h2h, spreads, and totals
            events = fetch_odds_api(sport_key, markets="h2h,spreads,totals")
            odds_data[sport_key] = events
            rprint(f"  {sport_key}: {len(events)} events")
    elif not get_current_key():
        rprint("\n[yellow]ODDS_API_KEY not set -- running without external odds data[/yellow]")
        rprint("[dim]Edge detection will be limited to market microstructure only[/dim]")

    # 4. Run edge detection per category
    opportunities: list[Opportunity] = []

    # Game outcomes
    for m in categorized.get("game", []):
        sport_key = None
        for prefix, sk in KALSHI_TO_ODDS_SPORT.items():
            if m["ticker"].startswith(prefix):
                sport_key = sk
                break
        if sport_key and sport_key in odds_data:
            opp = detect_edge_game(m, odds_data[sport_key])
            if opp and opp.edge >= min_edge:
                opportunities.append(opp)

    # Spreads
    for m in categorized.get("spread", []):
        sport_key = None
        for prefix, sk in KALSHI_TO_ODDS_SPORT.items():
            if m["ticker"].startswith(prefix):
                sport_key = sk
                break
        if sport_key and sport_key in odds_data:
            opp = detect_edge_spread(m, odds_data[sport_key])
            if opp and opp.edge >= min_edge:
                opportunities.append(opp)

    # Totals
    for m in categorized.get("total", []):
        sport_key = None
        for prefix, sk in KALSHI_TO_ODDS_SPORT.items():
            if m["ticker"].startswith(prefix):
                sport_key = sk
                break
        if sport_key and sport_key in odds_data:
            opp = detect_edge_total(m, odds_data[sport_key])
            if opp and opp.edge >= min_edge:
                opportunities.append(opp)

    # Sort by composite score descending
    opportunities.sort(key=lambda o: o.composite_score, reverse=True)
    return opportunities[:top_n]


# ── Output ────────────────────────────────────────────────────────────────────

def print_opportunities(opportunities: list[Opportunity]):
    if not opportunities:
        rprint("[yellow]No opportunities found above edge threshold.[/yellow]")
        return

    table = Table(title=f"Kalshi Opportunities (edge >= {MIN_EDGE:.0%})", show_lines=True)
    table.add_column("Ticker", style="cyan", max_width=35)
    table.add_column("Title", max_width=30)
    table.add_column("Side")
    table.add_column("Mkt Price", justify="right")
    table.add_column("Fair Value", justify="right", style="green")
    table.add_column("Edge", justify="right", style="bold green")
    table.add_column("Conf.")
    table.add_column("Score", justify="right")
    table.add_column("Source", style="dim", max_width=20)

    for o in opportunities:
        edge_color = "green" if o.edge >= 0.05 else "yellow"
        table.add_row(
            o.ticker[:35],
            o.title[:30],
            o.side.upper(),
            f"${o.market_price:.2f}",
            f"${o.fair_value:.2f}",
            f"[{edge_color}]+{o.edge:.1%}[/{edge_color}]",
            o.confidence[:3].upper(),
            f"{o.composite_score:.1f}",
            o.edge_source[:20],
        )
    console.print(table)


def save_opportunities(opportunities: list[Opportunity]):
    """Save opportunities to JSON for the pipeline to pick up."""
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_edge": MIN_EDGE,
        "count": len(opportunities),
        "opportunities": [asdict(o) for o in opportunities],
    }
    with open(OPPORTUNITIES_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)
    rprint(f"[dim]Saved {len(opportunities)} opportunities to {OPPORTUNITIES_PATH}[/dim]")


def print_detail(client: KalshiClient, ticker: str):
    """Print detailed edge analysis for a single market."""
    snap = client.get_market_snapshot(ticker)
    rprint(f"\n[bold]Market: {ticker}[/bold]")
    for k, v in snap.items():
        rprint(f"  {k:>18}: {v}")

    market = client.get_market(ticker).get("market", {})
    cat = categorize_market(ticker)
    rprint(f"\n  Category: {cat}")

    team = extract_team_from_market(market)
    rprint(f"  Team/Subject: {team}")

    strike = extract_strike(market)
    if strike:
        rprint(f"  Strike: {strike}")

    # Try to get odds
    sport_key = None
    for prefix, sk in KALSHI_TO_ODDS_SPORT.items():
        if ticker.startswith(prefix):
            sport_key = sk
            break

    if sport_key and ODDS_API_KEY:
        events = fetch_odds_api(sport_key, markets="h2h,spreads,totals")
        rprint(f"\n  Odds API: {len(events)} events for {sport_key}")

        if cat == "game" and team:
            result = consensus_fair_value(events, team)
            if result:
                fair, details = result
                rprint(f"\n  [bold]Consensus Fair Value: {fair:.1%}[/bold]")
                rprint(f"  Books sampled: {details['n_books']}")
                rprint(f"  Range: {details['min_fair']:.1%} - {details['max_fair']:.1%}")
                yes_ask = float(market.get("yes_ask_dollars", "0"))
                if yes_ask > 0:
                    rprint(f"  Edge (yes): {fair - yes_ask:+.1%}")
                for book, info in details.get("books", {}).items():
                    rprint(f"    {book:>20}: odds={info['raw_odds']:.3f}  implied={info['implied']:.1%}  devig={info['devigged']:.1%}")
    elif not get_current_key():
        rprint("\n  [yellow]ODDS_API_KEY not set -- cannot fetch external odds[/yellow]")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kalshi edge detector -- find +EV opportunities")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Scan all markets for edge")
    scan_p.add_argument("--min-edge", type=float, default=MIN_EDGE, help="Minimum edge threshold")
    scan_p.add_argument("--filter", dest="ticker_filter",
                        help="Filter by sport/prefix: ncaamb, nba, nhl, mlb, esports, or raw ticker prefix")
    scan_p.add_argument("--category", choices=["game", "spread", "total", "player_prop", "esports", "other"],
                        help="Filter to specific market category")
    scan_p.add_argument("--top", type=int, default=20, help="Number of top opportunities")
    scan_p.add_argument("--save", action="store_true", help="Save results to watchlist")

    detail_p = sub.add_parser("detail", help="Detailed analysis of one market")
    detail_p.add_argument("ticker", help="Market ticker")

    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    client = KalshiClient()

    if args.command == "scan":
        opportunities = scan_all_markets(
            client,
            min_edge=args.min_edge,
            category_filter=args.category,
            ticker_filter=args.ticker_filter,
            top_n=args.top,
        )
        print_opportunities(opportunities)
        if args.save and opportunities:
            save_opportunities(opportunities)

    elif args.command == "detail":
        print_detail(client, args.ticker)


if __name__ == "__main__":
    main()
