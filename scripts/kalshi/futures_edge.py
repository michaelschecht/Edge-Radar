"""
futures_edge.py
Edge detection for Kalshi futures/championship/award markets.

Compares Kalshi outright prices against sportsbook consensus odds from
The Odds API's outrights markets. Uses N-way de-vigging to extract
fair probabilities from multi-outcome futures.

Supported:
    - NFL Super Bowl winner
    - NBA Championship winner
    - NHL Stanley Cup winner
    - MLB World Series winner
    - NCAAB Championship winner
    - Golf majors (Masters, PGA, US Open, The Open)
    - FIFA World Cup winner
    - Soccer league winners (UCL, EPL, La Liga, Serie A, Bundesliga, Ligue 1)

Usage:
    Called by edge_detector.py scan --filter futures
    or directly:
        python scripts/kalshi/futures_edge.py scan
        python scripts/kalshi/futures_edge.py scan --filter nba-futures
"""

import os
import sys
import re
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from statistics import median
from dataclasses import asdict

import requests
from dotenv import load_dotenv
from rich import print as rprint

# Shared imports
from opportunity import Opportunity

from logging_setup import setup_logging

load_dotenv()
log = setup_logging("futures_edge")

from odds_api import get_current_key, rotate_key, report_remaining
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# ── Kalshi-to-Odds-API Mapping ───────────────────────────────────────────────

# Maps Kalshi series ticker prefixes to Odds API outright sport keys.
# Each entry: (odds_api_sport_key, market_type, human_label)
# The label appears in scan output so the user knows what they're betting on.
FUTURES_MAP = {
    # NFL
    "KXSB":            ("americanfootball_nfl_super_bowl_winner", "outrights", "NFL Super Bowl Champion"),
    # NBA
    "KXNBA":           ("basketball_nba_championship_winner", "outrights", "NBA Finals Champion"),
    # NHL
    "KXNHL":           ("icehockey_nhl_championship_winner", "outrights", "NHL Stanley Cup Champion"),
    # MLB
    "KXMLB":           ("baseball_mlb_world_series_winner", "outrights", "MLB World Series Champion"),
    # NCAAB
    "KXNCAAMBMOP":     ("basketball_ncaab_championship_winner", "outrights", "NCAAB Most Outstanding Player"),
    # Golf
    "KXPGATOUR":       ("golf_pga_championship_winner", "outrights", "PGA Tour Winner"),

    # ── Intentionally NOT mapped (2026-04-24) ────────────────────────────────
    # These markets exist on Kalshi but don't have a sensible free-tier Odds
    # API counterpart, so scanning them with championship-winner odds produces
    # garbage edges (e.g. KXMLBPLAYOFFS-26-LAD priced at $0.04 NO vs "fair" of
    # $0.72 because LAD's odds to MAKE PLAYOFFS are ~95% but their odds to WIN
    # THE WORLD SERIES are ~28%). R19 tracks adding proper data sources:
    #   - KXMLBPLAYOFFS  : "will X make the MLB playoffs?" (different market)
    #   - KXNBAEAST/WEST : NBA conference winners (need conf_winner outrights)
    #   - KXNHLEAST/WEST : NHL conference winners (need conf_winner outrights)
    # Note: European soccer outrights (EPL, La Liga, etc.) and UCL are also
    # not on The Odds API free tier.
}

# Filter shortcuts for CLI
FUTURES_FILTER_SHORTCUTS = {
    "futures":       list(FUTURES_MAP.keys()),
    "nfl-futures":   ["KXSB"],
    "nba-futures":   ["KXNBA"],
    "nhl-futures":   ["KXNHL"],
    "mlb-futures":   ["KXMLB"],
    "ncaab-futures": ["KXNCAAMBMOP"],
    "golf-futures":  ["KXPGATOUR"],
}


# ── Odds API ─────────────────────────────────────────────────────────────────

_outrights_cache: dict[str, list] = {}


