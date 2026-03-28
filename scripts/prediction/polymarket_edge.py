"""
polymarket_edge.py
Cross-reference Kalshi markets against Polymarket for edge detection.

Fetches active Polymarket markets via the Gamma API (free, no key required),
matches them to Kalshi markets by category + fuzzy title matching, and
surfaces price discrepancies as edge signals.

If Kalshi YES = $0.60 but Polymarket YES = $0.75, that's a 15-cent edge
signal suggesting Kalshi is underpriced.

Usage:
    Called by prediction_scanner.py with --cross-ref or --filter polymarket
    or directly:
        python scripts/prediction/polymarket_edge.py scan
        python scripts/prediction/polymarket_edge.py scan --filter crypto
        python scripts/prediction/polymarket_edge.py match KXBTC-28MAR26-T88000

Gamma API: https://gamma-api.polymarket.com (free, 750 req/10s)
"""

import re
import logging
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher

import requests

log = logging.getLogger("polymarket_edge")

GAMMA_API = "https://gamma-api.polymarket.com"
_TIMEOUT = 15
_USER_AGENT = "Edge-Radar/1.0 (polymarket-cross-ref)"

# ── Polymarket Market Cache ─────────────────────────────────────────────────

_market_cache: dict[str, list[dict]] = {}
_search_cache: dict[str, list[dict]] = {}


# ── Category-to-Search Mapping ──────────────────────────────────────────────

# Maps Kalshi prediction categories to Polymarket search queries / tags.
# These are used to pre-fetch relevant Polymarket markets for matching.
CATEGORY_SEARCH_MAP = {
    "crypto": [
        "Bitcoin", "BTC", "Ethereum", "ETH",
        "XRP", "Dogecoin", "DOGE", "Solana", "SOL",
    ],
    "weather": ["temperature", "weather", "degrees"],
    "spx": ["S&P 500", "S&P", "stock market"],
    "politics": ["impeachment", "president", "Congress"],
    "companies": ["bankruptcy", "IPO"],
    "mentions": [],  # TV mentions are Kalshi-specific, unlikely on Polymarket
}

# Kalshi ticker prefix -> normalized asset/topic for matching
TICKER_TOPIC_MAP = {
    "KXBTC": ("crypto", "bitcoin", "btc"),
    "KXETH": ("crypto", "ethereum", "eth"),
    "KXXRP": ("crypto", "xrp", "ripple"),
    "KXDOGE": ("crypto", "dogecoin", "doge"),
    "KXSOL": ("crypto", "solana", "sol"),
    "KXINX": ("spx", "s&p 500", "s&p"),
    "KXHIGH": ("weather", "temperature", "degrees"),
    "KXIMPEACH": ("politics", "impeach", "impeachment"),
    "KXBANKRUPTCY": ("companies", "bankruptcy", "bankrupt"),
}


# ── Gamma API Client ────────────────────────────────────────────────────────

def fetch_polymarket_search(query: str, limit: int = 50) -> list[dict]:
    """
    Search Polymarket markets via the Gamma API public search endpoint.
    Returns list of market dicts with question, tokens, prices, etc.
    """
    cache_key = f"{query}:{limit}"
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "closed": "false",
                "limit": limit,
                "active": "true",
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        markets = resp.json()
        if not isinstance(markets, list):
            markets = markets.get("data", markets.get("markets", []))

        # Client-side filter by query terms (Gamma /markets doesn't have
        # a text search param, so we filter locally after fetching)
        query_lower = query.lower()
        query_terms = query_lower.split()
        filtered = [
            m for m in markets
            if any(
                term in (m.get("question", "") + " " + m.get("description", "")).lower()
                for term in query_terms
            )
        ]

        _search_cache[cache_key] = filtered
        log.info("Polymarket search '%s': %d/%d markets matched", query, len(filtered), len(markets))
        return filtered
    except Exception as e:
        log.warning("Polymarket search error for '%s': %s", query, e)
        return []


