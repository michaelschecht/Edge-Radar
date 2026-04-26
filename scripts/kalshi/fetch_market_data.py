"""
fetch_market_data.py
Fetches current market data across stocks, prediction markets, and crypto.
Usage:
    python scripts/fetch_market_data.py --type stocks --symbols AAPL TSLA NVDA
    python scripts/fetch_market_data.py --type prediction --limit 20
    python scripts/fetch_market_data.py --type crypto --symbols BTC-USD ETH-USD
    python scripts/fetch_market_data.py --type all
"""

import sys
import json
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path


import requests
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint
from logging_setup import setup_logging
from app.config import get_config

# ── Setup ──────────────────────────────────────────────────────────────────────
load_dotenv()
console = Console()
log = setup_logging("fetch_market_data")

_cfg = get_config()
# `or None` preserves the original `os.getenv("X")` semantics — if unset,
# the credential is `None` (falsy) rather than `""`. The downstream
# `if not X:` checks are identical, but headers dicts and f-strings would
# render `""` differently from `None`.
ALPACA_API_KEY    = _cfg.alpaca.api_key or None
ALPACA_SECRET_KEY = _cfg.alpaca.secret_key or None
ALPACA_BASE_URL   = _cfg.alpaca.base_url
ALPACA_DATA_URL   = "https://data.alpaca.markets/v2"

POLYMARKET_URL    = "https://clob.polymarket.com"
KALSHI_URL        = "https://trading-api.kalshi.com/trade-api/v2"
KALSHI_API_KEY    = _cfg.kalshi.api_key or None

COINBASE_URL      = "https://api.coinbase.com/api/v3/brokerage"

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)


# ── Alpaca / Stocks ────────────────────────────────────────────────────────────

def get_alpaca_headers() -> dict:
    return {
        "APCA-API-KEY-ID": ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY,
    }


