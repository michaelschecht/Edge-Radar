"""
backtester.py — Edge-Radar backtesting framework (W1).

Analyzes settled trades to evaluate strategy performance, signal quality,
and risk-adjusted returns.  Supports what-if strategy simulations.

Usage:
    python scripts/backtest/backtester.py                     # Full report
    python scripts/backtest/backtester.py --sport mlb          # MLB only
    python scripts/backtest/backtester.py --min-edge 0.05      # Edge >= 5%
    python scripts/backtest/backtester.py --confidence high     # High conf only
    python scripts/backtest/backtester.py --simulate            # Strategy comparison
    python scripts/backtest/backtester.py --save                # Save markdown report
"""

import sys
import json
import math
import argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

# Path setup
import paths  # noqa: F401
from trade_log import load_settlement_log
from ticker_display import sport_from_ticker, bet_type_from_ticker
from logging_setup import setup_logging
from app.config import get_config

from rich.console import Console
from rich.table import Table
from rich import print as rprint

log = setup_logging("backtester")
console = Console()


# ── Data Loading ───────────────────────────────────────────────────────────

def load_trades() -> list[dict]:
    """Load and enrich settlement log with derived fields."""
    settlements = load_settlement_log()
    if not settlements:
        return []

    for s in settlements:
        ticker = s.get("ticker", "")
        s["sport"] = sport_from_ticker(ticker)
        s["category"] = _category_from_ticker(ticker)
        s["edge_estimated"] = s.get("edge_estimated") or 0
        s["fair_value"] = s.get("fair_value") or 0
        s["market_price_at_entry"] = s.get("market_price_at_entry") or 0
        s["net_pnl"] = s.get("net_pnl") or 0
        s["cost"] = s.get("cost") or 0
        s["roi"] = s.get("roi") or 0
        s["confidence"] = s.get("confidence") or "unknown"
        s["won"] = s.get("won", False)
        s["settled_at"] = s.get("settled_at", "")

    # Sort chronologically
    settlements.sort(key=lambda t: t["settled_at"])
    return settlements


def _category_from_ticker(ticker: str) -> str:
    """Derive category from ticker pattern."""
    t = ticker.upper()
    if "SPREAD" in t:
        return "spread"
    elif "TOTAL" in t:
        return "total"
    elif "GAME" in t:
        return "game"
    return "other"


def filter_trades(
    trades: list[dict],
    sport: str | None = None,
    category: str | None = None,
    confidence: str | None = None,
    min_edge: float | None = None,
    max_edge: float | None = None,
    after: str | None = None,
) -> list[dict]:
    """Filter trades by criteria."""
    result = trades
    if sport:
        sport_upper = sport.upper()
        result = [t for t in result if t["sport"].upper() == sport_upper]
    if category:
        result = [t for t in result if t["category"] == category.lower()]
    if confidence:
        result = [t for t in result if t["confidence"] == confidence.lower()]
    if min_edge is not None:
        result = [t for t in result if t["edge_estimated"] >= min_edge]
    if max_edge is not None:
        result = [t for t in result if t["edge_estimated"] < max_edge]
    if after:
        result = [t for t in result if t["settled_at"][:10] >= after]
    return result


# ── Core Analytics ─────────────────────────────────────────────────────────

