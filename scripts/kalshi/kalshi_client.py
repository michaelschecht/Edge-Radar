"""
kalshi_client.py
Unified Kalshi API client for Edge-Radar.

Handles authentication (RSA-PSS signing), market data, order placement,
position tracking, and balance queries.

Usage:
    from kalshi_client import KalshiClient

    client = KalshiClient()           # reads config from .env
    markets = client.get_markets(status="open", limit=50)
    balance = client.get_balance()
    order   = client.create_order(ticker="KXTEMP-...", side="yes", action="buy",
                                  yes_price_cents=55, count=10)
"""

import os
import sys
import json
import datetime
import base64
import logging
from pathlib import Path
from urllib.parse import urlparse, urlencode

import requests
from dotenv import load_dotenv
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
log = logging.getLogger("kalshi_client")


class KalshiClient:
    """Authenticated Kalshi API client with full trading capabilities."""

    def __init__(
        self,
        api_key: str | None = None,
        private_key_path: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.getenv("KALSHI_API_KEY", "")
        self.base_url = (base_url or os.getenv(
            "KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2"
        )).rstrip("/")

        key_path = private_key_path or os.getenv("KALSHI_PRIVATE_KEY_PATH", "")
        # Resolve relative paths from project root
        key_file = Path(key_path)
        if not key_file.is_absolute():
            key_file = Path(__file__).resolve().parent.parent.parent / key_path.lstrip("/\\")

        if not key_file.exists():
            raise FileNotFoundError(
                f"Kalshi private key not found at {key_file}. "
                "Set KALSHI_PRIVATE_KEY_PATH in .env"
            )

        self._private_key = self._load_private_key(key_file)
        self.is_demo = "demo" in self.base_url
        self.dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

        log.info(
            "KalshiClient initialized — env=%s, dry_run=%s",
            "DEMO" if self.is_demo else "LIVE",
            self.dry_run,
        )

    # ── Authentication ────────────────────────────────────────────────────────

    @staticmethod
    def _load_private_key(key_path: Path):
        with open(key_path, "rb") as f:
            return serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )

    def _sign(self, timestamp_ms: str, method: str, path: str) -> str:
        """Create RSA-PSS SHA256 signature for request authentication."""
        # Strip query params for signing
        path_only = path.split("?")[0]
        message = f"{timestamp_ms}{method.upper()}{path_only}".encode("utf-8")
        signature = self._private_key.sign(
            message,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def _auth_headers(self, method: str, path: str) -> dict:
        """Build the three required Kalshi auth headers."""
        ts = str(int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1000))
        sig = self._sign(ts, method, path)
        return {
            "KALSHI-ACCESS-KEY": self.api_key,
            "KALSHI-ACCESS-TIMESTAMP": ts,
            "KALSHI-ACCESS-SIGNATURE": sig,
            "Content-Type": "application/json",
        }

    # ── HTTP helpers ──────────────────────────────────────────────────────────

    def _request(self, method: str, path: str, params: dict | None = None,
                 body: dict | None = None, timeout: int = 15) -> dict:
        """Make an authenticated request to the Kalshi API."""
        url = f"{self.base_url}{path}"
        if params:
            # Filter out None values
            params = {k: v for k, v in params.items() if v is not None}

        # Sign using the full path (as seen by server)
        sign_path = urlparse(url).path
        headers = self._auth_headers(method.upper(), sign_path)

        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            params=params,
            json=body,
            timeout=timeout,
        )

        if resp.status_code == 429:
            log.warning("Rate limited by Kalshi API")
            raise KalshiRateLimitError("Rate limited — back off and retry")

        if not resp.ok:
            log.error("Kalshi API error %s: %s", resp.status_code, resp.text[:500])
            raise KalshiAPIError(resp.status_code, resp.text)

        return resp.json() if resp.content else {}

    def _get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def _post(self, path: str, body: dict | None = None) -> dict:
        return self._request("POST", path, body=body)

    def _delete(self, path: str, body: dict | None = None) -> dict:
        return self._request("DELETE", path, body=body)

    # ── Market Data (public-ish, but we sign anyway) ──────────────────────────

    def get_markets(
        self,
        limit: int = 100,
        cursor: str | None = None,
        status: str | None = None,
        series_ticker: str | None = None,
        event_ticker: str | None = None,
        tickers: str | None = None,
    ) -> dict:
        """
        Fetch markets from Kalshi.

        Args:
            limit: 1-1000, default 100
            status: unopened | open | paused | closed | settled
            series_ticker: filter by series
            event_ticker: filter by event
            tickers: comma-separated market tickers
        """
        return self._get("/markets", params={
            "limit": limit,
            "cursor": cursor,
            "status": status,
            "series_ticker": series_ticker,
            "event_ticker": event_ticker,
            "tickers": tickers,
        })

    def get_market(self, ticker: str) -> dict:
        """Fetch a single market by ticker."""
        return self._get(f"/markets/{ticker}")

    def get_all_open_markets(self, max_pages: int = 10) -> list[dict]:
        """Paginate through all open markets."""
        all_markets = []
        cursor = None
        for _ in range(max_pages):
            resp = self.get_markets(limit=1000, status="open", cursor=cursor)
            markets = resp.get("markets", [])
            all_markets.extend(markets)
            cursor = resp.get("cursor", "")
            if not cursor:
                break
        log.info("Fetched %d open markets", len(all_markets))
        return all_markets

    # ── Portfolio & Balance ───────────────────────────────────────────────────

    def get_balance(self) -> dict:
        """
        Get account balance.
        Returns: { balance, portfolio_value, updated_ts } — all in cents.
        """
        return self._get("/portfolio/balance")

    def get_positions(
        self,
        limit: int = 100,
        cursor: str | None = None,
        ticker: str | None = None,
        event_ticker: str | None = None,
        count_filter: str | None = None,
    ) -> dict:
        """
        Get current positions.

        Args:
            count_filter: "position" (non-zero position) or "total_traded"
        """
        return self._get("/portfolio/positions", params={
            "limit": limit,
            "cursor": cursor,
            "ticker": ticker,
            "event_ticker": event_ticker,
            "count_filter": count_filter,
        })

    def get_fills(
        self,
        limit: int = 100,
        cursor: str | None = None,
        ticker: str | None = None,
    ) -> dict:
        """Get trade fills / execution history."""
        return self._get("/portfolio/fills", params={
            "limit": limit,
            "cursor": cursor,
            "ticker": ticker,
        })

    def get_settlements(
        self,
        limit: int = 100,
        cursor: str | None = None,
        ticker: str | None = None,
        event_ticker: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
    ) -> dict:
        """
        Get settlement history.

        Returns settled positions with market_result (yes/no/void),
        revenue (payout in cents), and cost basis.
        """
        return self._get("/portfolio/settlements", params={
            "limit": limit,
            "cursor": cursor,
            "ticker": ticker,
            "event_ticker": event_ticker,
            "min_ts": min_ts,
            "max_ts": max_ts,
        })

    # ── Order Management ──────────────────────────────────────────────────────

    def create_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int = 1,
        yes_price_cents: int | None = None,
        no_price_cents: int | None = None,
        client_order_id: str | None = None,
        time_in_force: str = "good_till_canceled",
        expiration_ts: int | None = None,
        buy_max_cost: int | None = None,
    ) -> dict:
        """
        Place an order on Kalshi.

        Args:
            ticker: Market ticker (e.g. "KXTEMP-26MAR18-NYC-T55")
            side: "yes" or "no"
            action: "buy" or "sell"
            count: Number of contracts (min 1)
            yes_price_cents: Limit price for Yes side (1-99 cents)
            no_price_cents: Limit price for No side (1-99 cents)
            time_in_force: fill_or_kill | good_till_canceled | immediate_or_cancel
        """
        if self.dry_run and not self.is_demo:
            log.warning("[DRY RUN] Order blocked — DRY_RUN=true on non-demo env")
            return {"status": "dry_run_blocked", "ticker": ticker, "side": side}

        body = {
            "ticker": ticker,
            "side": side,
            "action": action,
            "count": count,
            "type": "limit",
            "time_in_force": time_in_force,
        }

        if yes_price_cents is not None:
            body["yes_price"] = yes_price_cents
        if no_price_cents is not None:
            body["no_price"] = no_price_cents
        if client_order_id:
            body["client_order_id"] = client_order_id
        if expiration_ts:
            body["expiration_ts"] = expiration_ts
        if buy_max_cost is not None:
            body["buy_max_cost"] = buy_max_cost

        log.info(
            "Placing order: %s %s %s @ %s cents — %d contracts",
            action, side, ticker,
            yes_price_cents or no_price_cents or "market",
            count,
        )
        return self._post("/portfolio/orders", body=body)

    def cancel_order(self, order_id: str) -> dict:
        """Cancel a resting order."""
        return self._delete(f"/portfolio/orders/{order_id}")

    def get_order(self, order_id: str) -> dict:
        """Get details of a specific order."""
        return self._get(f"/portfolio/orders/{order_id}")

    def get_orders(
        self,
        limit: int = 100,
        cursor: str | None = None,
        ticker: str | None = None,
        status: str | None = None,
    ) -> dict:
        """
        Get order history.

        Args:
            status: resting | canceled | executed
        """
        return self._get("/portfolio/orders", params={
            "limit": limit,
            "cursor": cursor,
            "ticker": ticker,
            "status": status,
        })

    # ── Convenience / Analysis ────────────────────────────────────────────────

    def get_balance_dollars(self) -> dict:
        """Get balance formatted in dollars instead of cents."""
        raw = self.get_balance()
        return {
            "balance": raw.get("balance", 0) / 100,
            "portfolio_value": raw.get("portfolio_value", 0) / 100,
            "updated_ts": raw.get("updated_ts"),
        }

    def get_market_snapshot(self, ticker: str) -> dict:
        """Get a clean snapshot of a market's current state."""
        m = self.get_market(ticker).get("market", {})
        return {
            "ticker": m.get("ticker"),
            "title": m.get("title", m.get("subtitle", "")),
            "status": m.get("status"),
            "yes_bid": m.get("yes_bid_dollars"),
            "yes_ask": m.get("yes_ask_dollars"),
            "no_bid": m.get("no_bid_dollars"),
            "no_ask": m.get("no_ask_dollars"),
            "last_price": m.get("last_price_dollars"),
            "volume_24h": m.get("volume_24h_fp"),
            "open_interest": m.get("open_interest_fp"),
            "close_time": m.get("close_time"),
            "expiration_time": m.get("latest_expiration_time"),
        }


