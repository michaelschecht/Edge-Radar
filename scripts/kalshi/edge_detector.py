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
from scipy.stats import norm

# Shared imports
import paths  # noqa: F401 -- path constants
from opportunity import Opportunity

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from kalshi_client import KalshiClient
from team_stats import get_team_stats
from sports_weather import get_game_weather
from line_movement import get_line_movement
from pitcher_stats import prefetch_mlb_pitchers
from rest_days import prefetch_rest_data
from logging_setup import setup_logging

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
log = setup_logging("edge_detector")
console = Console()

from odds_api import get_current_key, rotate_key, report_remaining
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

MIN_EDGE = float(os.getenv("MIN_EDGE_THRESHOLD", "0.03"))



# ── Market Categorization ────────────────────────────────────────────────────

# Map Kalshi ticker prefixes to categories
CATEGORY_MAP = {
    # --- Game (moneyline / winner) ---
    "KXMLBGAME":     "game",
    "KXNHLGAME":     "game",
    "KXNBAGAME":     "game",
    "KXNCAABBGAME":  "game",
    "KXNCAAMBGAME":  "game",
    "KXNCAAFBGAME":  "game",
    "KXNCAAWBGAME":  "game",
    "KXNFLGAME":     "game",
    "KXMLSGAME":     "game",
    "KXUCL":         "game",
    "KXEPL":         "game",
    "KXLALIGA":      "game",
    "KXSERIEA":      "game",
    "KXBUNDESLIGA":  "game",
    "KXLIGUE1":      "game",
    "KXUFCFIGHT":    "game",
    "KXBOXING":      "game",
    "KXIPL":         "game",
    # --- Spread ---
    "KXNBASPREAD":   "spread",
    "KXNHLSPREAD":   "spread",
    "KXNCAAMBSPREAD":"spread",
    "KXNFLSPREAD":   "spread",
    "KXMLSSPREAD":   "spread",
    # --- Total ---
    "KXNHLTOTAL":    "total",
    "KXNBATOTAL":    "total",
    "KXNCAAMBTOTAL": "total",
    "KXNFLTOTAL":    "total",
    "KXMLSTOTAL":    "total",
    # --- Player props ---
    "KXNHLGOAL":     "player_prop",
    "KXNHLPTS":      "player_prop",
    "KXNHLAST":      "player_prop",
    "KXNHLFIRSTGOAL":"player_prop",
    "KXNBABLK":      "player_prop",
    # --- Mentions ---
    "KXNBAMENTION":  "mention",
    "KXFOXNEWSMENTION": "mention",
    "KXPOLITICSMENTION":"mention",
    "KXLASTWORDCOUNT":"mention",
    # --- Esports ---
    "KXCS2MAP":      "esports",
    "KXCS2GAME":     "esports",
    "KXLOLMAP":      "esports",
    "KXLOLGAME":     "esports",
    # --- Motorsports / Golf (race/tournament winner) ---
    "KXF1":          "game",
    "KXNASCARRACE":  "game",
    "KXPGATOUR":     "game",
}

# Map Kalshi ticker prefixes to Odds API sport keys
# Full list: https://the-odds-api.com/sports-odds-data/sports-apis.html
KALSHI_TO_ODDS_SPORT = {
    # --- MLB ---
    "KXMLBGAME":       "baseball_mlb",
    # --- NHL ---
    "KXNHLGAME":       "icehockey_nhl",
    "KXNHLTOTAL":      "icehockey_nhl",
    "KXNHLSPREAD":     "icehockey_nhl",
    # --- NBA ---
    "KXNBAGAME":       "basketball_nba",
    "KXNBASPREAD":     "basketball_nba",
    "KXNBATOTAL":      "basketball_nba",
    # --- NFL ---
    "KXNFLGAME":       "americanfootball_nfl",
    "KXNFLSPREAD":     "americanfootball_nfl",
    "KXNFLTOTAL":      "americanfootball_nfl",
    # --- College Basketball ---
    "KXNCAABBGAME":    "basketball_ncaab",
    "KXNCAAMBGAME":    "basketball_ncaab",
    "KXNCAAMBSPREAD":  "basketball_ncaab",
    "KXNCAAMBTOTAL":   "basketball_ncaab",
    # --- College Football ---
    "KXNCAAFBGAME":    "americanfootball_ncaaf",
    # --- College Women's Basketball ---
    "KXNCAAWBGAME":    "basketball_wncaab",
    # --- Soccer ---
    "KXMLSGAME":       "soccer_usa_mls",
    "KXMLSSPREAD":     "soccer_usa_mls",
    "KXMLSTOTAL":      "soccer_usa_mls",
    "KXUCL":           "soccer_uefa_champs_league",
    "KXEPL":           "soccer_epl",
    "KXLALIGA":        "soccer_spain_la_liga",
    "KXSERIEA":        "soccer_italy_serie_a",
    "KXBUNDESLIGA":    "soccer_germany_bundesliga",
    "KXLIGUE1":        "soccer_france_ligue_one",
    # --- Combat Sports ---
    "KXUFCFIGHT":      "mma_mixed_martial_arts",
    "KXBOXING":        "boxing_boxing",
    # --- Motorsports ---
    # NOTE: The Odds API does not support F1 or NASCAR — no sport keys exist.
    # KXF1 and KXNASCARRACE markets are scanned on Kalshi but scored without external odds.
    # --- Golf ---
    "KXPGATOUR":       "golf_pga_championship_winner",
    # --- Cricket ---
    "KXIPL":           "cricket_ipl",
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
    """Fetch odds from The Odds API with caching and key rotation.

    Rotates through every configured key at most once on 401/429 before
    giving up, so a single-sport scan (no prior rotation warmup from other
    sports) still lands on a working key. Previously `range(3)` capped
    attempts at 3 and exited before trying the last rotated key — the full
    all-sports scan masked the issue because earlier sports burned through
    exhausted keys first.
    """
    if not get_current_key():
        return []

    cache_key = f"{sport_key}:{markets}"
    if cache_key in _odds_cache:
        return _odds_cache[cache_key]

    tried: set[str] = set()
    while True:
        api_key = get_current_key()
        if not api_key or api_key in tried:
            if tried:
                log.warning("All %d Odds API keys returned 401/429 for %s",
                            len(tried), sport_key)
            return []
        tried.add(api_key)
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
            if resp.status_code in (401, 429):
                rotate_key("http_" + str(resp.status_code))
                continue

            resp.raise_for_status()
            events = resp.json()
            remaining = resp.headers.get("x-requests-remaining", "?")
            log.info("Odds API: %s events, %s requests remaining", len(events), remaining)

            try:
                report_remaining(api_key, int(remaining))
            except (ValueError, TypeError):
                pass

            _odds_cache[cache_key] = events
            return events
        except Exception as e:
            log.warning("Odds API error for %s: %s", sport_key, e)
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


# ── Sharp Book Weighting ────────────────────────────────────────────────────

# Sharp books have tighter lines and more accurate prices.
# Recreational books have wider margins influenced by public money.
BOOK_WEIGHTS = {
    # Sharp (weight 3x)
    "pinnacle": 3.0,
    "pinnaclesports": 3.0,
    "circa": 3.0,
    "bookmaker": 2.5,
    # Mid-tier (weight 1.5x)
    "betonlineag": 1.5,
    "bovada": 1.5,
    "lowvig": 2.0,
    "betrivers": 1.0,
    "williamhill_us": 1.0,
    # Recreational (weight 0.7x)
    "draftkings": 0.7,
    "fanduel": 0.7,
    "betmgm": 0.7,
    "pointsbetus": 0.7,
    "caesars": 0.7,
    "espnbet": 0.7,
    "superbook": 1.0,
    "mybookieag": 0.7,
    "betus": 0.7,
    "ballybet": 0.7,
    "hardrockbet": 0.7,
    "fliff": 0.5,
}

DEFAULT_BOOK_WEIGHT = 1.0


def _book_weight(book_key: str) -> float:
    """Look up the weight for a bookmaker."""
    return BOOK_WEIGHTS.get(book_key.lower(), DEFAULT_BOOK_WEIGHT)


def weighted_median(values: list[float], weights: list[float]) -> float:
    """
    Calculate a weighted median.

    Sorts by value, accumulates weights, and returns the value at the
    50th percentile of cumulative weight.
    """
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]

    pairs = sorted(zip(values, weights))
    total_weight = sum(w for _, w in pairs)
    half = total_weight / 2.0
    cumulative = 0.0
    for val, w in pairs:
        cumulative += w
        if cumulative >= half:
            return val
    return pairs[-1][0]