@dataclass
class BacktestResult:
    """Complete backtest analysis output."""
    trades: list[dict]
    label: str = "All Trades"

    # Summary stats (computed by analyze())
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    net_pnl: float = 0.0
    total_wagered: float = 0.0
    roi: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0

    # Risk metrics
    equity_curve: list = field(default_factory=list)
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    longest_win_streak: int = 0
    longest_lose_streak: int = 0

    # Breakdowns
    by_sport: dict = field(default_factory=dict)
    by_category: dict = field(default_factory=dict)
    by_confidence: dict = field(default_factory=dict)
    by_edge_bucket: dict = field(default_factory=dict)
    calibration: list = field(default_factory=list)

    def analyze(self) -> "BacktestResult":
        """Compute all analytics from self.trades."""
        trades = self.trades
        if not trades:
            return self

        self.total_trades = len(trades)
        self.wins = sum(1 for t in trades if t["won"])
        self.losses = self.total_trades - self.wins
        self.win_rate = self.wins / self.total_trades if self.total_trades else 0

        pnls = [t["net_pnl"] for t in trades]
        self.net_pnl = sum(pnls)
        self.total_wagered = sum(t["cost"] for t in trades)
        self.roi = self.net_pnl / self.total_wagered if self.total_wagered else 0

        win_pnls = [p for p in pnls if p > 0]
        lose_pnls = [p for p in pnls if p <= 0]
        self.avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0
        self.avg_loss = sum(lose_pnls) / len(lose_pnls) if lose_pnls else 0
        total_wins = sum(win_pnls)
        total_losses = abs(sum(lose_pnls))
        self.profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")
        self.best_trade = max(pnls) if pnls else 0
        self.worst_trade = min(pnls) if pnls else 0

        # Streaks
        self.longest_win_streak, self.longest_lose_streak = _streaks(trades)

        # Equity curve + drawdown
        self.equity_curve = _equity_curve(trades)
        self.max_drawdown, self.max_drawdown_pct = _max_drawdown(self.equity_curve)

        # Sharpe ratio (daily P&L based)
        self.sharpe_ratio = _sharpe_ratio(trades)

        # Breakdowns
        self.by_sport = _breakdown(trades, "sport")
        self.by_category = _breakdown(trades, "category")
        self.by_confidence = _breakdown(trades, "confidence")
        self.by_edge_bucket = _edge_bucket_breakdown(trades)

        # Calibration curve
        self.calibration = _calibration_curve(trades)

        return self


def _equity_curve(trades: list[dict]) -> list[dict]:
    """Build cumulative P&L curve."""
    cumulative = 0.0
    curve = []
    for t in trades:
        cumulative += t["net_pnl"]
        curve.append({
            "date": t["settled_at"][:10],
            "ticker": t["ticker"],
            "pnl": t["net_pnl"],
            "cumulative": round(cumulative, 2),
        })
    return curve


def _max_drawdown(curve: list[dict]) -> tuple[float, float]:
    """Calculate maximum drawdown in dollars and percentage."""
    if not curve:
        return 0.0, 0.0
    peak = 0.0
    max_dd = 0.0
    max_dd_pct = 0.0
    for point in curve:
        cum = point["cumulative"]
        if cum > peak:
            peak = cum
        dd = peak - cum
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = dd / peak if peak > 0 else 0
    return round(max_dd, 2), round(max_dd_pct, 4)


def _sharpe_ratio(trades: list[dict]) -> float:
    """Annualized Sharpe ratio from per-trade returns."""
    if len(trades) < 2:
        return 0.0
    returns = [t["net_pnl"] / t["cost"] if t["cost"] > 0 else 0 for t in trades]
    mean_r = sum(returns) / len(returns)
    var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
    std_r = math.sqrt(var) if var > 0 else 0
    if std_r == 0:
        return 0.0
    # Annualize assuming ~250 trading days, ~3 trades/day average
    trades_per_year = 750
    return round((mean_r / std_r) * math.sqrt(trades_per_year), 2)


def _streaks(trades: list[dict]) -> tuple[int, int]:
    """Longest win and lose streaks."""
    max_win = max_lose = 0
    cur_win = cur_lose = 0
    for t in trades:
        if t["won"]:
            cur_win += 1
            cur_lose = 0
        else:
            cur_lose += 1
            cur_win = 0
        max_win = max(max_win, cur_win)
        max_lose = max(max_lose, cur_lose)
    return max_win, max_lose


def _breakdown(trades: list[dict], key: str) -> dict:
    """Win rate, P&L, ROI breakdown by a grouping key."""
    groups = defaultdict(list)
    for t in trades:
        groups[t.get(key, "unknown")].append(t)

    result = {}
    for name, group in sorted(groups.items()):
        wins = sum(1 for t in group if t["won"])
        total_pnl = sum(t["net_pnl"] for t in group)
        wagered = sum(t["cost"] for t in group)
        avg_edge = sum(t["edge_estimated"] for t in group) / len(group)
        result[name] = {
            "trades": len(group),
            "wins": wins,
            "losses": len(group) - wins,
            "win_rate": wins / len(group),
            "pnl": round(total_pnl, 2),
            "wagered": round(wagered, 2),
            "roi": round(total_pnl / wagered, 4) if wagered > 0 else 0,
            "avg_edge": round(avg_edge, 4),
        }
    return result