def fetch_polymarket_markets_bulk(limit: int = 200, offset: int = 0) -> list[dict]:
    """
    Fetch a batch of active Polymarket markets from the Gamma API.
    """
    cache_key = f"bulk:{limit}:{offset}"
    if cache_key in _market_cache:
        return _market_cache[cache_key]

    try:
        resp = requests.get(
            f"{GAMMA_API}/markets",
            params={
                "closed": "false",
                "active": "true",
                "limit": limit,
                "offset": offset,
            },
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        markets = resp.json()
        if not isinstance(markets, list):
            markets = markets.get("data", markets.get("markets", []))

        _market_cache[cache_key] = markets
        log.info("Polymarket bulk fetch: %d markets (offset=%d)", len(markets), offset)
        return markets
    except Exception as e:
        log.warning("Polymarket bulk fetch error: %s", e)
        return []


def fetch_polymarket_by_category(category: str) -> list[dict]:
    """
    Fetch Polymarket markets relevant to a Kalshi category.
    Uses search terms from CATEGORY_SEARCH_MAP.
    """
    cache_key = f"cat:{category}"
    if cache_key in _market_cache:
        return _market_cache[cache_key]

    queries = CATEGORY_SEARCH_MAP.get(category, [])
    if not queries:
        return []

    all_markets = []
    seen_ids = set()

    # Fetch a large batch and filter locally per search term
    bulk = fetch_polymarket_markets_bulk(limit=200)

    for query in queries:
        q_lower = query.lower()
        for m in bulk:
            mid = m.get("id") or m.get("condition_id", "")
            if mid in seen_ids:
                continue
            text = (m.get("question", "") + " " + m.get("description", "")).lower()
            if q_lower in text:
                all_markets.append(m)
                seen_ids.add(mid)

    _market_cache[cache_key] = all_markets
    log.info("Polymarket category '%s': %d markets from %d queries",
             category, len(all_markets), len(queries))
    return all_markets


# ── Market Matching ─────────────────────────────────────────────────────────

def _normalize_title(title: str) -> str:
    """Normalize a market title for fuzzy matching."""
    t = title.lower().strip()
    # Remove common filler words
    t = re.sub(r"\b(will|the|be|on|at|by|to|of|a|an|in|for|or|and)\b", " ", t)
    # Normalize whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _extract_strike(text: str) -> float | None:
    """Extract a numeric strike/threshold from market text."""
    # Match dollar amounts: $88,000 or $88000 or 88000
    m = re.search(r"\$?([\d,]+(?:\.\d+)?)", text.replace(",", ""))
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def _extract_date(text: str) -> str | None:
    """Extract a date reference from market text (YYYY-MM-DD or month day)."""
    # ISO date
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    # "March 28" style
    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "jun": "06", "jul": "07", "aug": "08", "sep": "09",
        "oct": "10", "nov": "11", "dec": "12",
    }
    for month_name, month_num in months.items():
        pattern = rf"\b{month_name}\s+(\d{{1,2}})\b"
        m = re.search(pattern, text.lower())
        if m:
            day = int(m.group(1))
            year = datetime.now().year
            return f"{year}-{month_num}-{day:02d}"
    return None


def _similarity(a: str, b: str) -> float:
    """Compute string similarity ratio (0-1)."""
    return SequenceMatcher(None, a, b).ratio()