def consensus_fair_value(events: list, team_name: str) -> tuple[float, dict] | None:
    """
    Calculate consensus fair probability for a team across all bookmakers.
    Uses weighted median — sharp books count more than recreational.
    """
    fair_probs = []
    book_keys = []
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
                book_keys.append(bookmaker["key"])
                book_details[bookmaker["key"]] = {
                    "raw_odds": outcomes[matched_idx]["price"],
                    "implied": round(prob_team, 4),
                    "devigged": round(fair_team, 4),
                }

    if not fair_probs:
        return None

    # Weighted median — sharp books (Pinnacle, Circa) count more than recreational
    weights = [_book_weight(b) for b in book_keys]
    median_fair = weighted_median(fair_probs, weights)

    return median_fair, {
        "n_books": len(fair_probs),
        "median_fair": round(median_fair, 4),
        "min_fair": round(min(fair_probs), 4),
        "max_fair": round(max(fair_probs), 4),
        "books": book_details,
    }


# Sport-specific score margin standard deviations (empirical).
# These represent the typical spread of final margin outcomes around the
# expected margin.  Used by the normal-CDF spread model.
#
# R2 (2026-04-21): NBA +15%, NCAAB +10%, MLB +15% to widen probability
# distributions.  Direct response to Brier 0.2646 and the 60-70% favorite
# band overconfidence in the 14-day review.  NHL left untouched (+87% ROI,
# well-calibrated).
SPORT_MARGIN_STDEV = {
    "basketball_nba": 13.8,       # R2: 12.0 * 1.15
    "basketball_ncaab": 12.1,     # R2: 11.0 * 1.10
    "americanfootball_nfl": 13.5,
    "americanfootball_ncaaf": 15.0,
    "baseball_mlb": 4.025,        # R2: 3.5 * 1.15
    "icehockey_nhl": 2.5,
    "soccer": 1.8,
    "mma": 5.0,
}

# Map Kalshi ticker prefixes to sport keys for stdev lookup
_PREFIX_TO_SPORT = {
    "KXNBA": "basketball_nba",
    "KXNCAAMB": "basketball_ncaab",
    "KXNCAABB": "basketball_ncaab",
    "KXNFL": "americanfootball_nfl",
    "KXNCAAF": "americanfootball_ncaaf",
    "KXMLB": "baseball_mlb",
    "KXNHL": "icehockey_nhl",
    "KXSOCCER": "soccer",
    "KXUFC": "mma",
    "KXMLS": "soccer",
}


def _get_margin_stdev(ticker: str) -> float:
    """Look up the score margin standard deviation for a ticker's sport."""
    for prefix, sport in _PREFIX_TO_SPORT.items():
        if ticker.startswith(prefix):
            return SPORT_MARGIN_STDEV[sport]
    return 12.0  # default fallback (basketball-like)