def fetch_outrights(sport_key: str) -> list:
    """Fetch outright/futures odds from The Odds API with key rotation. Cached per sport."""
    if sport_key in _outrights_cache:
        return _outrights_cache[sport_key]

    api_key = get_current_key()
    if not api_key:
        return []

    for attempt in range(3):
        try:
            resp = requests.get(
                f"{ODDS_API_BASE}/sports/{sport_key}/odds",
                params={
                    "apiKey": api_key,
                    "regions": "us",
                    "markets": "outrights",
                    "oddsFormat": "decimal",
                },
                timeout=15,
            )
            if resp.status_code in (401, 429):
                new_key = rotate_key("http_" + str(resp.status_code))
                if new_key:
                    api_key = new_key
                    continue
                else:
                    return []

            resp.raise_for_status()
            remaining = resp.headers.get("x-requests-remaining", "?")
            log.info("Odds API outrights %s: %d events, %s requests remaining",
                     sport_key, len(resp.json()), remaining)
            rprint(f"  Odds API: {sport_key} ({remaining} requests remaining)")

            try:
                report_remaining(api_key, int(remaining))
            except (ValueError, TypeError):
                pass

            _outrights_cache[sport_key] = resp.json()
            return resp.json()
        except Exception as e:
            log.warning("Odds API outright error for %s: %s", sport_key, e)
            return []

    return []


# ── N-Way De-Vigging ─────────────────────────────────────────────────────────

def devig_nway(outcomes: list[dict]) -> dict[str, float]:
    """
    De-vig N-way outright market by normalizing implied probabilities.

    Args:
        outcomes: list of {"name": "Team A", "price": 3.5, ...}

    Returns:
        dict mapping team name -> fair probability
    """
    implied = {}
    for o in outcomes:
        price = o.get("price", 0)
        if price > 1.0:
            implied[o["name"]] = 1.0 / price
        else:
            implied[o["name"]] = 0.0

    total = sum(implied.values())
    if total <= 0:
        return {}

    return {name: prob / total for name, prob in implied.items()}


def consensus_outright_fair_values(events: list) -> dict[str, dict]:
    """
    Build consensus fair probabilities across all bookmakers for an outright market.

    Returns dict: team_name -> {
        "fair_value": float (median de-vigged probability),
        "n_books": int,
        "min": float,
        "max": float,
    }
    """
    # Collect de-vigged probs per team per book (with book key for weighting)
    team_probs: dict[str, list[tuple[float, str]]] = {}  # name -> [(prob, book_key), ...]

    for event in events:
        for bookmaker in event.get("bookmakers", []):
            book_key = bookmaker["key"]
            for market in bookmaker.get("markets", []):
                if market["key"] != "outrights":
                    continue
                fair = devig_nway(market.get("outcomes", []))
                for name, prob in fair.items():
                    team_probs.setdefault(name, []).append((prob, book_key))

    # Compute weighted median for each team (sharp books count more)
    from edge_detector import weighted_median, _book_weight

    result = {}
    for name, prob_book_pairs in team_probs.items():
        if prob_book_pairs:
            probs = [p for p, _ in prob_book_pairs]
            weights = [_book_weight(bk) for _, bk in prob_book_pairs]
            med = weighted_median(probs, weights)
            result[name] = {
                "fair_value": med,
                "n_books": len(probs),
                "min": min(probs),
                "max": max(probs),
            }

    return result


# ── Name Matching ────────────────────────────────────────────────────────────

# Common aliases for fuzzy matching between Kalshi subtitles and Odds API names
FUTURES_ALIASES = {
    # NFL
    "kc": "kansas city chiefs", "chiefs": "kansas city chiefs",
    "sf": "san francisco 49ers", "49ers": "san francisco 49ers",
    "gb": "green bay packers", "packers": "green bay packers",
    # NBA
    "okc": "oklahoma city thunder", "thunder": "oklahoma city thunder",
    "lal": "los angeles lakers", "lakers": "los angeles lakers",
    "gsw": "golden state warriors", "warriors": "golden state warriors",
    "bos": "boston celtics", "celtics": "boston celtics",
    # NHL
    "edm": "edmonton oilers", "oilers": "edmonton oilers",
    "fla": "florida panthers", "panthers": "florida panthers",
    # Soccer
    "psg": "paris saint-germain", "paris saint germain": "paris saint-germain",
    "barca": "barcelona", "fc barcelona": "barcelona",
    "real": "real madrid", "atletico": "atletico madrid",
    "man city": "manchester city", "man utd": "manchester united",
    "bayern": "bayern munich", "fc bayern": "bayern munich",
    "inter": "inter milan", "ac milan": "ac milan",
}


