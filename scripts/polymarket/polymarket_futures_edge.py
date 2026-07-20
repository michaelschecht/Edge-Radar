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
import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

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
# `slug` is the precise Gamma lookup for the *current* season's event; slugs
# rot at season rollover (e.g. "...-2026" closes, "...-2027" opens), at which
# point `find_event` falls back to `search` via Gamma /public-search — each
# term matches when ALL of its words appear in an open event's title, and the
# highest-volume match wins. Refresh the slug when the fallback fires.
# Slugs verified live 2026-07-20 (PM1b).
PM_FUTURES = {
    "worldcup": {
        # 2026 event closed at the final (2026-07-20); dormant until the 2030
        # cycle's event opens — the search fallback should then find it.
        "slug": "world-cup-winner",
        "search": ("world cup winner", "world cup champion"),
        "odds_sport_key": "soccer_fifa_world_cup_winner",
        "label": "World Cup Winner",
    },
    "nfl": {
        "slug": "big-game-champion-2027",  # titled "NFL Champion 2027"
        "search": ("nfl champion", "super bowl champion"),
        "odds_sport_key": "americanfootball_nfl_super_bowl_winner",
        "label": "NFL Super Bowl Champion",
    },
    "mlb": {
        "slug": "mlb-world-series-champion-2026",
        "search": ("world series champion", "mlb champion"),
        "odds_sport_key": "baseball_mlb_world_series_winner",
        "label": "MLB World Series Champion",
    },
    "nba": {
        "slug": "nba-2027-champion",
        "search": ("nba champion",),
        "odds_sport_key": "basketball_nba_championship_winner",
        "label": "NBA Champion",
    },
    "nhl": {
        "slug": "nhl-2027-champion-20260612185656162",
        "search": ("nhl champion", "stanley cup champion"),
        "odds_sport_key": "icehockey_nhl_championship_winner",
        "label": "NHL Stanley Cup Champion",
    },
}

_FILTER_ALL = ("futures", "all", "")


def _route_filter(ticker_filter: str | None) -> tuple[str | None, list[str]]:
    """Map the CLI --filter to (futures_filter, game_sports).

    PM1d added per-game scanning next to futures:
      (empty) / all      → all futures + all game sports
      futures            → all futures only
      worldcup|nfl|...   → that single future only
      games              → all game sports only
      mlb-games|nba-...  → that sport's games only
    """
    key = (ticker_filter or "").lower()
    from polymarket_games_edge import PM_GAME_SPORTS
    if key in ("", "all"):
        return "futures", list(PM_GAME_SPORTS)
    if key == "futures":
        return "futures", []
    if key == "games":
        return None, list(PM_GAME_SPORTS)
    if key.endswith("-games") and key[:-6] in PM_GAME_SPORTS:
        return None, [key[:-6]]
    if key in PM_FUTURES:
        return key, []
    rprint(f"[yellow]Unknown Polymarket filter '{ticker_filter}'. Valid: "
           f"{', '.join(PM_FUTURES)} | futures | games | "
           f"{', '.join(s + '-games' for s in PM_GAME_SPORTS)} | all.[/yellow]")
    return None, []


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
    opps = opps[:top_n]
    # Record ticker → CLOB token mappings so the PM2 execution client can
    # resolve orders for these opportunities later.
    import market_registry
    market_registry.record_opportunities(opps)
    return opps


def _gate_statuses(opps: list[Opportunity]) -> list[str]:
    """Preflight each opp against the risk gates (read-only — no live
    portfolio state needed). Import inside so a missing executor never breaks
    the read-only scan; "-" means the preflight was unavailable."""
    try:
        from kalshi_executor import preflight_gate_status
    except Exception:
        return ["-"] * len(opps)
    return [preflight_gate_status(o) for o in opps]


def save_dryrun(
    opps: list[Opportunity],
    gates: list[str],
    ticker_filter: str | None,
    min_edge: float,
    log_path: Path | None = None,
    report_dir: str | None = None,
) -> Path:
    """Persist one dry-run scan record so the Phase 1 edge-proving window has
    evidence to evaluate (ROADMAP Priority 0: "prove edge → Phase 2").

    Appends a run record — timestamp, filter, count, and every opportunity
    with its gate verdict — to `data/polymarket/dryrun_log.jsonl` (append-only
    time series; zero-opportunity runs are logged too, since "how often does
    edge appear at all" is part of the evidence). Also writes the standard
    markdown scan report to `reports/Polymarket/` when there are rows.
    Returns the JSONL path.
    """
    path = log_path or (Path(__file__).resolve().parent.parent.parent
                        / "data" / "polymarket" / "dryrun_log.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filter": ticker_filter or "futures",
        "min_edge": min_edge,
        "count": len(opps),
        "opportunities": [
            {**asdict(o), "gate": g} for o, g in zip(opps, gates)
        ],
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, default=str) + "\n")

    if opps:
        from report_writer import save_scan_report
        rpt = save_scan_report(opps, report_type="polymarket",
                               filter_label=ticker_filter or "futures",
                               min_edge=min_edge, output_dir=report_dir)
        if rpt:
            rprint(f"[dim]Report saved to {rpt}[/dim]")
    rprint(f"[dim]Dry-run record appended to {path}[/dim]")
    return path


def _preview(opps: list[Opportunity], gates: list[str]) -> None:
    if not opps:
        rprint("\n[yellow]No Polymarket futures opportunities above the edge "
               "threshold.[/yellow]")
        return

    table = Table(title="Polymarket — Edge Preview (DRY RUN, read-only)")
    for col in ("#", "Bet", "Pick", "PM Ask", "Fair", "Edge",
                "Conf", "Score", "Gate"):
        table.add_column(col)
    for i, (o, gate) in enumerate(zip(opps, gates), 1):
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
                        help="all (default: futures+games) | futures | worldcup|nfl|mlb|nba|nhl "
                             "| games | mlb-games|nfl-games|nba-games|nhl-games")
    scan_p.add_argument("--min-edge", type=float, default=0.03)
    scan_p.add_argument("--top", type=int, default=20)
    scan_p.add_argument("--execute", action="store_true",
                        help="(Phase 2 — not implemented; refused)")
    scan_p.add_argument("--save", action="store_true",
                        help="Append this run to data/polymarket/dryrun_log.jsonl "
                             "(edge-proving evidence) + write a markdown report")
    scan_p.add_argument("--report-dir", type=str, default=None,
                        help="Override report output directory for --save")
    # Accept-and-ignore flags the unified scan.py may forward, so the dispatch
    # contract matches the other scanners without erroring.
    for ignored in ("--exclude-open", "--rescan"):
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

    fut_filter, game_sports = _route_filter(args.ticker_filter)
    opps: list[Opportunity] = []
    if fut_filter:
        opps += scan_polymarket_futures(
            min_edge=args.min_edge,
            ticker_filter=fut_filter,
            top_n=args.top,
        )
    if game_sports:
        # Lazy import: pulls the edge_detector consensus stack, which
        # futures-only scans don't need.
        from polymarket_games_edge import scan_polymarket_games
        rprint(f"[bold]Polymarket games scan: {', '.join(game_sports)}[/bold]")
        opps += scan_polymarket_games(
            min_edge=args.min_edge,
            sports=game_sports,
            top_n=args.top,
        )
    opps.sort(key=lambda o: o.composite_score, reverse=True)
    opps = opps[:args.top]
    gates = _gate_statuses(opps)
    _preview(opps, gates)
    if args.save:
        save_dryrun(opps, gates, args.ticker_filter, args.min_edge,
                    report_dir=args.report_dir)


if __name__ == "__main__":
    main()
