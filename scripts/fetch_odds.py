"""
fetch_odds.py
Fetches current odds from The Odds API and surfaces value opportunities.
Usage:
    python scripts/fetch_odds.py --market nba --dry-run
    python scripts/fetch_odds.py --market all
    python scripts/fetch_odds.py --market nfl --min-edge 0.04
"""

import os
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

# ── Setup ──────────────────────────────────────────────────────────────────────
load_dotenv()
console = Console()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)

BASE_URL = "https://api.the-odds-api.com/v4"
API_KEY = os.getenv("ODDS_API_KEY")

MIN_EDGE = float(os.getenv("MIN_EDGE_THRESHOLD", 0.03))

# Market slugs supported by The Odds API
SPORT_KEYS = {
    "nba":      "basketball_nba",
    "nfl":      "americanfootball_nfl",
    "mlb":      "baseball_mlb",
    "nhl":      "icehockey_nhl",
    "ncaafb":   "americanfootball_ncaaf",
    "ncaabb":   "basketball_ncaab",
    "soccer":   "soccer_epl",
    "mma":      "mma_mixed_martial_arts",
}

WATCHLIST_PATH = Path("data/watchlists/pending_review.json")
WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)


# ── Core Functions ─────────────────────────────────────────────────────────────

def get_sports(active_only: bool = True) -> list:
    """Fetch list of available sports."""
    resp = requests.get(
        f"{BASE_URL}/sports",
        params={"apiKey": API_KEY, "all": str(not active_only).lower()},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def get_odds(sport_key: str, markets: str = "h2h,spreads,totals", regions: str = "us") -> list:
    """Fetch current odds for a sport."""
    resp = requests.get(
        f"{BASE_URL}/sports/{sport_key}/odds",
        params={
            "apiKey": API_KEY,
            "regions": regions,
            "markets": markets,
            "oddsFormat": "decimal",
            "dateFormat": "iso",
        },
        timeout=15
    )
    resp.raise_for_status()
    log.info(f"Requests remaining: {resp.headers.get('x-requests-remaining', 'unknown')}")
    return resp.json()


def american_to_decimal(american: int) -> float:
    """Convert American odds to decimal."""
    if american > 0:
        return (american / 100) + 1
    else:
        return (100 / abs(american)) + 1


def implied_prob(decimal_odds: float) -> float:
    """Decimal odds → implied probability."""
    return 1 / decimal_odds


def no_vig_prob(prob_a: float, prob_b: float) -> tuple[float, float]:
    """Remove vig from two-outcome market to get true probabilities."""
    total = prob_a + prob_b
    return prob_a / total, prob_b / total


def find_best_odds(outcomes: list, outcome_name: str) -> tuple[float, str]:
    """Find the best (highest) decimal odds for an outcome across bookmakers."""
    best_odds = 0.0
    best_book = ""
    for book in outcomes:
        for o in book.get("outcomes", []):
            if o["name"] == outcome_name and o["price"] > best_odds:
                best_odds = o["price"]
                best_book = book["key"]
    return best_odds, best_book


def calculate_edge(best_odds: float, fair_prob: float) -> float:
    """Edge = (fair_prob * best_odds) - 1"""
    return (fair_prob * best_odds) - 1


def analyze_event(event: dict, min_edge: float) -> list:
    """
    Analyze a single event for value opportunities.
    Returns list of opportunity dicts that meet the min_edge threshold.
    """
    opportunities = []
    home = event.get("home_team")
    away = event.get("away_team")
    commence = event.get("commence_time")
    sport = event.get("sport_key")

    for market_data in event.get("bookmakers", []):
        for market in market_data.get("markets", []):
            market_type = market["key"]  # h2h, spreads, totals
            outcomes = market.get("outcomes", [])

            if market_type == "h2h" and len(outcomes) == 2:
                # Two-outcome — calculate no-vig fair probabilities
                odds_a = outcomes[0]["price"]
                odds_b = outcomes[1]["price"]
                name_a = outcomes[0]["name"]
                name_b = outcomes[1]["name"]

                prob_a_raw = implied_prob(odds_a)
                prob_b_raw = implied_prob(odds_b)
                fair_a, fair_b = no_vig_prob(prob_a_raw, prob_b_raw)

                # Check all bookmakers for best available odds
                all_books = event.get("bookmakers", [])
                best_odds_a, best_book_a = find_best_odds(all_books, name_a)
                best_odds_b, best_book_b = find_best_odds(all_books, name_b)

                edge_a = calculate_edge(best_odds_a, fair_a)
                edge_b = calculate_edge(best_odds_b, fair_b)

                for name, edge, best_odds, best_book, fair_prob in [
                    (name_a, edge_a, best_odds_a, best_book_a, fair_a),
                    (name_b, edge_b, best_odds_b, best_book_b, fair_b),
                ]:
                    if edge >= min_edge:
                        opportunities.append({
                            "opportunity_id": f"OPP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{name[:4].upper()}",
                            "surfaced_at": datetime.now(timezone.utc).isoformat(),
                            "market_type": "sports",
                            "sport": sport,
                            "platform": best_book,
                            "event": f"{away} @ {home}",
                            "commence_time": commence,
                            "instrument": f"{name} ML",
                            "direction": "yes",
                            "market_key": market_type,
                            "best_odds_decimal": round(best_odds, 3),
                            "best_book": best_book,
                            "fair_probability": round(fair_prob, 4),
                            "implied_probability": round(implied_prob(best_odds), 4),
                            "edge_estimate": round(edge, 4),
                            "composite_score": round(min(edge / 0.01, 10), 1),  # rough scoring
                            "data_age_minutes": 0,
                            "status": "pending_review"
                        })

    return opportunities


def load_existing_watchlist() -> list:
    if WATCHLIST_PATH.exists():
        with open(WATCHLIST_PATH) as f:
            return json.load(f)
    return []


def save_watchlist(opportunities: list):
    existing = load_existing_watchlist()
    # Deduplicate by event + instrument
    existing_keys = {(o["event"], o["instrument"]) for o in existing}
    new_items = [o for o in opportunities if (o["event"], o["instrument"]) not in existing_keys]
    combined = existing + new_items
    with open(WATCHLIST_PATH, "w") as f:
        json.dump(combined, f, indent=2)
    return len(new_items)


def print_opportunities_table(opportunities: list):
    if not opportunities:
        rprint("[yellow]No opportunities above threshold found.[/yellow]")
        return

    table = Table(title=f"Value Opportunities (edge ≥ {MIN_EDGE:.1%})", show_lines=True)
    table.add_column("Event", style="cyan", no_wrap=False)
    table.add_column("Bet", style="white")
    table.add_column("Best Odds", justify="right")
    table.add_column("Book", style="dim")
    table.add_column("Fair Prob", justify="right")
    table.add_column("Edge", justify="right", style="green")
    table.add_column("Score", justify="right")

    for o in sorted(opportunities, key=lambda x: x["edge_estimate"], reverse=True):
        table.add_row(
            o["event"],
            o["instrument"],
            str(o["best_odds_decimal"]),
            o["best_book"],
            f"{o['fair_probability']:.1%}",
            f"+{o['edge_estimate']:.2%}",
            str(o["composite_score"]),
        )
    console.print(table)


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch odds and surface value opportunities.")
    parser.add_argument("--market", default="nba", choices=list(SPORT_KEYS.keys()) + ["all"],
                        help="Sport market to scan")
    parser.add_argument("--min-edge", type=float, default=MIN_EDGE,
                        help="Minimum edge threshold (default from .env)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't save to watchlist, just print")
    parser.add_argument("--save", action="store_true",
                        help="Save opportunities to watchlist (default: only saves if not --dry-run)")
    args = parser.parse_args()

    if not API_KEY:
        rprint("[red]ERROR: ODDS_API_KEY not set in .env[/red]")
        return

    # Determine which sports to scan
    sports_to_scan = list(SPORT_KEYS.items()) if args.market == "all" else \
                     [(args.market, SPORT_KEYS[args.market])]

    all_opportunities = []

    for sport_name, sport_key in sports_to_scan:
        rprint(f"\n[bold]Scanning {sport_name.upper()}...[/bold]")
        try:
            events = get_odds(sport_key)
            rprint(f"  Found {len(events)} events")

            for event in events:
                opps = analyze_event(event, args.min_edge)
                all_opportunities.extend(opps)

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                rprint(f"  [yellow]No active events for {sport_name}[/yellow]")
            else:
                rprint(f"  [red]Error fetching {sport_name}: {e}[/red]")
        except Exception as e:
            rprint(f"  [red]Unexpected error for {sport_name}: {e}[/red]")

    # Display results
    rprint(f"\n[bold]Total opportunities found: {len(all_opportunities)}[/bold]")
    print_opportunities_table(all_opportunities)

    # Save
    if all_opportunities and not args.dry_run:
        added = save_watchlist(all_opportunities)
        rprint(f"\n[green]✓ Saved {added} new opportunities to {WATCHLIST_PATH}[/green]")
    elif args.dry_run:
        rprint("\n[dim][DRY RUN] — watchlist not updated[/dim]")


if __name__ == "__main__":
    main()
