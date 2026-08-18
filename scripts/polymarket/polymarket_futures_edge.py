"""
polymarket_futures_edge.py — Polymarket championship-futures edge detector (Phase 1).

Reuses Edge-Radar's existing sportsbook fair-value model (`futures_edge`) — the
same `fetch_outrights` + `consensus_outright_fair_values` de-vig that prices
Kalshi futures — but sources the *market* side from the **Polymarket US** retail
API (`polymarket_us_data`), the venue the operator actually trades on. Each US
candidate (e.g. "Los Angeles Dodgers" in "World Series Champion") is compared to
the consensus sportsbook fair value for that team, and any underpricing becomes
a normalized `Opportunity` carrying the US `market_slug` (so the execution
registry can address the order).

Repointed from international Gamma to US 2026-07-20: US and Gamma are separate
order books, so edge must be priced on the US quotes that will actually fill —
and only the US slug can address an order. See docs/setup/polymarket-us-setup.md.

Execution (PM2c, wired 2026-07-20): `--execute` routes futures opportunities
through the shared `execute_pipeline` (risk gates, Kelly sizing, venue
minimum-share bump, budget caps) with `venue="polymarket"`. Orders remain
**dry-run blocked** until BOTH `DRY_RUN=false` and `POLYMARKET_DRY_RUN=false`
— the venue-scoped flag (default true) holds Polymarket back while the
dry-run edge window accumulates evidence. Games opportunities (Gamma-sourced,
no US slug) are excluded from execution automatically. See docs/ROADMAP.md
Priority 0.

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
from polymarket_exec_client import MIN_ORDER_SHARES as _PM_MIN_ORDER_SHARES

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


# Each entry identifies a Polymarket US championship by the `question` its
# per-team markets share (matched word-wise via `championship_candidates`),
# optionally scoped to a team `league`, with `exclude` words to drop near-miss
# questions (e.g. conference champions). `odds_sport_key` is the Odds API
# outright feed that prices it — the same keys the Kalshi futures scanner uses.
# Question strings verified live against api.polymarket.us 2026-07-20.
#
# Note: World Cup was dropped in the US repoint — the 2026 event is over and the
# US product carries no World Cup futures. Soccer-league titles (EPL, LaLiga,
# UCL, MLS, …) exist on US and are candidates for a later add.
PM_FUTURES = {
    "mlb": {
        "terms": ("world series champion",), "league": "mlb", "exclude": (),
        "odds_sport_key": "baseball_mlb_world_series_winner",
        "label": "MLB World Series Champion",
    },
    "nfl": {
        "terms": ("pro football champion",), "league": "nfl", "exclude": (),
        "odds_sport_key": "americanfootball_nfl_super_bowl_winner",
        "label": "NFL Champion",
    },
    "nba": {
        # NBA team markets carry no league tag, so scope by question words and
        # exclude conference/MVP boards that also contain "nba"+"champion".
        "terms": ("nba champion",), "league": None,
        "exclude": ("conference", "mvp", "eastern", "western"),
        "odds_sport_key": "basketball_nba_championship_winner",
        "label": "NBA Champion",
    },
    "nhl": {
        "terms": ("stanley cup champion",), "league": None, "exclude": (),
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

    # C10 (2026-07-23): edge scale aligned to the sports composite, matching
    # the Kalshi futures path this formula mirrors. See the full rationale at
    # the `edge_score` line in `scripts/kalshi/futures_edge.py` — in short, the
    # old `edge * 20` was 5x stricter on edge than sports and put Gate 4 out of
    # reach of every realistic futures edge, which is what kept the Polymarket
    # US surface (futures-only) permanently unexecutable.
    edge_score = min(edge / 0.01, 10)
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * 5

    # Stable ticker — prefer the US market slug (unique + directly resolvable
    # by the execution registry); fall back to a synthetic handle.
    market_slug = cand.get("market_slug", "")
    if market_slug:
        ticker = f"PM-{market_slug}"[:64]
    else:
        cid = (cand.get("condition_id") or "").replace("0x", "")[:10]
        ticker = f"PM-{event_slug}-{cid or candidate.replace(' ', '')[:12]}"[:64]

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
            # Gate 3.6 reads the raw spread; `liquidity` above is lossy.
            "bid_ask_spread": round(bid_ask_spread, 4),
            "market_slug": cand.get("market_slug", ""),
            "condition_id": cand.get("condition_id", ""),
            "pm_volume": cand.get("volume", 0.0),
            # PM2c: per-order share minimum the exchange enforces; sizing
            # bumps up to it or rejects. Falls back to the exec client's
            # conservative default when the market doesn't report one.
            "min_order_shares": int(cand.get("min_order_shares") or 0)
                                or _PM_MIN_ORDER_SHARES,
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

    rprint(f"[bold]Polymarket US futures scan: {', '.join(keys)}[/bold]")

    # Fetch the US futures board once and reuse it across championships.
    try:
        from polymarket_us_data import PolymarketUSData, championship_candidates
        markets = PolymarketUSData().fetch_open_futures()
    except FileNotFoundError:
        rprint("  [dim]Polymarket US credentials not set (POLYMARKET_KEY_ID / "
               "POLYMARKET_SECRET_KEY) — skipping futures.[/dim]")
        return []
    except Exception as e:  # network / API — dry-run scan must not crash
        rprint(f"  [dim]Polymarket US market-data fetch failed: {e} — skipping.[/dim]")
        return []

    opps: list[Opportunity] = []
    for key in keys:
        cfg = PM_FUTURES[key]
        label = cfg["label"]

        candidates = championship_candidates(
            markets, cfg["terms"], cfg.get("league"), cfg.get("exclude", ()))
        if not candidates:
            rprint(f"  [dim]{label}: no open US markets — skipping.[/dim]")
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
        rprint(f"  {label}: {len(candidates)} US candidates, {len(fair_values)} "
               f"sportsbook outcomes → [green]{found}[/green] edge(s)")

    opps.sort(key=lambda o: o.composite_score, reverse=True)
    opps = opps[:top_n]
    # Record ticker → US market_slug mappings so the execution client can
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

    Each opportunity carries an `executable` flag and the record an
    `executable_count`. Only opps with a US `market_slug` can ever reach
    `create_order` — the games scanner still reads international Gamma, whose
    rows are dry-run evidence only. Without this split the log conflates two
    surfaces and the Phase 1→2 "prove edge" gate reads as far busier than the
    tradable universe actually is (4 days of live evidence: 66 of 79 rows were
    non-executable Gamma games).
    """
    path = log_path or (Path(__file__).resolve().parent.parent.parent
                        / "data" / "polymarket" / "dryrun_log.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    logged = [
        {**asdict(o), "gate": g,
         "executable": bool((o.details or {}).get("market_slug"))}
        for o, g in zip(opps, gates)
    ]
    record = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filter": ticker_filter or "futures",
        "min_edge": min_edge,
        "count": len(opps),
        "executable_count": sum(1 for o in logged if o["executable"]),
        "opportunities": logged,
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