def _match_score(kalshi_market: dict, poly_market: dict) -> float:
    """
    Score how well a Polymarket market matches a Kalshi market.
    Returns 0-1 where 1 is a perfect match.

    Considers: title similarity, strike price match, date match, asset match.
    """
    k_title = kalshi_market.get("title", "")
    p_question = poly_market.get("question", "")

    k_norm = _normalize_title(k_title)
    p_norm = _normalize_title(p_question)

    # Title similarity (base score)
    title_sim = _similarity(k_norm, p_norm)

    # Strike price match bonus
    k_strike = kalshi_market.get("floor_strike")
    if k_strike is None:
        k_strike = _extract_strike(k_title)
    else:
        k_strike = float(k_strike)

    p_strike = _extract_strike(p_question)

    strike_bonus = 0.0
    if k_strike and p_strike:
        if k_strike == p_strike:
            strike_bonus = 0.3  # Exact strike match is a strong signal
        elif abs(k_strike - p_strike) / max(k_strike, p_strike) < 0.02:
            strike_bonus = 0.2  # Within 2% is still good

    # Date match bonus
    k_date = _extract_date(k_title)
    p_date = _extract_date(p_question)
    date_bonus = 0.2 if (k_date and p_date and k_date == p_date) else 0.0

    # Asset keyword match bonus (BTC, ETH, S&P, etc.)
    asset_keywords = [
        "bitcoin", "btc", "ethereum", "eth", "xrp", "ripple",
        "dogecoin", "doge", "solana", "sol", "s&p", "s&p 500",
    ]
    shared_assets = sum(
        1 for kw in asset_keywords
        if kw in k_norm and kw in p_norm
    )
    asset_bonus = min(0.2, shared_assets * 0.1)

    total = title_sim + strike_bonus + date_bonus + asset_bonus
    # Normalize to 0-1 range (max theoretical = 1.0 + 0.3 + 0.2 + 0.2 = 1.7)
    return min(1.0, total / 1.2)


def find_matching_market(
    kalshi_market: dict,
    poly_markets: list[dict],
    min_score: float = 0.45,
) -> tuple[dict, float] | None:
    """
    Find the best matching Polymarket market for a given Kalshi market.

    Returns (polymarket_market, match_score) or None if no match above threshold.
    """
    if not poly_markets:
        return None

    best_match = None
    best_score = 0.0

    for pm in poly_markets:
        score = _match_score(kalshi_market, pm)
        if score > best_score:
            best_score = score
            best_match = pm

    if best_match and best_score >= min_score:
        return best_match, best_score

    return None


# ── Price Extraction ────────────────────────────────────────────────────────

def get_polymarket_price(market: dict) -> tuple[float, float] | None:
    """
    Extract YES and NO prices from a Polymarket market.
    Returns (yes_price, no_price) or None.
    """
    tokens = market.get("tokens", [])

    yes_price = None
    no_price = None

    for token in tokens:
        outcome = token.get("outcome", "").lower()
        price = token.get("price")
        if price is not None:
            price = float(price)
            if outcome == "yes":
                yes_price = price
            elif outcome == "no":
                no_price = price

    # Some markets store prices at market level
    if yes_price is None:
        best_ask = market.get("bestAsk")
        if best_ask is not None:
            yes_price = float(best_ask)

    if yes_price is None:
        outcomePrices = market.get("outcomePrices")
        if outcomePrices:
            try:
                if isinstance(outcomePrices, str):
                    import json
                    outcomePrices = json.loads(outcomePrices)
                if isinstance(outcomePrices, list) and len(outcomePrices) >= 2:
                    yes_price = float(outcomePrices[0])
                    no_price = float(outcomePrices[1])
            except (ValueError, TypeError, IndexError):
                pass

    if yes_price is not None:
        if no_price is None:
            no_price = 1.0 - yes_price
        return yes_price, no_price

    return None


# ── Edge Detection ──────────────────────────────────────────────────────────

