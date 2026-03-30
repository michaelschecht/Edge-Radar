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
import re
import sys
import json
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Shared imports
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
from logging_setup import setup_logging

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
log = setup_logging("kalshi_settler")
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

        # Capture closing price for CLV tracking
        closing_price = None
        try:
            market_data = client.get_market(ticker).get("market", {})
            if trade.get("side") == "yes":
                closing_price = float(market_data.get("last_price", 0)) / 100
            else:
                last = float(market_data.get("last_price", 0)) / 100
                closing_price = 1.0 - last if last > 0 else None
        except Exception:
            log.debug("Could not fetch closing price for %s", ticker)

        entry_price = trade.get("market_price_at_entry", 0)
        clv = round(closing_price - entry_price, 4) if closing_price and entry_price else None

        # Update trade record
        trade["net_pnl"] = pnl["net_pnl"]
        trade["closed_at"] = settlement.get("settled_time", datetime.now(timezone.utc).isoformat())
        trade["settlement_result"] = pnl["result"]
        trade["settlement_revenue"] = pnl["revenue"]
        trade["settlement_won"] = pnl["won"]
        trade["settlement_roi"] = pnl["roi"]
        trade["closing_price"] = closing_price
        trade["clv"] = clv

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

def generate_report(detail: bool = False, save: bool = False):
    """Generate P&L and performance report from trade log.

    Args:
        detail: Show per-trade breakdown table.
        save: Write report to reports/Accounts/Kalshi/ with today's date.
    """
    trade_log = load_trade_log()

    if not trade_log:
        rprint("[yellow]No trades in log.[/yellow]")
        return

    settled = [t for t in trade_log if t.get("closed_at") is not None]
    unsettled = [t for t in trade_log if t.get("closed_at") is None and t.get("status") != "error"]

    # Markdown lines for file output (built alongside console output)
    md: list[str] = []

    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    rprint(f"\n-- Kalshi Performance Report --")
    rprint(f"  Generated: {generated_at}")
    rprint(f"  Total trades:    {len(trade_log)}")
    rprint(f"  Settled:         {len(settled)}")
    rprint(f"  Open/Pending:    {len(unsettled)}")

    md.append(f"# Kalshi Performance Report")
    md.append(f"")
    md.append(f"*Generated: {generated_at}*")
    md.append(f"")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Total trades | {len(trade_log)} |")
    md.append(f"| Settled | {len(settled)} |")
    md.append(f"| Open/Pending | {len(unsettled)} |")

    if not settled:
        rprint("\n  No settled trades yet -- run 'settle' after markets resolve.")
        md.append(f"")
        md.append(f"> No settled trades yet -- run `settle` after markets resolve.")

        if unsettled:
            total_exposure = sum(t.get("cost_dollars", 0) for t in unsettled)
            rprint(f"\nOpen Positions")
            rprint(f"  Total exposure: ${total_exposure:.2f}")
            md.append(f"")
            md.append(f"## Open Positions")
            md.append(f"")
            md.append(f"**Total exposure:** ${total_exposure:.2f}")
            md.append(f"")
            md.append(f"| Ticker | Side | Contracts | Price | Edge |")
            md.append(f"|--------|------|-----------|-------|------|")
            for t in unsettled:
                rprint(
                    f"  {t['ticker'][:40]} | {t['side'].upper()} x{t.get('contracts',0)} "
                    f"@ ${t.get('price_cents',0)/100:.2f} | edge={t.get('edge_estimated',0):.1%}"
                )
                md.append(
                    f"| {t['ticker'][:40]} | {t['side'].upper()} | "
                    f"{t.get('contracts',0)} | ${t.get('price_cents',0)/100:.2f} | "
                    f"{t.get('edge_estimated',0):.1%} |"
                )

        if save:
            _save_report_file(md)
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

    pnl_color = "green" if total_pnl >= 0 else "red"
    rprint(f"\n[bold]P&L Summary[/bold]")
    rprint(f"  Net P&L:         [{pnl_color}]${total_pnl:+.2f}[/{pnl_color}]")
    rprint(f"  Total wagered:   ${total_wagered:.2f}")
    rprint(f"  Total fees:      ${total_fees:.2f}")
    rprint(f"  ROI:             [{pnl_color}]{roi:+.1%}[/{pnl_color}]")

    md.append(f"")
    md.append(f"## P&L Summary")
    md.append(f"")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Net P&L | **${total_pnl:+.2f}** |")
    md.append(f"| Total wagered | ${total_wagered:.2f} |")
    md.append(f"| Total fees | ${total_fees:.2f} |")
    md.append(f"| ROI | **{roi:+.1%}** |")

    rprint(f"\n[bold]Win/Loss[/bold]")
    rprint(f"  Record:          {len(wins)}W - {len(losses)}L ({win_rate:.0%})")
    rprint(f"  Avg win:         ${avg_win:+.2f}")
    rprint(f"  Avg loss:        ${avg_loss:+.2f}")

    md.append(f"")
    md.append(f"## Win/Loss")
    md.append(f"")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Record | {len(wins)}W - {len(losses)}L ({win_rate:.0%}) |")
    md.append(f"| Avg win | ${avg_win:+.2f} |")
    md.append(f"| Avg loss | ${avg_loss:+.2f} |")

    if wins and losses:
        profit_factor = abs(sum(t["net_pnl"] for t in wins)) / abs(sum(t["net_pnl"] for t in losses))
        rprint(f"  Profit factor:   {profit_factor:.2f}")
        md.append(f"| Profit factor | {profit_factor:.2f} |")

    best = max(settled, key=lambda t: t.get("net_pnl", 0))
    worst = min(settled, key=lambda t: t.get("net_pnl", 0))
    rprint(f"  Best trade:      ${best['net_pnl']:+.2f} ({best['ticker'][:30]})")
    rprint(f"  Worst trade:     ${worst['net_pnl']:+.2f} ({worst['ticker'][:30]})")
    md.append(f"| Best trade | ${best['net_pnl']:+.2f} (`{best['ticker'][:30]}`) |")
    md.append(f"| Worst trade | ${worst['net_pnl']:+.2f} (`{worst['ticker'][:30]}`) |")

    # ── Edge calibration
    avg_edge_est = sum(t.get("edge_estimated", 0) for t in settled) / len(settled)
    edge_realized = roi

    rprint(f"\n[bold]Edge Calibration[/bold]")
    rprint(f"  Avg estimated edge:  {avg_edge_est:.1%}")
    rprint(f"  Realized edge (ROI): {edge_realized:+.1%}")

    md.append(f"")
    md.append(f"## Edge Calibration")
    md.append(f"")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Avg estimated edge | {avg_edge_est:.1%} |")
    md.append(f"| Realized edge (ROI) | {edge_realized:+.1%} |")

    if avg_edge_est > 0:
        realization = edge_realized / avg_edge_est
        rprint(f"  Edge realization:    {realization:.0%}")
        md.append(f"| Edge realization | {realization:.0%} |")

    # CLV (Closing Line Value)
    clv_trades = [t for t in settled if t.get("clv") is not None]
    if clv_trades:
        avg_clv = sum(t["clv"] for t in clv_trades) / len(clv_trades)
        positive_clv = sum(1 for t in clv_trades if t["clv"] > 0)
        clv_color = "green" if avg_clv > 0 else "red"
        rprint(f"\n[bold]Closing Line Value (CLV)[/bold]")
        rprint(f"  Avg CLV:             [{clv_color}]{avg_clv:+.1%}[/{clv_color}]")
        rprint(f"  Beat the close:      {positive_clv}/{len(clv_trades)} ({positive_clv/len(clv_trades):.0%})")

        md.append(f"")
        md.append(f"## Closing Line Value (CLV)")
        md.append(f"")
        md.append(f"| Metric | Value |")
        md.append(f"|--------|-------|")
        md.append(f"| Avg CLV | {avg_clv:+.1%} |")
        md.append(f"| Beat the close | {positive_clv}/{len(clv_trades)} ({positive_clv/len(clv_trades):.0%}) |")

    # By confidence level
    conf_rows = []
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
            conf_rows.append(
                f"| {conf.capitalize()} | {len(conf_trades)} | ${conf_pnl:+.2f} | "
                f"{conf_wins}/{len(conf_trades)} |"
            )

    if conf_rows:
        md.append(f"")
        md.append(f"### By Confidence")
        md.append(f"")
        md.append(f"| Confidence | Trades | P&L | Wins |")
        md.append(f"|------------|--------|-----|------|")
        md.extend(conf_rows)

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
        md.append(f"")
        md.append(f"### By Category")
        md.append(f"")
        md.append(f"| Category | Trades | P&L | Wins |")
        md.append(f"|----------|--------|-----|------|")
        for cat, stats in sorted(categories.items(), key=lambda x: -x[1]["pnl"]):
            rprint(
                f"  {cat:>12}: {stats['trades']} trades, "
                f"${stats['pnl']:+.2f}, "
                f"{stats['wins']}/{stats['trades']} wins"
            )
            md.append(
                f"| {cat} | {stats['trades']} | ${stats['pnl']:+.2f} | "
                f"{stats['wins']}/{stats['trades']} |"
            )

    # ── Detail table
    if detail:
        from ticker_display import parse_game_datetime, format_bet_label

        rprint("")
        table = Table(title="Trade Detail", show_lines=True)
        table.add_column("Bet", style="cyan", max_width=30)
        table.add_column("Date", style="dim")
        table.add_column("Side")
        table.add_column("Result")
        table.add_column("Cost", justify="right")
        table.add_column("P&L", justify="right")
        table.add_column("ROI", justify="right")

        md.append(f"")
        md.append(f"## Trade Detail")
        md.append(f"")
        md.append(f"| Bet | Date | Side | Result | Cost | P&L | ROI |")
        md.append(f"|-----|------|------|--------|------|-----|-----|")

        for t in sorted(settled, key=lambda x: x.get("closed_at", "")):
            pnl = t.get("net_pnl", 0)
            pnl_color = "green" if pnl >= 0 else "red"
            result = t.get("settlement_result", "?")
            won = "W" if t.get("settlement_won") else "L"
            ticker = t["ticker"]
            bet_label = format_bet_label(ticker, t.get("title", ticker))
            when = parse_game_datetime(ticker)

            table.add_row(
                bet_label[:30],
                when,
                t.get("side", "").upper(),
                f"{result.upper()} ({won})",
                f"${t.get('cost_dollars', 0):.2f}",
                f"[{pnl_color}]${pnl:+.2f}[/{pnl_color}]",
                f"{t.get('settlement_roi', 0):+.0%}",
            )
            md.append(
                f"| {bet_label[:30]} | {when} | {t.get('side','').upper()} | "
                f"{result.upper()} ({won}) | "
                f"${t.get('cost_dollars',0):.2f} | "
                f"${pnl:+.2f} | "
                f"{t.get('settlement_roi',0):+.0%} |"
            )
        console.print(table)

    # ── Save to file
    if save:
        _save_report_file(md)


