"""
polymarket_futures_edge.py — Polymarket championship-futures edge detector (Phase 1).

Reuses Edge-Radar's existing sportsbook fair-value model (`futures_edge`) — the
same `fetch_outrights` + `consensus_outright_fair_values` de-vig that prices
Kalshi futures — but sources the *market* side from Polymarket's Gamma API
instead of Kalshi. Each Polymarket candidate (e.g. "Spain" in "World Cup Winner")
is compared to the consensus sportsbook fair value for that team, and any
underpricing becomes a normalized `Opportunity`.

Phase 1 is **read-only / dry-run**: it previews opportunities and shows which
risk gate each would hit, but places NO orders. Execution is Phase 2 (wallet /
py-clob-client) and is intentionally refused here. See docs/ROADMAP.md Priority 0.

Scope (v1): YES-side only (back a candidate to win) — the meaningful futures bet.
NO-side futures on a large field are near-locks with negligible edge.
"""

import argparse
import sys

from rich import print as rprint
from rich.table import Table

from opportunity import Opportunity

# Reuse the sportsbook fair-value side from the Kalshi futures scanner unchanged.
from futures_edge import (
    fetch_outrights,
    consensus_outright_fair_values,
    _futures_name_match,
)

try:
    from logging_setup import setup_logging
    log = setup_logging("polymarket_futures_edge")
except Exception:  # pragma: no cover
    import logging
    log = logging.getLogger("polymarket_futures_edge")

import polymarket_client as pm


# Each entry: Polymarket event (slug + title search terms) → the Odds API
# outright sport_key that prices it, plus a human label. Odds keys are the same
# ones already validated by the Kalshi futures scanner (futures_edge.FUTURES_MAP).
# `slug` is the precise Gamma lookup; `search` is the keyword fallback.
PM_FUTURES = {
    "worldcup": {
        "slug": "world-cup-winner",
        "search": ("world cup winner", "world cup champion"),
        "odds_sport_key": "soccer_fifa_world_cup_winner",
        "label": "World Cup Winner",
    },
    "nfl": {
        "slug": None,
        "search": ("super bowl", "nfl champion"),
        "odds_sport_key": "americanfootball_nfl_super_bowl_winner",
        "label": "NFL Super Bowl Champion",
    },
    "mlb": {
        "slug": None,
        "search": ("world series", "mlb champion"),
        "odds_sport_key": "baseball_mlb_world_series_winner",
        "label": "MLB World Series Champion",
    },
    "nba": {
        "slug": None,
        "search": ("nba champion", "nba finals"),
        "odds_sport_key": "basketball_nba_championship_winner",
        "label": "NBA Champion",
    },
    "nhl": {
        "slug": None,
        "search": ("stanley cup",),
        "odds_sport_key": "icehockey_nhl_championship_winner",
        "label": "NHL Stanley Cup Champion",
    },
}

_FILTER_ALL = ("futures", "all", "")


def detect_edge_futures_polymarket(
    cand: dict, fair_values: dict[str, dict], label: str, event_slug: str
) -> Opportunity | None:
    """Compare one Polymarket candidate to the consensus sportsbook fair value.

    Mirrors `futures_edge.detect_edge_futures` (same confidence/liquidity/
    composite math) but reads the Polymarket candidate shape and prices the
    YES side only. Returns an `Opportunity` when the sportsbook fair value
    exceeds the Polymarket ask (positive edge), else None.
    """
    candidate = cand["candidate"]
    yes_price = cand["yes_price"]
    if yes_price <= 0 or yes_price >= 1.0:
        return None

    # Match candidate name to an Odds API outright outcome.
    matched_fair = None
    matched_name = None
    for odds_name, fv in fair_values.items():
        if _futures_name_match(odds_name, candidate):
            matched_fair = fv
            matched_name = odds_name
            break
    if not matched_fair:
        log.debug("No sportsbook match for '%s' (%d outcomes)", candidate, len(fair_values))
        return None

    fair_yes = matched_fair["fair_value"]
    edge = fair_yes - yes_price
    if edge <= 0:
        return None

    # Confidence: same rule as the Kalshi futures path.
    n_books = matched_fair["n_books"]
    spread_range = matched_fair["max"] - matched_fair["min"]
    if n_books >= 8 and spread_range < 0.05:
        confidence = "high"
    elif n_books >= 4:
        confidence = "medium"
    else:
        confidence = "low"

    # Liquidity from the Yes-token bid/ask spread.
    yes_bid = cand.get("yes_bid", 0.0)
    bid_ask_spread = (yes_price - yes_bid) if yes_bid > 0 else 1.0
    liquidity = max(0.0, 10 - bid_ask_spread * 20)

    edge_score = min(10, edge * 20)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * 5

    # Synthetic, stable ticker so downstream (dedup, logging) has a handle.
    cid = (cand.get("condition_id") or "").replace("0x", "")[:10]
    ticker = f"PM-{event_slug}-{cid or candidate.replace(' ', '')[:12]}"

    return Opportunity(
        ticker=ticker,
        title=f"{label}: {candidate}",
        category="futures",
        side="yes",
        market_price=round(yes_price, 4),
        fair_value=round(fair_yes, 4),
        edge=round(edge, 4),
        edge_source="polymarket_vs_outrights",
        confidence=confidence,
        liquidity_score=round(liquidity, 1),
        composite_score=round(composite, 1),
        details={
            "venue": "polymarket",
            "candidate": candidate,
            "matched_to": matched_name,
            "bet_type": label,
            "n_books": n_books,
            "fair_range": f"{matched_fair['min']:.3f} - {matched_fair['max']:.3f}",
            "condition_id": cand.get("condition_id", ""),
            "clob_token_ids": cand.get("clob_token_ids", []),
            "pm_volume": cand.get("volume", 0.0),
        },
    )


