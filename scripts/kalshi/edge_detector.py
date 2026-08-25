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

import re
import sys
import os
import json
import math
import time
import logging
import argparse
from datetime import datetime, timezone, timedelta
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
from app.config import get_config

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
log = setup_logging("edge_detector")
console = Console()

from odds_api import get_current_key, rotate_key, report_remaining, mark_exhausted, redact_secrets
import odds_cache
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

MIN_EDGE = get_config().gates.min_edge_threshold



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
    "KXWCGAME":      "game",
    "KXUFCFIGHT":    "game",
    "KXBOXING":      "game",
    "KXIPL":         "game",
    # --- Tennis (Wimbledon) ---
    "KXATPMATCH":    "game",
    "KXWTAMATCH":    "game",
    # --- Spread ---
    "KXMLBSPREAD":   "spread",
    "KXNBASPREAD":   "spread",
    "KXNHLSPREAD":   "spread",
    "KXNCAAMBSPREAD":"spread",
    "KXNFLSPREAD":   "spread",
    "KXMLSSPREAD":   "spread",
    "KXWCSPREAD":    "spread",
    # --- Total ---
    "KXMLBTOTAL":    "total",
    "KXNHLTOTAL":    "total",
    "KXNBATOTAL":    "total",
    "KXNCAAMBTOTAL": "total",
    "KXNFLTOTAL":    "total",
    "KXMLSTOTAL":    "total",
    "KXWCTOTAL":     "total",
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
    "KXMLBSPREAD":     "baseball_mlb",
    "KXMLBTOTAL":      "baseball_mlb",
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
    "KXWCGAME":        "soccer_fifa_world_cup",
    "KXWCSPREAD":      "soccer_fifa_world_cup",
    "KXWCTOTAL":       "soccer_fifa_world_cup",
    # --- Combat Sports ---
    "KXUFCFIGHT":      "mma_mixed_martial_arts",
    "KXBOXING":        "boxing_boxing",
    # --- Motorsports / Golf ---
    # NOTE: The Odds API has no game-level keys for F1, NASCAR, or PGA tournament winners.
    # `golf_pga_championship_winner` is outrights-only, which 422s when requested with
    # h2h/spreads/totals. KXF1, KXNASCARRACE, and KXPGATOUR are scanned on Kalshi but
    # scored without external odds; PGA tournament winners are handled separately by
    # futures_edge.py using the `outrights` market type.
    # --- Cricket ---
    "KXIPL":           "cricket_ipl",
    # --- Tennis (Wimbledon) ---
    # h2h match-winner only; no spread/total on Kalshi.
    # NOTE: verify these prefixes locally — Kalshi API was egress-blocked during
    # the initial implementation (2026-06-28). Also try: KXATPGAME, KXWTAGAME.
    "KXATPMATCH":      "tennis_atp_wimbledon",
    "KXWTAMATCH":      "tennis_wta_wimbledon",
}


def categorize_market(ticker: str) -> str:
    """Determine market category from ticker prefix."""
    for prefix, cat in CATEGORY_MAP.items():
        if ticker.startswith(prefix):
            return cat
    return "other"


# ── Odds API Integration ─────────────────────────────────────────────────────

# In-process cache: maps "{sport_key}:{markets}" -> (stored_at_monotonic, events).
# A TTL was added in L1: previously this dict had none and returned the first
# response for the entire process lifetime, which is the dominant F44 mechanism
# in a long-running host process (pre-game odds frozen for hours while a game
# plays out). Entries now expire on the same live-aware rule as the file cache.
_odds_cache: dict[str, tuple[float, list]] = {}


def fetch_odds_api(sport_key: str, markets: str = "h2h") -> list:
    """Fetch odds from The Odds API with caching and key rotation.

    Two-tier cache: the in-process `_odds_cache` dict (fastest, scoped to
    one Python process) sits in front of `odds_cache` (file-backed, shared
    across processes). On a fresh process the file cache lets back-to-back
    `scan.py` invocations within `ODDS_CACHE_TTL_SECONDS` skip the HTTP
    fetch entirely — addresses R24b / F31 (quota burn from scheduler bursts
    + dashboard re-renders).

    Rotates through every configured key at most once on 401/429 before
    giving up, so a single-sport scan (no prior rotation warmup from other
    sports) still lands on a working key. Previously `range(3)` capped
    attempts at 3 and exited before trying the last rotated key — the full
    all-sports scan masked the issue because earlier sports burned through
    exhausted keys first.
    """
    cache_key = f"{sport_key}:{markets}"
    cfg = get_config().odds_cache

    cached = _odds_cache.get(cache_key)
    if cached is not None:
        stored_at, events = cached
        ttl = odds_cache.effective_ttl(events, cfg.ttl_seconds, cfg.live_ttl_seconds)
        if time.monotonic() - stored_at <= ttl:
            return events
        # Expired (live game refreshed past its short TTL, or pre-game past 300s).
        del _odds_cache[cache_key]

    if cfg.enabled:
        cached_events, age = odds_cache.load(
            sport_key, markets, cfg.ttl_seconds, cfg.live_ttl_seconds
        )
        if cached_events is not None:
            log.info("Odds API file cache hit for %s (age %ds, %d events)",
                     sport_key, age, len(cached_events))
            _odds_cache[cache_key] = (time.monotonic(), cached_events)
            return cached_events

    if not get_current_key():
        return []

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
                if resp.status_code == 401:
                    mark_exhausted(api_key)
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

            _odds_cache[cache_key] = (time.monotonic(), events)
            if cfg.enabled:
                odds_cache.store(sport_key, markets, events)
            return events
        except Exception as e:
            log.warning("Odds API error for %s: %s", sport_key, redact_secrets(e))
            return []


_event_odds_cache: dict[str, tuple[float, dict]] = {}


