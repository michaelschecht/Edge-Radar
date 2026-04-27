"""
risk_check.py
Live portfolio risk dashboard pulling data from Kalshi API and trade log.

Usage:
    python scripts/kalshi/risk_check.py                       # Full risk dashboard
    python scripts/kalshi/risk_check.py --report positions    # Open positions only
    python scripts/kalshi/risk_check.py --report pnl          # Today's P&L only
    python scripts/kalshi/risk_check.py --report limits       # Risk limit status
    python scripts/kalshi/risk_check.py --report watchlist    # Pending opportunities
    python scripts/kalshi/risk_check.py --report reconciliation  # Trade-log ↔ settlement audit
    python scripts/kalshi/risk_check.py --gate                # Returns exit code 1 if limits breached
"""

import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path

import paths  # noqa: F401 -- path constants

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from kalshi_client import KalshiClient
from trade_log import load_trade_log, load_settlement_log, get_today_pnl, get_filled_cost
from ticker_display import parse_game_datetime, parse_matchup, parse_pick_team, TEAM_NAMES
from logging_setup import setup_logging
from app.config import get_config

# ── Setup ──────────────────────────────────────────────────────────────────────
load_dotenv()
console = Console()
log = setup_logging("risk_check")

# ── Risk Limits (from app.config) ─────────────────────────────────────────────
_cfg = get_config()
MAX_BET_SIZE        = _cfg.risk.max_bet_size
MAX_DAILY_LOSS      = _cfg.risk.max_daily_loss
MAX_OPEN_POSITIONS  = _cfg.risk.max_open_positions
DRY_RUN             = _cfg.system.dry_run

# ── Watchlist path ────────────────────────────────────────────────────────────
WATCHLIST_PATH = paths.SPORTS_OPPORTUNITIES_PATH
PREDICTION_WATCHLIST = paths.PREDICTION_OPPORTUNITIES_PATH


# ── Data Fetchers ─────────────────────────────────────────────────────────────

def fetch_positions(client: KalshiClient) -> list[dict]:
    """Fetch live open positions from Kalshi API."""
    resp = client.get_positions(limit=100, count_filter="position")
    return resp.get("market_positions", [])


def fetch_balance(client: KalshiClient) -> dict:
    """Fetch live balance from Kalshi API."""
    return client.get_balance_dollars()


def fetch_resting_orders(client: KalshiClient) -> list[dict]:
    """Fetch resting (unfilled) orders from Kalshi API."""
    try:
        resp = client.get_orders(limit=50, status="resting")
        return resp.get("orders", [])
    except Exception:
        return []


def get_today_trades() -> tuple[list[dict], float]:
    """Load trade log and return today's trades + daily P&L."""
    trade_log = load_trade_log()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_trades = [t for t in trade_log if t.get("timestamp", "").startswith(today)]
    daily_pnl = get_today_pnl(trade_log)
    return today_trades, daily_pnl


def load_watchlist() -> list[dict]:
    """Load saved opportunities from watchlist files."""
    opps = []
    for wl_path in [WATCHLIST_PATH, PREDICTION_WATCHLIST]:
        if wl_path.exists():
            try:
                with open(wl_path) as f:
                    data = json.load(f)
                opps.extend(data.get("opportunities", []))
            except (json.JSONDecodeError, KeyError):
                pass
    return opps


# ── Risk Calculations ─────────────────────────────────────────────────────────

def get_daily_limit_pct(daily_pnl: float) -> float:
    if MAX_DAILY_LOSS == 0:
        return 0
    return abs(min(daily_pnl, 0)) / MAX_DAILY_LOSS * 100


def is_daily_limit_breached(daily_pnl: float) -> bool:
    return daily_pnl <= -MAX_DAILY_LOSS


# ── Display Functions ─────────────────────────────────────────────────────────

def print_risk_header(client: KalshiClient):
    mode = "DEMO" if client.is_demo else "LIVE"
    mode_tag = f"[red bold]{mode}[/red bold]" if not DRY_RUN else f"[green bold]DRY RUN ({mode})[/green bold]"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    console.print(Panel(
        f"[bold]Edge-Radar Risk Dashboard[/bold]  {mode_tag}\n[dim]{ts}[/dim]",
        expand=False
    ))