def detect_cross_market_edge(
    kalshi_market: dict,
    poly_match: dict,
    match_score: float,
) -> dict | None:
    """
    Detect edge by comparing Kalshi price to Polymarket price for matched markets.

    The Polymarket price serves as an independent fair value estimate from
    a deep, liquid prediction market with a different participant base.

    Returns an opportunity dict or None if no edge.
    """
    ticker = kalshi_market.get("ticker", "")
    title = kalshi_market.get("title", "")

    # Get Kalshi prices
    k_yes_ask = float(kalshi_market.get("yes_ask_dollars") or 0)
    k_no_ask = float(kalshi_market.get("no_ask_dollars") or 0)
    k_yes_bid = float(kalshi_market.get("yes_bid_dollars") or 0)

    if k_yes_ask <= 0 or k_yes_ask >= 1.0:
        return None

    # Get Polymarket prices
    poly_prices = get_polymarket_price(poly_match)
    if not poly_prices:
        return None

    p_yes, p_no = poly_prices

    if p_yes <= 0 or p_yes >= 1.0:
        return None

    # Use Polymarket price as fair value reference
    # YES edge: Polymarket says YES is worth more than Kalshi asks
    yes_edge = p_yes - k_yes_ask
    # NO edge: Polymarket says NO is worth more than Kalshi asks
    no_edge = (p_no - k_no_ask) if 0 < k_no_ask < 1.0 else -1

    if yes_edge >= no_edge:
        side = "yes"
        fair_value = p_yes
        market_price = k_yes_ask
        edge = yes_edge
    else:
        side = "no"
        fair_value = p_no
        market_price = k_no_ask
        edge = no_edge

    if edge <= 0:
        return None

    # Confidence is driven by match quality and price discrepancy magnitude
    if match_score >= 0.75 and edge >= 0.10:
        confidence = "high"
    elif match_score >= 0.55 and edge >= 0.05:
        confidence = "medium"
    else:
        confidence = "low"

    # Liquidity score from Kalshi spread
    spread = k_yes_ask - k_yes_bid if k_yes_bid > 0 else 1.0
    liquidity = max(0, 10 - spread * 20)

    # Polymarket volume as additional liquidity signal
    poly_volume = 0
    try:
        poly_volume = float(poly_match.get("volume", 0) or 0)
    except (ValueError, TypeError):
        pass

    volume_bonus = min(2.0, poly_volume / 50000)  # Up to +2 for high volume
    liquidity = min(10, liquidity + volume_bonus)

    # Composite score
    edge_score = min(10, edge * 20)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    match_adj = match_score * 10  # Higher match quality = more trustworthy

    composite = (
        0.30 * edge_score
        + 0.25 * conf_score
        + 0.25 * match_adj
        + 0.20 * liquidity
    )

    return {
        "ticker": ticker,
        "title": title,
        "category": "polymarket_xref",
        "side": side,
        "market_price": market_price,
        "fair_value": round(fair_value, 4),
        "edge": round(edge, 4),
        "edge_source": "polymarket_cross_reference",
        "confidence": confidence,
        "liquidity_score": round(liquidity, 1),
        "composite_score": round(composite, 1),
        "details": {
            "polymarket_question": poly_match.get("question", ""),
            "polymarket_yes": round(p_yes, 4),
            "polymarket_no": round(p_no, 4),
            "polymarket_volume": poly_volume,
            "kalshi_yes_ask": k_yes_ask,
            "kalshi_no_ask": k_no_ask,
            "match_score": round(match_score, 3),
            "price_discrepancy": round(abs(p_yes - k_yes_ask), 4),
        },
    }


# ── Batch Scanner ───────────────────────────────────────────────────────────

def scan_polymarket_cross_refs(
    kalshi_markets: list[dict],
    categories: list[str] | None = None,
    min_edge: float = 0.03,
    min_match_score: float = 0.45,
) -> list[dict]:
    """
    Scan a batch of Kalshi markets for Polymarket cross-reference edges.

    Args:
        kalshi_markets: List of Kalshi market dicts
        categories: Which categories to check (None = all available)
        min_edge: Minimum edge to report
        min_match_score: Minimum match quality threshold

    Returns list of opportunity dicts sorted by composite score.
    """
    if not kalshi_markets:
        return []

    # Determine categories to fetch from Polymarket
    cats = categories or list(CATEGORY_SEARCH_MAP.keys())

    # Pre-fetch Polymarket markets for each relevant category
    poly_by_cat: dict[str, list[dict]] = {}
    for cat in cats:
        markets = fetch_polymarket_by_category(cat)
        if markets:
            poly_by_cat[cat] = markets
            log.info("Polymarket %s: %d candidate markets", cat, len(markets))

    if not poly_by_cat:
        log.info("No Polymarket markets found for categories: %s", cats)
        return []

    # Match each Kalshi market against relevant Polymarket markets
    opportunities = []

    for km in kalshi_markets:
        ticker = km.get("ticker", "")

        # Find which category this Kalshi market belongs to
        km_cat = None
        for prefix, (cat, *_keywords) in TICKER_TOPIC_MAP.items():
            if ticker.startswith(prefix):
                km_cat = cat
                break

        if not km_cat or km_cat not in poly_by_cat:
            continue

        result = find_matching_market(km, poly_by_cat[km_cat], min_score=min_match_score)
        if not result:
            continue

        poly_match, match_score = result
        opp = detect_cross_market_edge(km, poly_match, match_score)

        if opp and opp["edge"] >= min_edge:
            opportunities.append(opp)

    opportunities.sort(key=lambda o: o["composite_score"], reverse=True)
    return opportunities


