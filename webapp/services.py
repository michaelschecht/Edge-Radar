"""
services.py — Thin wrapper around Edge-Radar core functions for the Streamlit UI.

Imports existing scanner, executor, settler, and risk functions.
Captures rich console output so Streamlit can render its own tables.
"""

import os
import sys
from io import StringIO
from pathlib import Path
from contextlib import contextmanager

# Ensure script dirs are on sys.path (mirrors what .pth does for the venv)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
for subdir in ["scripts/kalshi", "scripts/shared", "scripts/prediction", "scripts/polymarket"]:
    p = str(PROJECT_ROOT / subdir)
    if p not in sys.path:
        sys.path.insert(0, p)

from kalshi_client import KalshiClient
from edge_detector import scan_all_markets, FILTER_SHORTCUTS
from kalshi_executor import execute_pipeline, UNIT_SIZE
from kalshi_settler import settle_trades, generate_report
from risk_check import (
    fetch_balance, fetch_positions, fetch_resting_orders,
    get_today_trades, load_watchlist,
)
from trade_log import load_trade_log, get_today_pnl
from ticker_display import (
    filter_by_date, resolve_date_arg, filter_exclude_tickers,
    parse_game_datetime, format_bet_label, format_pick_label,
    sport_from_ticker, bet_type_from_ticker,
)
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "250"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "10"))
MAX_PER_EVENT = int(os.getenv("MAX_PER_EVENT", "2"))
MIN_EDGE_THRESHOLD = float(os.getenv("MIN_EDGE_THRESHOLD", "0.03"))
MIN_COMPOSITE_SCORE = float(os.getenv("MIN_COMPOSITE_SCORE", "6.0"))
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"


@contextmanager
def capture_console():
    """Capture stdout (rich prints to stdout) and return the output."""
    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        yield buf
    finally:
        sys.stdout = old_stdout


def get_client() -> KalshiClient:
    """Create an authenticated Kalshi client."""
    return KalshiClient()


# ── Sport filter options ────────────────────────────────────────────────────

SPORT_FILTERS = sorted([
    k for k in FILTER_SHORTCUTS
    if not k.endswith("-futures") and k not in ("futures", "superbowl")
])

CATEGORY_OPTIONS = ["all", "game", "spread", "total", "player_prop", "esports", "other"]

DATE_OPTIONS = ["all dates", "today", "tomorrow"]


# ── Scan ────────────────────────────────────────────────────────────────────

def run_scan(
    client: KalshiClient,
    ticker_filter: str | None = None,
    category_filter: str | None = None,
    date_filter: str | None = None,
    min_edge: float = MIN_EDGE_THRESHOLD,
    top_n: int = 20,
    exclude_open: bool = False,
) -> tuple[list, str]:
    """
    Run a sports scan and return (opportunities, console_output).
    """
    with capture_console() as buf:
        opportunities = scan_all_markets(
            client,
            min_edge=min_edge,
            category_filter=category_filter,
            ticker_filter=ticker_filter,
            top_n=top_n,
        )

        if opportunities and date_filter and date_filter != "all dates":
            target = resolve_date_arg(date_filter)
            opportunities = filter_by_date(opportunities, target)

        if opportunities and exclude_open:
            positions = client.get_positions(limit=200, count_filter="position")
            open_tickers = {p.get("ticker", "") for p in positions.get("market_positions", [])}
            opportunities = filter_exclude_tickers(opportunities, open_tickers)

    return opportunities, buf.getvalue()


# ── Execute ─────────────────────────────────────────────────────────────────