def print_limits_status(daily_pnl: float, open_count: int):
    limit_pct = get_daily_limit_pct(daily_pnl)
    breached = is_daily_limit_breached(daily_pnl)

    if limit_pct >= 100 or breached:
        status = "[red bold]HARD STOP — LIMIT BREACHED[/red bold]"
    elif limit_pct >= 90:
        status = "[red]CRITICAL (90%+)[/red]"
    elif limit_pct >= 75:
        status = "[yellow]WARNING (75%+)[/yellow]"
    elif limit_pct >= 50:
        status = "[yellow]CAUTION (50%+)[/yellow]"
    else:
        status = "[green]Normal[/green]"

    table = Table(title="Risk Limit Status", show_lines=True)
    table.add_column("Limit", style="cyan")
    table.add_column("Used", justify="right")
    table.add_column("Max", justify="right")
    table.add_column("Utilization", justify="right")
    table.add_column("Status")

    pnl_used = abs(min(daily_pnl, 0))
    table.add_row(
        "Daily Loss Limit",
        f"${pnl_used:.2f}",
        f"${MAX_DAILY_LOSS:.2f}",
        f"{limit_pct:.1f}%",
        status
    )
    pos_pct = open_count / MAX_OPEN_POSITIONS * 100 if MAX_OPEN_POSITIONS > 0 else 0
    table.add_row(
        "Open Positions",
        str(open_count),
        str(MAX_OPEN_POSITIONS),
        f"{pos_pct:.0f}%",
        "[green]OK[/green]" if open_count < MAX_OPEN_POSITIONS else "[red]AT LIMIT[/red]"
    )
    table.add_row(
        "Max Bet Size",
        "—",
        f"${MAX_BET_SIZE:.0f}",
        "—",
        "[green]OK[/green]"
    )
    console.print(table)


