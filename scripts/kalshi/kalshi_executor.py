"""
kalshi_executor.py
Automated Kalshi wagering pipeline.

Reads scored opportunities from the edge detector, applies risk management
(Kelly sizing, daily loss limits, position limits), and places orders.

Usage:
    # Scan + execute in one shot (default: dry run preview)
    python scripts/kalshi_executor.py run

    # Live execution on demo
    python scripts/kalshi_executor.py run --execute

    # Execute from saved watchlist instead of fresh scan
    python scripts/kalshi_executor.py run --from-file --execute

    # Check current state
    python scripts/kalshi_executor.py status
"""

import os
import sys
import json
import uuid
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict

# Shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401 -- configures sys.path
from opportunity import Opportunity
from trade_log import load_trade_log, save_trade_log, get_today_pnl

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from kalshi_client import KalshiClient, KalshiAPIError, make_prod_client
from edge_detector import scan_all_markets

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
from logging_setup import setup_logging
log = setup_logging("kalshi_executor")
console = Console()

TRADE_LOG_PATH = paths.TRADE_LOG_PATH

# ── Risk Parameters ───────────────────────────────────────────────────────────

MAX_BET_SIZE = float(os.getenv("MAX_BET_SIZE_PREDICTION", "100"))
DEFAULT_BET_SIZE = float(os.getenv("DEFAULT_BET_SIZE", "10"))
UNIT_SIZE = float(os.getenv("UNIT_SIZE", "1.00"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "250"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "10"))
MIN_EDGE_THRESHOLD = float(os.getenv("MIN_EDGE_THRESHOLD", "0.03"))
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))
MAX_CONCENTRATION = float(os.getenv("MAX_POSITION_CONCENTRATION", "0.20"))
MIN_COMPOSITE_SCORE = float(os.getenv("MIN_COMPOSITE_SCORE", "6.0"))
MIN_CONFIDENCE = os.getenv("MIN_CONFIDENCE", "medium")  # low, medium, high

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


# ── Position Sizing ──────────────────────────────────────────────────────────

@dataclass
class SizedOrder:
    """An opportunity that has passed risk checks and been sized."""
    opportunity: Opportunity
    contracts: int
    price_cents: int
    cost_dollars: float
    bankroll_pct: float
    risk_approval: str  # approved / rejected + reason


def unit_size_contracts(market_price: float, unit: float | None = None) -> int:
    """
    Calculate number of contracts to buy for a fixed dollar unit size.

    Examples (unit=$1.00):
        price $0.02 -> 50 contracts ($1.00)
        price $0.50 ->  2 contracts ($1.00)
        price $0.03 -> 33 contracts ($0.99)
        price $0.07 -> 14 contracts ($0.98)
    """
    if unit is None:
        unit = UNIT_SIZE
    if market_price <= 0 or market_price >= 1:
        return 0
    return max(1, round(unit / market_price))


def size_order(opp: Opportunity, bankroll: float, open_positions: int,
               daily_pnl: float, unit_size: float = UNIT_SIZE) -> SizedOrder:
    """
    Apply all risk checks and size at fixed unit size.
    Returns a SizedOrder with approval status.
    """
    rejection = None

    # ── Risk Gate 1: Daily loss limit
    if daily_pnl <= -MAX_DAILY_LOSS:
        rejection = f"daily_loss_limit_breached (P&L: ${daily_pnl:.2f})"

    # ── Risk Gate 2: Max open positions
    elif open_positions >= MAX_OPEN_POSITIONS:
        rejection = f"max_positions_reached ({open_positions}/{MAX_OPEN_POSITIONS})"

    # ── Risk Gate 3: Minimum edge
    elif opp.edge < MIN_EDGE_THRESHOLD:
        rejection = f"edge_below_threshold ({opp.edge:.1%} < {MIN_EDGE_THRESHOLD:.1%})"

    # ── Risk Gate 4: Minimum composite score
    elif opp.composite_score < MIN_COMPOSITE_SCORE:
        rejection = f"score_below_minimum ({opp.composite_score:.1f} < {MIN_COMPOSITE_SCORE:.1f})"

    # ── Risk Gate 5: Confidence filter
    elif CONFIDENCE_RANK.get(opp.confidence, 0) < CONFIDENCE_RANK.get(MIN_CONFIDENCE, 1):
        rejection = f"confidence_too_low ({opp.confidence} < {MIN_CONFIDENCE})"

    if rejection:
        return SizedOrder(
            opportunity=opp, contracts=0, price_cents=0,
            cost_dollars=0, bankroll_pct=0,
            risk_approval=f"REJECTED: {rejection}",
        )

    # ── Size at fixed unit
    price_cents = int(opp.market_price * 100)
    if price_cents <= 0:
        price_cents = 1
    if price_cents >= 100:
        price_cents = 99

    contracts = unit_size_contracts(opp.market_price, unit_size)
    actual_cost = contracts * opp.market_price

    # Final check: don't exceed bankroll
    if actual_cost > bankroll:
        contracts = max(1, int(bankroll / opp.market_price))
        actual_cost = contracts * opp.market_price

    bankroll_pct = actual_cost / bankroll if bankroll > 0 else 0

    return SizedOrder(
        opportunity=opp,
        contracts=contracts,
        price_cents=price_cents,
        cost_dollars=round(actual_cost, 2),
        bankroll_pct=round(bankroll_pct, 4),
        risk_approval="APPROVED",
    )