def _edge_bucket_breakdown(trades: list[dict]) -> dict:
    """Breakdown by edge bucket."""
    buckets = [
        ("3-5%", 0.03, 0.05),
        ("5-10%", 0.05, 0.10),
        ("10-15%", 0.10, 0.15),
        ("15-25%", 0.15, 0.25),
        ("25%+", 0.25, 1.0),
    ]
    result = {}
    for label, lo, hi in buckets:
        group = [t for t in trades if lo <= t["edge_estimated"] < hi]
        if not group:
            continue
        wins = sum(1 for t in group if t["won"])
        total_pnl = sum(t["net_pnl"] for t in group)
        wagered = sum(t["cost"] for t in group)
        avg_edge = sum(t["edge_estimated"] for t in group) / len(group)
        result[label] = {
            "trades": len(group),
            "wins": wins,
            "losses": len(group) - wins,
            "win_rate": wins / len(group),
            "pnl": round(total_pnl, 2),
            "wagered": round(wagered, 2),
            "roi": round(total_pnl / wagered, 4) if wagered > 0 else 0,
            "avg_edge": round(avg_edge, 4),
        }
    return result


def _calibration_curve(trades: list[dict]) -> list[dict]:
    """Predicted probability vs realized win rate in buckets."""
    buckets = [
        ("0-30%", 0.0, 0.30),
        ("30-40%", 0.30, 0.40),
        ("40-50%", 0.40, 0.50),
        ("50-60%", 0.50, 0.60),
        ("60-70%", 0.60, 0.70),
        ("70-80%", 0.70, 0.80),
        ("80-100%", 0.80, 1.01),
    ]
    result = []
    for label, lo, hi in buckets:
        group = [t for t in trades if lo <= t["fair_value"] < hi]
        if not group:
            continue
        avg_predicted = sum(t["fair_value"] for t in group) / len(group)
        actual_win_rate = sum(1 for t in group if t["won"]) / len(group)
        result.append({
            "bucket": label,
            "count": len(group),
            "avg_predicted": round(avg_predicted, 3),
            "actual_win_rate": round(actual_win_rate, 3),
            "gap": round(actual_win_rate - avg_predicted, 3),
        })
    return result


# ── Strategy Simulation ────────────────────────────────────────────────────

def simulate_strategies(trades: list[dict]) -> list[BacktestResult]:
    """Run what-if comparisons across different filter strategies."""
    strategies = []

    # Baseline: all trades
    strategies.append(BacktestResult(trades=trades, label="Baseline (all trades)").analyze())

    # By minimum edge threshold
    for edge in [0.05, 0.08, 0.10, 0.15]:
        filtered = filter_trades(trades, min_edge=edge)
        if len(filtered) >= 5:
            strategies.append(BacktestResult(
                trades=filtered,
                label=f"Edge >= {edge:.0%}",
            ).analyze())

    # By confidence
    for conf in ["medium", "high"]:
        filtered = filter_trades(trades, confidence=conf)
        if len(filtered) >= 5:
            strategies.append(BacktestResult(
                trades=filtered,
                label=f"Confidence: {conf}",
            ).analyze())

    # High confidence + high edge
    filtered = filter_trades(trades, confidence="high", min_edge=0.10)
    if len(filtered) >= 5:
        strategies.append(BacktestResult(
            trades=filtered,
            label="High conf + edge >= 10%",
        ).analyze())

    # By category
    for cat in ["game", "spread", "total"]:
        filtered = filter_trades(trades, category=cat)
        if len(filtered) >= 5:
            strategies.append(BacktestResult(
                trades=filtered,
                label=f"Category: {cat}",
            ).analyze())

    # By sport (only if enough trades)
    for sport in set(t["sport"] for t in trades):
        filtered = filter_trades(trades, sport=sport)
        if len(filtered) >= 5:
            strategies.append(BacktestResult(
                trades=filtered,
                label=f"Sport: {sport}",
            ).analyze())

    return strategies


# ── Display ────────────────────────────────────────────────────────────────

