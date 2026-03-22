#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Recent Trades Script

Get recent trades across all markets or for a specific market.
Completely self-contained with embedded HTTP client.

Usage:
    uv run trades.py
    uv run trades.py --limit 20
    uv run trades.py --ticker MARKET_TICKER
    uv run trades.py --json
"""

import json
import sys
from datetime import datetime
from typing import Any

import click
import httpx

# Configuration
API_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_TIMEOUT = 30.0  # seconds
USER_AGENT = "Kalshi-CLI/1.0"


class KalshiClient:
    """Minimal HTTP client for Kalshi API - trades functionality"""

    def __init__(self):
        """Initialize HTTP client"""
        self.client = httpx.Client(
            base_url=API_BASE_URL, timeout=API_TIMEOUT, headers={"User-Agent": USER_AGENT}
        )

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup"""
        self.client.close()

    def get_trades(
        self,
        limit: int = 10,
        ticker: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """
        Get recent trades.

        Args:
            limit: Number of trades to return (1-1000)
            ticker: Filter by market ticker
            min_ts: Filter trades after this Unix timestamp
            max_ts: Filter trades before this Unix timestamp
            cursor: Pagination cursor

        Returns:
            Dict with 'trades' array and optional 'cursor'

        Raises:
            Exception if API call fails
        """
        params = {"limit": str(limit)}
        if ticker:
            params["ticker"] = ticker
        if min_ts is not None:
            params["min_ts"] = str(min_ts)
        if max_ts is not None:
            params["max_ts"] = str(max_ts)
        if cursor:
            params["cursor"] = cursor

        try:
            response = self.client.get("/markets/trades", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to readable string"""
    if not timestamp_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return timestamp_str


def format_trade(trade: dict[str, Any], index: int) -> str:
    """Format a single trade for display"""
    ticker = trade.get("ticker", "N/A")
    yes_price = trade.get("yes_price", 0)
    no_price = trade.get("no_price", 0)
    count = trade.get("count", 0)
    created = format_timestamp(trade.get("created_time", ""))

    # Determine trade side
    if yes_price > 0:
        price = yes_price
        side = "YES"
        emoji = "✅"
    else:
        price = no_price
        side = "NO"
        emoji = "❌"

    lines = []
    lines.append(f"{index}. {emoji} {ticker}")
    lines.append(f"   {side} @ {price}¢ | {count:,} contracts")
    lines.append(f"   {created}")

    return "\n".join(lines)


def format_trades_list(data: dict[str, Any]) -> str:
    """
    Format trades list for human-readable output.

    Args:
        data: Response data with trades array

    Returns:
        Formatted string for display
    """
    trades = data.get("trades", [])
    cursor = data.get("cursor", "")

    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("📊 Recent Trades")
    lines.append("=" * 60)
    lines.append(f"Found {len(trades)} trades\n")

    for i, trade in enumerate(trades, 1):
        lines.append(format_trade(trade, i))
        lines.append("")  # Blank line between trades

    if cursor:
        lines.append("─" * 60)
        lines.append(f"📄 More results available. Use --cursor {cursor[:20]}...")

    lines.append("=" * 60)
    return "\n".join(lines)


@click.command()
@click.option("--limit", default=10, type=int, help="Number of trades to return (1-1000)")
@click.option("--ticker", help="Filter trades for specific market ticker")
@click.option("--min-ts", type=int, help="Filter trades after this Unix timestamp")
@click.option("--max-ts", type=int, help="Filter trades before this Unix timestamp")
@click.option("--cursor", help="Pagination cursor for next page")
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(
    limit: int,
    ticker: str | None,
    min_ts: int | None,
    max_ts: int | None,
    cursor: str | None,
    output_json: bool,
):
    """
    Get recent trades across all markets or for a specific market.

    Shows trade price, size, and timestamp for recent market activity.
    No authentication required.
    """
    try:
        # Validate limit
        if limit < 1 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")

        # Get trades from API
        with KalshiClient() as client:
            data = client.get_trades(
                limit=limit, ticker=ticker, min_ts=min_ts, max_ts=max_ts, cursor=cursor
            )

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(data, indent=2))
        else:
            # Human-readable output
            formatted = format_trades_list(data)
            click.echo(formatted)

        sys.exit(0)

    except Exception as e:
        if output_json:
            # JSON error format
            error_data = {"error": str(e)}
            click.echo(json.dumps(error_data, indent=2))
        else:
            # Human-readable error
            click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