def fetch_event_odds_api(sport_key: str, event_id: str, markets: str = "h2h,spreads,totals") -> dict | None:
    """Fetch event-level odds from The Odds API with caching and key rotation (Phase 2)."""
    cache_key = f"{sport_key}:{event_id}:{markets}"
    cfg = get_config().odds_cache

    cached = _event_odds_cache.get(cache_key)
    if cached is not None:
        stored_at, event = cached
        if time.monotonic() - stored_at <= cfg.live_ttl_seconds:
            return event
        del _event_odds_cache[cache_key]

    if cfg.enabled:
        cached_event, age = odds_cache.load_event(
            sport_key, event_id, cfg.live_ttl_seconds
        )
        if cached_event is not None:
            log.info("Odds API (event) file cache hit for %s:%s (age %ds)",
                     sport_key, event_id, age)
            _event_odds_cache[cache_key] = (time.monotonic(), cached_event)
            return cached_event

    if not get_current_key():
        return None

    tried: set[str] = set()
    while True:
        api_key = get_current_key()
        if not api_key or api_key in tried:
            if tried:
                log.warning("All %d Odds API keys returned 401/429 for event %s",
                            len(tried), event_id)
            return None
        tried.add(api_key)
        try:
            resp = requests.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/events/{event_id}/odds",
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
                if resp.status_code == 401:
                    mark_exhausted(api_key)
                rotate_key("http_" + str(resp.status_code))
                continue

            resp.raise_for_status()
            event = resp.json()
            remaining = resp.headers.get("x-requests-remaining", "?")
            log.info("Odds API (event): success, %s requests remaining", remaining)

            try:
                report_remaining(api_key, int(remaining))
            except (ValueError, TypeError):
                pass

            _event_odds_cache[cache_key] = (time.monotonic(), event)
            if cfg.enabled:
                odds_cache.store_event(sport_key, event_id, event)
            return event
        except Exception as e:
            log.warning("Odds API (event) error for %s:%s: %s", sport_key, event_id, redact_secrets(e))
            return None


def _refresh_event_if_live(matched_event: dict, market: dict) -> dict:
    """If the game is in progress, refresh its odds from the per-event Odds API endpoint (Phase 2)."""
    is_live = False
    from ticker_display import is_game_started
    if is_game_started(market.get("ticker", "")):
        is_live = True
    else:
        commence_str = matched_event.get("commence_time")
        if commence_str:
            commence_dt = _parse_iso_utc(commence_str)
            if commence_dt and commence_dt <= datetime.now(timezone.utc):
                is_live = True

    if is_live:
        sport_key = matched_event.get("sport_key")
        event_id = matched_event.get("id")
        if sport_key and event_id:
            refreshed = fetch_event_odds_api(sport_key, event_id)
            if refreshed:
                return refreshed
            # Refresh failed (404 / quota exhausted / network). Falling back to the
            # sport-level snapshot means pricing a live game on pre-game odds — make
            # that visible rather than silent so a bad fill is diagnosable.
            log.warning(
                "Live odds refresh failed for %s (%s); proceeding on the stale "
                "sport-level snapshot", event_id, sport_key,
            )
    return matched_event


def _event_is_live(event: dict) -> bool:
    """True if the event's commence_time is in the past (game in progress)."""
    commence_dt = _parse_iso_utc(event.get("commence_time", ""))
    return commence_dt is not None and commence_dt <= datetime.now(timezone.utc)


def _live_consensus_too_thin(events: list, n_fresh_books: int, n_excluded: int) -> bool:
    """For an in-progress game whose consensus was thinned by the stale-book
    filter, require a minimum number of surviving fresh books before trusting it
    (Phase 2). The filter can strip a live market down to 1-2 quotes (uneven
    in-play coverage, suspended books); sizing off that is the 'garbage
    consensus' the freshness work exists to avoid.

    The guard only fires when staleness ACTUALLY removed books (n_excluded > 0).
    A live game whose books are all fresh is no thinner than it would be
    pre-game, so it keeps the existing behavior — as do all pre-game markets
    (thin futures / early lines are unaffected)."""
    if n_excluded <= 0:
        return False
    if not any(_event_is_live(ev) for ev in events):
        return False
    floor = get_config().gates.min_live_consensus_books
    if n_fresh_books < floor:
        log.warning(
            "Live consensus thinned to %d fresh book(s) (< %d) after dropping %d "
            "stale book(s) — skipping rather than pricing off a thin sample",
            n_fresh_books, floor, n_excluded,
        )
        return True
    return False