def _futures_name_match(odds_name: str, kalshi_name: str) -> bool:
    """Fuzzy match between Odds API outright name and Kalshi market subtitle."""
    o = odds_name.lower().strip()
    k = kalshi_name.lower().strip()

    # Direct substring
    if k in o or o in k:
        return True

    # Alias lookup
    if k in FUTURES_ALIASES:
        if FUTURES_ALIASES[k] in o or o in FUTURES_ALIASES[k]:
            return True

    # Word overlap: if all words in the shorter string appear in the longer
    k_words = set(k.split())
    o_words = set(o.split())
    if len(k_words) >= 2 and k_words.issubset(o_words):
        return True
    if len(o_words) >= 2 and o_words.issubset(k_words):
        return True

    # Last word match (e.g., "Thunder" matches "Oklahoma City Thunder")
    if k.split()[-1] == o.split()[-1] and len(k.split()[-1]) > 3:
        return True

    return False


# ── Edge Detection ───────────────────────────────────────────────────────────

def detect_edge_futures(market: dict, fair_values: dict[str, dict], label: str = "") -> Opportunity | None:
    """
    Detect edge on a Kalshi futures market by comparing to consensus outright odds.

    Args:
        market: Kalshi market dict
        fair_values: Output of consensus_outright_fair_values()
        label: Human-readable bet type (e.g., "NBA Finals Champion")

    Returns:
        Opportunity or None
    """
    ticker = market.get("ticker", "")

    # Get the candidate name from Kalshi
    candidate = (market.get("yes_sub_title") or market.get("subtitle") or "").strip()
    if not candidate or candidate.lower() in ("yes", "no", ""):
        return None

    yes_ask = float(market.get("yes_ask_dollars") or 0)
    no_ask = float(market.get("no_ask_dollars") or 0)
    yes_bid = float(market.get("yes_bid_dollars") or 0)

    if yes_ask <= 0 or yes_ask >= 1.0:
        return None

    # Match to Odds API fair value
    matched_fair = None
    matched_name = None
    for odds_name, fv in fair_values.items():
        if _futures_name_match(odds_name, candidate):
            matched_fair = fv
            matched_name = odds_name
            break

    if not matched_fair:
        log.debug("No match for '%s' in %d outright outcomes", candidate, len(fair_values))
        return None

    fair_yes = matched_fair["fair_value"]
    fair_no = 1.0 - fair_yes

    # Pick better side
    yes_edge = fair_yes - yes_ask
    no_edge = (fair_no - no_ask) if 0 < no_ask < 1.0 else -1

    if yes_edge >= no_edge:
        side, fair_value, market_price, edge = "yes", fair_yes, yes_ask, yes_edge
    else:
        side, fair_value, market_price, edge = "no", fair_no, no_ask, no_edge

    if edge <= 0:
        return None

    # Confidence based on number of books and spread between min/max
    n_books = matched_fair["n_books"]
    spread_range = matched_fair["max"] - matched_fair["min"]
    if n_books >= 8 and spread_range < 0.05:
        confidence = "high"
    elif n_books >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    # Liquidity
    bid_ask_spread = yes_ask - yes_bid if yes_bid > 0 else 1.0
    liquidity = max(0, 10 - bid_ask_spread * 20)

    # Composite score
    edge_score = min(10, edge * 20)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * 5

    # Build a clear title: "NBA Finals Champion: Oklahoma City Thunder"
    display_title = f"{label}: {candidate}" if label else market.get("title", "")

    return Opportunity(
        ticker=ticker,
        title=display_title,
        category="futures",
        side=side,
        market_price=market_price,
        fair_value=round(fair_value, 4),
        edge=round(edge, 4),
        edge_source="outrights_consensus",
        confidence=confidence,
        liquidity_score=round(liquidity, 1),
        composite_score=round(composite, 1),
        details={
            "candidate": candidate,
            "matched_to": matched_name,
            "bet_type": label,
            "n_books": n_books,
            "fair_range": f"{matched_fair['min']:.3f} - {matched_fair['max']:.3f}",
        },
    )


