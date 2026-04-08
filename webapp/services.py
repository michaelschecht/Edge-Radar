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

# On Streamlit Cloud, inject secrets into os.environ so all existing
# os.getenv() calls in scripts (odds_api, edge_detector, etc.) work
# without modification. Must run before any script imports.
#
# Supports two TOML layouts:
#   Nested:    [kalshi] / api_key = "..."    → mapped via _secrets_map
#   Flat:      KALSHI_API_KEY = "..."        → mapped via _flat_keys
try:
    import streamlit as st
    _secrets_map = {
        "ODDS_API_KEY": lambda: st.secrets["odds"]["api_key"],
        "ODDS_API_KEYS": lambda: st.secrets["odds"]["api_keys"],
        "KALSHI_API_KEY": lambda: st.secrets["kalshi"]["api_key"],
        "KALSHI_PRIVATE_KEY": lambda: st.secrets["kalshi"]["private_key"],
        "KALSHI_BASE_URL": lambda: st.secrets["kalshi"]["base_url"],
        "DRY_RUN": lambda: st.secrets["DRY_RUN"],
    }
    # Also check for flat top-level keys (e.g. ODDS_API_KEY = "...")
    _flat_keys = [
        "ODDS_API_KEY", "ODDS_API_KEYS",
        "KALSHI_API_KEY", "KALSHI_PRIVATE_KEY", "KALSHI_BASE_URL",
        "DRY_RUN",
    ]
    for env_var, getter in _secrets_map.items():
        if env_var not in os.environ:
            try:
                os.environ[env_var] = str(getter())
            except (KeyError, FileNotFoundError):
                pass
    for key in _flat_keys:
        if key not in os.environ:
            try:
                os.environ[key] = str(st.secrets[key])
            except (KeyError, FileNotFoundError):
                pass
except Exception:
    pass

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
DRY_RUN = os.getenv("DRY_RUN", "true").lower() in ("true", "1", "yes")


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
    """Create an authenticated Kalshi client.

    On Streamlit Cloud, reads credentials from st.secrets["kalshi"].
    Locally, reads from .env as usual.
    Raises FileNotFoundError with a clear message if credentials are missing.
    """
    import streamlit as st

    # Try to pull credentials from Streamlit secrets (Cloud deployment)
    try:
        kalshi_secrets = st.secrets["kalshi"]
        return KalshiClient(
            api_key=kalshi_secrets.get("api_key"),
            private_key_content=kalshi_secrets.get("private_key"),
            base_url=kalshi_secrets.get("base_url"),
        )
    except (KeyError, FileNotFoundError):
        pass

    # Fall back to .env-based config (local dev)
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
    """Convert raw Kalshi position dicts to display-friendly rows.

    Kalshi API fields:
        position_fp: str — signed contract count (positive=YES, negative=NO)
        total_traded_dollars: str — cost basis
        market_exposure_dollars: str — current market value
        fees_paid_dollars: str — fees paid
        realized_pnl_dollars: str — realized P&L
    """
    rows = []
    for p in positions:
        ticker = p.get("ticker", "")
        title = p.get("title", ticker)

        # position_fp is a string like "3.00" (YES) or "-3.00" (NO)
        position_fp = float(p.get("position_fp", 0))
        side = "YES" if position_fp > 0 else "NO"
        qty = abs(int(position_fp))

        cost = float(p.get("total_traded_dollars", 0))
        exposure = float(p.get("market_exposure_dollars", 0))
        fees = float(p.get("fees_paid_dollars", 0))

        # Avg price per contract
        avg_price = cost / qty if qty > 0 else 0

        # Unrealized P&L: exposure - cost - fees
        pnl = exposure - cost - fees

        rows.append({
            "Sport": sport_from_ticker(ticker),
            "Bet": format_bet_label(ticker, title),
            "Type": bet_type_from_ticker(ticker),
            "Side": side,
            "Qty": qty,
            "Avg Price": f"${avg_price:.2f}",
            "Cost": f"${cost:.2f}",
            "Value": f"${exposure:.2f}",
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


# ── Settlement History ──────────────────────────────────────────────────

def get_settlement_history(limit: int = 50) -> list[dict]:
    """Load recent settlements from the settlement log."""
    from trade_log import load_settlement_log
    settlements = load_settlement_log()
    # Most recent first
    settlements.sort(key=lambda s: s.get("settled_at", ""), reverse=True)
    return settlements[:limit]


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