def consensus_spread_prob(events: list, team_name: str, strike: float,
                          ticker: str = "",
                          stdev_adjustment: float = 0.0) -> tuple[float, dict] | None:
    """
    Estimate probability of a team winning by > strike points using
    sportsbook spreads and a normal-distribution model.

    Instead of the old linear adjustment (3% per point), we:
    1. Collect the median book spread and implied cover probability
    2. Use those to infer the expected margin (mean of the distribution)
    3. Model the final margin as Normal(mean, stdev) where stdev is
       sport-specific
    4. Calculate P(margin > strike) = 1 - Phi((strike - mean) / stdev)

    This correctly handles alternate spreads: the probability of covering
    a large spread drops off following the bell curve, not linearly.
    """
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

    # Weighted median using sharp book weights
    sd_weights = [_book_weight(s["book"]) for s in spread_data]
    sd_spreads = [s["spread"] for s in spread_data]
    sd_implieds = [s["implied"] for s in spread_data]
    median_spread = weighted_median(sd_spreads, sd_weights)
    median_implied = weighted_median(sd_implieds, sd_weights)

    stdev = _get_margin_stdev(ticker) + stdev_adjustment

    # The book says the team covers median_spread with median_implied probability.
    # Book spread is negative for favorites: spread=-5.5 means "favored by 5.5".
    # P(margin > -spread) = median_implied
    # margin ~ Normal(mean, stdev)
    # median_implied = 1 - Phi((-median_spread - mean) / stdev)
    # Solve for mean:
    #   Phi((-median_spread - mean) / stdev) = 1 - median_implied
    #   (-median_spread - mean) / stdev = Phi_inv(1 - median_implied)
    #   mean = -median_spread - stdev * Phi_inv(1 - median_implied)

    # Clamp implied to avoid infinities at 0 or 1
    clamped_implied = max(0.01, min(0.99, median_implied))
    mean_margin = -median_spread - stdev * norm.ppf(1.0 - clamped_implied)

    # Now calculate P(margin > strike)
    adjusted_prob = 1.0 - norm.cdf(strike, loc=mean_margin, scale=stdev)
    adjusted_prob = max(0.01, min(0.99, adjusted_prob))

    # Book disagreement: if spreads vary widely across books, something
    # is moving (likely injury news). High disagreement = lower confidence.
    all_spreads = [s["spread"] for s in spread_data]
    spread_range = max(all_spreads) - min(all_spreads) if len(all_spreads) > 1 else 0

    return adjusted_prob, {
        "n_books": len(spread_data),
        "median_book_spread": median_spread,
        "kalshi_strike": strike,
        "spread_diff": round(abs(median_spread) - strike, 1),
        "raw_median_implied": round(median_implied, 4),
        "adjusted_prob": round(adjusted_prob, 4),
        "inferred_mean_margin": round(mean_margin, 2),
        "margin_stdev": stdev,
        "book_spread_range": round(spread_range, 1),
        "books": spread_data[:5],
    }


# Sport-specific total score standard deviations (empirical).
# Represents how much the combined score varies around the expected total.
SPORT_TOTAL_STDEV = {
    "basketball_nba": 20.7,       # R2: 18.0 * 1.15
    "basketball_ncaab": 17.6,     # R2: 16.0 * 1.10
    "americanfootball_nfl": 13.0,
    "americanfootball_ncaaf": 14.0,
    "baseball_mlb": 3.45,         # R2: 3.0 * 1.15
    "icehockey_nhl": 2.2,
    "soccer": 1.5,
}


def _get_total_stdev(ticker: str) -> float:
    """Look up the total score standard deviation for a ticker's sport."""
    for prefix, sport in _PREFIX_TO_SPORT.items():
        if ticker.startswith(prefix):
            return SPORT_TOTAL_STDEV.get(sport, 12.0)
    return 12.0


def consensus_total_prob(events: list, strike: float,
                         ticker: str = "",
                         stdev_adjustment: float = 0.0) -> tuple[float, dict] | None:
    """
    Estimate probability of total going over strike using sportsbook totals
    and a normal-distribution model.

    Same approach as spread model:
    1. Collect median book total line and implied over probability
    2. Infer the expected total (mean of distribution)
    3. Calculate P(total > strike) using normal CDF
    """
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

    # Weighted median using sharp book weights
    td_weights = [_book_weight(t["book"]) for t in total_data]
    td_lines = [t["line"] for t in total_data]
    td_implieds = [t["implied"] for t in total_data]
    median_line = weighted_median(td_lines, td_weights)
    median_implied = weighted_median(td_implieds, td_weights)

    stdev = _get_total_stdev(ticker) + stdev_adjustment

    # The book says P(total > median_line) = median_implied
    # total ~ Normal(mean, stdev)
    # median_implied = 1 - Phi((median_line - mean) / stdev)
    # Solve for mean:
    #   mean = median_line - stdev * Phi_inv(1 - median_implied)
    clamped_implied = max(0.01, min(0.99, median_implied))
    mean_total = median_line - stdev * norm.ppf(1.0 - clamped_implied)

    # P(total > strike)
    adjusted_prob = 1.0 - norm.cdf(strike, loc=mean_total, scale=stdev)
    adjusted_prob = max(0.01, min(0.99, adjusted_prob))

    return adjusted_prob, {
        "n_books": len(total_data),
        "median_book_line": median_line,
        "kalshi_strike": strike,
        "line_diff": round(median_line - strike, 1),
        "adjusted_prob": round(adjusted_prob, 4),
        "inferred_mean_total": round(mean_total, 2),
        "total_stdev": stdev,
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


# ── Team Stats Integration ───────────────────────────────────────────────────

def _sport_from_ticker(ticker: str) -> str | None:
    """Map a Kalshi ticker prefix to a sport key for team_stats lookup."""
    for prefix, sport in _PREFIX_TO_SPORT.items():
        if ticker.startswith(prefix):
            return sport
    return None


def _stats_confidence_signal(team_name: str, ticker: str, side: str) -> dict:
    """
    Look up team stats and return a confidence signal.

    Returns dict with:
        - "stats_found": bool
        - "win_pct": float (0-1)
        - "signal": "supports" | "contradicts" | "neutral"
        - "team_record": str (e.g., "56-15")

    For YES bets (team wins/covers), a high win% supports the bet.
    For NO bets (team loses/doesn't cover), a low win% supports the bet.
    """
    sport = _sport_from_ticker(ticker)
    if not sport:
        return {"stats_found": False}

    try:
        stats = get_team_stats(team_name, sport)
    except Exception:
        return {"stats_found": False}

    if not stats:
        return {"stats_found": False}

    win_pct = stats.get("win_pct", 0)
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)

    # Determine if stats support the bet direction
    if side == "yes":
        # Betting the team wins/covers — high win% supports
        if win_pct >= 0.60:
            signal = "supports"
        elif win_pct <= 0.40:
            signal = "contradicts"
        else:
            signal = "neutral"
    else:
        # Betting against the team — low win% supports
        if win_pct <= 0.40:
            signal = "supports"
        elif win_pct >= 0.60:
            signal = "contradicts"
        else:
            signal = "neutral"

    return {
        "stats_found": True,
        "win_pct": round(win_pct, 3),
        "team_record": f"{wins}-{losses}",
        "signal": signal,
    }


