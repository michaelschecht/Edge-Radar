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
    get_today_pnl, get_filled_contracts, get_filled_cost,
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
    contracts = get_filled_contracts(trade)
    cost = get_filled_cost(trade)
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

    # Find unsettled trades (skip zero-fill resting orders — they have no exposure)
    unsettled = [
        t for t in trade_log
        if t.get("closed_at") is None
        and t.get("status") != "error"
        and t.get("fill_status") != "resting"
    ]

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

        # Add to settlement log (use filled values for accurate accounting)
        settlement_log.append({
            "trade_id": trade.get("trade_id"),
            "ticker": ticker,
            "side": trade.get("side"),
            "result": pnl["result"],
            "won": pnl["won"],
            "contracts": int(get_filled_contracts(trade)),
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

def _fetch_api_settlements(client: KalshiClient, days: int | None = None) -> list[dict]:
    """Fetch all settlements from the Kalshi API, optionally filtered by date."""
    all_settlements: list[dict] = []
    cursor = None
    for _ in range(20):  # safety limit
        resp = client.get_settlements(limit=200, cursor=cursor)
        settlements = resp.get("settlements", [])
        all_settlements.extend(settlements)
        cursor = resp.get("cursor", "")
        if not cursor:
            break

    if days is not None:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        all_settlements = [s for s in all_settlements if (s.get("settled_time") or "") >= cutoff]

    return all_settlements


def _settlement_to_record(s: dict) -> dict:
    """Convert a Kalshi API settlement into a normalized record for reporting."""
    yes_count = float(s.get("yes_count_fp", 0))
    no_count = float(s.get("no_count_fp", 0))
    yes_cost = float(s.get("yes_total_cost_dollars", 0))
    no_cost = float(s.get("no_total_cost_dollars", 0))
    revenue_cents = s.get("revenue", 0)
    revenue = revenue_cents / 100 if isinstance(revenue_cents, int) and revenue_cents > 1 else float(revenue_cents)
    fees = float(s.get("fee_cost", 0))
    result = s.get("market_result", "")

    # Determine which side we were on
    if yes_count > 0 and no_count > 0:
        side = "yes" if yes_cost > no_cost else "no"
    elif yes_count > 0:
        side = "yes"
    else:
        side = "no"

    contracts = yes_count if side == "yes" else no_count
    cost = yes_cost if side == "yes" else no_cost
    won = (side == "yes" and result == "yes") or (side == "no" and result == "no")
    net_pnl = revenue - cost - fees

    return {
        "ticker": s.get("ticker", ""),
        "event_ticker": s.get("event_ticker", ""),
        "side": side,
        "contracts": int(contracts),
        "cost": round(cost, 4),
        "revenue": round(revenue, 4),
        "fees": round(fees, 4),
        "net_pnl": round(net_pnl, 4),
        "roi": round(net_pnl / cost, 4) if cost > 0 else 0,
        "won": won,
        "result": result,
        "settled_time": s.get("settled_time", ""),
    }


def generate_report(detail: bool = False, save: bool = False, days: int | None = None):
    """Generate P&L and performance report from Kalshi API + local trade log.

    Pulls settlement data directly from the Kalshi API so the report is
    accurate even for trades placed outside Edge-Radar (e.g. on the website).
    Local trade log data enriches the report with edge estimates and confidence.

    Args:
        detail: Show per-trade breakdown table.
        save: Write report to reports/Accounts/Kalshi/ with today's date.
        days: Only include trades settled in the last N days. None = all time.
    """
    from ticker_display import (
        format_bet_label, bet_type_from_ticker,
        parse_game_datetime, sport_from_ticker,
    )

    # ── Fetch data from Kalshi API ───────────────────────────────────────────
    client = KalshiClient()

    rprint("[dim]Fetching account data from Kalshi API...[/dim]")
    api_settlements = _fetch_api_settlements(client, days=days)
    api_positions = client.get_positions(limit=200, count_filter="position").get("market_positions", [])
    balance = client.get_balance_dollars()

    # Normalize settlements
    settled_records = [_settlement_to_record(s) for s in api_settlements]
    # Filter out zero-exposure settlements (no position)
    settled_records = [r for r in settled_records if r["cost"] > 0 or r["revenue"] > 0]

    # Enrich with local trade log data (edge estimates, confidence, etc.)
    trade_log = load_trade_log()
    local_by_ticker = {}
    for t in trade_log:
        local_by_ticker[t.get("ticker", "")] = t

    for rec in settled_records:
        local = local_by_ticker.get(rec["ticker"])
        if local:
            rec["edge_estimated"] = local.get("edge_estimated", 0)
            rec["confidence"] = local.get("confidence", "")
            rec["category"] = local.get("category", "")
            rec["title"] = local.get("title", "")
            rec["composite_score"] = local.get("composite_score", 0)

    # ── Markdown + console output ────────────────────────────────────────────
    md: list[str] = []
    generated_at = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    period = f"Last {days} days" if days else "All time"

    rprint(f"\n-- Kalshi Account Report ({period}) --")
    rprint(f"  Generated: {generated_at}")

    md.append(f"# Kalshi Account Report ({period})")
    md.append(f"")
    md.append(f"*Generated: {generated_at}*")

    # ── Account Balance ──────────────────────────────────────────────────────
    bal = balance.get("balance", 0)
    portfolio = balance.get("portfolio_value", 0)
    total_value = bal + portfolio

    rprint(f"\n[bold]Account Balance[/bold]")
    rprint(f"  Available:       ${bal:.2f}")
    rprint(f"  Portfolio value: ${portfolio:.2f}")
    rprint(f"  Total value:     ${total_value:.2f}")

    md.append(f"")
    md.append(f"## Account Balance")
    md.append(f"")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Available | ${bal:.2f} |")
    md.append(f"| Portfolio value | ${portfolio:.2f} |")
    md.append(f"| Total value | **${total_value:.2f}** |")

    # ── Open Positions (from API) ────────────────────────────────────────────
    live_positions = [p for p in api_positions if float(p.get("position_fp", 0)) != 0]

    if live_positions:
        rprint(f"\n[bold]Open Positions ({len(live_positions)})[/bold]")
        md.append(f"")
        md.append(f"## Open Positions ({len(live_positions)})")
        md.append(f"")
        md.append(f"| Bet | Side | Contracts | Exposure |")
        md.append(f"|-----|------|-----------|----------|")

        for p in live_positions:
            ticker = p.get("ticker", "")
            pos = float(p.get("position_fp", 0))
            side = "YES" if pos > 0 else "NO"
            contracts = int(abs(pos))
            exposure = float(p.get("market_exposure_dollars", 0))
            local = local_by_ticker.get(ticker)
            bet_label = format_bet_label(ticker, local.get("title", ticker) if local else ticker)

            rprint(f"  {bet_label[:40]} | {side} x{contracts} | ${exposure:.2f}")
            md.append(f"| {bet_label[:40]} | {side} | {contracts} | ${exposure:.2f} |")

    # ── Settlement Summary ───────────────────────────────────────────────────
    wins = [r for r in settled_records if r["won"]]
    losses = [r for r in settled_records if not r["won"]]

    total_settled = len(settled_records)
    total_pnl = sum(r["net_pnl"] for r in settled_records)
    total_wagered = sum(r["cost"] for r in settled_records)
    total_revenue = sum(r["revenue"] for r in settled_records)
    total_fees = sum(r["fees"] for r in settled_records)
    win_rate = len(wins) / total_settled if total_settled else 0
    avg_win = sum(r["net_pnl"] for r in wins) / len(wins) if wins else 0
    avg_loss = sum(r["net_pnl"] for r in losses) / len(losses) if losses else 0
    roi = total_pnl / total_wagered if total_wagered > 0 else 0

    pnl_color = "green" if total_pnl >= 0 else "red"

    rprint(f"\n[bold]Settlement Summary ({total_settled} bets)[/bold]")
    rprint(f"  Record:          {len(wins)}W - {len(losses)}L ({win_rate:.0%})")
    rprint(f"  Net P&L:         [{pnl_color}]${total_pnl:+.2f}[/{pnl_color}]")
    rprint(f"  Total wagered:   ${total_wagered:.2f}")
    rprint(f"  Total revenue:   ${total_revenue:.2f}")
    rprint(f"  Total fees:      ${total_fees:.2f}")
    rprint(f"  ROI:             [{pnl_color}]{roi:+.1%}[/{pnl_color}]")
    rprint(f"  Avg win:         ${avg_win:+.2f}")
    rprint(f"  Avg loss:        ${avg_loss:+.2f}")

    md.append(f"")
    md.append(f"## Settlement Summary ({total_settled} bets)")
    md.append(f"")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Record | **{len(wins)}W - {len(losses)}L ({win_rate:.0%})** |")
    md.append(f"| Net P&L | **${total_pnl:+.2f}** |")
    md.append(f"| Total wagered | ${total_wagered:.2f} |")
    md.append(f"| Total revenue | ${total_revenue:.2f} |")
    md.append(f"| Total fees | ${total_fees:.2f} |")
    md.append(f"| ROI | **{roi:+.1%}** |")
    md.append(f"| Avg win | ${avg_win:+.2f} |")
    md.append(f"| Avg loss | ${avg_loss:+.2f} |")

    if wins and losses:
        loss_total = abs(sum(r["net_pnl"] for r in losses))
        if loss_total > 0:
            profit_factor = abs(sum(r["net_pnl"] for r in wins)) / loss_total
            rprint(f"  Profit factor:   {profit_factor:.2f}")
            md.append(f"| Profit factor | {profit_factor:.2f} |")

    if settled_records:
        best = max(settled_records, key=lambda r: r["net_pnl"])
        worst = min(settled_records, key=lambda r: r["net_pnl"])
        best_label = format_bet_label(best["ticker"], best.get("title", best["ticker"]))
        worst_label = format_bet_label(worst["ticker"], worst.get("title", worst["ticker"]))
        rprint(f"  Best trade:      ${best['net_pnl']:+.2f} ({best_label[:30]})")
        rprint(f"  Worst trade:     ${worst['net_pnl']:+.2f} ({worst_label[:30]})")
        md.append(f"| Best trade | ${best['net_pnl']:+.2f} — {best_label[:30]} |")
        md.append(f"| Worst trade | ${worst['net_pnl']:+.2f} — {worst_label[:30]} |")

    # ── Edge Calibration (only for trades with local data) ───────────────────
    edge_trades = [r for r in settled_records if r.get("edge_estimated")]
    if edge_trades:
        avg_edge_est = sum(r["edge_estimated"] for r in edge_trades) / len(edge_trades)
        edge_wagered = sum(r["cost"] for r in edge_trades)
        edge_pnl = sum(r["net_pnl"] for r in edge_trades)
        edge_realized = edge_pnl / edge_wagered if edge_wagered > 0 else 0

        rprint(f"\n[bold]Edge Calibration ({len(edge_trades)} Edge-Radar trades)[/bold]")
        rprint(f"  Avg estimated edge:  {avg_edge_est:.1%}")
        rprint(f"  Realized edge (ROI): {edge_realized:+.1%}")

        md.append(f"")
        md.append(f"## Edge Calibration ({len(edge_trades)} Edge-Radar trades)")
        md.append(f"")
        md.append(f"| Metric | Value |")
        md.append(f"|--------|-------|")
        md.append(f"| Avg estimated edge | {avg_edge_est:.1%} |")
        md.append(f"| Realized edge (ROI) | {edge_realized:+.1%} |")

        if avg_edge_est > 0:
            realization = edge_realized / avg_edge_est
            rprint(f"  Edge realization:    {realization:.0%}")
            md.append(f"| Edge realization | {realization:.0%} |")

    # ── Dimensional breakdowns ───────────────────────────────────────────────
    def _breakdown(label: str, groups: dict, md: list):
        """Print and append a dimensional breakdown table."""
        if not groups:
            return
        rprint(f"\n[bold]{label}[/bold]")
        md.append(f"")
        md.append(f"### {label}")
        md.append(f"")
        md.append(f"| {label} | Bets | Win Rate | P&L | ROI |")
        md.append(f"|{'-' * max(len(label), 4)}--|------|----------|-----|-----|")
        for name, records in sorted(groups.items(), key=lambda x: -sum(r["net_pnl"] for r in x[1])):
            n = len(records)
            w = sum(1 for r in records if r["won"])
            pnl = sum(r["net_pnl"] for r in records)
            wagered = sum(r["cost"] for r in records)
            roi_val = pnl / wagered if wagered > 0 else 0
            wr = w / n if n else 0
            pnl_color = "green" if pnl >= 0 else "red"
            rprint(
                f"  {name:>12}: {n} bets, {w}/{n} ({wr:.0%}), "
                f"[{pnl_color}]${pnl:+.2f}[/{pnl_color}], ROI {roi_val:+.0%}"
            )
            md.append(f"| {name} | {n} | {w}/{n} ({wr:.0%}) | ${pnl:+.2f} | {roi_val:+.0%} |")

    if settled_records:
        # By sport (derived from ticker)
        sport_groups: dict[str, list] = {}
        for r in settled_records:
            sport = sport_from_ticker(r["ticker"]) or "Other"
            sport_groups.setdefault(sport, []).append(r)
        _breakdown("By Sport", sport_groups, md)

        # By bet type (derived from ticker)
        type_groups: dict[str, list] = {}
        for r in settled_records:
            btype = bet_type_from_ticker(r["ticker"])
            type_groups.setdefault(btype, []).append(r)
        _breakdown("By Type", type_groups, md)

        # By result
        result_groups: dict[str, list] = {}
        for r in settled_records:
            result_groups.setdefault(r["side"].upper(), []).append(r)
        _breakdown("By Side", result_groups, md)

    # ── Detail table ─────────────────────────────────────────────────────────
    if detail and settled_records:
        rprint("")
        table = Table(title="Settlement Detail", show_lines=True)
        table.add_column("#", style="dim", justify="right")
        table.add_column("Bet", style="cyan", max_width=30)
        table.add_column("Type", style="magenta")
        table.add_column("Date", style="dim")
        table.add_column("Side")
        table.add_column("Result")
        table.add_column("Qty", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Revenue", justify="right")
        table.add_column("P&L", justify="right")

        md.append(f"")
        md.append(f"## Settlement Detail")
        md.append(f"")
        md.append(f"| # | Bet | Type | Date | Side | Result | Qty | Cost | Revenue | P&L |")
        md.append(f"|---|-----|------|------|------|--------|-----|------|---------|-----|")

        for i, r in enumerate(sorted(settled_records, key=lambda x: x.get("settled_time", "")), 1):
            pnl_color = "green" if r["net_pnl"] >= 0 else "red"
            won_str = "W" if r["won"] else "L"
            ticker = r["ticker"]
            bet_label = format_bet_label(ticker, r.get("title", ticker))
            btype = bet_type_from_ticker(ticker)
            when = parse_game_datetime(ticker)

            table.add_row(
                str(i),
                bet_label[:30],
                btype,
                when,
                r["side"].upper(),
                f"{r['result'].upper()} ({won_str})",
                str(r["contracts"]),
                f"${r['cost']:.2f}",
                f"${r['revenue']:.2f}",
                f"[{pnl_color}]${r['net_pnl']:+.2f}[/{pnl_color}]",
            )
            md.append(
                f"| {i} | {bet_label[:30]} | {btype} | {when} | "
                f"{r['side'].upper()} | {r['result'].upper()} ({won_str}) | "
                f"{r['contracts']} | ${r['cost']:.2f} | ${r['revenue']:.2f} | "
                f"${r['net_pnl']:+.2f} |"
            )
        console.print(table)

    if not settled_records:
        rprint("\n  [dim]No settlements in this period.[/dim]")
        md.append(f"")
        md.append(f"> No settlements found for this period.")

    # ── Save to file
    if save:
        _save_report_file(md, days=days)


def _save_report_file(lines: list[str], days: int | None = None):
    """Write report lines to reports/Accounts/Kalshi/ with today's date.

    When ``days`` is 7 or 30, saves into a weekly/ or monthly/ subdirectory
    so scheduled reports don't overwrite the default all-time report.
    """
    base = Path(__file__).resolve().parent.parent.parent / "reports" / "Accounts" / "Kalshi"
    if days is not None and days <= 7:
        report_dir = base / "weekly"
    elif days is not None and days <= 30:
        report_dir = base / "monthly"
    else:
        report_dir = base
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
        local_tickers[ticker]["contracts"] += int(get_filled_contracts(t))
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
    report_p.add_argument("--days", type=int, default=None, help="Only include trades settled in the last N days (default: all)")

    sub.add_parser("reconcile", help="Compare local trade log vs Kalshi API positions")

    args = parser.parse_args()

    if args.command == "settle":
        client = KalshiClient()
        settle_trades(client)

    elif args.command == "report":
        generate_report(detail=args.detail, save=args.save, days=args.days)

    elif args.command == "reconcile":
        client = KalshiClient()
        reconcile_positions(client)


if __name__ == "__main__":
    main()
