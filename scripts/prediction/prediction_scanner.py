"""
prediction_scanner.py
Unified scanner for Kalshi prediction markets (crypto, weather, S&P 500).

Fetches markets from Kalshi, pulls external data from free APIs (CoinGecko,
NWS, Yahoo Finance), calculates fair probabilities, and surfaces +EV
opportunities.

Usage:
    python scripts/prediction/prediction_scanner.py scan
    python scripts/prediction/prediction_scanner.py scan --filter crypto
    python scripts/prediction/prediction_scanner.py scan --filter weather --min-edge 0.05
    python scripts/prediction/prediction_scanner.py scan --filter spx
    python scripts/prediction/prediction_scanner.py scan --filter btc --save
"""

import os
import sys
import json
import concurrent.futures
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import asdict

# Shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401 -- configures sys.path
from opportunity import Opportunity

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from kalshi_client import KalshiClient

# Local imports
from crypto_edge import detect_edge_crypto, CRYPTO_PREFIX_MAP, fetch_crypto_price, fetch_crypto_history
from weather_edge import detect_edge_weather, TICKER_CITY_MAP
from spx_edge import detect_edge_spx, fetch_spx_data
from mentions_edge import (
    MENTION_PREFIXES, get_mention_type,
    fetch_historical_counts, fetch_historical_mention_rate,
    detect_edge_lastword, detect_edge_binary_mention,
)
from companies_edge import detect_edge_bankruptcy, fetch_bankruptcy_data
from politics_edge import detect_edge_political_event, EVENT_BASE_RATES

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
from logging_setup import setup_logging
log = setup_logging("prediction_scanner")
console = Console()

MIN_EDGE = float(os.getenv("MIN_EDGE_THRESHOLD", "0.03"))
OPPORTUNITIES_PATH = paths.PREDICTION_OPPORTUNITIES_PATH


# ── Filter Shortcuts ─────────────────────────────────────────────────────────

FILTER_SHORTCUTS = {
    # Crypto
    "crypto":  list(CRYPTO_PREFIX_MAP.keys()),
    "btc":     ["KXBTC"],
    "eth":     ["KXETH"],
    "xrp":     ["KXXRP"],
    "doge":    ["KXDOGE"],
    "sol":     ["KXSOL"],
    # Weather
    "weather": list(TICKER_CITY_MAP.keys()),
    # S&P 500
    "spx":     ["KXINX"],
    "sp500":   ["KXINX"],
    # TV Mentions
    "mentions": list(MENTION_PREFIXES.keys()),
    "lastword": ["KXLASTWORDCOUNT"],
    "politicsmention": ["KXPOLITICSMENTION"],
    "foxnews": ["KXFOXNEWSMENTION"],
    "nbamention": ["KXNBAMENTION"],
    # Companies
    "companies": ["KXBANKRUPTCY", "KXIPO"],
    "bankruptcy": ["KXBANKRUPTCY"],
    "ipo":     ["KXIPO"],
    # Politics / Tech Events
    "politics": ["KXIMPEACH"],
    "impeach": ["KXIMPEACH"],
    "techscience": ["KXQUANTUM", "KXFUSION"],
    "quantum": ["KXQUANTUM"],
    "fusion":  ["KXFUSION"],
}


# ── Market Fetching ──────────────────────────────────────────────────────────

def get_all_prediction_prefixes() -> list[str]:
    """Return all known prediction market ticker prefixes."""
    prefixes = set()
    prefixes.update(CRYPTO_PREFIX_MAP.keys())
    prefixes.update(TICKER_CITY_MAP.keys())
    prefixes.add("KXINX")
    prefixes.update(MENTION_PREFIXES.keys())
    prefixes.update(["KXBANKRUPTCY", "KXIPO"])
    prefixes.update(EVENT_BASE_RATES.keys())
    return sorted(prefixes)