def _adjust_confidence_with_stats(confidence: str, stats_signal: dict) -> str:
    """Adjust confidence level based on an auxiliary signal.

    R13 (2026-04-24): One-way bumps — *contradicts* drops a level, *supports*
    is a no-op. 30-day calibration showed High-confidence WR (47%) below
    Medium (53%) and NBA High at -71% ROI. The upward-bump path was
    correlated with inflated claimed edge, not better outcomes. Downward
    bumps remain (still a legitimate filter: opposing team stats, B2B
    disadvantage, sharp money against). Called from three sites — team
    stats, rest/B2B, sharp money — all share this behavior.
    """
    if not stats_signal.get("stats_found"):
        return confidence

    if stats_signal.get("signal") != "contradicts":
        return confidence

    levels = ["low", "medium", "high"]
    idx = levels.index(confidence)
    return levels[max(idx - 1, 0)]


def _sharp_money_signal(team_name: str, side: str, ticker: str,
                        sharp_signals: dict) -> dict:
    """
    Check if ESPN line movement data shows sharp action relevant to this bet.

    Returns dict with:
        - "signal_found": bool
        - "sharp_side": str or None ("home"/"away"/"over"/"under")
        - "agrees_with_bet": bool or None
        - "reason": str
    """
    if not sharp_signals:
        return {"signal_found": False}

    # Try to find this team in the sharp signals index
    # Normalize: try the team name and common abbreviations
    signal = None
    for key in sharp_signals:
        if key.lower() in team_name.lower() or team_name.lower() in key.lower():
            signal = sharp_signals[key]
            break

    # Also try matching by ticker prefix abbreviations
    if not signal:
        # Extract team abbrev from ticker: KXNBAGAME-26MAR25OKLBOS-OKC -> OKC, BOS
        import re
        match = re.search(r"\d{2}[A-Z]{3}\d{2}(\w+)-", ticker)
        if match:
            matchup = match.group(1)
            for key in sharp_signals:
                if key.upper() in matchup.upper():
                    signal = sharp_signals[key]
                    break

    if not signal:
        return {"signal_found": False}

    sharp_side = signal.get("sharp_signal")
    reason = signal.get("signal_reason", "")

    # Determine if the sharp signal agrees with our bet
    agrees = None
    if sharp_side in ("home", "away"):
        # For game/spread bets, check if sharp side matches our side
        # This is approximate — we'd need to know if our team is home or away
        agrees = None  # can't determine without home/away context
    elif sharp_side == "over" and side == "yes":
        agrees = True  # sharp over supports YES on total over
    elif sharp_side == "under" and side == "no":
        agrees = True  # sharp under supports NO on total over
    elif sharp_side in ("over", "under"):
        agrees = False

    return {
        "signal_found": True,
        "sharp_side": sharp_side,
        "agrees_with_bet": agrees,
        "reason": reason,
        "spread_move": signal.get("spread_move"),
        "total_move": signal.get("total_move"),
    }


# ── Core Edge Detection ──────────────────────────────────────────────────────

def detect_edge_game(market: dict, odds_events: list,
                     sharp_signals: dict | None = None,
                     pitcher_data: dict | None = None,
                     rest_data: dict | None = None) -> Opportunity | None:
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

    # Adjust confidence with team stats
    stats_signal = _stats_confidence_signal(team, ticker, side)
    confidence = _adjust_confidence_with_stats(confidence, stats_signal)
    details["team_stats"] = stats_signal

    # Add pitcher context for MLB games (informational — moneyline odds
    # already price in the starter heavily, so no confidence adjustment)
    if pitcher_data and pitcher_data.get("matchup_quality") != "unknown":
        details["pitchers"] = {
            "matchup": pitcher_data["matchup_quality"],
            "away": (pitcher_data.get("away_pitcher") or {}).get("name", "TBD"),
            "home": (pitcher_data.get("home_pitcher") or {}).get("name", "TBD"),
        }

    # Rest day / back-to-back context for NBA/NHL games
    if rest_data and rest_data.get("is_b2b"):
        details["rest"] = {
            "is_b2b": rest_data["is_b2b"],
            "days_rest": rest_data["days_rest"],
            "opponent_is_b2b": rest_data.get("opponent_is_b2b", False),
            "rest_advantage": rest_data.get("rest_advantage", 0),
        }
        # B2B team on the road is a disadvantage — reduce confidence if betting YES
        if rest_data.get("rest_advantage", 0) < 0 and side == "yes":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "contradicts"})
        elif rest_data.get("rest_advantage", 0) > 0 and side == "yes":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "supports"})

    # Adjust confidence with sharp money / line movement
    sharp = _sharp_money_signal(team, side, ticker, sharp_signals or {})
    if sharp.get("signal_found"):
        details["sharp_money"] = sharp
        if sharp.get("agrees_with_bet") is True:
            confidence = _adjust_confidence_with_stats(confidence, {"stats_found": True, "signal": "supports"})
        elif sharp.get("agrees_with_bet") is False:
            confidence = _adjust_confidence_with_stats(confidence, {"stats_found": True, "signal": "contradicts"})

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