def _selected_keys(ticker_filter: str | None) -> list[str]:
    if not ticker_filter or ticker_filter.lower() in _FILTER_ALL:
        return list(PM_FUTURES.keys())
    key = ticker_filter.lower()
    if key in PM_FUTURES:
        return [key]
    rprint(f"[yellow]Unknown Polymarket futures filter '{ticker_filter}'. "
           f"Valid: {', '.join(PM_FUTURES)} (or 'futures' for all).[/yellow]")
    return []


def scan_polymarket_futures(
    min_edge: float = 0.03,
    ticker_filter: str | None = None,
    top_n: int = 20,
) -> list[Opportunity]:
    """Scan configured Polymarket championship futures for +EV YES bets."""
    keys = _selected_keys(ticker_filter)
    if not keys:
        return []

    rprint(f"[bold]Polymarket futures scan: {', '.join(keys)}[/bold]")
    opps: list[Opportunity] = []
    for key in keys:
        cfg = PM_FUTURES[key]
        label = cfg["label"]

        event = pm.find_event(cfg.get("slug"), cfg.get("search", ()))
        if not event:
            rprint(f"  [dim]{label}: no active Polymarket event found — skipping.[/dim]")
            continue
        candidates = pm.iter_future_candidates(event)
        if not candidates:
            rprint(f"  [dim]{label}: event found but no tradable candidates.[/dim]")
            continue

        events = fetch_outrights(cfg["odds_sport_key"])
        fair_values = consensus_outright_fair_values(events) if events else {}
        if not fair_values:
            rprint(f"  [dim]{label}: no sportsbook outright feed "
                   f"({cfg['odds_sport_key']}) — can't price, skipping.[/dim]")
            continue

        found = 0
        for cand in candidates:
            opp = detect_edge_futures_polymarket(cand, fair_values, label, key)
            if opp and opp.edge >= min_edge:
                opps.append(opp)
                found += 1
        rprint(f"  {label}: {len(candidates)} candidates, {len(fair_values)} "
               f"sportsbook outcomes → [green]{found}[/green] edge(s)")

    opps.sort(key=lambda o: o.composite_score, reverse=True)
    return opps[:top_n]


def _preview(opps: list[Opportunity]) -> None:
    if not opps:
        rprint("\n[yellow]No Polymarket futures opportunities above the edge "
               "threshold.[/yellow]")
        return

    # Show which gate each opp would hit (read-only preflight — no live
    # portfolio state needed). Import here so a missing executor never breaks
    # the read-only scan.
    try:
        from kalshi_executor import preflight_gate_status
    except Exception:
        preflight_gate_status = None

    table = Table(title="Polymarket Futures — Edge Preview (DRY RUN, read-only)")
    for col in ("#", "Future", "Candidate", "PM Ask", "Fair", "Edge",
                "Conf", "Score", "Gate"):
        table.add_column(col)
    for i, o in enumerate(opps, 1):
        gate = preflight_gate_status(o) if preflight_gate_status else "-"
        table.add_row(
            str(i),
            o.details.get("bet_type", ""),
            o.details.get("candidate", ""),
            f"{o.market_price:.2f}",
            f"{o.fair_value:.2f}",
            f"{o.edge:+.1%}",
            o.confidence,
            f"{o.composite_score:.1f}",
            gate,
        )
    rprint(table)
    rprint(f"\n[dim]{len(opps)} opportunit(ies). Gate 'ok' = would pass the "
           f"per-opportunity risk gates. Execution is Phase 2 (not implemented).[/dim]")


def main():
    parser = argparse.ArgumentParser(description="Polymarket futures edge detector (Phase 1, read-only)")
    sub = parser.add_subparsers(dest="cmd")
    scan_p = sub.add_parser("scan", help="Scan Polymarket futures for edge (dry-run)")
    scan_p.add_argument("--filter", dest="ticker_filter", default=None,
                        help="futures | worldcup | nfl | mlb | nba | nhl")
    scan_p.add_argument("--min-edge", type=float, default=0.03)
    scan_p.add_argument("--top", type=int, default=20)
    scan_p.add_argument("--execute", action="store_true",
                        help="(Phase 2 — not implemented; refused)")
    # Accept-and-ignore flags the unified scan.py may forward, so the dispatch
    # contract matches the other scanners without erroring.
    for ignored in ("--save", "--exclude-open", "--rescan"):
        scan_p.add_argument(ignored, action="store_true")
    scan_p.add_argument("--unit-size", type=float, default=None)
    scan_p.add_argument("--max-bets", type=int, default=None)
    scan_p.add_argument("--budget", type=str, default=None)
    scan_p.add_argument("--date", type=str, default=None)

    args = parser.parse_args()
    if args.cmd != "scan":
        parser.print_help()
        sys.exit(0)

    if args.execute:
        rprint("[red bold]Refused:[/red bold] Polymarket execution is Phase 2 "
               "(wallet / py-clob-client) and is not implemented yet. Phase 1 "
               "is read-only. See docs/ROADMAP.md Priority 0 (PM2).")
        sys.exit(2)

    opps = scan_polymarket_futures(
        min_edge=args.min_edge,
        ticker_filter=args.ticker_filter,
        top_n=args.top,
    )
    _preview(opps)


if __name__ == "__main__":
    main()