def categorize_prediction(ticker: str) -> str:
    """Categorize a prediction market by its ticker prefix."""
    for prefix in CRYPTO_PREFIX_MAP:
        if ticker.startswith(prefix):
            return "crypto"
    for prefix in TICKER_CITY_MAP:
        if ticker.startswith(prefix):
            return "weather"
    if ticker.startswith("KXINX"):
        return "spx"
    for prefix in MENTION_PREFIXES:
        if ticker.startswith(prefix):
            return "mentions"
    if ticker.startswith("KXBANKRUPTCY") or ticker.startswith("KXIPO"):
        return "companies"
    for prefix in EVENT_BASE_RATES:
        if ticker.startswith(prefix):
            return "politics"
    return "other"


# ── Main Scanner ─────────────────────────────────────────────────────────────

def scan_prediction_markets(
    client: KalshiClient,
    min_edge: float = MIN_EDGE,
    category_filter: str | None = None,
    ticker_filter: str | None = None,
    top_n: int = 20,
) -> list[Opportunity]:
    """
    Scan Kalshi prediction markets for +EV opportunities.

    Args:
        client: Authenticated KalshiClient
        min_edge: Minimum edge threshold
        category_filter: "crypto", "weather", "spx", or None for all
        ticker_filter: Filter shortcut or raw ticker prefix
        top_n: Maximum opportunities to return

    Returns:
        List of Opportunity objects sorted by composite score
    """
    # Resolve filter
    if ticker_filter:
        shortcut = ticker_filter.lower()
        if shortcut in FILTER_SHORTCUTS:
            filter_prefixes = FILTER_SHORTCUTS[shortcut]
            rprint(f"[bold]Filter: {shortcut} -> {', '.join(filter_prefixes)}[/bold]")
        else:
            filter_prefixes = [ticker_filter.upper()]
            rprint(f"[bold]Filter: ticker prefix {filter_prefixes[0]}[/bold]")
    elif category_filter:
        cat_map = {
            "crypto": list(CRYPTO_PREFIX_MAP.keys()),
            "weather": list(TICKER_CITY_MAP.keys()),
            "spx": ["KXINX"],
            "mentions": list(MENTION_PREFIXES.keys()),
            "companies": ["KXBANKRUPTCY", "KXIPO"],
            "politics": list(EVENT_BASE_RATES.keys()),
        }
        filter_prefixes = cat_map.get(category_filter, [])
        if not filter_prefixes:
            rprint(f"[red]Unknown category: {category_filter}[/red]")
            return []
        rprint(f"[bold]Category: {category_filter} -> {', '.join(filter_prefixes)}[/bold]")
    else:
        filter_prefixes = get_all_prediction_prefixes()
        rprint(f"[bold]Scanning all prediction markets ({len(filter_prefixes)} prefixes)[/bold]")

    # 1. Fetch markets from Kalshi
    rprint("[bold]Fetching Kalshi markets...[/bold]")

    def fetch_markets_for_prefix(prefix: str, max_pages: int = 3) -> list:
        markets = []
        cursor = None
        for _ in range(max_pages):
            try:
                resp = client.get_markets(limit=1000, status="open", series_ticker=prefix, cursor=cursor)
                batch = resp.get("markets", [])
                markets.extend(batch)
                cursor = resp.get("cursor", "")
                if not cursor:
                    break
            except Exception as e:
                log.warning(f"Error fetching markets for {prefix}: {e}")
                break
        return markets

    all_markets = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(fetch_markets_for_prefix, prefix) for prefix in filter_prefixes]
        for future in concurrent.futures.as_completed(futures):
            all_markets.extend(future.result())

    rprint(f"  Found {len(all_markets)} markets")

    # Remove expired markets
    now = datetime.now(timezone.utc).isoformat()
    before = len(all_markets)
    all_markets = [m for m in all_markets
                   if (m.get("expected_expiration_time") or "") > now
                   or not m.get("expected_expiration_time")]
    expired = before - len(all_markets)
    if expired:
        rprint(f"  Skipped {expired} expired markets")

    # 2. Categorize
    categorized: dict[str, list] = {}
    for m in all_markets:
        cat = categorize_prediction(m["ticker"])
        categorized.setdefault(cat, []).append(m)
    rprint(f"  Categories: { {k: len(v) for k, v in categorized.items()} }")

    # 3. Fetch external data and detect edges
    opportunities: list[Opportunity] = []

    # ── Crypto ──
    crypto_markets = categorized.get("crypto", [])
    if crypto_markets:
        rprint(f"\n[bold]Analyzing {len(crypto_markets)} crypto markets...[/bold]")
        # Pre-fetch prices for all coins
        coins_needed = set()
        for m in crypto_markets:
            for prefix, coin_id in CRYPTO_PREFIX_MAP.items():
                if m["ticker"].startswith(prefix):
                    coins_needed.add(coin_id)

        import time
        for i, coin_id in enumerate(coins_needed):
            if i > 0:
                time.sleep(2)  # CoinGecko free tier rate limit
            price = fetch_crypto_price(coin_id)
            if price:
                rprint(f"  {coin_id}: ${price:,.2f}")
                time.sleep(2)
                fetch_crypto_history(coin_id, days=7)

        for m in crypto_markets:
            result = detect_edge_crypto(m)
            if result and result["edge"] >= min_edge:
                opportunities.append(Opportunity(**result))

        rprint(f"  Crypto opportunities: {sum(1 for o in opportunities if o.category == 'crypto')}")

    # ── Weather ──
    weather_markets = categorized.get("weather", [])
    if weather_markets:
        rprint(f"\n[bold]Analyzing {len(weather_markets)} weather markets...[/bold]")
        for m in weather_markets:
            result = detect_edge_weather(m)
            if result and result["edge"] >= min_edge:
                opportunities.append(Opportunity(**result))

        rprint(f"  Weather opportunities: {sum(1 for o in opportunities if o.category == 'weather')}")

    # ── S&P 500 ──
    spx_markets = categorized.get("spx", [])
    if spx_markets:
        rprint(f"\n[bold]Analyzing {len(spx_markets)} S&P 500 markets...[/bold]")
        spx_data = fetch_spx_data()
        if spx_data:
            spx_price, annual_vol = spx_data
            rprint(f"  S&P 500: ${spx_price:,.2f}  VIX vol: {annual_vol*100:.1f}%")

            for m in spx_markets:
                result = detect_edge_spx(m, spx_price, annual_vol)
                if result and result["edge"] >= min_edge:
                    opportunities.append(Opportunity(**result))

            rprint(f"  S&P 500 opportunities: {sum(1 for o in opportunities if o.category == 'spx')}")
        else:
            rprint("  [red]Failed to fetch S&P 500 data[/red]")

    # ── TV Mentions ──
    mention_markets = categorized.get("mentions", [])
    if mention_markets:
        rprint(f"\n[bold]Analyzing {len(mention_markets)} mention markets...[/bold]")

        # Separate LASTWORDCOUNT (numeric) from binary mention markets
        lastword_markets = [m for m in mention_markets if m["ticker"].startswith("KXLASTWORDCOUNT")]
        binary_markets = [m for m in mention_markets if not m["ticker"].startswith("KXLASTWORDCOUNT")]

        # LASTWORDCOUNT: fetch historical counts
        if lastword_markets:
            counts = fetch_historical_counts(client, "KXLASTWORDCOUNT")
            rprint(f"  LASTWORDCOUNT: {len(counts)} historical episodes, mean={sum(counts)/len(counts):.0f}" if counts else "  LASTWORDCOUNT: no historical data")
            for m in lastword_markets:
                result = detect_edge_lastword(m, counts)
                if result and result["edge"] >= min_edge:
                    opportunities.append(Opportunity(**result))

        # Binary mentions: fetch historical YES rate per series
        for series_prefix in ["KXPOLITICSMENTION", "KXFOXNEWSMENTION", "KXNBAMENTION"]:
            series_markets = [m for m in binary_markets if m["ticker"].startswith(series_prefix)]
            if series_markets:
                rate = fetch_historical_mention_rate(client, series_prefix)
                if rate is not None:
                    rprint(f"  {series_prefix}: historical YES rate = {rate:.0%}")
                    for m in series_markets:
                        result = detect_edge_binary_mention(m, rate)
                        if result and result["edge"] >= min_edge:
                            opportunities.append(Opportunity(**result))
                else:
                    rprint(f"  {series_prefix}: insufficient historical data")

        rprint(f"  Mention opportunities: {sum(1 for o in opportunities if o.category == 'mentions')}")

    # ── Companies ──
    company_markets = categorized.get("companies", [])
    if company_markets:
        rprint(f"\n[bold]Analyzing {len(company_markets)} company markets...[/bold]")

        bankruptcy_markets = [m for m in company_markets if m["ticker"].startswith("KXBANKRUPTCY")]
        ipo_markets = [m for m in company_markets if m["ticker"].startswith("KXIPO")]

        if bankruptcy_markets:
            bk_data = fetch_bankruptcy_data()
            if bk_data:
                rprint(f"  Bankruptcy data: {bk_data.get('source', 'fred')}")
                for m in bankruptcy_markets:
                    result = detect_edge_bankruptcy(m, bk_data)
                    if result and result["edge"] >= min_edge:
                        opportunities.append(Opportunity(**result))

        if ipo_markets:
            rprint(f"  IPO markets: {len(ipo_markets)} (browse only, no automated edge)")

        rprint(f"  Company opportunities: {sum(1 for o in opportunities if o.category == 'companies')}")

    # ── Politics / Tech Events ──
    politics_markets = categorized.get("politics", [])
    if politics_markets:
        rprint(f"\n[bold]Analyzing {len(politics_markets)} political/tech event markets...[/bold]")
        for m in politics_markets:
            result = detect_edge_political_event(m)
            if result and result["edge"] >= min_edge:
                opportunities.append(Opportunity(**result))

        rprint(f"  Political/tech opportunities: {sum(1 for o in opportunities if o.category == 'politics')}")

    # Sort by composite score
    opportunities.sort(key=lambda o: o.composite_score, reverse=True)
    return opportunities[:top_n]