# ── Trade Logging ─────────────────────────────────────────────────────────────
# load_trade_log, save_trade_log, get_today_pnl imported from scripts.shared.trade_log


def log_trade(order_response: dict, sized: SizedOrder, trade_log: list) -> dict:
    """Log an executed trade."""
    order = order_response.get("order", order_response)
    opp = sized.opportunity

    trade_record = {
        "trade_id": str(uuid.uuid4()),
        "order_id": order.get("order_id", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": opp.ticker,
        "title": opp.title,
        "category": opp.category,
        "side": opp.side,
        "action": "buy",
        "contracts": sized.contracts,
        "price_cents": sized.price_cents,
        "cost_dollars": sized.cost_dollars,
        "fill_count": order.get("fill_count_fp", "0"),
        "taker_fees": order.get("taker_fees_dollars", "0"),
        "maker_fees": order.get("maker_fees_dollars", "0"),
        "status": order.get("status", "unknown"),
        "edge_estimated": opp.edge,
        "fair_value": opp.fair_value,
        "market_price_at_entry": opp.market_price,
        "confidence": opp.confidence,
        "composite_score": opp.composite_score,
        "edge_source": opp.edge_source,
        "unit_size": UNIT_SIZE,
        "bankroll_pct": sized.bankroll_pct,
        "risk_approval": sized.risk_approval,
        "net_pnl": 0,  # updated on settlement
        "closed_at": None,
        "dry_run": False,
    }

    trade_log.append(trade_record)
    save_trade_log(trade_log)
    return trade_record


# ── Execution Pipeline ────────────────────────────────────────────────────────

def load_opportunities_from_file(prediction: bool = False) -> list[Opportunity]:
    """Load opportunities from saved watchlist file(s).

    Args:
        prediction: If True, load prediction market opportunities.
                    If False, load sports opportunities.
    """
    file_path = paths.PREDICTION_OPPORTUNITIES_PATH if prediction else paths.SPORTS_OPPORTUNITIES_PATH
    if not file_path.exists():
        return []
    with open(file_path) as f:
        data = json.load(f)
    return [
        Opportunity(**{k: v for k, v in o.items()})
        for o in data.get("opportunities", [])
    ]


def _parse_pick_rows(pick_str: str, total: int) -> list[int]:
    """Parse --pick argument into 0-based indices. Supports '1,3,5' and '1-3'."""
    indices = []
    for part in pick_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            for i in range(int(start), int(end) + 1):
                if 1 <= i <= total:
                    indices.append(i - 1)
        else:
            i = int(part)
            if 1 <= i <= total:
                indices.append(i - 1)
    return sorted(set(indices))


def execute_pipeline(
    client: KalshiClient,
    opportunities: list[Opportunity],
    execute: bool = False,
    max_bets: int = 5,
    unit_size: float = UNIT_SIZE,
    pick_rows: str | None = None,
    pick_tickers: list[str] | None = None,
) -> list[dict]:
    """
    Run the full pipeline: risk-check, size, and optionally execute.

    Args:
        client: Authenticated KalshiClient
        opportunities: Scored opportunities from edge detector
        execute: If True, actually place orders. If False, preview only.
        max_bets: Maximum number of bets to place in one run
    """
    # ── Gather portfolio state
    bal = client.get_balance_dollars()
    bankroll = bal["balance"]
    rprint(f"\n[bold]Portfolio State[/bold]")
    rprint(f"  Balance:    [green]${bankroll:,.2f}[/green]")
    rprint(f"  Portfolio:  [green]${bal['portfolio_value']:,.2f}[/green]")

    positions = client.get_positions(limit=100, count_filter="position")
    open_count = len(positions.get("market_positions", []))
    rprint(f"  Positions:  {open_count}/{MAX_OPEN_POSITIONS}")

    trade_log = load_trade_log()
    daily_pnl = get_today_pnl(trade_log)
    rprint(f"  Today P&L:  ${daily_pnl:,.2f} (limit: -${MAX_DAILY_LOSS:,.2f})")
    rprint(f"  Unit size:  ${UNIT_SIZE:.2f}")

    if daily_pnl <= -MAX_DAILY_LOSS:
        rprint("[red bold]DAILY LOSS LIMIT HIT -- no new bets allowed today[/red bold]")
        return []

    # ── Size all opportunities
    rprint(f"\n[bold]Risk-checking {len(opportunities)} opportunities...[/bold]")
    sized_orders: list[SizedOrder] = []
    for opp in opportunities:
        sized = size_order(opp, bankroll, open_count + len(sized_orders), daily_pnl, unit_size)
        sized_orders.append(sized)

    approved = [s for s in sized_orders if s.risk_approval == "APPROVED"]
    rejected = [s for s in sized_orders if s.risk_approval != "APPROVED"]

    rprint(f"  Approved: [green]{len(approved)}[/green]  Rejected: [red]{len(rejected)}[/red]")

    # Show rejections
    if rejected:
        for s in rejected[:5]:
            rprint(f"  [dim]SKIP {s.opportunity.ticker}: {s.risk_approval}[/dim]")
        if len(rejected) > 5:
            rprint(f"  [dim]... and {len(rejected) - 5} more[/dim]")

    if not approved:
        rprint("[yellow]No opportunities passed risk checks.[/yellow]")
        return []

    # ── Preview table
    to_execute = approved[:max_bets]

    table = Table(
        title=f"{'EXECUTING' if execute else 'PREVIEW'} -- {len(to_execute)} orders",
        show_lines=True,
    )
    table.add_column("#", justify="right", style="dim")
    table.add_column("Bet", style="cyan", max_width=60)
    table.add_column("Side")
    table.add_column("Qty", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("Edge", justify="right", style="bold green")
    table.add_column("Fair Val", justify="right")

    total_cost = 0
    for i, s in enumerate(to_execute, 1):
        total_cost += s.cost_dollars
        # Translate yes/no into human-readable labels based on category
        side = s.opportunity.side
        cat = s.opportunity.category
        if cat == "total":
            side_label = "OVER" if side == "yes" else "UNDER"
        elif cat == "spread":
            side_label = "COVERS" if side == "yes" else "DOESN'T COVER"
        elif cat == "game":
            side_label = "WIN" if side == "yes" else "LOSE"
        else:
            side_label = side.upper()

        table.add_row(
            str(i),
            s.opportunity.title[:60],
            side_label,
            str(s.contracts),
            f"${s.price_cents / 100:.2f}",
            f"${s.cost_dollars:.2f}",
            f"+{s.opportunity.edge:.1%}",
            f"${s.opportunity.fair_value:.2f}",
        )
    console.print(table)
    rprint(f"  Total cost: [bold]${total_cost:.2f}[/bold] of ${bankroll:.2f} available")
    if not execute:
        rprint("[dim]  Tip: use --pick '1,3' --execute to bet on specific rows[/dim]")
        rprint("\n[yellow]DRY RUN -- pass --execute to place these orders[/yellow]")
        return []

    # ── Filter by --pick or --ticker if specified
    if pick_rows is not None:
        selected = _parse_pick_rows(pick_rows, len(to_execute))
        to_execute = [to_execute[i] for i in selected]
        rprint(f"\n[bold]Picked {len(to_execute)} of {len(approved)} approved orders[/bold]")
    if pick_tickers is not None:
        pick_set = {t.upper() for t in pick_tickers}
        to_execute = [s for s in to_execute if s.opportunity.ticker.upper() in pick_set]
        rprint(f"\n[bold]Matched {len(to_execute)} orders by ticker[/bold]")

    if not to_execute:
        rprint("[yellow]No orders matched your --pick or --ticker selection.[/yellow]")
        return []

    # ── Execute
    rprint(f"\n[bold]Placing {len(to_execute)} orders...[/bold]")
    results = []

    for s in to_execute:
        opp = s.opportunity
        try:
            # Determine price based on side
            kwargs = {
                "ticker": opp.ticker,
                "side": opp.side,
                "action": "buy",
                "count": s.contracts,
                "time_in_force": "good_till_canceled",
            }
            if opp.side == "yes":
                kwargs["yes_price_cents"] = s.price_cents
            else:
                kwargs["no_price_cents"] = s.price_cents

            order_resp = client.create_order(**kwargs)
            order = order_resp.get("order", order_resp)
            status = order.get("status", "unknown")

            record = log_trade(order_resp, s, trade_log)
            results.append(record)

            fill = order.get("fill_count_fp", "0")
            fees = order.get("taker_fees_dollars", "0")
            rprint(
                f"  [green]OK[/green] {opp.ticker} "
                f"{opp.side.upper()} x{s.contracts} @ ${s.price_cents/100:.2f} "
                f"-- status={status} filled={fill} fees=${fees}"
            )

        except KalshiAPIError as e:
            rprint(f"  [red]FAIL[/red] {opp.ticker}: {e.message[:80]}")
            # Log the failure
            trade_log.append({
                "trade_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": opp.ticker,
                "side": opp.side,
                "status": "error",
                "error": str(e.message)[:200],
                "net_pnl": 0,
                "closed_at": None,
            })
            save_trade_log(trade_log)

    # ── Post-execution summary
    rprint(f"\n[bold]Execution complete[/bold]")
    new_bal = client.get_balance_dollars()
    rprint(f"  Balance: ${bankroll:.2f} -> ${new_bal['balance']:.2f}")
    rprint(f"  Orders placed: {len(results)}")
    rprint(f"  Trade log: {TRADE_LOG_PATH}")

    return results


# ── Status Command ────────────────────────────────────────────────────────────

def show_status(client: KalshiClient):
    """Show current portfolio status, positions, and today's activity."""
    bal = client.get_balance_dollars()
    rprint(f"\n[bold]-- Kalshi Portfolio Status --[/bold]")
    rprint(f"  Environment:  {'DEMO' if client.is_demo else 'LIVE'}")
    rprint(f"  Balance:      [green]${bal['balance']:,.2f}[/green]")
    rprint(f"  Portfolio:    [green]${bal['portfolio_value']:,.2f}[/green]")

    # Positions
    positions = client.get_positions(limit=100, count_filter="position")
    market_pos = positions.get("market_positions", [])
    rprint(f"  Positions:    {len(market_pos)}/{MAX_OPEN_POSITIONS}")

    if market_pos:
        table = Table(title="Open Positions", show_lines=True)
        table.add_column("Ticker", style="cyan", max_width=35)
        table.add_column("Qty", justify="right")
        table.add_column("Exposure", justify="right", style="green")
        table.add_column("P&L", justify="right")
        table.add_column("Fees", justify="right", style="dim")

        for p in market_pos:
            pnl = float(p.get("realized_pnl_dollars", "0"))
            pnl_style = "green" if pnl >= 0 else "red"
            table.add_row(
                p.get("ticker", "")[:35],
                p.get("position_fp", "0"),
                p.get("market_exposure_dollars", "0"),
                f"[{pnl_style}]{pnl:+.2f}[/{pnl_style}]",
                p.get("fees_paid_dollars", "0"),
            )
        console.print(table)

    # Today's trades
    trade_log = load_trade_log()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_trades = [t for t in trade_log if t.get("timestamp", "").startswith(today)]

    if today_trades:
        rprint(f"\n  [bold]Today's Activity: {len(today_trades)} trades[/bold]")
        daily_pnl = get_today_pnl(trade_log)
        total_wagered = sum(t.get("cost_dollars", 0) for t in today_trades)
        rprint(f"  Wagered:      ${total_wagered:,.2f}")
        rprint(f"  Realized P&L: ${daily_pnl:,.2f}")
        rprint(f"  Loss limit:   ${daily_pnl:,.2f} / -${MAX_DAILY_LOSS:,.2f}")
    else:
        rprint(f"\n  [dim]No trades today[/dim]")

    # Resting orders
    try:
        orders = client.get_orders(limit=50, status="resting")
        resting = orders.get("orders", [])
        if resting:
            rprint(f"\n  [bold]Resting Orders: {len(resting)}[/bold]")
            for o in resting[:5]:
                rprint(
                    f"    {o['ticker'][:30]} {o['side'].upper()} "
                    f"x{o.get('remaining_count_fp', '?')} @ {o.get('yes_price_dollars', '?')}"
                )
    except Exception:
        pass


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kalshi automated executor")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Scan markets and execute bets")
    run_p.add_argument("--execute", action="store_true",
                       help="Actually place orders (default: preview only)")
    run_p.add_argument("--from-file", action="store_true",
                       help="Use saved watchlist instead of fresh scan")
    run_p.add_argument("--prediction", action="store_true",
                       help="Use prediction market scanner (crypto, weather, S&P 500) instead of sports")
    run_p.add_argument("--filter", dest="ticker_filter",
                       help="Filter: ncaamb, nba, nhl, ... (sports) or crypto, btc, weather, spx (prediction)")
    run_p.add_argument("--min-edge", type=float, default=MIN_EDGE_THRESHOLD,
                       help="Minimum edge threshold")
    run_p.add_argument("--unit-size", type=float, default=UNIT_SIZE,
                       help=f"Dollar amount per bet (default ${UNIT_SIZE:.2f})")
    run_p.add_argument("--max-bets", type=int, default=5,
                       help="Max bets per run (default 5)")
    run_p.add_argument("--top", type=int, default=20,
                       help="Number of opportunities to scan")
    run_p.add_argument("--pick", type=str, default=None,
                       help="Execute only specific rows from preview (e.g., '1,3,5' or '1-3')")
    run_p.add_argument("--ticker", type=str, nargs="+", default=None,
                       help="Execute specific market ticker(s) from the scan results")

    sub.add_parser("status", help="Show portfolio status")

    args = parser.parse_args()

    # Client for execution and portfolio queries
    client = KalshiClient()

    # Production client for market data (if configured)
    prod_client = make_prod_client()
    if prod_client:
        rprint("[bold]Using PRODUCTION market data for scanning[/bold]")
        scan_client = prod_client
    else:
        scan_client = client

    if args.command == "status":
        show_status(client)

    elif args.command == "run":
        # Get opportunities
        if args.from_file:
            rprint(f"[bold]Loading {'prediction' if args.prediction else 'sports'} opportunities from file...[/bold]")
            opportunities = load_opportunities_from_file(prediction=args.prediction)
            src = paths.PREDICTION_OPPORTUNITIES_PATH if args.prediction else paths.SPORTS_OPPORTUNITIES_PATH
            rprint(f"  Loaded {len(opportunities)} from {src}")

        elif args.prediction:
            # Use prediction market scanner
            rprint("[bold]Running prediction market scan...[/bold]")
            from prediction_scanner import scan_prediction_markets
            opportunities = scan_prediction_markets(
                scan_client,
                min_edge=args.min_edge,
                ticker_filter=args.ticker_filter,
                top_n=args.top,
            )

        else:
            # Use sports edge detector
            rprint("[bold]Running fresh sports market scan...[/bold]")
            opportunities = scan_all_markets(
                scan_client,
                min_edge=args.min_edge,
                ticker_filter=args.ticker_filter,
                top_n=args.top,
            )

        if not opportunities:
            rprint("[yellow]No opportunities found.[/yellow]")
            return

        execute_pipeline(
            client=client,
            opportunities=opportunities,
            execute=args.execute,
            max_bets=args.max_bets,
            unit_size=args.unit_size,
            pick_rows=args.pick,
            pick_tickers=args.ticker,
        )


if __name__ == "__main__":
    main()