def detect_edge_spread(market: dict, odds_events: list,
                       sharp_signals: dict | None = None,
                       rest_data: dict | None = None,
                       weather_data: dict | None = None) -> Opportunity | None:
    """Detect edge on spread markets."""
    ticker = market["ticker"]
    team = extract_team_from_market(market)
    strike = extract_strike(market)
    if not team or strike is None:
        return None

    yes_ask = float(market.get("yes_ask_dollars", "0"))
    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    # Build compound stdev adjustment from rest + weather
    stdev_adj = 0.0
    if rest_data:
        stdev_adj += rest_data.get("stdev_adjustment", 0.0)
    if weather_data and weather_data.get("scoring_impact"):
        stdev_adj += weather_data["scoring_impact"].get("stdev_adjustment", 0.0)

    result = consensus_spread_prob(odds_events, team, strike, ticker=ticker,
                                   stdev_adjustment=stdev_adj)
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

    # Confidence: based on book count AND book agreement
    book_range = details.get("book_spread_range", 0)
    if details["n_books"] >= 6 and book_range <= 2.0:
        confidence = "high"
    elif details["n_books"] >= 3 and book_range <= 4.0:
        confidence = "medium"
    else:
        confidence = "low"

    # Adjust confidence with team stats
    stats_signal = _stats_confidence_signal(team, ticker, side)
    confidence = _adjust_confidence_with_stats(confidence, stats_signal)
    details["team_stats"] = stats_signal

    # Rest day / back-to-back adjustment for spreads
    if rest_data and (rest_data.get("is_b2b") or rest_data.get("opponent_is_b2b")):
        details["rest"] = {
            "is_b2b": rest_data.get("is_b2b", False),
            "days_rest": rest_data.get("days_rest", 1),
            "opponent_is_b2b": rest_data.get("opponent_is_b2b", False),
            "rest_advantage": rest_data.get("rest_advantage", 0),
        }
        # B2B team covering a spread is harder — reduce confidence
        if rest_data.get("rest_advantage", 0) < 0 and side == "yes":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "contradicts"})
        elif rest_data.get("rest_advantage", 0) > 0 and side == "yes":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "supports"})

    # Adjust confidence with sharp money / line movement
    sharp = _sharp_money_signal(team, side, ticker, sharp_signals or {})
    if sharp.get("signal_found"):
        details["sharp_money"] = sharp
        if sharp.get("agrees_with_bet") is True:
            confidence = _adjust_confidence_with_stats(confidence, {"stats_found": True, "signal": "supports"})
        elif sharp.get("agrees_with_bet") is False:
            confidence = _adjust_confidence_with_stats(confidence, {"stats_found": True, "signal": "contradicts"})

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


def _extract_home_team_abbr(ticker: str) -> str | None:
    """
    Extract the home team abbreviation from a Kalshi ticker.

    Tickers like KXNFLTOTAL-26SEP21KCSF-42 encode both teams after the date.
    The second team abbreviation (last 2-3 chars of the matchup) is typically
    the home team. This is a heuristic — Kalshi doesn't explicitly label home/away.
    """
    # Extract the matchup segment: e.g., "KCSF" from KXNFLTOTAL-26SEP21KCSF-42
    match = re.search(r"\d{2}[A-Z]{3}\d{2}(\w+)-", ticker)
    if not match:
        return None
    matchup = match.group(1)
    # Home team is the last 2-3 characters (common abbreviation length)
    if len(matchup) >= 4:
        return matchup[-3:] if len(matchup) >= 6 else matchup[-2:]
    return None


def _extract_game_date(ticker: str) -> str | None:
    """Extract game date from ticker as YYYY-MM-DD.

    Kalshi tickers use YYMMMDD format: e.g., 26MAR22 = 2026-03-22.
    """
    match = re.search(r"(\d{2})([A-Z]{3})(\d{2})", ticker)
    if not match:
        return None
    year_short, mon_str, day = match.groups()
    months = {"JAN": "01", "FEB": "02", "MAR": "03", "APR": "04", "MAY": "05",
              "JUN": "06", "JUL": "07", "AUG": "08", "SEP": "09", "OCT": "10",
              "NOV": "11", "DEC": "12"}
    month = months.get(mon_str)
    if not month:
        return None
    return f"20{year_short}-{month}-{day}"


def detect_edge_total(market: dict, odds_events: list,
                      sharp_signals: dict | None = None,
                      pitcher_data: dict | None = None,
                      rest_data: dict | None = None,
                      weather_data: dict | None = None) -> Opportunity | None:
    """Detect edge on over/under total markets."""
    ticker = market["ticker"]
    strike = extract_strike(market)
    if strike is None:
        return None

    yes_ask = float(market.get("yes_ask_dollars", "0"))
    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    # Compound stdev adjustment from pitcher + rest + weather
    stdev_adj = pitcher_data.get("stdev_adjustment", 0.0) if pitcher_data else 0.0
    if rest_data:
        stdev_adj += rest_data.get("stdev_adjustment", 0.0)
    if weather_data and weather_data.get("scoring_impact"):
        stdev_adj += weather_data["scoring_impact"].get("stdev_adjustment", 0.0)
    result = consensus_total_prob(odds_events, strike, ticker=ticker,
                                  stdev_adjustment=stdev_adj)
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

    # Weather fair-value adjustment for outdoor sports (NFL, MLB)
    # (stdev adjustment was already applied above in the compound stdev_adj)
    if weather_data and weather_data.get("scoring_impact"):
        impact = weather_data["scoring_impact"]
        adj = impact["adjustment"]
        if adj != 0:
            # Weather reduces scoring → adjust fair value for OVER bets down
            # For YES (over), lower fair value; for NO (under), higher fair value
            if side == "yes":
                fair = max(0.01, fair + adj)  # adj is negative = reduces over prob
            else:
                fair = min(0.99, fair - adj)  # inverse for under
            edge = fair - market_price
            details["weather"] = weather_data
            details["weather_adjustment"] = adj
            details["weather_stdev_adj"] = impact.get("stdev_adjustment", 0.0)
            log.info("Weather adjustment for %s: %+.1f%% fair, %+.2f stdev (%s)",
                     ticker, adj * 100, impact.get("stdev_adjustment", 0.0), impact["reason"])

    # Pitcher matchup signal for MLB totals
    if pitcher_data and pitcher_data.get("matchup_quality") != "unknown":
        details["pitchers"] = {
            "matchup": pitcher_data["matchup_quality"],
            "stdev_adj": pitcher_data["stdev_adjustment"],
            "away": (pitcher_data.get("away_pitcher") or {}).get("name", "TBD"),
            "home": (pitcher_data.get("home_pitcher") or {}).get("name", "TBD"),
        }
        psig = pitcher_data.get("confidence_signal", "neutral")
        if psig == "supports_over" and side == "yes":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "supports"})
        elif psig == "supports_under" and side == "no":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "supports"})
        elif psig == "supports_over" and side == "no":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "contradicts"})
        elif psig == "supports_under" and side == "yes":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "contradicts"})
        log.info("Pitcher matchup for %s: %s (stdev %+.2f)",
                 ticker, pitcher_data["matchup_quality"], stdev_adj)

    # Rest day / back-to-back signal for totals (NBA/NHL)
    if rest_data and (rest_data.get("is_b2b") or rest_data.get("opponent_is_b2b")):
        details["rest"] = {
            "is_b2b": rest_data.get("is_b2b", False),
            "opponent_is_b2b": rest_data.get("opponent_is_b2b", False),
            "stdev_adj": rest_data.get("stdev_adjustment", 0),
        }
        rsig = rest_data.get("confidence_signal", "neutral")
        if rsig == "supports_under" and side == "no":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "supports"})
        elif rsig == "supports_under" and side == "yes":
            confidence = _adjust_confidence_with_stats(
                confidence, {"stats_found": True, "signal": "contradicts"})
        log.info("Rest day signal for %s: b2b=%s opp_b2b=%s (stdev %+.2f)",
                 ticker, rest_data.get("is_b2b"), rest_data.get("opponent_is_b2b"),
                 rest_data.get("stdev_adjustment", 0))

    # Sharp money / line movement signal for totals
    home_team = _extract_home_team_abbr(ticker)
    sharp = _sharp_money_signal(home_team or "", side, ticker, sharp_signals or {})
    if sharp.get("signal_found"):
        details["sharp_money"] = sharp
        if sharp.get("agrees_with_bet") is True:
            confidence = _adjust_confidence_with_stats(confidence, {"stats_found": True, "signal": "supports"})
        elif sharp.get("agrees_with_bet") is False:
            confidence = _adjust_confidence_with_stats(confidence, {"stats_found": True, "signal": "contradicts"})

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