def run_execute(
    client: KalshiClient,
    opportunities: list,
    unit_size: float = UNIT_SIZE,
    max_bets: int = 5,
    min_bets: int | None = None,
    budget: float | None = None,
    pick_indices: list[int] | None = None,
    execute: bool = False,
) -> tuple[list, str]:
    """
    Run the execution pipeline and return (sized_orders, console_output).

    pick_indices: 0-based indices into the opportunities list to execute.
    """
    if pick_indices is not None:
        opportunities = [opportunities[i] for i in pick_indices if i < len(opportunities)]

    # Convert budget percentage to fraction
    budget_val = None
    if budget is not None:
        if budget <= 1:
            budget_val = budget
        elif budget <= 100:
            budget_val = budget / 100
        else:
            budget_val = budget

    with capture_console() as buf:
        sized_orders = execute_pipeline(
            client=client,
            opportunities=opportunities,
            execute=execute,
            max_bets=max_bets,
            unit_size=unit_size,
            budget=budget_val,
            min_bets=min_bets,
        )

    return sized_orders or [], buf.getvalue()


# ── Portfolio ───────────────────────────────────────────────────────────────

def get_portfolio_data(client: KalshiClient) -> dict:
    """Fetch all portfolio data in one call."""
    bal = fetch_balance(client)
    positions = fetch_positions(client)
    resting = fetch_resting_orders(client)
    today_trades, daily_pnl = get_today_trades()

    return {
        "balance": bal.get("balance", 0),
        "portfolio_value": bal.get("portfolio_value", 0),
        "positions": positions,
        "resting_orders": resting,
        "open_count": len(positions),
        "today_trades": today_trades,
        "daily_pnl": daily_pnl,
        "daily_limit": MAX_DAILY_LOSS,
        "max_positions": MAX_OPEN_POSITIONS,
        "dry_run": DRY_RUN,
    }


def format_positions_for_display(positions: list[dict]) -> list[dict]:
    """Convert raw position dicts to display-friendly rows."""
    rows = []
    for p in positions:
        ticker = p.get("ticker", "")
        title = p.get("title", ticker)
        side = "YES" if p.get("position", 0) > 0 else "NO"
        qty = abs(p.get("position", 0))
        avg_price = p.get("average_price", 0)
        if isinstance(avg_price, int) and avg_price > 1:
            avg_price = avg_price / 100
        cost = qty * avg_price
        market_price = p.get("market_price", 0)
        if isinstance(market_price, int) and market_price > 1:
            market_price = market_price / 100
        value = qty * market_price
        pnl = value - cost

        rows.append({
            "Sport": sport_from_ticker(ticker),
            "Bet": format_bet_label(ticker, title),
            "Type": bet_type_from_ticker(ticker),
            "Side": side,
            "Qty": qty,
            "Avg Price": f"${avg_price:.2f}",
            "Cost": f"${cost:.2f}",
            "Value": f"${value:.2f}",
            "P&L": f"${pnl:+.2f}",
        })
    return rows


# ── Settle ──────────────────────────────────────────────────────────────────

def run_settle(client: KalshiClient) -> tuple[dict, str]:
    """Run settlement and return (result, console_output)."""
    with capture_console() as buf:
        result = settle_trades(client)
    return result, buf.getvalue()


def run_report(detail: bool = False, days: int | None = None) -> tuple[str, str]:
    """Generate P&L report and return (markdown_content, console_output)."""
    with capture_console() as buf:
        md = generate_report(detail=detail, save=False, days=days)
    return md or "", buf.getvalue()


# ── Helpers ─────────────────────────────────────────────────────────────────

def opportunities_to_rows(opportunities: list) -> list[dict]:
    """Convert Opportunity objects to display-friendly dicts."""
    rows = []
    for i, opp in enumerate(opportunities):
        rows.append({
            "#": i + 1,
            "Sport": sport_from_ticker(opp.ticker),
            "Bet": format_bet_label(opp.ticker, opp.title),
            "Type": {"game": "ML", "spread": "Spread", "total": "Total",
                     "player_prop": "Prop", "esports": "Esports"}.get(opp.category, opp.category.title()),
            "Pick": format_pick_label(opp.ticker, opp.title, opp.side, opp.category),
            "When": parse_game_datetime(opp.ticker),
            "Price": f"${opp.market_price:.2f}",
            "Fair": f"${opp.fair_value:.2f}",
            "Edge": f"+{opp.edge:.1%}",
            "Conf": opp.confidence.title(),
            "Score": f"{opp.composite_score:.1f}",
        })
    return rows