def _is_bookmaker_stale(bookmaker: dict, event: dict, max_age: int) -> bool:
    """True if the bookmaker's last_update is too old for an in-progress game (Phase 2)."""
    commence_str = event.get("commence_time")
    if not commence_str:
        return False
    commence_dt = _parse_iso_utc(commence_str)
    if not commence_dt or commence_dt > datetime.now(timezone.utc):
        # Event is pre-game, last_update doesn't need to be fresh
        return False

    # Event is live/in-progress
    lu_str = bookmaker.get("last_update")
    lu_dt = _parse_iso_utc(lu_str) if lu_str else None
    if lu_dt is None:
        # Live game but no usable last_update — fail CLOSED: exclude this book
        # rather than trust a quote we can't date. A suspended/stale feed can drop
        # or mangle the field, and on a live game that stale line would poison the
        # consensus. The Odds API event endpoint returns last_update on every real
        # response, so this only fires on malformed/mocked data.
        log.warning(
            "Excluding bookmaker %s on live event: missing/unparseable last_update (%r)",
            bookmaker.get("key"), lu_str,
        )
        return True

    age = (datetime.now(timezone.utc) - lu_dt).total_seconds()
    if age > max_age:
        log.warning(
            "Excluding bookmaker %s because its last_update is %d seconds old (limit %d)",
            bookmaker.get("key"), age, max_age
        )
        return True

    return False


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
    matched_event_ids = set()
    n_stale_excluded = 0

    for ev_idx, event in enumerate(events):
        for bookmaker in event.get("bookmakers", []):
            max_age = get_config().gates.max_live_book_age_seconds
            if _is_bookmaker_stale(bookmaker, event, max_age):
                n_stale_excluded += 1
                continue
            for market in bookmaker.get("markets", []):
                if market["key"] != "h2h":
                    continue
                outcomes = market.get("outcomes", [])
                # 2-way (most sports) or 3-way (soccer: home/draw/away). For a
                # 3-way market the Kalshi "team to win?" binary resolves YES only
                # on a win, so the fair YES probability is the team's devigged
                # win share — draw and opponent-win both fall to the NO side.
                if len(outcomes) not in (2, 3):
                    continue

                # Pick the unique best-matching outcome (the "Draw" outcome
                # never matches a team name, so a 3-way market resolves to the
                # right side). Ranking by match strength + tie-refusal stops a
                # truncated same-city name ("Los Angeles D") from resolving to
                # whichever team the feed lists first.
                matched_idx, ambiguous = _match_team_outcome(outcomes, team_name)
                if ambiguous:
                    log.warning(
                        "consensus_fair_value: '%s' matches multiple outcomes "
                        "%s — ambiguous side, emitting no edge",
                        team_name, [o.get("name") for o in outcomes],
                    )
                    return None
                if matched_idx is None:
                    continue

                matched_event_ids.add(ev_idx)
                # Proportional devig across all outcomes (identical to
                # devig_two_way for the 2-way case; extends to 3-way).
                implieds = [implied_prob(o["price"]) for o in outcomes]
                total = sum(implieds)
                if total <= 0:
                    continue
                prob_team = implieds[matched_idx]
                fair_team = prob_team / total
                fair_probs.append(fair_team)
                book_keys.append(bookmaker["key"])
                book_details[bookmaker["key"]] = {
                    "raw_odds": outcomes[matched_idx]["price"],
                    "implied": round(prob_team, 4),
                    "devigged": round(fair_team, 4),
                }

    if not fair_probs:
        return None

    if _live_consensus_too_thin(events, len(fair_probs), n_stale_excluded):
        return None

    # Fix B (belt-and-suspenders): never pool a team across multiple games.
    # Callers should pre-scope via find_market_event; if a team still matched
    # in >1 event, refuse rather than blend two games' odds.
    if len(matched_event_ids) > 1:
        log.warning(
            "consensus_fair_value: '%s' matched %d distinct events — refusing "
            "to pool across games", team_name, len(matched_event_ids),
        )
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
    # soccer: 1.8 stands on its PHYSICAL argument only. 2026-06-29 calibration
    # against 74 completed World Cup matches: mean total 2.96 goals, so the
    # Poisson-consistent margin stdev = sqrt(mean_total) = 1.72, 95% CI
    # [1.59, 1.84] — 1.8 sits inside it. A Skellam fit reproduces the realized
    # margin tail (P(|m|>=2)=0.46, P(|m|>=3)=0.24); stdev 1.4 badly UNDER-
    # predicts it (P(|m|>=3)=0.07). That much still holds — do not fit the stdev
    # to Kalshi's board (which suggests ~1.4), which would import its pricing.
    #
    # RETRACTED 2026-08-25 — the betting-outcome half of this note. It used to
    # read: "the post-devig 'always-YES' lean on soccer spreads is largely a REAL
    # edge (Kalshi underprices goal margins — placed spreads hit 31% vs 19%
    # paid), not a stdev bug." On 53 settled soccer-family spreads (World Cup +
    # MLS), all YES, the realized hit rate is 15.1% against a 15.5% market price
    # — the market was near-exact and the model said 21.7%. The 31% figure did
    # not survive the sample growing. World Cup specifically: 36 bets, model
    # 22.9% / market 16.3% / reality 13.9%, -43.2% ROI.
    #
    # So the always-YES lean is a MODEL error, not a market inefficiency. The
    # stdev is probably not the culprit (the physical argument above is sound);
    # the likelier suspects are the mean-margin inference and the normal
    # approximation to a discrete, skewed goal margin. Untested either way.
    # World Cup is switched off pending that work (MIN_EDGE_THRESHOLD_WORLDCUP).
    # Evidence: docs/my-documents/repo-reviews/2026-08-25-calibration-study.md
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
    "KXWC": "soccer",
}


_last_loaded_stdev_time = 0.0
_cached_calibrated_margin_stdev = {}
_cached_calibrated_total_stdev = {}

# Sane bounds for a calibrated stdev. The writer clamps to [0.8, 1.5]x a base
# in [1.5, 20.7], so anything outside this range is corruption / a hand-edit and
# must never reach the normal-CDF pricing model (a 0 stdev makes every favorite
# ~100%, a negative one breaks scipy).
_STDEV_MIN = 0.5
_STDEV_MAX = 60.0


def _valid_stdev_map(raw) -> dict | None:
    """Return a clean {sport: float} stdev map, or None if any entry is unusable
    (non-dict, non-numeric, bool, non-finite, or outside [_STDEV_MIN, _STDEV_MAX]).
    Reject-the-whole-map semantics keep a single bad value from silently mispricing
    a sport — the caller falls back to the hardcoded SPORT_*_STDEV defaults."""
    if not isinstance(raw, dict):
        return None
    clean = {}
    for key, value in raw.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value) or not (_STDEV_MIN <= value <= _STDEV_MAX):
            return None
        clean[key] = float(value)
    return clean