def _game_key(ticker: str) -> str:
    """Extract a game identifier from a Kalshi ticker.

    Tickers follow the pattern: PREFIX-DDMMMDDMatchup-Variant
    e.g. KXNCAAMBSPREAD-26MAR22MICHALB-MICH4 -> 26MAR22MICHALB
    This groups all spread/total/game markets for the same matchup.
    """
    parts = ticker.rsplit("-", 1)  # split off variant
    if len(parts) < 2:
        return ticker
    base = parts[0]  # e.g. KXNCAAMBSPREAD-26MAR22MICHALB
    # Find the date portion (DDMMMDD) and everything after it
    match = re.search(r"(\d{2}[A-Z]{3}\d{2}\w+)$", base)
    return match.group(1) if match else ticker


def _cap_per_game(opportunities: list, max_per_game: int = 3) -> list:
    """Keep only the top N opportunities per game (by edge, highest first).

    Expects opportunities to already be sorted by edge descending.
    """
    game_counts: dict[str, int] = {}
    capped: list = []
    for opp in opportunities:
        key = _game_key(opp.ticker)
        count = game_counts.get(key, 0)
        if count < max_per_game:
            capped.append(opp)
            game_counts[key] = count + 1
    return capped


def scan_all_markets(
    client: KalshiClient,
    min_edge: float = MIN_EDGE,
    category_filter: str | None = None,
    ticker_filter: str | None = None,
    top_n: int = 20,
    date_filter: str | None = None,
) -> list[Opportunity]:
    """
    Scan all open Kalshi markets and score them for edge.

    Args:
        ticker_filter: Filter markets by ticker prefix. Can be a shortcut name
                       (ncaamb, nba, nhl, mlb, esports) or a raw prefix like "KXNCAAMB".
        date_filter: YYYY-MM-DD string. When set, markets are filtered to this date
                     before fetching external odds, saving Odds API quota.

    Returns list of Opportunity objects sorted by composite score.
    """
    # Resolve ticker filter (supports comma-separated, e.g. "mlb,nhl")
    filter_prefixes = None
    if ticker_filter:
        shortcuts = [s.strip().lower() for s in ticker_filter.split(",")]

        # Route futures filters to the dedicated futures scanner
        if len(shortcuts) == 1 and shortcuts[0] in FILTER_SHORTCUTS and FILTER_SHORTCUTS[shortcuts[0]][0].startswith("__FUTURES__"):
            from futures_edge import scan_futures_markets
            futures_filter = shortcuts[0] if shortcuts[0] != "futures" else None
            return scan_futures_markets(client, min_edge=min_edge,
                                        ticker_filter=futures_filter, top_n=top_n)

        filter_prefixes = []
        raw_prefixes = []
        for shortcut in shortcuts:
            if shortcut in FILTER_SHORTCUTS:
                filter_prefixes.extend(FILTER_SHORTCUTS[shortcut])
            else:
                filter_prefixes.append(shortcut.upper())
                raw_prefixes.append(shortcut.upper())

        label = ", ".join(shortcuts)
        if raw_prefixes:
            rprint(f"[bold]Filter: {label} -> {', '.join(filter_prefixes)}[/bold]")
        else:
            rprint(f"[bold]Filter: {label} -> {len(filter_prefixes)} prefixes[/bold]")

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

    # 1b. Apply date filter early to reduce Odds API calls
    if date_filter:
        before_date = len(all_markets)
        all_markets = [m for m in all_markets
                       if _extract_game_date(m["ticker"]) == date_filter
                       or _extract_game_date(m["ticker"]) is None]
        skipped_date = before_date - len(all_markets)
        if skipped_date:
            rprint(f"  Date pre-filter ({date_filter}): {before_date} -> {len(all_markets)} markets")

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

    # 3b. Pre-fetch line movement data from ESPN (free)
    sharp_signals: dict[str, dict] = {}  # team_abbr -> signal dict
    for sport_key in sports_needed:
        try:
            movements = get_line_movement(sport_key)
            for mv in movements:
                if mv.get("sharp_signal"):
                    # Index by both home and away team
                    sharp_signals[mv["home_team"]] = mv
                    sharp_signals[mv["away_team"]] = mv
            if movements:
                sharp_count = sum(1 for m in movements if m.get("sharp_signal"))
                rprint(f"  Line movement: {len(movements)} games, {sharp_count} sharp signals")
        except Exception as e:
            log.debug("Line movement fetch failed for %s: %s", sport_key, e)

    # 3c. Pre-fetch MLB starting pitcher data (free, MLB Stats API)
    pitcher_cache: dict[str, dict] = {}  # team_abbr -> pitcher matchup data
    if "baseball_mlb" in sports_needed:
        # Collect unique game dates from MLB market tickers
        mlb_dates = set()
        for m in all_markets:
            if m["ticker"].startswith("KXMLB"):
                gd = _extract_game_date(m["ticker"])
                if gd:
                    mlb_dates.add(gd)
        for gd in sorted(mlb_dates):
            try:
                day_pitchers = prefetch_mlb_pitchers(gd)
                pitcher_cache.update(day_pitchers)
            except Exception as e:
                log.debug("Pitcher fetch failed for %s: %s", gd, e)
        if pitcher_cache:
            matchup_types = {}
            for pd in pitcher_cache.values():
                mt = pd.get("matchup_quality", "unknown")
                matchup_types[mt] = matchup_types.get(mt, 0) + 1
            rprint(f"  Pitchers: {len(pitcher_cache) // 2} games ({matchup_types})")

    # 3d. Pre-fetch rest day / back-to-back data (NBA, NHL — free ESPN API)
    rest_cache: dict[str, dict] = {}  # team_abbr -> rest info
    rest_sports = {"basketball_nba", "icehockey_nhl"} & sports_needed
    for rs in rest_sports:
        # Collect unique game dates from tickers
        prefix_map = {v: k for k, v in KALSHI_TO_ODDS_SPORT.items()}
        game_dates = set()
        for m in all_markets:
            for prefix, sport in KALSHI_TO_ODDS_SPORT.items():
                if sport == rs and m["ticker"].startswith(prefix):
                    gd = _extract_game_date(m["ticker"])
                    if gd:
                        game_dates.add(gd)
        for gd in sorted(game_dates):
            try:
                day_rest = prefetch_rest_data(rs, gd)
                rest_cache.update(day_rest)
            except Exception as e:
                log.debug("Rest data fetch failed for %s %s: %s", rs, gd, e)
        if rest_cache:
            b2b_count = sum(1 for v in rest_cache.values() if v.get("is_b2b"))
            rprint(f"  Rest days ({rs.split('_')[-1].upper()}): {len(rest_cache)} teams, {b2b_count} on back-to-back")

    # 4. Run edge detection per category
    opportunities: list[Opportunity] = []

    # Helper: look up rest data for a market by home team abbreviation
    def _rest_for_market(ticker: str) -> dict | None:
        home = _extract_home_team_abbr(ticker)
        return rest_cache.get(home.upper()) if home else None

    # Helper: fetch weather data for outdoor sports (NFL, MLB)
    weather_cache: dict[str, dict | None] = {}

    def _weather_for_market(ticker: str) -> dict | None:
        home = _extract_home_team_abbr(ticker)
        if not home:
            return None
        if home in weather_cache:
            return weather_cache[home]
        sport = _sport_from_ticker(ticker)
        if sport not in ("americanfootball_nfl", "americanfootball_ncaaf", "baseball_mlb"):
            weather_cache[home] = None
            return None
        game_date = _extract_game_date(ticker)
        if not game_date:
            weather_cache[home] = None
            return None
        data = get_game_weather(home, sport, game_date)
        weather_cache[home] = data
        return data

    # Game outcomes
    for m in categorized.get("game", []):
        sport_key = None
        for prefix, sk in KALSHI_TO_ODDS_SPORT.items():
            if m["ticker"].startswith(prefix):
                sport_key = sk
                break
        if sport_key and sport_key in odds_data:
            # Attach pitcher data for MLB games
            mlb_pitchers = None
            if sport_key == "baseball_mlb":
                home = _extract_home_team_abbr(m["ticker"])
                if home:
                    mlb_pitchers = pitcher_cache.get(home.upper())
            opp = detect_edge_game(m, odds_data[sport_key], sharp_signals=sharp_signals,
                                   pitcher_data=mlb_pitchers,
                                   rest_data=_rest_for_market(m["ticker"]))
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
            opp = detect_edge_spread(m, odds_data[sport_key], sharp_signals=sharp_signals,
                                     rest_data=_rest_for_market(m["ticker"]),
                                     weather_data=_weather_for_market(m["ticker"]))
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
            # Attach pitcher data for MLB totals
            mlb_pitchers = None
            if sport_key == "baseball_mlb":
                home = _extract_home_team_abbr(m["ticker"])
                if home:
                    mlb_pitchers = pitcher_cache.get(home.upper())
            opp = detect_edge_total(m, odds_data[sport_key], sharp_signals=sharp_signals,
                                    pitcher_data=mlb_pitchers,
                                    rest_data=_rest_for_market(m["ticker"]),
                                    weather_data=_weather_for_market(m["ticker"]))
            if opp and opp.edge >= min_edge:
                opportunities.append(opp)

    # Sort by edge descending, then cap at 2 per game
    opportunities.sort(key=lambda o: o.edge, reverse=True)
    opportunities = _cap_per_game(opportunities, max_per_game=2)

    # Re-sort by composite score for final ranking
    opportunities.sort(key=lambda o: o.composite_score, reverse=True)
    return opportunities[:top_n]


