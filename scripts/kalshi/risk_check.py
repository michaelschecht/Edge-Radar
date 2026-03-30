"""
risk_check.py
Live portfolio risk dashboard pulling data from Kalshi API and trade log.

Usage:
    python scripts/kalshi/risk_check.py                       # Full risk dashboard
    python scripts/kalshi/risk_check.py --report positions    # Open positions only
    python scripts/kalshi/risk_check.py --report pnl          # Today's P&L only
    python scripts/kalshi/risk_check.py --report limits       # Risk limit status
    python scripts/kalshi/risk_check.py --report watchlist    # Pending opportunities
    python scripts/kalshi/risk_check.py --gate                # Returns exit code 1 if limits breached
"""

import os
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
from trade_log import load_trade_log, get_today_pnl
from ticker_display import parse_game_datetime, parse_matchup, parse_pick_team, TEAM_NAMES
from logging_setup import setup_logging

# ── Setup ──────────────────────────────────────────────────────────────────────
load_dotenv()
console = Console()
log = setup_logging("risk_check")

# ── Risk Limits (from .env with defaults) ─────────────────────────────────────
MAX_BET_SPORTS      = float(os.getenv("MAX_BET_SIZE_SPORTS", 50))
MAX_BET_PREDICTION  = float(os.getenv("MAX_BET_SIZE_PREDICTION", 100))
MAX_DAILY_LOSS      = float(os.getenv("MAX_DAILY_LOSS", 250))
MAX_OPEN_POSITIONS  = int(os.getenv("MAX_OPEN_POSITIONS", 10))
MIN_EDGE            = float(os.getenv("MIN_EDGE_THRESHOLD", 0.03))
DRY_RUN             = os.getenv("DRY_RUN", "true").lower() == "true"

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
        "Max Bet (Sports)",
        "—",
        f"${MAX_BET_SPORTS:.0f}",
        "—",
        "[green]OK[/green]"
    )
    table.add_row(
        "Max Bet (Prediction)",
        "—",
        f"${MAX_BET_PREDICTION:.0f}",
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

    table = Table(title=f"Open Positions ({len(positions)})", show_lines=True)
    table.add_column("Bet", style="cyan", max_width=32)
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
        "", "", "",
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
    total_wagered = sum(t.get("cost_dollars", 0) for t in today_trades)

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
                        choices=["all", "positions", "pnl", "limits", "watchlist"],
                        help="Report type to display")
    parser.add_argument("--gate", action="store_true",
                        help="Gate mode: exit 1 if limits breached (for automation)")
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