def _save_report_file(lines: list[str]):
    """Write report lines to reports/Accounts/Kalshi/ with today's date."""
    report_dir = Path(__file__).resolve().parent.parent.parent / "reports" / "Accounts" / "Kalshi"
    report_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    report_path = report_dir / f"kalshi_report_{today}.md"

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    rprint(f"\n[green]Report saved to:[/green] {report_path}")


# ── Reconciliation ───────────────────────────────────────────────────────────

def reconcile_positions(client: KalshiClient):
    """
    Compare local trade log against Kalshi API positions.
    Flags discrepancies: trades in API but not local, or vice versa.
    """
    rprint("\n[bold]Reconciling local trade log vs Kalshi API...[/bold]")

    trade_log = load_trade_log()
    unsettled = [t for t in trade_log if not t.get("closed_at") and t.get("status") == "executed"]

    # Local: unique tickers with open positions
    local_tickers = {}
    for t in unsettled:
        ticker = t.get("ticker", "")
        if ticker not in local_tickers:
            local_tickers[ticker] = {"contracts": 0, "trades": []}
        local_tickers[ticker]["contracts"] += t.get("contracts", 0)
        local_tickers[ticker]["trades"].append(t.get("trade_id", "?")[:8])

    # API: actual positions on Kalshi
    api_positions = client.get_positions(limit=200, count_filter="position")
    api_tickers = {}
    for p in api_positions.get("market_positions", []):
        ticker = p.get("ticker", "")
        position = int(float(p.get("position_fp", "0")))
        if position != 0:
            api_tickers[ticker] = {
                "position": position,
                "exposure": p.get("market_exposure_dollars", "0"),
            }

    # Compare
    only_local = set(local_tickers.keys()) - set(api_tickers.keys())
    only_api = set(api_tickers.keys()) - set(local_tickers.keys())
    in_both = set(local_tickers.keys()) & set(api_tickers.keys())

    rprint(f"  Local unsettled: {len(local_tickers)} tickers")
    rprint(f"  Kalshi API:      {len(api_tickers)} positions")

    issues = False

    if only_local:
        issues = True
        rprint(f"\n  [yellow]In local log but NOT on Kalshi ({len(only_local)}):[/yellow]")
        rprint("  [dim](May have been settled, cancelled, or sold on Kalshi directly)[/dim]")
        for ticker in sorted(only_local):
            info = local_tickers[ticker]
            rprint(f"    {ticker}  contracts={info['contracts']}")

    if only_api:
        issues = True
        rprint(f"\n  [yellow]On Kalshi but NOT in local log ({len(only_api)}):[/yellow]")
        rprint("  [dim](May have been placed manually on Kalshi website)[/dim]")
        for ticker in sorted(only_api):
            info = api_tickers[ticker]
            rprint(f"    {ticker}  position={info['position']}  exposure=${info['exposure']}")

    if in_both:
        mismatches = []
        for ticker in in_both:
            local_qty = local_tickers[ticker]["contracts"]
            api_qty = api_tickers[ticker]["position"]
            if local_qty != api_qty:
                mismatches.append((ticker, local_qty, api_qty))

        if mismatches:
            issues = True
            rprint(f"\n  [yellow]Quantity mismatches ({len(mismatches)}):[/yellow]")
            for ticker, local_qty, api_qty in mismatches:
                rprint(f"    {ticker}  local={local_qty}  kalshi={api_qty}")

    if not issues:
        rprint("\n  [green]All positions match.[/green]")
    else:
        rprint(f"\n  [yellow]Run 'settle' to resolve stale local entries.[/yellow]")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kalshi settlement tracker & performance reporting")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("settle", help="Check for settled markets and update trade log P&L")

    report_p = sub.add_parser("report", help="Performance report")
    report_p.add_argument("--detail", action="store_true", help="Show per-trade breakdown")
    report_p.add_argument("--save", action="store_true", help="Save report to reports/Accounts/Kalshi/")

    sub.add_parser("reconcile", help="Compare local trade log vs Kalshi API positions")

    args = parser.parse_args()

    if args.command == "settle":
        client = KalshiClient()
        settle_trades(client)

    elif args.command == "report":
        generate_report(detail=args.detail, save=args.save)

    elif args.command == "reconcile":
        client = KalshiClient()
        reconcile_positions(client)


if __name__ == "__main__":
    main()