def load_calibration_stdevs():
    """Load per-sport stdev overrides from calibration_stdevs.json when present,
    fresh, and valid. Any problem (missing, stale, unreadable, wrong version, or
    out-of-range values) falls back safely to the hardcoded SPORT_*_STDEV defaults."""
    global _last_loaded_stdev_time, _cached_calibrated_margin_stdev, _cached_calibrated_total_stdev
    if "pytest" in sys.modules and not get_config().system.test_calibration_stdevs:
        return
    calibration_path = paths.DATA_DIR / "cache" / "calibration_stdevs.json"
    if not calibration_path.exists():
        return
    try:
        mtime = calibration_path.stat().st_mtime
    except OSError:
        return
    if mtime == _last_loaded_stdev_time:
        return

    # Mark this file version processed up front, regardless of the outcome below.
    # load_calibration_stdevs() runs on every per-scan stdev lookup (thousands of
    # times), so a stale/invalid file must not be re-parsed and re-warned each
    # call. Every return path from here leaves both caches in a defined state.
    _last_loaded_stdev_time = mtime
    _cached_calibrated_margin_stdev = {}
    _cached_calibrated_total_stdev = {}

    ttl_days = get_config().gates.calibration_stdevs_ttl_days
    file_age_days = (time.time() - mtime) / 86400
    if file_age_days > ttl_days:
        log.warning("calibration_stdevs.json is stale (age %.1f days > %d days). Using defaults.",
                    file_age_days, ttl_days)
        return

    try:
        with open(calibration_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        log.warning("calibration_stdevs.json unreadable (%s). Using defaults.", e)
        return

    if data.get("version") != 1:
        log.warning("calibration_stdevs.json has unsupported version %r. Using defaults.",
                    data.get("version"))
        return

    margin = _valid_stdev_map(data.get("margin_stdev", {}))
    total = _valid_stdev_map(data.get("total_stdev", {}))
    if margin is None or total is None:
        log.warning("calibration_stdevs.json contains invalid stdev values. Using defaults.")
        return

    _cached_calibrated_margin_stdev = margin
    _cached_calibrated_total_stdev = total
    log.info("Loaded calibrated standard deviations from %s (age %.1f days).",
             calibration_path, file_age_days)


def _get_margin_stdev(ticker: str) -> float:
    """Look up the score margin standard deviation for a ticker's sport."""
    load_calibration_stdevs()
    for prefix, sport in _PREFIX_TO_SPORT.items():
        if ticker.startswith(prefix):
            if sport in _cached_calibrated_margin_stdev:
                return _cached_calibrated_margin_stdev[sport]
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
    matched_event_ids = set()
    n_stale_excluded = 0

    for ev_idx, event in enumerate(events):
        for bookmaker in event.get("bookmakers", []):
            max_age = get_config().gates.max_live_book_age_seconds
            if _is_bookmaker_stale(bookmaker, event, max_age):
                n_stale_excluded += 1
                continue
            for market in bookmaker.get("markets", []):
                if market["key"] != "spreads":
                    continue
                # Unique best-matching outcome only — never pool both teams'
                # spreads when a truncated same-city name matches both sides.
                outcomes = market.get("outcomes", [])
                idx, ambiguous = _match_team_outcome(outcomes, team_name)
                if ambiguous:
                    log.warning(
                        "consensus_spread_prob: '%s' matches multiple outcomes "
                        "%s — ambiguous side, emitting no edge",
                        team_name, [o.get("name") for o in outcomes],
                    )
                    return None
                if idx is None:
                    continue
                o = outcomes[idx]
                matched_event_ids.add(ev_idx)
                book_spread = o.get("point", 0)
                book_odds = o.get("price", 2.0)
                # De-vig across both spread sides (favorite covers / underdog
                # covers) so the implied cover probability that infers the mean
                # margin excludes the book's overround. The two-way spread sums
                # to ~1.05-1.08 implied; using the raw implied biased the
                # inferred mean — and thus P(cover) — high for BOTH sides, which
                # made the model over-price every favorite to cover and only
                # ever take the YES side. Mirrors the moneyline devig in
                # consensus_fair_value.
                raw_implied = implied_prob(book_odds)
                book_overround = sum(implied_prob(oc.get("price", 2.0))
                                     for oc in outcomes)
                devigged = (raw_implied / book_overround
                            if book_overround > 0 else raw_implied)
                spread_data.append({
                    "book": bookmaker["key"],
                    "spread": book_spread,
                    "odds": book_odds,
                    "implied": round(devigged, 4),
                    "raw_implied": round(raw_implied, 4),
                })

    if not spread_data:
        return None

    if _live_consensus_too_thin(events, len(spread_data), n_stale_excluded):
        return None

    # Fix B: refuse to pool one team's spread across multiple games.
    if len(matched_event_ids) > 1:
        log.warning(
            "consensus_spread_prob: '%s' matched %d distinct events — refusing "
            "to pool across games", team_name, len(matched_event_ids),
        )
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
    # soccer: FOLLOW-UP (logged in ROADMAP 2026-06-29) — empirically too LOW.
    # 74 WC matches show a realized total-goals stdev of 1.86 vs 1.5 here, so
    # the totals model is over-confident (distribution too narrow). Left as-is
    # for now because soccer totals are profitable (75% WR / +24% ROI, n=24);
    # raise toward ~1.8 only with a deliberate calibration pass + backtest.
    "soccer": 1.5,
}


def _get_total_stdev(ticker: str) -> float:
    """Look up the total score standard deviation for a ticker's sport."""
    load_calibration_stdevs()
    for prefix, sport in _PREFIX_TO_SPORT.items():
        if ticker.startswith(prefix):
            if sport in _cached_calibrated_total_stdev:
                return _cached_calibrated_total_stdev[sport]
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
    matched_event_ids = set()
    n_stale_excluded = 0

    for ev_idx, event in enumerate(events):
        for bookmaker in event.get("bookmakers", []):
            max_age = get_config().gates.max_live_book_age_seconds
            if _is_bookmaker_stale(bookmaker, event, max_age):
                n_stale_excluded += 1
                continue
            for market in bookmaker.get("markets", []):
                if market["key"] != "totals":
                    continue
                outcomes = market.get("outcomes", [])
                over = next((o for o in outcomes if o.get("name") == "Over"), None)
                if over is None:
                    continue
                matched_event_ids.add(ev_idx)
                # De-vig Over against Over+Under so the implied over-probability
                # that infers the mean total excludes the book's overround —
                # same bias the spread model carried (raw implied runs ~half the
                # vig high, pushing the inferred mean and P(over) up).
                raw_implied = implied_prob(over["price"])
                book_overround = sum(implied_prob(o.get("price", 2.0))
                                     for o in outcomes)
                devigged = (raw_implied / book_overround
                            if book_overround > 0 else raw_implied)
                total_data.append({
                    "book": bookmaker["key"],
                    "line": over.get("point", 0),
                    "odds": over.get("price", 2.0),
                    "implied": round(devigged, 4),
                    "raw_implied": round(raw_implied, 4),
                })

    if not total_data:
        return None

    if _live_consensus_too_thin(events, len(total_data), n_stale_excluded):
        return None

    # Fix B: this function keys only on "Over" (no team match), so an unscoped
    # multi-event list silently blends totals from different games. Refuse.
    if len(matched_event_ids) > 1:
        log.warning(
            "consensus_total_prob: totals matched %d distinct events — refusing "
            "to pool across games", len(matched_event_ids),
        )
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