# ── Scanner ──────────────────────────────────────────────────────────────────

def scan_futures_markets(
    client,
    min_edge: float = 0.03,
    ticker_filter: str | None = None,
    top_n: int = 20,
) -> list[Opportunity]:
    """
    Scan Kalshi futures markets for +EV opportunities.

    Args:
        client: KalshiClient
        min_edge: Minimum edge threshold
        ticker_filter: Filter shortcut (futures, nba-futures, etc.) or raw prefix
        top_n: Max opportunities to return
    """
    # Resolve filter
    if ticker_filter:
        shortcut = ticker_filter.lower()
        if shortcut in FUTURES_FILTER_SHORTCUTS:
            prefixes = FUTURES_FILTER_SHORTCUTS[shortcut]
            rprint(f"[bold]Futures filter: {shortcut} -> {', '.join(prefixes)}[/bold]")
        elif shortcut in FUTURES_MAP:
            prefixes = [shortcut.upper()]
        else:
            prefixes = [ticker_filter.upper()]
            rprint(f"[bold]Futures filter: {prefixes[0]}[/bold]")
    else:
        prefixes = list(FUTURES_MAP.keys())
        rprint(f"[bold]Scanning all futures markets ({len(prefixes)} series)[/bold]")

    # Fetch markets from Kalshi
    rprint("[bold]Fetching Kalshi futures markets...[/bold]")
    all_markets = []
    for prefix in prefixes:
        cursor = None
        for _ in range(3):
            resp = client.get_markets(limit=1000, status="open", series_ticker=prefix, cursor=cursor)
            batch = resp.get("markets", [])
            all_markets.extend(batch)
            cursor = resp.get("cursor", "")
            if not cursor:
                break
    rprint(f"  Found {len(all_markets)} futures markets")

    if not all_markets:
        return []

    # Determine which Odds API sport keys we need.
    # Match on the series ticker (everything before the first '-') so that
    # e.g. KXMLBPLAYOFFS-26-LAD doesn't collide with the KXMLB prefix and
    # get priced against World Series winner odds. Unmapped series are
    # silently skipped — see the FUTURES_MAP "intentionally NOT mapped"
    # block for the rationale.
    sports_needed: dict[str, list] = {}  # odds_sport_key -> [market, ...]
    market_labels: dict[str, str] = {}   # ticker -> human label
    for m in all_markets:
        ticker = m["ticker"]
        series = ticker.split("-", 1)[0]
        entry = FUTURES_MAP.get(series)
        if entry is None:
            continue
        sport_key, _, label = entry
        sports_needed.setdefault(sport_key, []).append(m)
        market_labels[ticker] = label

    # Fetch outright odds and build fair values
    opportunities: list[Opportunity] = []

    if not get_current_key():
        rprint("[yellow]No Odds API keys configured -- cannot fetch futures odds[/yellow]")
        return []

    rprint(f"\n[bold]Fetching outright odds for {len(sports_needed)} sport(s)...[/bold]")
    for sport_key, markets in sports_needed.items():
        events = fetch_outrights(sport_key)
        if not events:
            rprint(f"  [yellow]No outright data for {sport_key}[/yellow]")
            continue

        fair_values = consensus_outright_fair_values(events)
        rprint(f"  {sport_key}: {len(fair_values)} outcomes from {len(events[0].get('bookmakers', []))} books")

        matched = 0
        for m in markets:
            lbl = market_labels.get(m["ticker"], "")
            opp = detect_edge_futures(m, fair_values, label=lbl)
            if opp and opp.edge >= min_edge:
                opportunities.append(opp)
                matched += 1

        rprint(f"  -> {matched} opportunities with edge >= {min_edge:.0%}")

    opportunities.sort(key=lambda o: o.composite_score, reverse=True)
    return opportunities[:top_n]


# ── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from rich.console import Console
    from rich.table import Table
    from kalshi_client import KalshiClient

    parser = argparse.ArgumentParser(description="Kalshi futures edge detector")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Scan futures markets for edge")
    scan_p.add_argument("--filter", dest="ticker_filter",
                        help="Filter: futures, nba-futures, nhl-futures, soccer-futures, etc.")
    scan_p.add_argument("--min-edge", type=float, default=0.03)
    scan_p.add_argument("--top", type=int, default=20)
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
    scan_p.add_argument("--save", action="store_true",
                        help="Save results to watchlist")
    scan_p.add_argument("--date", type=str, default=None,
                        help="Only show markets on this date (today, tomorrow, YYYY-MM-DD, mar31)")
    scan_p.add_argument("--budget", type=str, default=None,
                        help="Max total cost for the batch. Percentage of bankroll (e.g. '10%%') "
                             "or dollar amount (e.g. '15'). Bets scaled down proportionally.")
    scan_p.add_argument("--exclude-open", action="store_true",
                        help="Exclude markets where you already have an open position")
    scan_p.add_argument("--report-dir", type=str, default=None,
                        help="Override report output directory for --save")

    args = parser.parse_args()

    client = KalshiClient()
    opps = scan_futures_markets(client, min_edge=args.min_edge,
                                 ticker_filter=args.ticker_filter, top_n=args.top)

    if opps and args.date:
        from ticker_display import filter_by_date, resolve_date_arg
        target = resolve_date_arg(args.date)
        before = len(opps)
        opps = filter_by_date(opps, target)
        rprint(f"[dim]Date filter ({target}): {before} -> {len(opps)} opportunities[/dim]")
    if opps and args.exclude_open:
        from ticker_display import filter_exclude_tickers
        positions = client.get_positions(limit=200, count_filter="position")
        open_tickers = {p.get("ticker", "") for p in positions.get("market_positions", [])}
        before = len(opps)
        opps = filter_exclude_tickers(opps, open_tickers)
        rprint(f"[dim]Excluded open positions: {before} -> {len(opps)} opportunities[/dim]")

    if not opps:
        rprint("[yellow]No futures opportunities found above edge threshold.[/yellow]")
    else:
        # If execution flags are set, route through the executor pipeline
        if args.execute or args.unit_size is not None or args.budget is not None:
            from kalshi_executor import execute_pipeline, UNIT_SIZE, parse_budget_arg
            execute_pipeline(
                client=client,
                opportunities=opps,
                execute=args.execute,
                max_bets=args.max_bets,
                unit_size=args.unit_size or UNIT_SIZE,
                pick_rows=args.pick,
                pick_tickers=args.ticker,
                budget=parse_budget_arg(args.budget),
                min_bets=args.min_bets,
            )
        else:
            console = Console()
            from ticker_display import parse_game_datetime

            table = Table(title=f"Futures Opportunities (edge >= {args.min_edge:.0%})", show_lines=True)
            table.add_column("Bet Type", style="bold", max_width=28)
            table.add_column("Candidate", style="cyan", max_width=25)
            table.add_column("Date", style="dim")
            table.add_column("Side")
            table.add_column("Mkt", justify="right")
            table.add_column("Fair", justify="right", style="green")
            table.add_column("Edge", justify="right", style="bold green")
            table.add_column("Conf.")
            table.add_column("Score", justify="right")

            for o in opps:
                table.add_row(
                    o.details.get("bet_type", "")[:28] or o.ticker[:28],
                    o.details.get("candidate", "")[:25],
                    parse_game_datetime(o.ticker),
                    o.side.upper(),
                    f"${o.market_price:.2f}",
                    f"${o.fair_value:.3f}",
                    f"+{o.edge:.1%}",
                    o.confidence[:3].upper(),
                    f"{o.composite_score:.1f}",
                )
            console.print(table)

        if args.save and opps:
            save_path = Path(__file__).resolve().parent.parent.parent / "data" / "watchlists" / "futures_opportunities.json"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_data = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "min_edge": args.min_edge,
                "count": len(opps),
                "opportunities": [asdict(o) for o in opps],
            }
            with open(save_path, "w") as f:
                json.dump(save_data, f, indent=2, default=str)
            rprint(f"[dim]Saved {len(opps)} opportunities to {save_path}[/dim]")
            from report_writer import save_scan_report
            rpt = save_scan_report(opps, report_type="futures",
                                   filter_label=args.ticker_filter or "", min_edge=args.min_edge,
                                   output_dir=args.report_dir)
            if rpt:
                rprint(f"[dim]Report saved to {rpt}[/dim]")
