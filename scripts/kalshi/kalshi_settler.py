"""
kalshi_settler.py
Settlement tracker for Kalshi positions.

Polls the Kalshi API for settled markets, matches them to our trade log,
calculates realized P&L, and updates records. Also generates performance
reports to validate whether our edge detection is working.

Usage:
    python scripts/kalshi_settler.py settle           # Update trade log with settlements
    python scripts/kalshi_settler.py report            # P&L and performance summary
    python scripts/kalshi_settler.py report --detail    # Per-trade breakdown
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401 -- configures sys.path
from trade_log import (
    load_trade_log, save_trade_log,
    load_settlement_log, save_settlement_log,
    get_today_pnl,
)

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from kalshi_client import KalshiClient

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
log = logging.getLogger("kalshi_settler")
console = Console()


# ── Settlement Logic ──────────────────────────────────────────────────────────

def calculate_pnl(trade: dict, settlement: dict) -> dict:
    """
    Calculate realized P&L for a settled trade.

    For binary contracts:
    - YES contract pays $1.00 if result is "yes", $0.00 if "no"
    - NO contract pays $1.00 if result is "no", $0.00 if "yes"

    P&L = revenue - cost - fees
    """
    side = trade.get("side", "")
    result = settlement.get("market_result", "")
    contracts = float(trade.get("fill_count") or trade.get("contracts", 0))
    cost = float(trade.get("cost_dollars", 0))
    fees = float(trade.get("taker_fees") or 0) + float(trade.get("maker_fees") or 0)

    # Revenue from settlement
    revenue_cents = settlement.get("revenue", 0)
    revenue_dollars = revenue_cents / 100 if isinstance(revenue_cents, int) else float(revenue_cents)

    # If we don't have revenue from the API, calculate it
    if revenue_dollars == 0 and contracts > 0:
        won = (side == "yes" and result == "yes") or (side == "no" and result == "no")
        revenue_dollars = contracts * 1.00 if won else 0.0

    net_pnl = revenue_dollars - cost - fees

    return {
        "won": revenue_dollars > cost,
        "revenue": round(revenue_dollars, 4),
        "cost": round(cost, 4),
        "fees": round(fees, 4),
        "net_pnl": round(net_pnl, 4),
        "roi": round(net_pnl / cost, 4) if cost > 0 else 0,
        "result": result,
    }


def settle_trades(client: KalshiClient) -> dict:
    """
    Fetch settlements from Kalshi and update the trade log.
    Returns summary of what changed.
    """
    trade_log = load_trade_log()
    settlement_log = load_settlement_log()

    # Find unsettled trades
    unsettled = [t for t in trade_log if t.get("closed_at") is None and t.get("status") != "error"]

    if not unsettled:
        rprint("[dim]No unsettled trades in log.[/dim]")
        return {"settled": 0, "still_open": 0}

    unsettled_tickers = {t["ticker"] for t in unsettled}
    rprint(f"Checking {len(unsettled)} unsettled trades across {len(unsettled_tickers)} markets...")

    # Fetch settlements from Kalshi
    all_settlements = []
    cursor = None
    for _ in range(10):
        resp = client.get_settlements(limit=200, cursor=cursor)
        settlements = resp.get("settlements", [])
        all_settlements.extend(settlements)
        cursor = resp.get("cursor", "")
        if not cursor:
            break

    rprint(f"  Fetched {len(all_settlements)} settlements from Kalshi")

    # Index settlements by ticker
    settlement_map: dict[str, dict] = {}
    for s in all_settlements:
        ticker = s.get("ticker", "")
        settlement_map[ticker] = s

    # Also check market status for tickers not in settlements
    # (market might be settled but we haven't received settlement yet)
    for ticker in unsettled_tickers:
        if ticker not in settlement_map:
            try:
                market = client.get_market(ticker).get("market", {})
                status = market.get("status", "")
                if status in ("settled", "closed"):
                    result = market.get("result", "")
                    if result:
                        settlement_map[ticker] = {
                            "ticker": ticker,
                            "market_result": result,
                            "revenue": 0,  # will be calculated
                            "settled_time": market.get("close_time", ""),
                        }
                        rprint(f"  [dim]Market {ticker} is {status}, result={result}[/dim]")
            except Exception as e:
                log.debug("Could not check market %s: %s", ticker, e)

    # Match and update
    settled_count = 0
    still_open = 0

    for trade in trade_log:
        if trade.get("closed_at") is not None:
            continue
        if trade.get("status") == "error":
            continue

        ticker = trade.get("ticker", "")
        settlement = settlement_map.get(ticker)

        if settlement is None:
            still_open += 1
            continue

        # Calculate P&L
        pnl = calculate_pnl(trade, settlement)

        # Update trade record
        trade["net_pnl"] = pnl["net_pnl"]
        trade["closed_at"] = settlement.get("settled_time", datetime.now(timezone.utc).isoformat())
        trade["settlement_result"] = pnl["result"]
        trade["settlement_revenue"] = pnl["revenue"]
        trade["settlement_won"] = pnl["won"]
        trade["settlement_roi"] = pnl["roi"]

        settled_count += 1

        won_str = "[green]WON[/green]" if pnl["won"] else "[red]LOST[/red]"
        rprint(
            f"  {won_str} {ticker} "
            f"({trade['side'].upper()}) "
            f"P&L: ${pnl['net_pnl']:+.2f} "
            f"(cost=${pnl['cost']:.2f}, rev=${pnl['revenue']:.2f}, fees=${pnl['fees']:.2f})"
        )

        # Add to settlement log
        settlement_log.append({
            "trade_id": trade.get("trade_id"),
            "ticker": ticker,
            "side": trade.get("side"),
            "result": pnl["result"],
            "won": pnl["won"],
            "contracts": trade.get("contracts"),
            "cost": pnl["cost"],
            "revenue": pnl["revenue"],
            "fees": pnl["fees"],
            "net_pnl": pnl["net_pnl"],
            "roi": pnl["roi"],
            "edge_estimated": trade.get("edge_estimated"),
            "fair_value": trade.get("fair_value"),
            "market_price_at_entry": trade.get("market_price_at_entry"),
            "confidence": trade.get("confidence"),
            "settled_at": trade["closed_at"],
        })

    # Save
    save_trade_log(trade_log)
    save_settlement_log(settlement_log)

    rprint(f"\n  Settled: [green]{settled_count}[/green]  Still open: [yellow]{still_open}[/yellow]")
    return {"settled": settled_count, "still_open": still_open}


# ── Performance Report ────────────────────────────────────────────────────────

def generate_report(detail: bool = False):
    """Generate P&L and performance report from trade log."""
    trade_log = load_trade_log()

    if not trade_log:
        rprint("[yellow]No trades in log.[/yellow]")
        return

    settled = [t for t in trade_log if t.get("closed_at") is not None]
    unsettled = [t for t in trade_log if t.get("closed_at") is None and t.get("status") != "error"]

    rprint(f"\n[bold]-- Kalshi Performance Report --[/bold]")
    rprint(f"  Total trades:    {len(trade_log)}")
    rprint(f"  Settled:         {len(settled)}")
    rprint(f"  Open/Pending:    {len(unsettled)}")

    if not settled:
        rprint("\n  [yellow]No settled trades yet -- run 'settle' after markets resolve.[/yellow]")

        # Show open positions summary
        if unsettled:
            rprint(f"\n[bold]Open Positions[/bold]")
            total_exposure = sum(t.get("cost_dollars", 0) for t in unsettled)
            rprint(f"  Total exposure: ${total_exposure:.2f}")
            for t in unsettled:
                rprint(
                    f"  {t['ticker'][:40]} | {t['side'].upper()} x{t.get('contracts',0)} "
                    f"@ ${t.get('price_cents',0)/100:.2f} | edge={t.get('edge_estimated',0):.1%}"
                )
        return

    # ── Aggregate stats
    wins = [t for t in settled if t.get("settlement_won")]
    losses = [t for t in settled if not t.get("settlement_won")]

    total_pnl = sum(t.get("net_pnl", 0) for t in settled)
    total_wagered = sum(t.get("cost_dollars", 0) for t in settled)
    total_fees = sum(
        float(t.get("taker_fees") or 0) + float(t.get("maker_fees") or 0)
        for t in settled
    )
    win_rate = len(wins) / len(settled) if settled else 0
    avg_win = sum(t.get("net_pnl", 0) for t in wins) / len(wins) if wins else 0
    avg_loss = sum(t.get("net_pnl", 0) for t in losses) / len(losses) if losses else 0
    roi = total_pnl / total_wagered if total_wagered > 0 else 0

    rprint(f"\n[bold]P&L Summary[/bold]")
    pnl_color = "green" if total_pnl >= 0 else "red"
    rprint(f"  Net P&L:         [{pnl_color}]${total_pnl:+.2f}[/{pnl_color}]")
    rprint(f"  Total wagered:   ${total_wagered:.2f}")
    rprint(f"  Total fees:      ${total_fees:.2f}")
    rprint(f"  ROI:             [{pnl_color}]{roi:+.1%}[/{pnl_color}]")

    rprint(f"\n[bold]Win/Loss[/bold]")
    rprint(f"  Record:          {len(wins)}W - {len(losses)}L ({win_rate:.0%})")
    rprint(f"  Avg win:         ${avg_win:+.2f}")
    rprint(f"  Avg loss:        ${avg_loss:+.2f}")

    if wins and losses:
        profit_factor = abs(sum(t["net_pnl"] for t in wins)) / abs(sum(t["net_pnl"] for t in losses))
        rprint(f"  Profit factor:   {profit_factor:.2f}")

    best = max(settled, key=lambda t: t.get("net_pnl", 0))
    worst = min(settled, key=lambda t: t.get("net_pnl", 0))
    rprint(f"  Best trade:      ${best['net_pnl']:+.2f} ({best['ticker'][:30]})")
    rprint(f"  Worst trade:     ${worst['net_pnl']:+.2f} ({worst['ticker'][:30]})")

    # ── Edge calibration
    rprint(f"\n[bold]Edge Calibration[/bold]")
    avg_edge_est = sum(t.get("edge_estimated", 0) for t in settled) / len(settled)
    edge_realized = roi  # actual ROI is our realized edge

    rprint(f"  Avg estimated edge:  {avg_edge_est:.1%}")
    rprint(f"  Realized edge (ROI): {edge_realized:+.1%}")
    if avg_edge_est > 0:
        realization = edge_realized / avg_edge_est
        rprint(f"  Edge realization:    {realization:.0%}")

    # By confidence level
    for conf in ["high", "medium", "low"]:
        conf_trades = [t for t in settled if t.get("confidence") == conf]
        if conf_trades:
            conf_pnl = sum(t.get("net_pnl", 0) for t in conf_trades)
            conf_wins = sum(1 for t in conf_trades if t.get("settlement_won"))
            rprint(
                f"  {conf:>8}: {len(conf_trades)} trades, "
                f"${conf_pnl:+.2f}, "
                f"{conf_wins}/{len(conf_trades)} wins"
            )

    # By category
    categories = {}
    for t in settled:
        cat = t.get("category", "other")
        if cat not in categories:
            categories[cat] = {"trades": 0, "pnl": 0, "wins": 0}
        categories[cat]["trades"] += 1
        categories[cat]["pnl"] += t.get("net_pnl", 0)
        if t.get("settlement_won"):
            categories[cat]["wins"] += 1

    if len(categories) > 1:
        rprint(f"\n[bold]By Category[/bold]")
        for cat, stats in sorted(categories.items(), key=lambda x: -x[1]["pnl"]):
            rprint(
                f"  {cat:>12}: {stats['trades']} trades, "
                f"${stats['pnl']:+.2f}, "
                f"{stats['wins']}/{stats['trades']} wins"
            )

    # ── Detail table
    if detail:
        rprint("")
        table = Table(title="Trade Detail", show_lines=True)
        table.add_column("Ticker", style="cyan", max_width=30)
        table.add_column("Side")
        table.add_column("Result")
        table.add_column("Cost", justify="right")
        table.add_column("Revenue", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("Edge Est", justify="right")
        table.add_column("ROI", justify="right")

        for t in sorted(settled, key=lambda x: x.get("closed_at", "")):
            pnl = t.get("net_pnl", 0)
            pnl_color = "green" if pnl >= 0 else "red"
            result = t.get("settlement_result", "?")
            won = "W" if t.get("settlement_won") else "L"

            table.add_row(
                t["ticker"][:30],
                t.get("side", "").upper(),
                f"{result.upper()} ({won})",
                f"${t.get('cost_dollars', 0):.2f}",
                f"${t.get('settlement_revenue', 0):.2f}",
                f"[{pnl_color}]${pnl:+.2f}[/{pnl_color}]",
                f"{t.get('edge_estimated', 0):.1%}",
                f"{t.get('settlement_roi', 0):+.0%}",
            )
        console.print(table)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kalshi settlement tracker & performance reporting")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("settle", help="Check for settled markets and update trade log P&L")

    report_p = sub.add_parser("report", help="Performance report")
    report_p.add_argument("--detail", action="store_true", help="Show per-trade breakdown")

    args = parser.parse_args()
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    if args.command == "settle":
        client = KalshiClient()
        settle_trades(client)

    elif args.command == "report":
        generate_report(detail=args.detail)


if __name__ == "__main__":
    main()
