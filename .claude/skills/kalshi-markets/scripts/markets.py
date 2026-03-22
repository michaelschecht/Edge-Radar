#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Markets List Script

List Kalshi prediction markets with various filters.
Completely self-contained with embedded HTTP client.

Usage:
    uv run markets.py
    uv run markets.py --limit 5
    uv run markets.py --status closed
    uv run markets.py --json
"""

import json
import sys
from typing import Any

import click
import httpx

# Configuration
API_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_TIMEOUT = 30.0  # seconds
USER_AGENT = "Kalshi-CLI/1.0"


class KalshiClient:
    """Minimal HTTP client for Kalshi API - markets functionality"""

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

    def get_markets(
        self,
        limit: int = 10,
        status: str | None = None,
        cursor: str | None = None,
        event_ticker: str | None = None,
        series_ticker: str | None = None,
        tickers: str | None = None,
        mve_filter: str | None = None,
    ) -> dict[str, Any]:
        """
        Get list of markets with filters.

        Args:
            limit: Number of markets to return (1-1000)
            status: Market status filter (open, closed, settled)
            cursor: Pagination cursor
            event_ticker: Filter by event ticker
            series_ticker: Filter by series ticker
            tickers: Comma-separated list of market tickers
            mve_filter: Multivariate events filter (only, exclude)

        Returns:
            Dict with 'markets' array and optional 'cursor'

        Raises:
            Exception if API call fails
        """
        # Build query parameters
        params = {"limit": str(limit)}
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if tickers:
            params["tickers"] = tickers
        if mve_filter:
            params["mve_filter"] = mve_filter

        try:
            response = self.client.get("/markets", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")


def format_market_summary(market: dict[str, Any]) -> str:
    """
    Format a single market for display.

    Args:
        market: Market data dict

    Returns:
        Formatted string summary of the market
    """
    ticker = market.get("ticker", "N/A")
    title = market.get("title", "N/A")
    status = market.get("status", "unknown")

    # Get current prices
    yes_bid = market.get("yes_bid", 0)
    yes_ask = market.get("yes_ask", 0)
    last_price = market.get("last_price", 0)

    # Get volume
    volume = market.get("volume", 0)
    volume_24h = market.get("volume_24h", 0)

    # Format status emoji
    status_icon = "🟢" if status == "active" else "🔴" if status == "closed" else "⚫"

    # Build summary
    lines = []
    lines.append(f"{status_icon} {ticker}")
    lines.append(f"   {title[:70]}{'...' if len(title) > 70 else ''}")

    if yes_bid or yes_ask:
        lines.append(f"   Price: {yes_bid}¢-{yes_ask}¢ (Last: {last_price}¢)")

    if volume_24h > 0:
        lines.append(f"   24h Vol: ${volume_24h/100:,.2f}")
    elif volume > 0:
        lines.append(f"   Total Vol: ${volume/100:,.2f}")

    return "\n".join(lines)


def format_markets_list(data: dict[str, Any]) -> str:
    """
    Format markets list for human-readable output.

    Args:
        data: Response data with markets array

    Returns:
        Formatted string for display
    """
    markets = data.get("markets", [])
    cursor = data.get("cursor", "")

    lines = []
    lines.append("\nKalshi Markets")
    lines.append("=" * 60)
    lines.append(f"Found {len(markets)} markets")
    lines.append("")

    for i, market in enumerate(markets, 1):
        lines.append(f"{i}. {format_market_summary(market)}")
        lines.append("")

    if cursor:
        lines.append(f"📄 More results available. Use --cursor {cursor[:20]}...")
        lines.append("")

    return "\n".join(lines)


@click.command()
@click.option("--limit", default=10, type=int, help="Number of markets to return (1-1000)")
@click.option(
    "--status", default="open", help="Market status (open, closed, settled, or comma-separated)"
)
@click.option("--event-ticker", help="Filter by event ticker")
@click.option("--series-ticker", help="Filter by series ticker")
@click.option("--tickers", help="Filter by market tickers (comma-separated)")
@click.option(
    "--mve-filter", type=click.Choice(["only", "exclude"]), help="Multivariate events filter"
)
@click.option("--cursor", help="Pagination cursor for next page")
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(
    limit: int,
    status: str,
    event_ticker: str | None,
    series_ticker: str | None,
    tickers: str | None,
    mve_filter: str | None,
    cursor: str | None,
    output_json: bool,
):
    """
    List Kalshi prediction markets with filters.

    Returns markets matching the specified criteria.
    No authentication required.
    """
    try:
        # Validate limit
        if limit < 1 or limit > 1000:
            raise ValueError("Limit must be between 1 and 1000")

        # Get markets from API
        with KalshiClient() as client:
            data = client.get_markets(
                limit=limit,
                status=status,
                cursor=cursor,
                event_ticker=event_ticker,
                series_ticker=series_ticker,
                tickers=tickers,
                mve_filter=mve_filter,
            )

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(data, indent=2))
        else:
            # Human-readable output
            formatted = format_markets_list(data)
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
