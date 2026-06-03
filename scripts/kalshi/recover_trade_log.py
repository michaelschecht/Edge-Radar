"""
recover_trade_log.py
Rebuild data/history/kalshi_trades.json from LIVE Kalshi positions.

One-shot recovery for the 2026-06-03 incident where the test suite's
``log_trade()`` side effect (``save_trade_log``) overwrote the live trade log
with a single test record. The fix (tests/conftest.py autouse guard) prevents
recurrence; this restores the working set of OPEN positions so the risk gates
and settler see them again.

What it reconstructs (from each live position):
    ticker, side (sign of position_fp), filled contracts/cost, fees, avg entry
    price, approximate timestamp (last_updated_ts).

What is NOT recoverable (lived only in the clobbered log) and is set to
null/"unknown": edge_estimated, fair_value, confidence, composite_score,
bankroll_pct, unit_size. These are informational — settlement P&L and the risk
gates do not need them.

Settled trades are intentionally NOT re-added: they already live in
kalshi_settlements.json (the permanent record). The trade log is the working
set of open trades only.

Usage:
    python scripts/kalshi/recover_trade_log.py            # preview only
    python scripts/kalshi/recover_trade_log.py --write    # back up + rewrite
"""

import argparse
import shutil
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from rich import print as rprint
from rich.console import Console
from rich.table import Table

import paths  # noqa: F401 -- path constants
from paths import TRADE_LOG_PATH
from kalshi_client import KalshiClient
from trade_log import load_trade_log, save_trade_log
from edge_detector import categorize_market

load_dotenv()
console = Console()

RECON_SOURCE = "reconstructed_from_kalshi_position"
RECON_NOTE = (
    "Rebuilt 2026-06-03 from live Kalshi position after the trade log was "
    "overwritten by a test (log_trade side effect). Model fields "
    "(edge/fair_value/confidence/composite) are unrecoverable."
)


def _is_test_or_empty(trade: dict) -> bool:
    """Records to drop from the clobbered log: the seeded test order(s)."""
    return (
        trade.get("edge_source") == "test"
        or str(trade.get("order_id", "")).startswith("ord-test")
    )


def build_record(client: KalshiClient, pos: dict) -> dict:
    ticker = pos["ticker"]
    pos_fp = float(pos.get("position_fp", "0") or 0)
    side = "yes" if pos_fp > 0 else "no"
    contracts = int(abs(pos_fp))
    cost = float(pos.get("total_traded_dollars", "0") or 0)
    fees = float(pos.get("fees_paid_dollars", "0") or 0)
    avg_price = round(cost / contracts, 4) if contracts else 0.0
    ts = pos.get("last_updated_ts") or datetime.now(timezone.utc).isoformat()

    title = ticker
    try:
        market = client.get_market(ticker).get("market", {})
        title = market.get("title", "") or ticker
    except Exception:
        pass

    return {
        "trade_id": str(uuid.uuid4()),
        "order_id": "",
        "timestamp": ts,
        "ticker": ticker,
        "title": title,
        "category": categorize_market(ticker),
        "side": side,
        "action": "buy",
        "requested_contracts": contracts,
        "requested_cost": round(cost, 4),
        "filled_contracts": contracts,
        "filled_cost": round(cost, 4),
        "contracts": contracts,
        "cost_dollars": round(cost, 4),
        "fill_count": contracts,
        "remaining_count": 0,
        "price_cents": int(round(avg_price * 100)),
        "taker_fees": str(round(fees, 6)),
        "maker_fees": "0",
        "status": "executed",      # settler reconcile path keys on this
        "fill_status": "filled",   # != "resting" so it counts as exposure
        "edge_estimated": None,
        "fair_value": None,
        "market_price_at_entry": avg_price,
        "confidence": "unknown",
        "composite_score": None,
        "edge_source": RECON_SOURCE,
        "unit_size": None,
        "bankroll_pct": None,
        "risk_approval": "RECONSTRUCTED",
        "net_pnl": 0,
        "closed_at": None,
        "dry_run": False,
        "reconstructed": True,
        "reconstruction_note": RECON_NOTE,
    }


def main():
    ap = argparse.ArgumentParser(description="Rebuild trade log from live Kalshi positions")
    ap.add_argument("--write", action="store_true",
                    help="Back up the current log and write the rebuilt one")
    args = ap.parse_args()

    client = KalshiClient()
    resp = client.get_positions(limit=200, count_filter="position")
    positions = [
        p for p in resp.get("market_positions", [])
        if float(p.get("position_fp", "0") or 0) != 0
    ]

    existing = load_trade_log()
    kept = [t for t in existing if not _is_test_or_empty(t)]
    open_tickers = {t.get("ticker") for t in kept if t.get("closed_at") is None}
    dropped = len(existing) - len(kept)

    new_records = [
        build_record(client, p)
        for p in positions
        if p["ticker"] not in open_tickers
    ]
    rebuilt = kept + new_records

    table = Table(title="Trade-log reconstruction preview", show_lines=False)
    _numeric = ("Qty", "Cost", "Fees", "Entry")
    for col in ("Ticker", "Side", *_numeric):
        table.add_column(col, justify="right" if col in _numeric else "left")
    for r in new_records:
        table.add_row(r["ticker"], r["side"], str(r["contracts"]),
                      f"${r['filled_cost']:.2f}", f"${float(r['taker_fees']):.2f}",
                      f"${r['market_price_at_entry']:.2f}")
    console.print(table)

    rprint(f"\nLive Kalshi open positions: [bold]{len(positions)}[/bold]")
    rprint(f"Dropped test/empty records: [bold]{dropped}[/bold]")
    rprint(f"Already-present open tickers kept: [bold]{len(open_tickers)}[/bold]")
    rprint(f"Reconstructed records: [bold]{len(new_records)}[/bold]")
    rprint(f"Final trade-log size: [bold]{len(rebuilt)}[/bold]")

    total_cost = sum(r["filled_cost"] for r in new_records)
    rprint(f"Reconstructed exposure: [bold]${total_cost:.2f}[/bold]")

    if not args.write:
        rprint("\n[yellow]Preview only. Re-run with --write to back up and apply.[/yellow]")
        return

    if TRADE_LOG_PATH.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = TRADE_LOG_PATH.with_suffix(f".clobbered-{stamp}.bak")
        shutil.copy2(TRADE_LOG_PATH, backup)
        rprint(f"\n[dim]Backed up current log -> {backup}[/dim]")

    save_trade_log(rebuilt)
    rprint(f"[green]Wrote {len(rebuilt)} records to {TRADE_LOG_PATH}[/green]")


if __name__ == "__main__":
    main()