def _order_mode() -> tuple[bool, str]:
    """(orders_live, human description) for the current two-flag state.

    Read live rather than hardcoded: once `POLYMARKET_DRY_RUN=false` the old
    "orders blocked" footer became actively misleading, which is the last
    thing a preview should be about real money. Fails safe to "blocked" if
    the config can't be read.
    """
    try:
        from app.config import get_config
        cfg = get_config()
        gdr = bool(cfg.system.dry_run)
        vdr = bool(getattr(cfg.polymarket, "dry_run", True))
    except Exception:
        return False, "order mode unknown — assuming blocked"
    if not gdr and not vdr:
        return True, "DRY_RUN=false AND POLYMARKET_DRY_RUN=false"
    blockers = [n for n, v in (("DRY_RUN", gdr),
                               ("POLYMARKET_DRY_RUN", vdr)) if v]
    return False, "blocked by " + " and ".join(f"{b}=true" for b in blockers)


def _preview(opps: list[Opportunity], gates: list[str]) -> None:
    if not opps:
        rprint("\n[yellow]No Polymarket futures opportunities above the edge "
               "threshold.[/yellow]")
        return

    live, mode = _order_mode()
    table = Table(title="Polymarket — Edge Preview ("
                        + ("LIVE ORDERS ARMED" if live else "DRY RUN")
                        + ", read-only until --execute)")
    for col in ("#", "US", "Bet", "Pick", "PM Ask", "Fair", "Edge",
                "Conf", "Score", "Gate"):
        table.add_column(col)
    n_exec = 0
    for i, (o, gate) in enumerate(zip(opps, gates), 1):
        # Only US-slug rows are orderable; Gamma games are evidence only.
        executable = bool((o.details or {}).get("market_slug"))
        n_exec += executable
        table.add_row(
            str(i),
            # ASCII only: this runs headless under Windows Task Scheduler,
            # where a cp1252 console raises UnicodeEncodeError on non-ASCII
            # and would kill the daily evidence run.
            "[green]YES[/green]" if executable else "[dim]-[/dim]",
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
    rprint(f"\n[dim]{len(opps)} opportunit(ies); [bold]{n_exec} executable on "
           f"Polymarket US[/bold] (US YES = has a market_slug; '-' = Gamma-sourced "
           f"game, dry-run evidence only). Gate 'ok' = would pass the "
           f"per-opportunity risk gates.[/dim]")
    if live:
        rprint(f"[red bold]LIVE ORDERS ARMED[/red bold] [red]({mode}) — "
               f"--execute will place REAL orders on any row that clears the "
               f"gates. Set POLYMARKET_DRY_RUN=true to halt this venue.[/red]")
    else:
        rprint(f"[dim]Add --execute to route through the execution pipeline "
               f"(orders {mode}).[/dim]")


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
                        help="Route futures opportunities through the risk-gate/"
                             "sizing pipeline and place orders (PM2c). Orders stay "
                             "blocked (dry_run_blocked) until BOTH DRY_RUN=false "
                             "and POLYMARKET_DRY_RUN=false — see docs/setup/"
                             "polymarket-us-setup.md")
    scan_p.add_argument("--save", action="store_true",
                        help="Append this run to data/polymarket/dryrun_log.jsonl "
                             "(edge-proving evidence) + write a markdown report")
    scan_p.add_argument("--report-dir", type=str, default=None,
                        help="Override report output directory for --save")
    scan_p.add_argument("--unit-size", type=float, default=None,
                        help="Dollar amount per bet (default: UNIT_SIZE from .env)")
    scan_p.add_argument("--max-bets", type=int, default=5,
                        help="Maximum number of bets to place")
    scan_p.add_argument("--min-bets", type=int, default=None,
                        help="Minimum approved bets required to proceed")
    scan_p.add_argument("--pick", type=str, default=None,
                        help="Comma-separated preview row numbers to execute (e.g. '1,3')")
    scan_p.add_argument("--ticker", type=str, nargs="+", default=None,
                        help="Execute only these specific tickers")
    scan_p.add_argument("--budget", type=str, default=None,
                        help="Max total cost for the batch ('10%%' of bankroll or dollars)")
    # Accept-and-ignore flags the unified scan.py may forward, so the dispatch
    # contract matches the other scanners without erroring. --exclude-open is
    # redundant here: the pipeline's Gate 5 already rejects tickers matching
    # open Polymarket positions (get_positions normalizes to PM-{slug}).
    for ignored in ("--exclude-open", "--rescan"):
        scan_p.add_argument(ignored, action="store_true")
    scan_p.add_argument("--date", type=str, default=None)

    args = parser.parse_args()
    if args.cmd != "scan":
        parser.print_help()
        sys.exit(0)

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

    wants_pipeline = (args.execute or args.unit_size is not None
                      or args.budget is not None)
    if wants_pipeline and opps:
        # PM2c: only opportunities carrying a US market_slug are executable.
        # The games scanner still reads international Gamma (different slug
        # namespace, not orderable on the US API) and records no slug — so
        # this filter cleanly excludes games until their seasonal US repoint.
        executable = [o for o in opps if (o.details or {}).get("market_slug")]
        dropped = len(opps) - len(executable)
        if dropped:
            rprint(f"[yellow]{dropped} opportunit(ies) without a US market_slug "
                   f"(Gamma-sourced games) excluded from execution — dry-run "
                   f"evidence only.[/yellow]")
        if not executable:
            rprint("[yellow]Nothing executable on Polymarket US in this scan.[/yellow]")
        else:
            from market_client import get_market_client
            try:
                client = get_market_client("polymarket")
            except FileNotFoundError as e:
                rprint(f"[red bold]Refused:[/red bold] {e}")
                sys.exit(2)
            from kalshi_executor import execute_pipeline, UNIT_SIZE, parse_budget_arg
            execute_pipeline(
                client=client,
                opportunities=executable,
                execute=args.execute,
                max_bets=args.max_bets,
                unit_size=args.unit_size or UNIT_SIZE,
                pick_rows=args.pick,
                pick_tickers=args.ticker,
                budget=parse_budget_arg(args.budget),
                min_bets=args.min_bets,
                venue="polymarket",
            )
    else:
        _preview(opps, gates)

    if args.save:
        save_dryrun(opps, gates, args.ticker_filter, args.min_edge,
                    report_dir=args.report_dir)


if __name__ == "__main__":
    main()