def fetch_stock_quotes(symbols: list[str]) -> dict:
    """Fetch latest quotes for a list of symbols via Alpaca."""
    if not ALPACA_API_KEY:
        rprint("[red]ERROR: ALPACA_API_KEY not set in .env[/red]")
        return {}

    symbols_str = ",".join(symbols)
    resp = requests.get(
        f"{ALPACA_DATA_URL}/stocks/quotes/latest",
        headers=get_alpaca_headers(),
        params={"symbols": symbols_str, "feed": "iex"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json().get("quotes", {})


def fetch_stock_bars(symbols: list[str], timeframe: str = "1Day", limit: int = 10) -> dict:
    """Fetch OHLCV bars for a list of symbols."""
    if not ALPACA_API_KEY:
        return {}

    symbols_str = ",".join(symbols)
    resp = requests.get(
        f"{ALPACA_DATA_URL}/stocks/bars",
        headers=get_alpaca_headers(),
        params={
            "symbols": symbols_str,
            "timeframe": timeframe,
            "limit": limit,
            "adjustment": "split",
            "feed": "iex",
        },
        timeout=10
    )
    resp.raise_for_status()
    return resp.json().get("bars", {})


def fetch_account_info() -> dict:
    """Fetch Alpaca account info (balance, buying power, etc.)."""
    if not ALPACA_API_KEY:
        return {}

    resp = requests.get(
        f"{ALPACA_BASE_URL}/v2/account",
        headers=get_alpaca_headers(),
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def fetch_open_positions_alpaca() -> list:
    """Fetch all open positions from Alpaca."""
    if not ALPACA_API_KEY:
        return []

    resp = requests.get(
        f"{ALPACA_BASE_URL}/v2/positions",
        headers=get_alpaca_headers(),
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def print_stock_quotes(quotes: dict):
    table = Table(title="Stock Quotes", show_lines=True)
    table.add_column("Symbol", style="cyan")
    table.add_column("Ask", justify="right")
    table.add_column("Bid", justify="right")
    table.add_column("Mid", justify="right", style="green")
    table.add_column("Spread", justify="right", style="dim")
    table.add_column("Timestamp", style="dim")

    for symbol, q in quotes.items():
        ask = q.get("ap", 0)
        bid = q.get("bp", 0)
        mid = round((ask + bid) / 2, 4) if ask and bid else 0
        spread = round(ask - bid, 4) if ask and bid else 0
        ts = q.get("t", "")[:19].replace("T", " ")
        table.add_row(symbol, f"${ask:.4f}", f"${bid:.4f}", f"${mid:.4f}", f"${spread:.4f}", ts)

    console.print(table)


# ── Prediction Markets ─────────────────────────────────────────────────────────

def fetch_polymarket_markets(limit: int = 20, active: bool = True) -> list:
    """Fetch active markets from Polymarket CLOB."""
    resp = requests.get(
        f"{POLYMARKET_URL}/markets",
        params={"limit": limit, "active": str(active).lower(), "closed": "false"},
        timeout=10
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", data) if isinstance(data, dict) else data


def fetch_polymarket_orderbook(token_id: str) -> dict:
    """Fetch order book for a specific Polymarket token."""
    resp = requests.get(
        f"{POLYMARKET_URL}/book",
        params={"token_id": token_id},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def fetch_kalshi_markets(limit: int = 20, status: str = "open") -> list:
    """Fetch markets from Kalshi."""
    headers = {}
    if KALSHI_API_KEY:
        headers["Authorization"] = f"Token {KALSHI_API_KEY}"

    resp = requests.get(
        f"{KALSHI_URL}/markets",
        headers=headers,
        params={"limit": limit, "status": status},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json().get("markets", [])


def print_prediction_markets(markets: list, source: str = "Polymarket"):
    table = Table(title=f"{source} Active Markets", show_lines=True)
    table.add_column("Question", style="cyan", max_width=50)
    table.add_column("Yes Price", justify="right", style="green")
    table.add_column("No Price", justify="right", style="red")
    table.add_column("Volume", justify="right", style="dim")
    table.add_column("Ends", style="dim")

    for m in markets[:20]:
        question = m.get("question", m.get("title", ""))[:50]
        tokens = m.get("tokens", [])
        yes_price = no_price = "—"
        for t in tokens:
            if t.get("outcome", "").lower() == "yes":
                yes_price = f"${float(t.get('price', 0)):.3f}"
            elif t.get("outcome", "").lower() == "no":
                no_price = f"${float(t.get('price', 0)):.3f}"

        volume = m.get("volume", m.get("volume_24hr", 0))
        try:
            volume_fmt = f"${float(volume):,.0f}"
        except (ValueError, TypeError):
            volume_fmt = str(volume)

        end_date = m.get("end_date_iso", m.get("close_time", ""))
        end_fmt = end_date[:10] if end_date else "—"

        table.add_row(question, yes_price, no_price, volume_fmt, end_fmt)

    console.print(table)


# ── Crypto ─────────────────────────────────────────────────────────────────────

def fetch_crypto_prices(symbols: list[str]) -> list:
    """Fetch crypto prices from Coinbase (public endpoint, no auth needed)."""
    results = []
    for symbol in symbols:
        try:
            resp = requests.get(
                f"https://api.coinbase.com/v2/prices/{symbol}/spot",
                timeout=10
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            results.append({
                "symbol": symbol,
                "price": float(data.get("amount", 0)),
                "currency": data.get("currency", "USD"),
                "fetched_at": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            log.warning(f"Failed to fetch {symbol}: {e}")
            results.append({"symbol": symbol, "price": None, "error": str(e)})
    return results


def print_crypto_prices(prices: list):
    table = Table(title="Crypto Prices", show_lines=True)
    table.add_column("Symbol", style="cyan")
    table.add_column("Price (USD)", justify="right", style="green")
    table.add_column("Fetched At", style="dim")

    for p in prices:
        price_str = f"${p['price']:,.4f}" if p.get("price") else "[red]ERROR[/red]"
        ts = p.get("fetched_at", "")[:19].replace("T", " ")
        table.add_row(p["symbol"], price_str, ts)

    console.print(table)


# ── Snapshot Save ──────────────────────────────────────────────────────────────

def save_snapshot(data_type: str, data: dict | list):
    """Save market data snapshot to data/ directory."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = DATA_DIR / f"{data_type}_snapshot_{ts}.json"
    with open(path, "w") as f:
        json.dump({"fetched_at": datetime.now(timezone.utc).isoformat(), "data": data}, f, indent=2)
    rprint(f"[dim]Saved snapshot → {path}[/dim]")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch market data across asset classes.")
    parser.add_argument("--type", default="stocks",
                        choices=["stocks", "prediction", "crypto", "account", "all"],
                        help="Data type to fetch")
    parser.add_argument("--symbols", nargs="+", default=["AAPL", "NVDA", "TSLA", "SPY", "QQQ"],
                        help="Symbols for stocks or crypto (e.g. BTC-USD)")
    parser.add_argument("--limit", type=int, default=20,
                        help="Number of prediction market results")
    parser.add_argument("--save", action="store_true",
                        help="Save snapshot to data/ directory")
    parser.add_argument("--source", default="polymarket",
                        choices=["polymarket", "kalshi"],
                        help="Prediction market source")
    args = parser.parse_args()

    fetch_type = args.type

    # Stocks
    if fetch_type in ("stocks", "all"):
        rprint("\n[bold cyan]── Stock Quotes ──────────────────────[/bold cyan]")
        try:
            quotes = fetch_stock_quotes(args.symbols)
            print_stock_quotes(quotes)
            if args.save:
                save_snapshot("stocks", quotes)
        except Exception as e:
            rprint(f"[red]Stocks error: {e}[/red]")

    # Account info
    if fetch_type in ("account", "all"):
        rprint("\n[bold cyan]── Alpaca Account ────────────────────[/bold cyan]")
        try:
            account = fetch_account_info()
            rprint(f"  Portfolio Value:  [green]${float(account.get('portfolio_value', 0)):,.2f}[/green]")
            rprint(f"  Cash:             [green]${float(account.get('cash', 0)):,.2f}[/green]")
            rprint(f"  Buying Power:     [green]${float(account.get('buying_power', 0)):,.2f}[/green]")
            rprint(f"  Account Status:   {account.get('status', 'unknown')}")
            rprint(f"  Paper Trading:    {'paper' in ALPACA_BASE_URL}")
        except Exception as e:
            rprint(f"[red]Account error: {e}[/red]")

    # Prediction markets
    if fetch_type in ("prediction", "all"):
        rprint(f"\n[bold cyan]── {args.source.title()} Markets ──────────────────[/bold cyan]")
        try:
            if args.source == "polymarket":
                markets = fetch_polymarket_markets(limit=args.limit)
                print_prediction_markets(markets, "Polymarket")
                if args.save:
                    save_snapshot("polymarket", markets)
            elif args.source == "kalshi":
                markets = fetch_kalshi_markets(limit=args.limit)
                print_prediction_markets(markets, "Kalshi")
                if args.save:
                    save_snapshot("kalshi", markets)
        except Exception as e:
            rprint(f"[red]Prediction markets error: {e}[/red]")

    # Crypto
    if fetch_type in ("crypto", "all"):
        rprint("\n[bold cyan]── Crypto Prices ─────────────────────[/bold cyan]")
        crypto_symbols = args.symbols if fetch_type == "crypto" else ["BTC-USD", "ETH-USD", "SOL-USD"]
        try:
            prices = fetch_crypto_prices(crypto_symbols)
            print_crypto_prices(prices)
            if args.save:
                save_snapshot("crypto", prices)
        except Exception as e:
            rprint(f"[red]Crypto error: {e}[/red]")


if __name__ == "__main__":
    main()