def _team_match_strength(odds_api_name: str, kalshi_name: str) -> int:
    """Score how strongly a Kalshi team reference matches an Odds API name.

    0 = no match; higher = stronger. The ranking lets callers disambiguate when
    a *truncated* Kalshi name loosely matches both teams in a same-city game.
    Kalshi truncates its sub-titles, so a Dodgers market reads "Los Angeles D";
    the weak city-word fallback (tier 1) then matches BOTH "Los Angeles Dodgers"
    and "Los Angeles Angels". Because substring (tier 3) outranks the city-word
    fallback, the correct team wins, and _match_team_outcome refuses on a tie.
    """
    odds_lower = odds_api_name.lower().strip()
    kalshi_lower = kalshi_name.lower().strip()

    # Tier 3 — one name contains the other. Covers truncated nicknames:
    # "los angeles d" is a prefix of "los angeles dodgers".
    if kalshi_lower in odds_lower or odds_lower in kalshi_lower:
        return 3

    # Tier 2 — alias table (e.g. "ny yankees" <-> "new york yankees").
    for alias_key, alias_list in TEAM_ALIASES.items():
        if kalshi_lower.startswith(alias_key) or alias_key.startswith(kalshi_lower):
            if any(a in odds_lower or odds_lower in a for a in alias_list):
                return 2

    kalshi_words = kalshi_lower.split()
    odds_words = odds_lower.split()
    if kalshi_words and odds_words:
        # Tier 2 — nickname (last word) shared: "dodgers" in "los angeles dodgers".
        if kalshi_words[-1] in odds_words:
            return 2
        # Tier 1 — only the city/first word matches. Ambiguous for same-city
        # matchups (both LA teams share "los"); kept as a last resort so a
        # full-city reference still hits, but ranked below real nickname matches.
        if kalshi_words[0] in odds_words:
            return 1

    return 0


def _team_match(odds_api_name: str, kalshi_name: str) -> bool:
    """Fuzzy match between Odds API team name and Kalshi team reference."""
    return _team_match_strength(odds_api_name, kalshi_name) > 0


def _match_team_outcome(outcomes: list, team_name: str) -> tuple[int | None, bool]:
    """Pick the single outcome that best matches team_name.

    Returns (index, ambiguous). index is None when nothing matches; ambiguous
    is True when >=2 outcomes tie at the top match strength. On a tie the caller
    emits no edge rather than guess which side — this is what stops a truncated
    "Los Angeles D" reference from silently resolving to whichever LA team the
    odds feed happened to list first (which inverted the favorite and
    fabricated a large phantom edge).
    """
    scored = [(_team_match_strength(o.get("name", ""), team_name), i)
              for i, o in enumerate(outcomes)]
    scored = [(s, i) for s, i in scored if s > 0]
    if not scored:
        return None, False
    best = max(s for s, _ in scored)
    top = [i for s, i in scored if s == best]
    if len(top) > 1:
        return None, True
    return top[0], False


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


def _clean_team(name: str) -> str:
    """Strip filler the rules-regex sometimes captures.

    Totals rules read "If the teams in the New York at San Antonio ..." so the
    first capture group picks up a "teams in the " prefix. Drop it so the name
    matches cleanly against odds-feed team names.
    """
    name = name.strip()
    name = re.sub(r"^(?:the\s+)?teams\s+in\s+the\s+", "", name, flags=re.IGNORECASE)
    # Playoff-series rules read "... the Game 4: San Antonio at New York ..."
    name = re.sub(r"^game\s+\d+:\s*", "", name, flags=re.IGNORECASE)
    return name.strip()


def extract_event_teams(market: dict) -> tuple[str, str] | None:
    """Extract both team names from the event ticker or rules."""
    rules = market.get("rules_primary", "")
    # Pattern: "Team A vs Team B" or "Team A at Team B" (multiple context words)
    match = re.search(
        r"the (.+?) (?:vs\.?|at) (.+?) (?:professional|college|men's college|women's college|NCAA|MLB|NBA|NHL|NFL|MLS)",
        rules, re.IGNORECASE,
    )
    if match:
        return _clean_team(match.group(1)), _clean_team(match.group(2))
    # Fallback: simpler pattern
    match = re.search(r"in the (.+?) (?:vs\.?|at) (.+?) (?:game|match)", rules, re.IGNORECASE)
    if match:
        return _clean_team(match.group(1)), _clean_team(match.group(2))
    # Tennis (Wimbledon) is already covered by the first pattern: its rules read
    # "... wins the <LastA> vs <LastB> professional tennis match in the 2026
    # Wimbledon ...", so the "(?:vs|at) ... professional" branch returns the two
    # players' last names (which substring-match the Odds API full names).
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