def enrich_opportunity_with_polymarket(
    opportunity: dict,
    kalshi_market: dict,
    poly_markets: list[dict] | None = None,
    min_match_score: float = 0.45,
) -> dict:
    """
    Enrich an existing edge opportunity with Polymarket cross-reference data.

    If Polymarket agrees with the edge direction, boosts confidence.
    If Polymarket disagrees, lowers confidence. If no match, returns unchanged.

    Args:
        opportunity: Existing opportunity dict from another edge module
        kalshi_market: The raw Kalshi market dict
        poly_markets: Pre-fetched Polymarket markets (fetches if None)

    Returns the opportunity dict with polymarket_xref added to details.
    """
    ticker = kalshi_market.get("ticker", "")

    # Find category
    km_cat = None
    for prefix, (cat, *_keywords) in TICKER_TOPIC_MAP.items():
        if ticker.startswith(prefix):
            km_cat = cat
            break

    if not km_cat:
        return opportunity

    if poly_markets is None:
        poly_markets = fetch_polymarket_by_category(km_cat)

    if not poly_markets:
        return opportunity

    result = find_matching_market(kalshi_market, poly_markets, min_score=min_match_score)
    if not result:
        return opportunity

    poly_match, match_score = result
    poly_prices = get_polymarket_price(poly_match)
    if not poly_prices:
        return opportunity

    p_yes, p_no = poly_prices

    # Determine if Polymarket agrees with our edge direction
    side = opportunity.get("side", "yes")
    fair_value = opportunity.get("fair_value", 0.5)
    market_price = opportunity.get("market_price", 0.5)

    if side == "yes":
        poly_agrees = p_yes > market_price
        poly_fair = p_yes
    else:
        poly_agrees = p_no > market_price
        poly_fair = p_no

    # Confidence adjustment
    details = dict(opportunity.get("details", {}))
    details["polymarket_xref"] = {
        "question": poly_match.get("question", ""),
        "poly_yes": round(p_yes, 4),
        "poly_no": round(p_no, 4),
        "poly_fair_for_side": round(poly_fair, 4),
        "match_score": round(match_score, 3),
        "agrees_with_edge": poly_agrees,
    }

    updated = dict(opportunity)
    updated["details"] = details

    # Adjust composite score based on Polymarket agreement
    score = opportunity.get("composite_score", 5.0)
    if poly_agrees and match_score >= 0.55:
        # Polymarket confirms our edge -- boost score
        boost = match_score * 1.5  # Up to +1.5 for perfect match
        updated["composite_score"] = round(min(10, score + boost), 1)
        updated["edge_source"] = opportunity.get("edge_source", "") + "+polymarket"
    elif not poly_agrees and match_score >= 0.65:
        # Polymarket disagrees -- reduce score
        penalty = match_score * 1.0
        updated["composite_score"] = round(max(0, score - penalty), 1)
        # Downgrade confidence if it was high
        if updated.get("confidence") == "high":
            updated["confidence"] = "medium"

    return updated


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    import argparse
    import sys
    from pathlib import Path
    from rich.console import Console
    from rich.table import Table
    from rich import print as rprint
    from dotenv import load_dotenv

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
    import paths  # noqa: F401

    load_dotenv()
    logging.basicConfig(level="INFO")
    console = Console()

    parser = argparse.ArgumentParser(description="Polymarket cross-reference edge detector")
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Scan for cross-market edges")
    scan_p.add_argument("--filter", choices=["crypto", "weather", "spx", "politics", "companies"],
                        help="Category filter")
    scan_p.add_argument("--min-edge", type=float, default=0.03)
    scan_p.add_argument("--min-match", type=float, default=0.45,
                        help="Minimum match score (0-1)")
    scan_p.add_argument("--top", type=int, default=20)

    match_p = sub.add_parser("match", help="Find Polymarket match for a Kalshi ticker")
    match_p.add_argument("ticker", help="Kalshi ticker to match")

    args = parser.parse_args()

    if args.command == "scan":
        from kalshi_client import KalshiClient
        client = KalshiClient()

        # Determine which prefixes to fetch
        if args.filter:
            from prediction_scanner import FILTER_SHORTCUTS
            prefixes = FILTER_SHORTCUTS.get(args.filter, [args.filter.upper()])
        else:
            prefixes = list(TICKER_TOPIC_MAP.keys())

        rprint(f"[bold]Fetching Kalshi markets for {len(prefixes)} prefixes...[/bold]")
        kalshi_markets = []
        for prefix in prefixes:
            resp = client.get_markets(limit=200, status="open", series_ticker=prefix)
            kalshi_markets.extend(resp.get("markets", []))
        rprint(f"  Found {len(kalshi_markets)} Kalshi markets")

        cats = [args.filter] if args.filter else None
        results = scan_polymarket_cross_refs(
            kalshi_markets,
            categories=cats,
            min_edge=args.min_edge,
            min_match_score=args.min_match,
        )

        if not results:
            rprint("[yellow]No cross-market edges found.[/yellow]")
            return

        table = Table(title="Polymarket Cross-Reference Edges", show_lines=True)
        table.add_column("Kalshi Ticker", style="cyan", max_width=30)
        table.add_column("Side")
        table.add_column("Kalshi", justify="right")
        table.add_column("Poly Fair", justify="right", style="green")
        table.add_column("Edge", justify="right", style="bold green")
        table.add_column("Match", justify="right")
        table.add_column("Conf.")
        table.add_column("Score", justify="right")
        table.add_column("Poly Question", max_width=35)

        for opp in results[:args.top]:
            d = opp["details"]
            table.add_row(
                opp["ticker"][:30],
                opp["side"].upper(),
                f"${opp['market_price']:.2f}",
                f"${opp['fair_value']:.2f}",
                f"+{opp['edge']:.1%}",
                f"{d['match_score']:.0%}",
                opp["confidence"][:3].upper(),
                f"{opp['composite_score']:.1f}",
                d.get("polymarket_question", "")[:35],
            )

        console.print(table)

    elif args.command == "match":
        from kalshi_client import KalshiClient
        client = KalshiClient()

        resp = client.get_market(args.ticker)
        if not resp:
            rprint(f"[red]Market {args.ticker} not found on Kalshi[/red]")
            return

        km = resp
        rprint(f"[bold]Kalshi:[/bold] {km.get('title', args.ticker)}")

        # Try all categories
        for cat in CATEGORY_SEARCH_MAP:
            poly_markets = fetch_polymarket_by_category(cat)
            result = find_matching_market(km, poly_markets)
            if result:
                pm, score = result
                poly_prices = get_polymarket_price(pm)
                rprint(f"\n[bold green]Match found![/bold green] (score: {score:.2f})")
                rprint(f"  [bold]Polymarket:[/bold] {pm.get('question', '')}")
                if poly_prices:
                    rprint(f"  YES: ${poly_prices[0]:.3f}  NO: ${poly_prices[1]:.3f}")
                return

        rprint("[yellow]No matching Polymarket market found.[/yellow]")


if __name__ == "__main__":
    main()