def print_summary(result: BacktestResult):
    """Print a rich terminal summary."""
    rprint(f"\n[bold cyan]=== {result.label} ===[/bold cyan]")
    rprint(f"  Trades: {result.total_trades}  |  "
           f"Record: [green]{result.wins}W[/green]-[red]{result.losses}L[/red]  |  "
           f"Win rate: {result.win_rate:.1%}")

    pnl_color = "green" if result.net_pnl >= 0 else "red"
    rprint(f"  P&L: [{pnl_color}]${result.net_pnl:+.2f}[/{pnl_color}]  |  "
           f"Wagered: ${result.total_wagered:.2f}  |  "
           f"ROI: [{pnl_color}]{result.roi:+.1%}[/{pnl_color}]")

    rprint(f"  Profit factor: {result.profit_factor:.2f}  |  "
           f"Avg win: ${result.avg_win:+.2f}  |  Avg loss: ${result.avg_loss:+.2f}")
    rprint(f"  Best: ${result.best_trade:+.2f}  |  Worst: ${result.worst_trade:+.2f}  |  "
           f"Streaks: {result.longest_win_streak}W / {result.longest_lose_streak}L")
    rprint(f"  Max drawdown: ${result.max_drawdown:.2f} ({result.max_drawdown_pct:.1%})  |  "
           f"Sharpe: {result.sharpe_ratio:.2f}")