# ── Output ────────────────────────────────────────────────────────────────────

def print_opportunities(opportunities: list[Opportunity]):
    if not opportunities:
        rprint("[yellow]No opportunities found above edge threshold.[/yellow]")
        return

    table = Table(title=f"Prediction Market Opportunities (edge >= {MIN_EDGE:.0%})", show_lines=True)
    table.add_column("Ticker", style="cyan", max_width=35)
    table.add_column("Title", max_width=35)
    table.add_column("Cat.")
    table.add_column("Side")
    table.add_column("Mkt Price", justify="right")
    table.add_column("Fair Value", justify="right", style="green")
    table.add_column("Edge", justify="right", style="bold green")
    table.add_column("Conf.")
    table.add_column("Score", justify="right")

    for opp in opportunities:
        table.add_row(
            opp.ticker[:35],
            opp.title[:35],
            opp.category[:6],
            opp.side.upper(),
            f"${opp.market_price:.2f}",
            f"${opp.fair_value:.2f}",
            f"+{opp.edge:.1%}",
            opp.confidence[:3].upper(),
            f"{opp.composite_score:.1f}",
        )
    console.print(table)


def save_opportunities(opportunities: list[Opportunity]):
    data = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(opportunities),
        "min_edge": MIN_EDGE,
        "opportunities": [asdict(o) for o in opportunities],
    }
    with open(OPPORTUNITIES_PATH, "w") as f:
        json.dump(data, f, indent=2, default=str)
    rprint(f"[dim]Saved {len(opportunities)} opportunities to {OPPORTUNITIES_PATH}[/dim]")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kalshi prediction market edge detector")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Scan prediction markets for edge")
    scan_p.add_argument("--min-edge", type=float, default=MIN_EDGE,
                        help="Minimum edge threshold")
    scan_p.add_argument("--filter", dest="ticker_filter",
                        help="Filter: crypto, btc, eth, weather, spx, or raw ticker prefix")
    scan_p.add_argument("--category", choices=["crypto", "weather", "spx", "mentions", "companies", "politics"],
                        help="Filter by category")
    scan_p.add_argument("--top", type=int, default=20,
                        help="Number of top opportunities")
    scan_p.add_argument("--save", action="store_true",
                        help="Save results to watchlist")

    args = parser.parse_args()

    client = KalshiClient()

    if args.command == "scan":
        opportunities = scan_prediction_markets(
            client,
            min_edge=args.min_edge,
            category_filter=args.category,
            ticker_filter=args.ticker_filter,
            top_n=args.top,
        )
        print_opportunities(opportunities)

        if args.save and opportunities:
            save_opportunities(opportunities)


if __name__ == "__main__":
    main()