def _fp_float(raw, default: float = 0.0) -> float:
    """Parse one of Kalshi's fixed-point string fields (``volume_24h_fp``,
    ``open_interest_fp``) to a float, tolerating None/''/garbage."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


def liquidity_details(market: dict, spread: float) -> dict:
    """Raw book microstructure carried on every Opportunity for Gate 3.6.

    The composite already folds the spread into ``liquidity_score``, but that
    term is lossy (it clamps to 0 for any spread >= 50c) and says nothing about
    whether the market actually trades. The executor's liquidity gate needs the
    untransformed numbers, so stash them in ``details`` at scoring time -- the
    market dict is not available downstream.
    """
    return {
        "bid_ask_spread": round(spread, 4),
        "volume_24h": _fp_float(market.get("volume_24h_fp")),
        "open_interest": _fp_float(market.get("open_interest_fp")),
    }


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

    # Fix A: pin to the one odds event for THIS game (both teams, right day).
    # Without this, a team name matches any event it appears in — pairing the
    # market against the wrong opponent and fabricating edge.
    matched_event = find_market_event(market, odds_events)
    if matched_event is None:
        return None
    matched_event = _refresh_event_if_live(matched_event, market)
    odds_events = [matched_event]

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
    details.update(liquidity_details(market, spread))

    confidence = "low"
    if details["n_books"] >= 5:
        confidence = "medium"
    if details["n_books"] >= 8 and (details["max_fair"] - details["min_fair"]) < 0.05:
        confidence = "high"
    # C4 (2026-06-24): the base "high" tier above (>=8 sharp books + tight
    # consensus) carries no positive predictive signal. The 306-bet review
    # (F49) found High at 41.5% WR / +13.5% ROI vs Medium 53.2% / +44.4%, and
    # at *equal* claimed edge High underperforms Medium (5-10% edge bucket:
    # 34% vs 63% WR) — a tight 8-book consensus means the price is efficient,
    # so a large model edge against it is more likely model error than signal.
    # The "high" label is retained (it still gates NO-favorite bets at executor
    # Gate 4.6, a conservative restriction) but no longer earns a composite-
    # score premium below: high is capped to medium in the composite weight, so
    # it can no longer float no-signal bets up the --max-bets execution queue.
    # Sizing never used confidence. See R13 (one-way stat bumps) for prior art.

    # NBA consensus book threshold (R29)
    if ticker.startswith("KXNBA"):
        min_books = get_config().gates.min_consensus_books_nba
        if details.get("n_books", 0) < min_books:
            confidence = "low"

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
        {"low": 3, "medium": 6, "high": 6}[confidence] * 0.30 +  # confidence (30%) — C4: high capped to medium (F49)
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

    # Fix A: scope to the one odds event for this exact game (see detect_edge_game).
    matched_event = find_market_event(market, odds_events)
    if matched_event is None:
        return None
    matched_event = _refresh_event_if_live(matched_event, market)
    odds_events = [matched_event]

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
    details.update(liquidity_details(market, spread))

    # Confidence: based on book count AND book agreement
    book_range = details.get("book_spread_range", 0)
    if details["n_books"] >= 6 and book_range <= 2.0:
        confidence = "high"
    elif details["n_books"] >= 3 and book_range <= 4.0:
        confidence = "medium"
    else:
        confidence = "low"

    # NBA consensus book threshold (R29)
    if ticker.startswith("KXNBA"):
        min_books = get_config().gates.min_consensus_books_nba
        if details.get("n_books", 0) < min_books:
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
        {"low": 3, "medium": 6, "high": 6}[confidence] * 0.30 +  # C4: high capped to medium (F49)
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


_MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
           "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

# Eastern Time is UTC-4 (EDT) through the bulk of the sports calendar. This
# offset is used ONLY to disambiguate which odds event a Kalshi market refers
# to (matching scheduled start times); a 1-hour EST/EDT slip is immaterial
# against the multi-hour matching window, so we skip the tzdata dependency.
_ET_UTC_OFFSET_HOURS = 4


def _extract_game_date(ticker: str) -> str | None:
    """Extract game date from ticker as YYYY-MM-DD.

    Kalshi tickers use YYMMMDD format: e.g., 26MAR22 = 2026-03-22.
    """
    match = re.search(r"(\d{2})([A-Z]{3})(\d{2})", ticker)
    if not match:
        return None
    year_short, mon_str, day = match.groups()
    month = _MONTHS.get(mon_str)
    if not month:
        return None
    return f"20{year_short}-{month:02d}-{day}"


def _ticker_scheduled_utc(ticker: str) -> datetime | None:
    """Parse a game ticker's scheduled start (YYMMMDD + HHMM, ET) as UTC.

    Only moneyline (GAME) tickers embed the HHMM time, e.g.
    ``KXMLBGAME-26JUN052140WSHAZ-WSH`` -> Jun 5 2026 21:40 ET. Returns None
    when no time is embedded (spread/total tickers carry date only).
    """
    m = re.search(r"(\d{2})([A-Z]{3})(\d{2})(\d{4})", ticker)
    if not m:
        return None
    yy, mon_str, dd, hhmm = m.groups()
    month = _MONTHS.get(mon_str)
    if not month:
        return None
    try:
        # Treat the ET wall-clock numerals as UTC, then shift by the ET offset
        # to land on the true UTC instant (good enough for event matching).
        et_as_utc = datetime(2000 + int(yy), month, int(dd),
                             int(hhmm[:2]), int(hhmm[2:]), tzinfo=timezone.utc)
    except ValueError:
        return None
    return et_as_utc + timedelta(hours=_ET_UTC_OFFSET_HOURS)


def _parse_iso_utc(value: str) -> datetime | None:
    """Parse an Odds API commence_time (ISO-8601, possibly 'Z') to aware UTC."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _commence_et_date(event: dict) -> str | None:
    """ET calendar date (YYYY-MM-DD) of an odds event's commence_time."""
    dt = _parse_iso_utc(event.get("commence_time", ""))
    if dt is None:
        return None
    return (dt - timedelta(hours=_ET_UTC_OFFSET_HOURS)).date().isoformat()


def _event_has_matchup(event: dict, team_a: str, team_b: str) -> bool:
    """True if the event's two sides correspond to {team_a, team_b}.

    Requires each Kalshi team to match a *different* side of the event, so a
    single shared city/word can't satisfy both.
    """
    home = event.get("home_team", "") or ""
    away = event.get("away_team", "") or ""
    return (
        (_team_match(home, team_a) and _team_match(away, team_b))
        or (_team_match(away, team_a) and _team_match(home, team_b))
    )


def _is_tennis_market(ticker: str) -> bool:
    """True for tennis tickers, which need date-tolerant odds matching.

    Tennis tickers date the market by its *expected expiration* (roughly a day
    after the match), not by commence time, so exact ET-date equality never
    lines up with the odds feed (e.g. KXATPMATCH-26JUL01... is the Jun 30 09:00
    UTC Tsitsipas vs Djokovic match). Derived from KALSHI_TO_ODDS_SPORT so any
    future tennis tournament prefix mapped to a ``tennis_*`` key inherits this.
    """
    prefix = ticker.split("-", 1)[0]
    return KALSHI_TO_ODDS_SPORT.get(prefix, "").startswith("tennis_")