def print_breakdown(result: BacktestResult):
    """Print breakdown tables."""
    for title, data in [
        ("By Sport", result.by_sport),
        ("By Category", result.by_category),
        ("By Confidence", result.by_confidence),
        ("By Edge Bucket", result.by_edge_bucket),
    ]:
        if not data:
            continue
        table = Table(title=title, show_header=True, header_style="bold")
        table.add_column("Group", style="cyan")
        table.add_column("Trades", justify="right")
        table.add_column("Record", justify="right")
        table.add_column("Win %", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("ROI", justify="right")
        table.add_column("Avg Edge", justify="right")

        for name, stats in data.items():
            pnl_style = "green" if stats["pnl"] >= 0 else "red"
            roi_style = "green" if stats["roi"] >= 0 else "red"
            table.add_row(
                str(name),
                str(stats["trades"]),
                f"{stats['wins']}W-{stats['losses']}L",
                f"{stats['win_rate']:.0%}",
                f"[{pnl_style}]${stats['pnl']:+.2f}[/{pnl_style}]",
                f"[{roi_style}]{stats['roi']:+.1%}[/{roi_style}]",
                f"{stats.get('avg_edge', 0):.1%}",
            )
        console.print(table)


def print_calibration(result: BacktestResult):
    """Print calibration curve."""
    if not result.calibration:
        return
    table = Table(title="Calibration Curve (Predicted Prob vs Actual Win Rate)",
                  show_header=True, header_style="bold")
    table.add_column("Bucket", style="cyan")
    table.add_column("Count", justify="right")
    table.add_column("Predicted", justify="right")
    table.add_column("Actual", justify="right")
    table.add_column("Gap", justify="right")

    for row in result.calibration:
        gap = row["gap"]
        gap_style = "green" if gap >= 0 else "red"
        table.add_row(
            row["bucket"],
            str(row["count"]),
            f"{row['avg_predicted']:.1%}",
            f"{row['actual_win_rate']:.1%}",
            f"[{gap_style}]{gap:+.1%}[/{gap_style}]",
        )
    console.print(table)


def print_equity_curve(result: BacktestResult):
    """Print equity curve as a simple ASCII sparkline by date."""
    if not result.equity_curve:
        return
    rprint("\n[bold]Equity Curve[/bold]")

    # Group by date
    daily = defaultdict(float)
    daily_cum = {}
    for point in result.equity_curve:
        d = point["date"]
        daily[d] += point["pnl"]

    cum = 0.0
    for d in sorted(daily):
        cum += daily[d]
        daily_cum[d] = cum

    # Simple text sparkline
    dates = sorted(daily_cum)
    values = [daily_cum[d] for d in dates]
    min_v = min(values) if values else 0
    max_v = max(values) if values else 0
    span = max_v - min_v if max_v != min_v else 1
    bar_chars = " .-=+*#@$%"

    for d, v in zip(dates, values):
        idx = int((v - min_v) / span * 8)
        idx = max(0, min(8, idx))
        bar = bar_chars[idx]
        color = "green" if v >= 0 else "red"
        day_pnl = daily[d]
        rprint(f"  {d}  [{color}]{bar * 3} ${v:+7.2f}[/{color}]  (day: ${day_pnl:+.2f})")


def print_simulation(strategies: list[BacktestResult]):
    """Print strategy simulation comparison table."""
    rprint("\n[bold cyan]=== Strategy Simulation ===[/bold cyan]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Strategy", style="cyan", min_width=25)
    table.add_column("Trades", justify="right")
    table.add_column("Win %", justify="right")
    table.add_column("P&L", justify="right")
    table.add_column("ROI", justify="right")
    table.add_column("Sharpe", justify="right")
    table.add_column("Max DD", justify="right")
    table.add_column("PF", justify="right")

    for s in strategies:
        pnl_style = "green" if s.net_pnl >= 0 else "red"
        roi_style = "green" if s.roi >= 0 else "red"
        table.add_row(
            s.label,
            str(s.total_trades),
            f"{s.win_rate:.0%}",
            f"[{pnl_style}]${s.net_pnl:+.2f}[/{pnl_style}]",
            f"[{roi_style}]{s.roi:+.1%}[/{roi_style}]",
            f"{s.sharpe_ratio:.2f}",
            f"${s.max_drawdown:.2f}",
            f"{s.profit_factor:.2f}",
        )
    console.print(table)

    # Find best strategy by ROI
    best = max(strategies, key=lambda s: s.roi)
    if best.label != "Baseline (all trades)":
        rprint(f"\n  [green]Best strategy: {best.label}[/green] "
               f"(ROI: {best.roi:+.1%}, Sharpe: {best.sharpe_ratio:.2f})")


# ── Markdown Report ────────────────────────────────────────────────────────

def generate_markdown(result: BacktestResult,
                      strategies: list[BacktestResult] | None = None) -> str:
    """Generate a comprehensive markdown report."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# Edge-Radar Backtest Report")
    lines.append(f"*Generated: {now}*\n")

    # Summary
    lines.append("## Summary\n")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Trades | {result.total_trades} |")
    lines.append(f"| Record | {result.wins}W-{result.losses}L ({result.win_rate:.1%}) |")
    lines.append(f"| Net P&L | ${result.net_pnl:+.2f} |")
    lines.append(f"| Total Wagered | ${result.total_wagered:.2f} |")
    lines.append(f"| ROI | {result.roi:+.1%} |")
    lines.append(f"| Profit Factor | {result.profit_factor:.2f} |")
    lines.append(f"| Avg Win / Loss | ${result.avg_win:+.2f} / ${result.avg_loss:+.2f} |")
    lines.append(f"| Best / Worst | ${result.best_trade:+.2f} / ${result.worst_trade:+.2f} |")
    lines.append(f"| Win/Lose Streaks | {result.longest_win_streak}W / {result.longest_lose_streak}L |")
    lines.append(f"| Max Drawdown | ${result.max_drawdown:.2f} ({result.max_drawdown_pct:.1%}) |")
    lines.append(f"| Sharpe Ratio | {result.sharpe_ratio:.2f} |")
    lines.append("")

    # Breakdowns
    for title, data in [
        ("By Sport", result.by_sport),
        ("By Category", result.by_category),
        ("By Confidence", result.by_confidence),
        ("By Edge Bucket", result.by_edge_bucket),
    ]:
        if not data:
            continue
        lines.append(f"## {title}\n")
        lines.append("| Group | Trades | Record | Win % | P&L | ROI | Avg Edge |")
        lines.append("|-------|--------|--------|-------|-----|-----|----------|")
        for name, s in data.items():
            lines.append(
                f"| {name} | {s['trades']} | {s['wins']}W-{s['losses']}L | "
                f"{s['win_rate']:.0%} | ${s['pnl']:+.2f} | {s['roi']:+.1%} | "
                f"{s.get('avg_edge', 0):.1%} |"
            )
        lines.append("")

    # Calibration
    if result.calibration:
        lines.append("## Calibration Curve\n")
        lines.append("| Bucket | Count | Predicted | Actual | Gap |")
        lines.append("|--------|-------|-----------|--------|-----|")
        for row in result.calibration:
            lines.append(
                f"| {row['bucket']} | {row['count']} | {row['avg_predicted']:.1%} | "
                f"{row['actual_win_rate']:.1%} | {row['gap']:+.1%} |"
            )
        lines.append("")

    # Equity curve
    if result.equity_curve:
        lines.append("## Equity Curve\n")
        lines.append("| Date | Day P&L | Cumulative |")
        lines.append("|------|---------|------------|")
        daily = defaultdict(float)
        daily_cum = {}
        for point in result.equity_curve:
            daily[point["date"]] += point["pnl"]
        cum = 0.0
        for d in sorted(daily):
            cum += daily[d]
            daily_cum[d] = cum
            lines.append(f"| {d} | ${daily[d]:+.2f} | ${cum:+.2f} |")
        lines.append("")

    # Strategy simulation
    if strategies:
        lines.append("## Strategy Simulation\n")
        lines.append("| Strategy | Trades | Win % | P&L | ROI | Sharpe | Max DD | PF |")
        lines.append("|----------|--------|-------|-----|-----|--------|--------|-----|")
        for s in strategies:
            lines.append(
                f"| {s.label} | {s.total_trades} | {s.win_rate:.0%} | "
                f"${s.net_pnl:+.2f} | {s.roi:+.1%} | {s.sharpe_ratio:.2f} | "
                f"${s.max_drawdown:.2f} | {s.profit_factor:.2f} |"
            )
        lines.append("")

    return "\n".join(lines)


# ── CLI ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Edge-Radar Backtester")
    parser.add_argument("--sport", help="Filter by sport (e.g., mlb, nba)")
    parser.add_argument("--category", help="Filter by category (game, spread, total)")
    parser.add_argument("--confidence", help="Filter by confidence (low, medium, high)")
    parser.add_argument("--min-edge", type=float, help="Minimum edge threshold")
    parser.add_argument("--after", help="Only trades settled after date (YYYY-MM-DD)")
    parser.add_argument("--simulate", action="store_true", help="Run strategy comparison")
    parser.add_argument("--save", action="store_true", help="Save markdown report")
    parser.add_argument("--quiet", action="store_true", help="Skip terminal tables")
    args = parser.parse_args()

    # Load data
    all_trades = load_trades()
    if not all_trades:
        rprint("[red]No settled trades found.[/red]")
        sys.exit(1)

    rprint(f"[dim]Loaded {len(all_trades)} settled trades[/dim]")

    # Apply filters
    trades = filter_trades(
        all_trades,
        sport=args.sport,
        category=args.category,
        confidence=args.confidence,
        min_edge=args.min_edge,
        after=args.after,
    )

    if not trades:
        rprint("[red]No trades match the filters.[/red]")
        sys.exit(1)

    if len(trades) < len(all_trades):
        rprint(f"[dim]Filtered to {len(trades)} trades[/dim]")

    # Run analysis
    label = "All Trades"
    parts = []
    if args.sport:
        parts.append(args.sport.upper())
    if args.category:
        parts.append(args.category)
    if args.confidence:
        parts.append(f"conf={args.confidence}")
    if args.min_edge:
        parts.append(f"edge>={args.min_edge:.0%}")
    if parts:
        label = " + ".join(parts)

    result = BacktestResult(trades=trades, label=label).analyze()

    if not args.quiet:
        print_summary(result)
        print_breakdown(result)
        print_calibration(result)
        print_equity_curve(result)

    # Strategy simulation
    strategies = None
    if args.simulate:
        strategies = simulate_strategies(all_trades)
        if not args.quiet:
            print_simulation(strategies)

    # Save report
    if args.save:
        report_dir = Path(get_config().system.project_root or paths.PROJECT_ROOT) / "reports" / "backtest"
        report_dir.mkdir(parents=True, exist_ok=True)
        filename = f"backtest_{datetime.now().strftime('%Y-%m-%d_%H%M')}.md"
        report_path = report_dir / filename
        md = generate_markdown(result, strategies)
        report_path.write_text(md)
        rprint(f"\n[green]Report saved: {report_path}[/green]")


if __name__ == "__main__":
    main()