def print_balance(bal: dict):
    table = Table(title="Account Balance", show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Cash Balance", f"[green]${bal['balance']:,.2f}[/green]")
    table.add_row("Portfolio Value", f"[green]${bal['portfolio_value']:,.2f}[/green]")
    console.print(table)


def print_open_positions(positions: list[dict]):
    if not positions:
        rprint("\n[dim]No open positions on Kalshi.[/dim]")
        return

    from ticker_display import bet_type_from_ticker

    table = Table(title=f"Open Positions ({len(positions)})", show_lines=True)
    table.add_column("Bet", style="cyan", max_width=32)
    table.add_column("Type", style="magenta")
    table.add_column("When", style="dim")
    table.add_column("Pick", justify="center")
    table.add_column("Qty", justify="right")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("P&L", justify="right")

    total_exposure = 0.0
    total_pnl = 0.0
    total_fees = 0.0

    for p in positions:
        ticker = p.get("ticker", "")
        pnl = float(p.get("realized_pnl_dollars", "0"))
        exposure = float(p.get("market_exposure_dollars", "0"))
        fees = float(p.get("fees_paid_dollars", "0"))
        pnl_style = "green" if pnl >= 0 else "red"
        total_exposure += exposure
        total_pnl += pnl
        total_fees += fees

        # Determine side
        yes_qty = float(p.get("position_fp", "0"))
        side = "YES" if yes_qty > 0 else "NO"
        qty = int(abs(yes_qty))

        matchup = parse_matchup(ticker) or ticker[:32]
        when = parse_game_datetime(ticker)
        pick_name = parse_pick_team(ticker) or side
        pick_label = f"{side} {pick_name}"

        table.add_row(
            matchup,
            bet_type_from_ticker(ticker),
            when,
            pick_label,
            str(qty),
            f"${exposure:.2f}",
            f"[{pnl_style}]${pnl:+.2f}[/{pnl_style}]",
        )

    # Summary row
    pnl_style = "green" if total_pnl >= 0 else "red"
    table.add_row(
        f"[bold]TOTAL[/bold] [dim](fees: ${total_fees:.2f})[/dim]",
        "", "", "", "",
        f"[bold]${total_exposure:.2f}[/bold]",
        f"[bold {pnl_style}]${total_pnl:+.2f}[/bold {pnl_style}]",
    )
    console.print(table)


def print_resting_orders(orders: list[dict]):
    if not orders:
        rprint("\n[dim]No resting orders.[/dim]")
        return

    table = Table(title=f"Resting Orders ({len(orders)})", show_lines=True)
    table.add_column("Ticker", style="cyan", max_width=35)
    table.add_column("Side")
    table.add_column("Remaining", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Created", style="dim")

    for o in orders:
        created = o.get("created_time", "")[:16].replace("T", " ")
        price = o.get("yes_price_dollars") or o.get("no_price_dollars") or "?"
        table.add_row(
            o.get("ticker", "")[:35],
            o.get("side", "").upper(),
            o.get("remaining_count_fp", "?"),
            f"${price}" if price != "?" else "?",
            created,
        )
    console.print(table)


def print_pnl_summary(today_trades: list[dict], daily_pnl: float):
    wins = [t for t in today_trades if t.get("net_pnl", 0) > 0]
    losses = [t for t in today_trades if t.get("net_pnl", 0) < 0]
    win_rate = len(wins) / len(today_trades) * 100 if today_trades else 0
    total_wagered = sum(get_filled_cost(t) for t in today_trades)

    table = Table(title="Today's P&L", show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    pnl_color = "green" if daily_pnl >= 0 else "red"
    table.add_row("Realized P&L", f"[{pnl_color}][bold]${daily_pnl:+.2f}[/bold][/{pnl_color}]")
    table.add_row("Total Wagered", f"${total_wagered:.2f}")
    table.add_row("Trades Today", str(len(today_trades)))
    table.add_row("Record", f"{len(wins)}W - {len(losses)}L")
    table.add_row("Win Rate", f"{win_rate:.1f}%")
    table.add_row("Loss Limit", f"${daily_pnl:+.2f} / -${MAX_DAILY_LOSS:.2f}")

    if today_trades:
        best = max(today_trades, key=lambda t: t.get("net_pnl", 0))
        worst = min(today_trades, key=lambda t: t.get("net_pnl", 0))
        table.add_row("Best Trade", f"[green]${best.get('net_pnl', 0):+.2f}[/green]  {best.get('ticker', '')[:25]}")
        table.add_row("Worst Trade", f"[red]${worst.get('net_pnl', 0):+.2f}[/red]  {worst.get('ticker', '')[:25]}")

    console.print(table)


def print_watchlist(opps: list[dict]):
    if not opps:
        rprint("\n[dim]No saved opportunities in watchlist.[/dim]")
        return

    table = Table(title=f"Watchlist ({len(opps)} opportunities)", show_lines=True)
    table.add_column("Ticker", style="cyan", max_width=35)
    table.add_column("Side")
    table.add_column("Edge", justify="right", style="green")
    table.add_column("Fair Value", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Confidence")

    for o in sorted(opps, key=lambda x: x.get("composite_score", 0), reverse=True)[:15]:
        table.add_row(
            o.get("ticker", "")[:35],
            o.get("side", "").upper(),
            f"+{o.get('edge', 0):.1%}",
            f"${o.get('fair_value', 0):.2f}",
            f"{o.get('composite_score', 0):.1f}",
            o.get("confidence", "")[:3].upper(),
        )
    console.print(table)


# ── Reconciliation Report ─────────────────────────────────────────────────────

# Settlement-side fields that became part of the schema after R5 (2026-04-27).
# Pre-R5 settlements have these as null/missing — useful for measuring how much
# of the historical cohort is missing trade-side context.
_R5_FIELDS = (
    "composite_score", "risk_approval", "bankroll_pct", "edge_source",
    "fill_status", "category", "title", "unit_size", "closing_price", "clv",
    "order_id",
)


def print_reconciliation():
    """Audit the trade log ↔ settlement log join health.

    Three views:
      1. Counts and trade_id overlap (how many settlements have a matching trade record).
      2. Open trades and orphaned settlements (still-pending vs no-link-back).
      3. Field-coverage on settlements (% populated for the fields R5 added).
    """
    trades = load_trade_log()
    settlements = load_settlement_log()

    trade_ids_log = {t.get("trade_id") for t in trades if t.get("trade_id")}
    trade_ids_settled = {s.get("trade_id") for s in settlements if s.get("trade_id")}
    overlap = trade_ids_log & trade_ids_settled
    orphaned_settlements = trade_ids_settled - trade_ids_log
    open_trades = [t for t in trades if not t.get("closed_at") and t.get("status") != "error"]

    # ── Summary counts ────────────────────────────────────────────────────────
    summary = Table(title="Trade Log <-> Settlement Reconciliation", show_lines=False)
    summary.add_column("Metric", style="cyan")
    summary.add_column("Value", justify="right")
    summary.add_row("Trade log entries", str(len(trades)))
    summary.add_row("Settlement entries", str(len(settlements)))
    summary.add_row("Joined on trade_id", f"[green]{len(overlap)}[/green]")
    coverage = (len(overlap) / len(settlements) * 100) if settlements else 0
    summary.add_row("Settlement join coverage", f"{coverage:.1f}%")
    summary.add_row("Orphaned settlements (no trade-log match)",
                    f"[red]{len(orphaned_settlements)}[/red]" if orphaned_settlements else "0")
    summary.add_row("Open trades (not yet settled)", str(len(open_trades)))
    console.print(summary)

    # ── Orphan window (oldest / newest) ───────────────────────────────────────
    if orphaned_settlements:
        orphan_records = [s for s in settlements if s.get("trade_id") in orphaned_settlements]
        orphan_records.sort(key=lambda s: s.get("settled_at") or "")
        oldest = orphan_records[0].get("settled_at", "?")
        newest = orphan_records[-1].get("settled_at", "?")
        rprint(
            f"\n[dim]Orphaned settlement window: {oldest[:10]} -> {newest[:10]} "
            f"({len(orphan_records)} records)[/dim]"
        )

    # ── Field-coverage matrix ─────────────────────────────────────────────────
    if settlements:
        coverage_table = Table(
            title="Settlement Field Coverage (R5-added fields)",
            show_lines=False,
        )
        coverage_table.add_column("Field", style="cyan")
        coverage_table.add_column("Populated", justify="right")
        coverage_table.add_column("%", justify="right")

        for field in _R5_FIELDS:
            populated = sum(
                1 for s in settlements
                if s.get(field) not in (None, "", 0)
            )
            pct = populated / len(settlements) * 100
            color = "green" if pct >= 80 else "yellow" if pct >= 20 else "red"
            coverage_table.add_row(
                field,
                f"{populated}/{len(settlements)}",
                f"[{color}]{pct:.0f}%[/{color}]",
            )
        console.print(coverage_table)

        if any(
            sum(1 for s in settlements if s.get(f) not in (None, "", 0)) == 0
            for f in _R5_FIELDS
        ):
            rprint(
                "\n[dim]Fields at 0% are pre-R5 -- see "
                "data/history/README.md for context.[/dim]"
            )


# ── Gate Mode ─────────────────────────────────────────────────────────────────

def run_gate_check(client: KalshiClient) -> int:
    """
    Gate mode: returns exit code 0 if safe to trade, 1 if limits breached.
    Used by automation scripts to check before execution.
    """
    positions = fetch_positions(client)
    _, daily_pnl = get_today_trades()

    failures = []

    if is_daily_limit_breached(daily_pnl):
        failures.append(f"Daily loss limit breached: ${abs(daily_pnl):.2f} / ${MAX_DAILY_LOSS:.2f}")

    if len(positions) >= MAX_OPEN_POSITIONS:
        failures.append(f"Max open positions reached: {len(positions)} / {MAX_OPEN_POSITIONS}")

    if failures:
        rprint("[red bold]GATE CHECK FAILED — DO NOT EXECUTE[/red bold]")
        for f in failures:
            rprint(f"   • {f}")
        return 1

    limit_pct = get_daily_limit_pct(daily_pnl)
    rprint(f"[green bold]GATE CHECK PASSED[/green bold] — Daily limit at {limit_pct:.1f}%")
    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Live portfolio risk dashboard (Kalshi API)")
    parser.add_argument("--report", default="all",
                        choices=["all", "positions", "pnl", "limits", "watchlist", "reconciliation"],
                        help="Report type to display")
    parser.add_argument("--gate", action="store_true",
                        help="Gate mode: exit 1 if limits breached (for automation)")
    parser.add_argument("--save", action="store_true",
                        help="Save dashboard as markdown to reports/Accounts/Kalshi/")
    args = parser.parse_args()

    # Reconciliation report doesn't need live API data — short-circuit.
    if args.report == "reconciliation":
        print_reconciliation()
        return

    client = KalshiClient()

    if args.gate:
        sys.exit(run_gate_check(client))

    # Fetch live data
    bal = fetch_balance(client)
    positions = fetch_positions(client)
    resting = fetch_resting_orders(client)
    today_trades, daily_pnl = get_today_trades()
    watchlist = load_watchlist()

    print_risk_header(client)

    report = args.report

    if report in ("all", "limits"):
        print_balance(bal)
        print_limits_status(daily_pnl, len(positions))

    if report in ("all", "positions"):
        print_open_positions(positions)
        print_resting_orders(resting)

    if report in ("all", "pnl"):
        print_pnl_summary(today_trades, daily_pnl)

    if report in ("all", "watchlist"):
        print_watchlist(watchlist)

    if report == "all":
        if is_daily_limit_breached(daily_pnl):
            console.print(Panel(
                "[red bold]HARD STOP ACTIVE — No new positions permitted today[/red bold]",
                expand=False
            ))
        else:
            limit_pct = get_daily_limit_pct(daily_pnl)
            console.print(Panel(
                f"[green]Trading permitted — Daily limit at {limit_pct:.1f}%[/green]",
                expand=False
            ))

    # Save markdown report
    if args.save:
        _save_dashboard_report(client, bal, positions, resting, today_trades, daily_pnl, watchlist)


def _save_dashboard_report(client, bal, positions, resting, today_trades, daily_pnl, watchlist):
    """Generate and save a markdown risk dashboard report."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    env = "DEMO" if client.is_demo else "LIVE"
    limit_pct = get_daily_limit_pct(daily_pnl)
    breached = is_daily_limit_breached(daily_pnl)

    md = []
    md.append(f"# Risk Dashboard")
    md.append(f"")
    md.append(f"*{now.strftime('%A, %B %d, %Y')} | {now.strftime('%I:%M %p UTC')} | {env}*")
    md.append(f"")

    # Balance & limits
    md.append(f"## Account")
    md.append(f"")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Cash Balance | ${bal['balance']:,.2f} |")
    md.append(f"| Portfolio Value | ${bal['portfolio_value']:,.2f} |")
    md.append(f"| Open Positions | {len(positions)}/{MAX_OPEN_POSITIONS} |")
    md.append(f"| Daily Loss Used | ${abs(min(daily_pnl, 0)):.2f} / ${MAX_DAILY_LOSS:.2f} ({limit_pct:.1f}%) |")
    status = "HARD STOP" if breached else "Normal" if limit_pct < 50 else "Caution"
    md.append(f"| Status | **{status}** |")

    # Positions
    if positions:
        total_exp = 0.0
        total_pnl_pos = 0.0
        md.append(f"")
        md.append(f"## Open Positions ({len(positions)})")
        md.append(f"")
        md.append(f"| Bet | When | Pick | Qty | Cost | P&L |")
        md.append(f"|-----|------|------|-----|------|-----|")
        for p in positions:
            ticker = p.get("ticker", "")
            pnl = float(p.get("realized_pnl_dollars", "0"))
            exposure = float(p.get("market_exposure_dollars", "0"))
            total_exp += exposure
            total_pnl_pos += pnl
            yes_qty = float(p.get("position_fp", "0"))
            side = "YES" if yes_qty > 0 else "NO"
            pick_name = parse_pick_team(ticker) or side
            md.append(
                f"| {parse_matchup(ticker) or ticker[:30]} "
                f"| {parse_game_datetime(ticker)} "
                f"| {side} {pick_name} "
                f"| {int(abs(yes_qty))} "
                f"| ${exposure:.2f} "
                f"| ${pnl:+.2f} |"
            )
        md.append(f"| **TOTAL** | | | | **${total_exp:.2f}** | **${total_pnl_pos:+.2f}** |")

    # Recent settlements from Kalshi API (last 7 days)
    from datetime import timedelta
    from ticker_display import format_bet_label, bet_type_from_ticker, sport_from_ticker

    try:
        cutoff = (now - timedelta(days=7)).isoformat()
        all_settlements = []
        cursor = None
        for _ in range(20):
            resp = client.get_settlements(limit=200, cursor=cursor)
            setts = resp.get("settlements", [])
            all_settlements.extend(setts)
            cursor = resp.get("cursor", "")
            if not cursor:
                break

        recent = [s for s in all_settlements if (s.get("settled_time") or "") >= cutoff]

        # Normalize settlement records
        settled_records = []
        for s in recent:
            yes_count = float(s.get("yes_count_fp", 0))
            no_count = float(s.get("no_count_fp", 0))
            yes_cost = float(s.get("yes_total_cost_dollars", 0))
            no_cost = float(s.get("no_total_cost_dollars", 0))
            revenue_cents = s.get("revenue", 0)
            revenue = revenue_cents / 100 if isinstance(revenue_cents, int) and revenue_cents > 1 else float(revenue_cents)
            fees = float(s.get("fee_cost", 0))
            result = s.get("market_result", "")
            side = "yes" if yes_count > 0 and (no_count == 0 or yes_cost > no_cost) else "no"
            cost = yes_cost if side == "yes" else no_cost
            won = (side == "yes" and result == "yes") or (side == "no" and result == "no")
            net_pnl = revenue - cost - fees

            if cost > 0 or revenue > 0:
                settled_records.append({
                    "ticker": s.get("ticker", ""),
                    "side": side, "cost": cost, "revenue": revenue,
                    "fees": fees, "net_pnl": round(net_pnl, 4),
                    "won": won, "result": result,
                    "contracts": int(yes_count if side == "yes" else no_count),
                    "settled_time": s.get("settled_time", ""),
                })

        # Settlement summary
        if settled_records:
            s_wins = [r for r in settled_records if r["won"]]
            s_losses = [r for r in settled_records if not r["won"]]
            s_pnl = sum(r["net_pnl"] for r in settled_records)
            s_wagered = sum(r["cost"] for r in settled_records)
            s_revenue = sum(r["revenue"] for r in settled_records)
            s_fees = sum(r["fees"] for r in settled_records)
            s_roi = s_pnl / s_wagered if s_wagered > 0 else 0
            s_wr = len(s_wins) / len(settled_records) if settled_records else 0
            s_avg_win = sum(r["net_pnl"] for r in s_wins) / len(s_wins) if s_wins else 0
            s_avg_loss = sum(r["net_pnl"] for r in s_losses) / len(s_losses) if s_losses else 0

            pnl_sign = "+" if s_pnl >= 0 else ""
            md.append(f"")
            md.append(f"## Settlement Summary (Last 7 Days — {len(settled_records)} bets)")
            md.append(f"")
            md.append(f"| Metric | Value |")
            md.append(f"|--------|-------|")
            md.append(f"| Record | **{len(s_wins)}W - {len(s_losses)}L ({s_wr:.0%})** |")
            md.append(f"| Net P&L | **${s_pnl:+.2f}** |")
            md.append(f"| Total wagered | ${s_wagered:.2f} |")
            md.append(f"| Total revenue | ${s_revenue:.2f} |")
            md.append(f"| Total fees | ${s_fees:.2f} |")
            md.append(f"| ROI | **{s_roi:+.1%}** |")
            md.append(f"| Avg win | ${s_avg_win:+.2f} |")
            md.append(f"| Avg loss | ${s_avg_loss:+.2f} |")

            if s_wins and s_losses:
                loss_total = abs(sum(r["net_pnl"] for r in s_losses))
                if loss_total > 0:
                    md.append(f"| Profit factor | {abs(sum(r['net_pnl'] for r in s_wins)) / loss_total:.2f} |")

            best = max(settled_records, key=lambda r: r["net_pnl"])
            worst = min(settled_records, key=lambda r: r["net_pnl"])
            md.append(f"| Best trade | ${best['net_pnl']:+.2f} — {format_bet_label(best['ticker'], best['ticker'])[:30]} |")
            md.append(f"| Worst trade | ${worst['net_pnl']:+.2f} — {format_bet_label(worst['ticker'], worst['ticker'])[:30]} |")

            # By sport breakdown
            sport_groups: dict[str, list] = {}
            for r in settled_records:
                sport = sport_from_ticker(r["ticker"]) or "Other"
                sport_groups.setdefault(sport, []).append(r)
            if sport_groups:
                md.append(f"")
                md.append(f"### By Sport")
                md.append(f"")
                md.append(f"| Sport | Bets | Win Rate | P&L | ROI |")
                md.append(f"|-------|------|----------|-----|-----|")
                for name, recs in sorted(sport_groups.items(), key=lambda x: -sum(r["net_pnl"] for r in x[1])):
                    n = len(recs)
                    w = sum(1 for r in recs if r["won"])
                    pnl = sum(r["net_pnl"] for r in recs)
                    wag = sum(r["cost"] for r in recs)
                    roi_v = pnl / wag if wag > 0 else 0
                    md.append(f"| {name} | {n} | {w}/{n} ({w/n:.0%}) | ${pnl:+.2f} | {roi_v:+.0%} |")

            # By type breakdown
            type_groups: dict[str, list] = {}
            for r in settled_records:
                btype = bet_type_from_ticker(r["ticker"])
                type_groups.setdefault(btype, []).append(r)
            if type_groups:
                md.append(f"")
                md.append(f"### By Type")
                md.append(f"")
                md.append(f"| Type | Bets | Win Rate | P&L | ROI |")
                md.append(f"|------|------|----------|-----|-----|")
                for name, recs in sorted(type_groups.items(), key=lambda x: -sum(r["net_pnl"] for r in x[1])):
                    n = len(recs)
                    w = sum(1 for r in recs if r["won"])
                    pnl = sum(r["net_pnl"] for r in recs)
                    wag = sum(r["cost"] for r in recs)
                    roi_v = pnl / wag if wag > 0 else 0
                    md.append(f"| {name} | {n} | {w}/{n} ({w/n:.0%}) | ${pnl:+.2f} | {roi_v:+.0%} |")

            # Recent settlement detail (last 15)
            recent_sorted = sorted(settled_records, key=lambda x: x.get("settled_time", ""), reverse=True)[:15]
            md.append(f"")
            md.append(f"### Recent Settlements (latest 15)")
            md.append(f"")
            md.append(f"| Bet | Type | Side | Result | Qty | Cost | Revenue | P&L |")
            md.append(f"|-----|------|------|--------|-----|------|---------|-----|")
            for r in recent_sorted:
                won_str = "W" if r["won"] else "L"
                md.append(
                    f"| {format_bet_label(r['ticker'], r['ticker'])[:30]} "
                    f"| {bet_type_from_ticker(r['ticker'])} "
                    f"| {r['side'].upper()} "
                    f"| {r['result'].upper()} ({won_str}) "
                    f"| {r['contracts']} "
                    f"| ${r['cost']:.2f} "
                    f"| ${r['revenue']:.2f} "
                    f"| ${r['net_pnl']:+.2f} |"
                )
    except Exception as e:
        log.warning("Could not fetch settlements for dashboard: %s", e)

    # Resting orders
    if resting:
        md.append(f"")
        md.append(f"## Resting Orders ({len(resting)})")
        md.append(f"")
        md.append(f"| Ticker | Side | Remaining | Price |")
        md.append(f"|--------|------|-----------|-------|")
        for o in resting:
            price = o.get("yes_price_dollars") or o.get("no_price_dollars") or "?"
            md.append(f"| {o.get('ticker', '')[:35]} | {o.get('side', '').upper()} | {o.get('remaining_count_fp', '?')} | ${price} |")

    # Watchlist
    if watchlist:
        md.append(f"")
        md.append(f"## Watchlist ({len(watchlist)} opportunities)")
        md.append(f"")
        md.append(f"| Ticker | Side | Edge | Score | Conf |")
        md.append(f"|--------|------|------|-------|------|")
        for o in sorted(watchlist, key=lambda x: x.get("composite_score", 0), reverse=True)[:10]:
            md.append(
                f"| {o.get('ticker', '')[:30]} | {o.get('side', '').upper()} "
                f"| {o.get('edge', 0):+.1%} | {o.get('composite_score', 0):.1f} "
                f"| {o.get('confidence', '')[:3].upper()} |"
            )

    md.append(f"")
    md.append(f"---")
    md.append(f"*Generated by Edge-Radar*")

    report_dir = Path(__file__).resolve().parent.parent.parent / "reports" / "Accounts" / "Kalshi"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"kalshi_dashboard_{today}.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    rprint(f"\n[dim]Dashboard saved to {report_path}[/dim]")


if __name__ == "__main__":
    main()