def find_market_event(market: dict, events: list) -> dict | None:
    """Return the single odds event for this market's specific game, or None.

    Opponent-validated matching (fix A): both teams in the Kalshi market must
    appear on opposite sides of the odds event. This prevents the contamination
    bug where a team name matched *any* event it appeared in — pairing a market
    against the wrong opponent (e.g. a different day's game) and fabricating a
    huge edge. When the real game is simply absent from the odds feed, this
    returns None so the caller emits no edge instead of guessing.

    A team in a series / doubleheader matches multiple events, so matching
    BOTH teams is not enough on its own — the date must also agree. A playoff
    series (e.g. NBA Finals SAS vs NYK, Games 1-4) puts the same two teams in
    the feed repeatedly with home/away alternating; pairing a Game-4 market
    against the only Game-1 event in the feed flips the favorite and fabricates
    a large edge. So the matched event must line up with the ticker's scheduled
    time (moneyline tickers embed HHMM) or, failing that, its ET game date.
    When the specific game is absent or ambiguous, return None (refuse).
    """
    teams = extract_event_teams(market)
    if not teams:
        return None
    team_a, team_b = teams
    candidates = [e for e in events if _event_has_matchup(e, team_a, team_b)]
    if not candidates:
        return None

    ticker = market.get("ticker", "")

    # Moneyline (GAME) tickers embed the start time — match it precisely. This
    # is authoritative: if the exact game isn't within the window, the specific
    # game is absent from the feed, so refuse rather than fall back to a looser
    # same-day match (which could grab the other half of a doubleheader).
    sched = _ticker_scheduled_utc(ticker)
    if sched is not None:
        best, best_diff = None, None
        for e in candidates:
            cdt = _parse_iso_utc(e.get("commence_time", ""))
            if cdt is None:
                continue
            diff = abs((cdt - sched).total_seconds())
            if best_diff is None or diff < best_diff:
                best, best_diff = e, diff
        if best is not None and best_diff <= 6 * 3600:
            return best
        log.warning(
            "find_market_event: no odds event within 6h of %s scheduled start "
            "— specific game absent, emitting no edge", ticker)
        return None

    # Tennis: the ticker date is the market's expected expiration (~a day after
    # the match), not its commence date, so exact ET-date equality never matches
    # the odds feed. A given player pair meets at most once per tournament, so a
    # single both-players candidate is unambiguous; accept it when its commence
    # lands within a few days of the ticker date. >1 candidate (unexpected in
    # one tournament) or a far-off date stays a refusal.
    if _is_tennis_market(ticker):
        if len(candidates) == 1:
            tdate = _extract_game_date(ticker)
            cdate = _commence_et_date(candidates[0])
            if not tdate:
                return candidates[0]
            try:
                within = abs((datetime.fromisoformat(cdate)
                              - datetime.fromisoformat(tdate)).days) <= 3
            except (ValueError, TypeError):
                within = False
            if within:
                return candidates[0]
        log.warning(
            "find_market_event: %d tennis candidate(s) for %s — absent/"
            "ambiguous, emitting no edge", len(candidates), ticker)
        return None

    # Spread/total and NBA/NHL game tickers carry the date but no time. Require
    # exactly one candidate on the ticker's ET date; 0 means absent, >1 means
    # an unresolvable same-day clash. Either way, refuse.
    gdate = _extract_game_date(ticker)
    if gdate:
        same_day = [e for e in candidates if _commence_et_date(e) == gdate]
        if len(same_day) == 1:
            return same_day[0]
        log.warning(
            "find_market_event: %d candidate events on %s for %s — series/"
            "absent/ambiguous, emitting no edge", len(same_day), gdate, ticker)
        return None

    # No date signal at all (unexpected for game tickers): only safe to match
    # when there is exactly one candidate.
    if len(candidates) == 1:
        return candidates[0]

    log.warning(
        "find_market_event: %d candidate events for %s (%s vs %s) — ambiguous, "
        "emitting no edge", len(candidates), ticker, team_a, team_b,
    )
    return None


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

    # Fix A: scope to the one odds event for this exact game. Totals are the
    # worst offender — consensus_total_prob pools every "Over" outcome across
    # all events with no team match at all, so an unscoped list blends games.
    matched_event = find_market_event(market, odds_events)
    if matched_event is None:
        return None
    matched_event = _refresh_event_if_live(matched_event, market)
    odds_events = [matched_event]

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
    details.update(liquidity_details(market, spread))

    confidence = "low" if details["n_books"] < 3 else "medium"

    # NBA consensus book threshold (R29)
    if ticker.startswith("KXNBA"):
        min_books = get_config().gates.min_consensus_books_nba
        if details.get("n_books", 0) < min_books:
            confidence = "low"

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
        {"low": 3, "medium": 6, "high": 6}[confidence] * 0.30 +  # C4: high capped to medium (F49)
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
    # KXMLBSPREAD/KXMLBTOTAL added 2026-07-20 — the series launched on Kalshi
    # after MLB was first wired (March), so MLB ran moneyline-only all season.
    "mlb":     ["KXMLBGAME", "KXMLBSPREAD", "KXMLBTOTAL", "KXMLBPLAYOFFS"],
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
    "worldcup": ["KXWCGAME", "KXWCSPREAD", "KXWCTOTAL"],
    "wc":      ["KXWCGAME", "KXWCSPREAD", "KXWCTOTAL"],
    "soccer":  ["KXMLSGAME", "KXMLSSPREAD", "KXMLSTOTAL", "KXUCL", "KXEPL", "KXLALIGA", "KXSERIEA", "KXBUNDESLIGA", "KXLIGUE1", "KXWCGAME", "KXWCSPREAD", "KXWCTOTAL"],
    # --- Combat Sports ---
    "ufc":     ["KXUFCFIGHT"],
    "boxing":  ["KXBOXING"],
    # --- Motorsports ---
    "f1":      ["KXF1", "KXF1CONSTRUCTORS"],
    "nascar":  ["KXNASCARRACE"],
    # --- Golf ---
    # PGA Tour markets (KXPGATOUR) are outright tournament-winner markets, so
    # they route to the futures scanner, which prices the 4 majors against The
    # Odds API outright fields. Weekly tour stops have no odds feed and are
    # skipped there. `golf-futures` is the equivalent futures-path filter.
    "pga":     ["__FUTURES__golf-futures"],
    # --- Cricket ---
    "ipl":     ["KXIPL"],
    # --- Tennis (Wimbledon) ---
    # Match-winner only (no spread/total). Both ATP and WTA singles.
    # NOTE: verify KXATPMATCH/KXWTAMATCH against live Kalshi markets.
    # Alternate prefixes to try: KXATPGAME, KXWTAGAME, KXWIMMEN, KXWMENSINGLES.
    "wimbledon": ["KXATPMATCH", "KXWTAMATCH"],
    "tennis":    ["KXATPMATCH", "KXWTAMATCH"],
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

    # Remove markets past their expected expiration. NOTE: expected_expiration_time
    # is the market CLOSE (after the game ends), so this does NOT drop in-progress
    # games — those keep producing edges (stale pre-game odds vs live Kalshi price)
    # until the market expires. The scan views flag them via is_game_started (R27/F44).
    now = datetime.now(timezone.utc).isoformat()
    before = len(all_markets)
    all_markets = [m for m in all_markets
                   if (m.get("expected_expiration_time") or "") > now
                   or not m.get("expected_expiration_time")]
    expired = before - len(all_markets)
    if expired:
        rprint(f"  Skipped {expired} closed markets (past expiration; in-progress games are kept)")

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
        is_game_started,
    )

    CATEGORY_LABELS = {
        "game": "ML",
        "spread": "Spread",
        "total": "Total",
        "player_prop": "Prop",
        "esports": "Esports",
    }

    from kalshi_executor import preflight_gate_status

    table = Table(title=f"Kalshi Opportunities (edge >= {MIN_EDGE:.0%})", show_lines=True)
    table.add_column("Sport", style="yellow")
    table.add_column("Bet", style="cyan", max_width=35)
    table.add_column("Type", style="magenta")
    table.add_column("Pick", style="bold white", max_width=22)
    table.add_column("When", style="dim")
    table.add_column("Started")  # R27: flag in-progress games (live price vs stale pre-game odds, F44)
    table.add_column("Mkt", justify="right")
    table.add_column("Fair", justify="right", style="green")
    table.add_column("Edge", justify="right", style="bold green")
    table.add_column("Conf.")
    table.add_column("Score", justify="right")
    table.add_column("Gate")  # R18: will this row clear the static risk gates?

    for o in opportunities:
        edge_color = "green" if o.edge >= 0.05 else "yellow"
        gate = preflight_gate_status(o)
        gate_display = "[green]ok[/green]" if gate == "ok" else f"[red]{gate}[/red]"
        table.add_row(
            sport_from_ticker(o.ticker),
            format_bet_label(o.ticker, o.title),
            CATEGORY_LABELS.get(o.category, o.category.title()),
            format_pick_label(o.ticker, o.title, o.side, o.category),
            parse_game_datetime(o.ticker),
            "[red]LIVE[/red]" if is_game_started(o.ticker) else "",
            f"${o.market_price:.2f}",
            f"${o.fair_value:.2f}",
            f"[{edge_color}]+{o.edge:.1%}[/{edge_color}]",
            o.confidence[:3].upper(),
            f"{o.composite_score:.1f}",
            gate_display,
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

        # Scope to this game's event (fix A) so the detail view matches the
        # scanner and never blends a team's odds across multiple games.
        matched_event = find_market_event(market, events)
        if matched_event is None:
            rprint("  [yellow]No single odds event matches this game "
                   "(absent from feed or ambiguous) — no edge computed[/yellow]")
            events = []
        else:
            teams = extract_event_teams(market)
            rprint(f"  Matched event: {matched_event.get('away_team')} @ "
                   f"{matched_event.get('home_team')}  (market teams: {teams})")
            events = [matched_event]

        if cat == "game" and team and events:
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
    scan_p.add_argument("--rescan", action="store_true",
                        help="R26: ignore the scan cache and rescan live. Default behavior "
                             "for --execute --pick/--ticker is to replay the cached preview "
                             "so row indices stay locked to what you saw.")

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

        # R26 scan-cache fingerprint — args that determine the row universe.
        # `--unit-size`, `--max-bets`, `--budget`, `--min-bets` deliberately
        # excluded: those reshape sizing/caps but the rows already in
        # `cached_rows` were sized under the original args.
        fingerprint = {
            "scanner": "sports",
            "filter": args.ticker_filter,
            "category": args.category,
            "date": resolved_date,
            "exclude_open": bool(args.exclude_open),
            "min_edge": float(args.min_edge),
            "top": int(args.top),
        }

        # ── R26 replay path: when the user follows up a preview with
        #    `--pick`/`--ticker --execute`, replay the cached rows instead
        #    of rescanning live. Without this, two back-to-back live scans
        #    can reorder rows on price/score drift, executing the wrong picks.
        cached_rows = None
        cache_age_seconds = None
        if (
            args.execute
            and (args.pick is not None or args.ticker is not None)
            and not args.rescan
        ):
            from scan_cache import load as _scan_cache_load, fingerprints_match
            cached = _scan_cache_load()
            if cached is None:
                rprint(
                    "[dim]Scan cache: no fresh preview found "
                    "— running a live scan first.[/dim]"
                )
            else:
                ok, diffs = fingerprints_match(cached["fingerprint"], fingerprint)
                if not ok:
                    rprint(
                        "\n[bold red]"
                        "╔══════════════════════════════════════════════════════════════════╗\n"
                        "║  WARNING: Scan-cache fingerprint mismatch.                       ║\n"
                        "║  Your --pick row numbers will reference a NEW ranking, not the   ║\n"
                        "║  preview you just saw. Differing args:                           ║\n"
                        "╚══════════════════════════════════════════════════════════════════╝"
                        "[/bold red]"
                    )
                    for d in diffs:
                        rprint(f"  [bold red]- {d}[/bold red]")
                    rprint(
                        "[bold yellow]Rescanning live now. To lock row order: re-run the "
                        "preview with the same filter args, then re-run with --pick. "
                        "Pass --rescan to silence this warning.[/bold yellow]\n"
                    )
                else:
                    cached_rows = cached["rows"]
                    cache_age_seconds = cached["age_seconds"]

        if cached_rows is not None:
            opportunities = []  # not used on the replay path
        else:
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
        if (cached_rows is not None) or (
            opportunities and (args.execute or args.unit_size is not None or args.budget is not None)
        ):
            from kalshi_executor import execute_pipeline, UNIT_SIZE, parse_budget_arg
            budget_val = parse_budget_arg(args.budget)
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
                fingerprint=fingerprint,
                cached_rows=cached_rows,
                cache_age_seconds=cache_age_seconds,
            )
        else:
            print_opportunities(opportunities)
        if args.save:
            from report_writer import save_execution_report, save_scan_report
            if sized_orders is not None:
                rpt = save_execution_report(sized_orders, report_type="sports",
                                            filter_label=args.ticker_filter or "", min_edge=args.min_edge,
                                            output_dir=args.report_dir)
            elif opportunities:
                rpt = save_scan_report(opportunities, report_type="sports",
                                       filter_label=args.ticker_filter or "", min_edge=args.min_edge,
                                       output_dir=args.report_dir)
            else:
                # No opportunities cleared the edge threshold. Still emit a
                # proof-of-life report (empty "0 orders" execution report) so the
                # paired email task has something to send on empty days, rather
                # than silently skipping (feedback_sameday_empty_emails).
                rpt = save_execution_report([], report_type="sports",
                                            filter_label=args.ticker_filter or "", min_edge=args.min_edge,
                                            output_dir=args.report_dir)
            if rpt:
                rprint(f"[dim]Report saved to {rpt}[/dim]")

    elif args.command == "detail":
        print_detail(client, args.ticker)


if __name__ == "__main__":
    main()
