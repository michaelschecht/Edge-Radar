"""
risk_check.py
Checks current portfolio risk status, open positions, and daily P&L limits.
Usage:
    python scripts/risk_check.py                       # Full risk dashboard
    python scripts/risk_check.py --report positions    # Open positions only
    python scripts/risk_check.py --report pnl          # Today's P&L only
    python scripts/risk_check.py --report limits       # Risk limit status
    python scripts/risk_check.py --report watchlist    # Pending opportunities
    python scripts/risk_check.py --gate                # Returns exit code 1 if limits breached
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime, timezone, date
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# ── Setup ──────────────────────────────────────────────────────────────────────
load_dotenv()
console = Console()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger(__name__)

# ── Risk Limits (from .env with defaults) ─────────────────────────────────────
MAX_BET_SPORTS      = float(os.getenv("MAX_BET_SIZE_SPORTS", 50))
MAX_BET_PREDICTION  = float(os.getenv("MAX_BET_SIZE_PREDICTION", 100))
MAX_POSITION_STOCKS = float(os.getenv("MAX_POSITION_STOCKS", 500))
MAX_DAILY_LOSS      = float(os.getenv("MAX_DAILY_LOSS", 250))
MAX_OPEN_POSITIONS  = int(os.getenv("MAX_OPEN_POSITIONS", 10))
MIN_EDGE            = float(os.getenv("MIN_EDGE_THRESHOLD", 0.03))
MAX_PORTFOLIO_RISK  = float(os.getenv("MAX_PORTFOLIO_RISK_PCT", 0.02))
DRY_RUN             = os.getenv("DRY_RUN", "true").lower() == "true"

# ── File Paths ─────────────────────────────────────────────────────────────────
DATA_DIR            = Path("data")
POSITIONS_FILE      = DATA_DIR / "positions" / "open_positions.json"
HISTORY_FILE        = DATA_DIR / "history" / "today_trades.json"
WATCHLIST_FILE      = DATA_DIR / "watchlists" / "pending_review.json"
ALERTS_FILE         = DATA_DIR / "history" / "alerts.json"

# Ensure directories exist
for p in [DATA_DIR / "positions", DATA_DIR / "history", DATA_DIR / "watchlists"]:
    p.mkdir(parents=True, exist_ok=True)


# ── File Helpers ───────────────────────────────────────────────────────────────

def load_json(path: Path, default=None):
    if default is None:
        default = []
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return default


def save_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── Risk Calculations ──────────────────────────────────────────────────────────

def get_open_positions() -> list:
    return load_json(POSITIONS_FILE, [])


def get_today_trades() -> list:
    trades = load_json(HISTORY_FILE, [])
    today = date.today().isoformat()
    return [t for t in trades if t.get("closed_at", "")[:10] == today]


def calculate_daily_pnl(trades: list) -> float:
    return sum(t.get("net_pnl", 0) for t in trades)


def calculate_unrealized_pnl(positions: list) -> float:
    return sum(p.get("current_pnl", 0) for p in positions)


def calculate_total_exposure(positions: list) -> float:
    return sum(p.get("entry_cost", 0) for p in positions)


def get_daily_limit_pct(daily_pnl: float) -> float:
    if MAX_DAILY_LOSS == 0:
        return 0
    return abs(min(daily_pnl, 0)) / MAX_DAILY_LOSS * 100


def is_daily_limit_breached(daily_pnl: float) -> bool:
    return daily_pnl <= -MAX_DAILY_LOSS


def get_tilt_signals(trades: list, positions: list) -> list:
    """Detect behavioral risk signals."""
    signals = []
    today_losses = [t for t in trades if t.get("net_pnl", 0) < 0]

    if len(today_losses) >= 3:
        signals.append(f"⚠️  {len(today_losses)} losing trades today — monitor for tilt")

    # Check for re-entries on same instrument after stop-out
    closed_instruments = [t.get("instrument") for t in trades if t.get("close_reason") == "stop_loss"]
    open_instruments = [p.get("instrument") for p in positions]
    for inst in closed_instruments:
        if inst in open_instruments:
            signals.append(f"⚠️  Re-entered {inst} after stop-loss today")

    return signals


def get_correlated_groups(positions: list) -> dict:
    """Group positions by market correlation."""
    groups = {}
    for p in positions:
        sport = p.get("sport", p.get("market_type", "other"))
        groups.setdefault(sport, []).append(p.get("instrument", "unknown"))
    return {k: v for k, v in groups.items() if len(v) > 1}


# ── Display Functions ──────────────────────────────────────────────────────────

def print_risk_header():
    mode_tag = "[red bold]🔴 LIVE[/red bold]" if not DRY_RUN else "[green bold]🟢 DRY RUN[/green bold]"
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    console.print(Panel(
        f"[bold]FinAgent Risk Dashboard[/bold]  {mode_tag}\n[dim]{ts}[/dim]",
        expand=False
    ))


def print_limits_status(daily_pnl: float, open_count: int):
    limit_pct = get_daily_limit_pct(daily_pnl)
    breached = is_daily_limit_breached(daily_pnl)

    if limit_pct >= 100 or breached:
        status = "[red bold]⛔ HARD STOP — LIMIT BREACHED[/red bold]"
    elif limit_pct >= 90:
        status = "[red]🔴 CRITICAL (90%+)[/red]"
    elif limit_pct >= 75:
        status = "[yellow]🟠 WARNING (75%+)[/yellow]"
    elif limit_pct >= 50:
        status = "[yellow]🟡 CAUTION (50%+)[/yellow]"
    else:
        status = "[green]🟢 Normal[/green]"

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
    table.add_row(
        "Open Positions",
        str(open_count),
        str(MAX_OPEN_POSITIONS),
        f"{open_count / MAX_OPEN_POSITIONS * 100:.0f}%",
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
    table.add_row(
        "Max Position (Stocks)",
        "—",
        f"${MAX_POSITION_STOCKS:.0f}",
        "—",
        "[green]OK[/green]"
    )
    console.print(table)


def print_open_positions(positions: list):
    if not positions:
        rprint("\n[dim]No open positions.[/dim]")
        return

    table = Table(title=f"Open Positions ({len(positions)})", show_lines=True)
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Instrument", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Platform", style="dim")
    table.add_column("Entry $", justify="right")
    table.add_column("Cost $", justify="right")
    table.add_column("Current $", justify="right")
    table.add_column("P&L $", justify="right")
    table.add_column("P&L %", justify="right")
    table.add_column("Stop", justify="right", style="dim")
    table.add_column("Status")

    for p in positions:
        pnl = p.get("current_pnl", 0)
        pnl_pct = p.get("current_pnl_pct", 0)
        pnl_color = "green" if pnl >= 0 else "red"
        status = p.get("status", "open")
        status_color = "red" if status == "at_risk" else "green"

        table.add_row(
            p.get("position_id", "")[-8:],
            p.get("instrument", "")[:30],
            p.get("market_type", ""),
            p.get("platform", ""),
            f"${p.get('entry_price', 0):.4f}",
            f"${p.get('entry_cost', 0):.2f}",
            f"${p.get('current_value', 0):.2f}",
            f"[{pnl_color}]${pnl:+.2f}[/{pnl_color}]",
            f"[{pnl_color}]{pnl_pct:+.1%}[/{pnl_color}]",
            f"${p.get('stop_loss', 0):.4f}" if p.get("stop_loss") else "—",
            f"[{status_color}]{status}[/{status_color}]"
        )

    console.print(table)


def print_pnl_summary(trades: list, positions: list):
    daily_pnl = calculate_daily_pnl(trades)
    unrealized = calculate_unrealized_pnl(positions)
    total_pnl = daily_pnl + unrealized

    wins = [t for t in trades if t.get("net_pnl", 0) > 0]
    losses = [t for t in trades if t.get("net_pnl", 0) < 0]
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    table = Table(title="Today's P&L", show_lines=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    pnl_color = "green" if daily_pnl >= 0 else "red"
    total_color = "green" if total_pnl >= 0 else "red"

    table.add_row("Realized P&L (closed)", f"[{pnl_color}]${daily_pnl:+.2f}[/{pnl_color}]")
    table.add_row("Unrealized P&L (open)", f"${unrealized:+.2f}")
    table.add_row("Total P&L", f"[{total_color}][bold]${total_pnl:+.2f}[/bold][/{total_color}]")
    table.add_row("Closed Trades", str(len(trades)))
    table.add_row("Wins / Losses", f"{len(wins)} / {len(losses)}")
    table.add_row("Win Rate", f"{win_rate:.1f}%")

    if trades:
        best = max(trades, key=lambda t: t.get("net_pnl", 0))
        worst = min(trades, key=lambda t: t.get("net_pnl", 0))
        table.add_row("Best Trade", f"[green]{best.get('instrument', '')} +${best.get('net_pnl', 0):.2f}[/green]")
        table.add_row("Worst Trade", f"[red]{worst.get('instrument', '')} ${worst.get('net_pnl', 0):.2f}[/red]")

    console.print(table)


def print_watchlist(opportunities: list):
    pending = [o for o in opportunities if o.get("status") == "pending_review"]
    if not pending:
        rprint("\n[dim]No pending opportunities in watchlist.[/dim]")
        return

    table = Table(title=f"Pending Opportunities ({len(pending)})", show_lines=True)
    table.add_column("Instrument", style="cyan")
    table.add_column("Type", style="dim")
    table.add_column("Platform", style="dim")
    table.add_column("Edge", justify="right", style="green")
    table.add_column("Score", justify="right")
    table.add_column("Surfaced At", style="dim")

    for o in sorted(pending, key=lambda x: x.get("edge_estimate", 0), reverse=True):
        ts = o.get("surfaced_at", "")[:16].replace("T", " ")
        table.add_row(
            o.get("instrument", "")[:35],
            o.get("market_type", ""),
            o.get("platform", ""),
            f"+{o.get('edge_estimate', 0):.2%}",
            str(o.get("composite_score", "—")),
            ts
        )

    console.print(table)


def print_tilt_warnings(signals: list):
    if signals:
        rprint("\n[bold yellow]⚠️  Tilt Signals Detected:[/bold yellow]")
        for s in signals:
            rprint(f"   {s}")


def print_correlation_warnings(groups: dict):
    if groups:
        rprint("\n[bold yellow]📊 Correlated Position Groups:[/bold yellow]")
        for group, instruments in groups.items():
            rprint(f"   [cyan]{group}:[/cyan] {', '.join(instruments)}")


# ── Gate Mode ─────────────────────────────────────────────────────────────────

def run_gate_check() -> int:
    """
    Gate mode: returns exit code 0 if safe to trade, 1 if limits breached.
    Used by automation scripts to check before execution.
    """
    positions = get_open_positions()
    trades = get_today_trades()
    daily_pnl = calculate_daily_pnl(trades)

    failures = []

    if is_daily_limit_breached(daily_pnl):
        failures.append(f"Daily loss limit breached: ${abs(daily_pnl):.2f} / ${MAX_DAILY_LOSS:.2f}")

    if len(positions) >= MAX_OPEN_POSITIONS:
        failures.append(f"Max open positions reached: {len(positions)} / {MAX_OPEN_POSITIONS}")

    if failures:
        rprint("[red bold]❌ GATE CHECK FAILED — DO NOT EXECUTE[/red bold]")
        for f in failures:
            rprint(f"   • {f}")
        return 1

    limit_pct = get_daily_limit_pct(daily_pnl)
    rprint(f"[green bold]✅ GATE CHECK PASSED[/green bold] — Daily limit at {limit_pct:.1f}%")
    return 0


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Check portfolio risk status and limits.")
    parser.add_argument("--report", default="all",
                        choices=["all", "positions", "pnl", "limits", "watchlist"],
                        help="Report type to display")
    parser.add_argument("--gate", action="store_true",
                        help="Gate mode: exit 1 if limits breached (for automation)")
    args = parser.parse_args()

    if args.gate:
        sys.exit(run_gate_check())

    # Load data
    positions = get_open_positions()
    trades = get_today_trades()
    daily_pnl = calculate_daily_pnl(trades)
    watchlist = load_json(WATCHLIST_FILE, [])
    tilt_signals = get_tilt_signals(trades, positions)
    correlated_groups = get_correlated_groups(positions)

    print_risk_header()

    report = args.report

    if report in ("all", "limits"):
        print_limits_status(daily_pnl, len(positions))

    if report in ("all", "pnl"):
        print_pnl_summary(trades, positions)

    if report in ("all", "positions"):
        print_open_positions(positions)

    if report in ("all", "watchlist"):
        print_watchlist(watchlist)

    if report == "all":
        print_tilt_warnings(tilt_signals)
        print_correlation_warnings(correlated_groups)

        # Final verdict
        if is_daily_limit_breached(daily_pnl):
            console.print(Panel(
                "[red bold]⛔ HARD STOP ACTIVE — No new positions permitted today[/red bold]",
                expand=False
            ))
        else:
            limit_pct = get_daily_limit_pct(daily_pnl)
            console.print(Panel(
                f"[green]✅ Trading permitted — Daily limit at {limit_pct:.1f}%[/green]",
                expand=False
            ))


if __name__ == "__main__":
    main()