# ── Output ────────────────────────────────────────────────────────────────────

def print_opportunities(opportunities: list[Opportunity]):
    if not opportunities:
        rprint("[yellow]No opportunities found above edge threshold.[/yellow]")
        return

    from ticker_display import (
        parse_game_datetime, format_bet_label, format_pick_label, sport_from_ticker,
    )

    CATEGORY_LABELS = {
        "game": "ML",
        "spread": "Spread",
        "total": "Total",
        "player_prop": "Prop",
        "esports": "Esports",
    }

    table = Table(title=f"Kalshi Opportunities (edge >= {MIN_EDGE:.0%})", show_lines=True)
    table.add_column("Sport", style="yellow")
    table.add_column("Bet", style="cyan", max_width=35)
    table.add_column("Type", style="magenta")
    table.add_column("Pick", style="bold white", max_width=22)
    table.add_column("When", style="dim")
    table.add_column("Mkt", justify="right")
    table.add_column("Fair", justify="right", style="green")
    table.add_column("Edge", justify="right", style="bold green")
    table.add_column("Conf.")
    table.add_column("Score", justify="right")

    for o in opportunities:
        edge_color = "green" if o.edge >= 0.05 else "yellow"
        table.add_row(
            sport_from_ticker(o.ticker),
            format_bet_label(o.ticker, o.title),
            CATEGORY_LABELS.get(o.category, o.category.title()),
            format_pick_label(o.ticker, o.title, o.side, o.category),
            parse_game_datetime(o.ticker),
            f"${o.market_price:.2f}",
            f"${o.fair_value:.2f}",
            f"[{edge_color}]+{o.edge:.1%}[/{edge_color}]",
            o.confidence[:3].upper(),
            f"{o.composite_score:.1f}",
        )
    console.print(table)



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
    scan_p.add_argument("--execute", action="store_true",
                        help="Execute bets through the pipeline (requires confirmation)")
    scan_p.add_argument("--unit-size", type=float, default=None,
                        help="Dollar amount per bet (default: UNIT_SIZE from .env)")
    scan_p.add_argument("--max-bets", type=int, default=5,
                        help="Maximum number of bets to place")
    scan_p.add_argument("--min-bets", type=int, default=None,
                        help="Minimum approved bets required to proceed. If fewer pass "
                             "risk checks, abort to avoid over-concentrating budget.")
    scan_p.add_argument("--pick", type=str, default=None,
                        help="Comma-separated row numbers to execute (e.g., '1,3,5')")
    scan_p.add_argument("--ticker", type=str, nargs="+", default=None,
                        help="Execute only these specific tickers")
    scan_p.add_argument("--date", type=str, default=None,
                        help="Only show games on this date (today, tomorrow, YYYY-MM-DD, mar31)")
    scan_p.add_argument("--budget", type=str, default=None,
                        help="Max total cost for the batch. Percentage of bankroll (e.g. '10%%') "
                             "or dollar amount (e.g. '15'). Bets scaled down proportionally.")
    scan_p.add_argument("--exclude-open", action="store_true",
                        help="Exclude markets where you already have an open position")
    scan_p.add_argument("--report-dir", type=str, default=None,
                        help="Override report output directory for --save")

    detail_p = sub.add_parser("detail", help="Detailed analysis of one market")
    detail_p.add_argument("ticker", help="Market ticker")

    args = parser.parse_args()

    client = KalshiClient()

    if args.command == "scan":
        # Resolve date early so it can be passed into scan for Odds API optimization
        resolved_date = None
        if args.date:
            from ticker_display import resolve_date_arg
            resolved_date = resolve_date_arg(args.date)

        opportunities = scan_all_markets(
            client,
            min_edge=args.min_edge,
            category_filter=args.category,
            ticker_filter=args.ticker_filter,
            top_n=args.top,
            date_filter=resolved_date,
        )
        # Apply date filter on opportunities (catches any edge cases the early filter missed)
        if opportunities and resolved_date:
            from ticker_display import filter_by_date
            before = len(opportunities)
            opportunities = filter_by_date(opportunities, resolved_date)
            if len(opportunities) < before:
                rprint(f"[dim]Date filter ({resolved_date}): {before} -> {len(opportunities)} opportunities[/dim]")
        if opportunities and args.exclude_open:
            from ticker_display import filter_exclude_tickers
            positions = client.get_positions(limit=200, count_filter="position")
            open_tickers = {p.get("ticker", "") for p in positions.get("market_positions", [])}
            before = len(opportunities)
            opportunities = filter_exclude_tickers(opportunities, open_tickers)
            rprint(f"[dim]Excluded open positions: {before} -> {len(opportunities)} opportunities[/dim]")

        sized_orders = None
        if opportunities and (args.execute or args.unit_size is not None or args.budget is not None):
            from kalshi_executor import execute_pipeline, UNIT_SIZE
            # Parse --budget: "10%" -> 0.10 (fraction), "15" -> 15.0 (dollars)
            budget_val = None
            if args.budget is not None:
                raw = args.budget.strip().rstrip("%")
                num = float(raw)
                # Treat values <= 100 without a decimal point as percentages
                # (e.g., "15" or "15%" both mean 15% of bankroll).
                # Values > 100 are treated as flat dollar amounts.
                # Explicit decimals like "0.15" are treated as fractions.
                if num <= 1:
                    budget_val = num  # already a fraction (e.g., 0.15)
                elif num <= 100:
                    budget_val = num / 100  # percentage (e.g., 15 -> 0.15)
                else:
                    budget_val = num  # flat dollar amount (e.g., 150)
            sized_orders = execute_pipeline(
                client=client,
                opportunities=opportunities,
                execute=args.execute,
                max_bets=args.max_bets,
                unit_size=args.unit_size or UNIT_SIZE,
                pick_rows=args.pick,
                pick_tickers=args.ticker,
                budget=budget_val,
                min_bets=args.min_bets,
            )
        else:
            print_opportunities(opportunities)
        if args.save and opportunities:
            if sized_orders is not None:
                from report_writer import save_execution_report
                rpt = save_execution_report(sized_orders, report_type="sports",
                                            filter_label=args.ticker_filter or "", min_edge=args.min_edge,
                                            output_dir=args.report_dir)
            else:
                from report_writer import save_scan_report
                rpt = save_scan_report(opportunities, report_type="sports",
                                       filter_label=args.ticker_filter or "", min_edge=args.min_edge,
                                       output_dir=args.report_dir)
            if rpt:
                rprint(f"[dim]Report saved to {rpt}[/dim]")

    elif args.command == "detail":
        print_detail(client, args.ticker)


if __name__ == "__main__":
    main()