# ── Factory Helpers ───────────────────────────────────────────────────────────

def make_prod_client() -> KalshiClient | None:
    """
    Create a production Kalshi client for read-only market data.
    Returns None if prod credentials are not configured.
    """
    prod_key = os.getenv("KALSHI_PROD_API_KEY", "")
    prod_key_path = os.getenv("KALSHI_PROD_PRIVATE_KEY_PATH", "")
    prod_url = os.getenv("KALSHI_PROD_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")

    if not prod_key or not prod_key_path:
        return None

    try:
        return KalshiClient(
            api_key=prod_key,
            private_key_path=prod_key_path,
            base_url=prod_url,
        )
    except FileNotFoundError:
        return None


# ── Exceptions ────────────────────────────────────────────────────────────────

class KalshiAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Kalshi API {status_code}: {message}")


class KalshiRateLimitError(KalshiAPIError):
    def __init__(self, message: str = "Rate limited"):
        super().__init__(429, message)


# ── CLI quick test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from rich.console import Console
    from rich.table import Table
    from rich import print as rprint

    from logging_setup import setup_logging
    setup_logging("kalshi_client")
    console = Console()

    parser = argparse.ArgumentParser(description="Kalshi API client — quick test")
    parser.add_argument("command", choices=["balance", "markets", "positions", "orders", "market"],
                        help="What to query")
    parser.add_argument("--ticker", help="Market ticker (for 'market' command)")
    parser.add_argument("--limit", type=int, default=20, help="Number of results")
    parser.add_argument("--status", default="open", help="Market status filter")
    args = parser.parse_args()

    try:
        client = KalshiClient()

        if args.command == "balance":
            bal = client.get_balance_dollars()
            rprint(f"\n[bold cyan]-- Kalshi Account Balance --[/bold cyan]")
            rprint(f"  Environment:     {'[yellow]DEMO[/yellow]' if client.is_demo else '[red]LIVE[/red]'}")
            rprint(f"  Available:       [green]${bal['balance']:,.2f}[/green]")
            rprint(f"  Portfolio Value: [green]${bal['portfolio_value']:,.2f}[/green]")

        elif args.command == "markets":
            resp = client.get_markets(limit=args.limit, status=args.status)
            markets = resp.get("markets", [])

            table = Table(title=f"Kalshi Markets ({args.status})", show_lines=True)
            table.add_column("Ticker", style="cyan", max_width=30)
            table.add_column("Title", max_width=45)
            table.add_column("Yes Bid", justify="right", style="green")
            table.add_column("Yes Ask", justify="right", style="green")
            table.add_column("Volume 24h", justify="right", style="dim")
            table.add_column("Closes", style="dim", max_width=12)

            for m in markets:
                table.add_row(
                    m.get("ticker", "")[:30],
                    (m.get("title") or m.get("subtitle", ""))[:45],
                    m.get("yes_bid_dollars", "—"),
                    m.get("yes_ask_dollars", "—"),
                    m.get("volume_24h_fp", "—"),
                    (m.get("close_time") or "")[:10],
                )
            console.print(table)
            rprint(f"[dim]Showing {len(markets)} of {args.limit} requested[/dim]")

        elif args.command == "positions":
            resp = client.get_positions(limit=args.limit, count_filter="position")
            positions = resp.get("market_positions", [])

            if not positions:
                rprint("[yellow]No open positions[/yellow]")
            else:
                table = Table(title="Open Positions", show_lines=True)
                table.add_column("Ticker", style="cyan")
                table.add_column("Position", justify="right")
                table.add_column("Exposure", justify="right", style="green")
                table.add_column("Realized P&L", justify="right")

                for p in positions:
                    pnl = p.get("realized_pnl_dollars", "0")
                    pnl_style = "green" if float(pnl) >= 0 else "red"
                    table.add_row(
                        p.get("ticker", ""),
                        p.get("position_fp", "0"),
                        p.get("market_exposure_dollars", "0"),
                        f"[{pnl_style}]{pnl}[/{pnl_style}]",
                    )
                console.print(table)

        elif args.command == "orders":
            resp = client.get_orders(limit=args.limit, status=args.status if args.status != "open" else "resting")
            orders = resp.get("orders", [])

            if not orders:
                rprint("[yellow]No orders found[/yellow]")
            else:
                table = Table(title="Orders", show_lines=True)
                table.add_column("Order ID", style="cyan", max_width=20)
                table.add_column("Ticker", max_width=25)
                table.add_column("Side")
                table.add_column("Action")
                table.add_column("Price", justify="right")
                table.add_column("Status")

                for o in orders:
                    table.add_row(
                        o.get("order_id", "")[:20],
                        o.get("ticker", "")[:25],
                        o.get("side", ""),
                        o.get("action", ""),
                        o.get("yes_price_dollars", "—"),
                        o.get("status", ""),
                    )
                console.print(table)

        elif args.command == "market":
            if not args.ticker:
                rprint("[red]--ticker required for 'market' command[/red]")
            else:
                snap = client.get_market_snapshot(args.ticker)
                rprint(f"\n[bold cyan]-- {snap['ticker']} --[/bold cyan]")
                for k, v in snap.items():
                    if k != "ticker":
                        rprint(f"  {k:>15}: {v}")

    except FileNotFoundError as e:
        rprint(f"[red]Key error: {e}[/red]")
    except KalshiAPIError as e:
        rprint(f"[red]API error: {e}[/red]")
    except Exception as e:
        rprint(f"[red]Error: {e}[/red]")
