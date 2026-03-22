#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Event Details Script

Get detailed information for a specific event.
Completely self-contained with embedded HTTP client.

Usage:
    uv run event.py EVENT_TICKER
    uv run event.py KXELONMARS-99
    uv run event.py EVENT_TICKER --with-markets
    uv run event.py EVENT_TICKER --json
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
    """Minimal HTTP client for Kalshi API - event details functionality"""

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

    def get_event(self, event_ticker: str, with_nested_markets: bool = False) -> dict[str, Any]:
        """
        Get detailed information for a specific event.

        Args:
            event_ticker: Event ticker identifier
            with_nested_markets: Include nested markets in response

        Returns:
            Event details including markets if requested

        Raises:
            Exception if API call fails
        """
        params = {}
        if with_nested_markets:
            params["with_nested_markets"] = "true"

        try:
            response = self.client.get(f"/events/{event_ticker}", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Event not found: {event_ticker}")
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")


def format_market_in_event(market: dict[str, Any]) -> str:
    """Format a market within an event"""
    ticker = market.get("ticker", "N/A")
    title = market.get("title", "N/A")[:60]
    yes_bid = market.get("yes_bid", 0)
    yes_ask = market.get("yes_ask", 0)
    status = market.get("status", "unknown")

    status_icon = "🟢" if status == "active" else "🔴"

    return f"     {status_icon} {ticker}\n        {title}... (Bid: {yes_bid}¢ Ask: {yes_ask}¢)"


def format_event_detail(data: dict[str, Any]) -> str:
    """
    Format event details for human-readable output.

    Args:
        data: Event data from API

    Returns:
        Formatted string for display
    """
    # Handle nested event object if present
    event = data.get("event", data)
    markets = data.get("markets", [])

    lines = []
    lines.append("\n" + "=" * 80)
    lines.append(f"📁 Event: {event.get('event_ticker', 'N/A')}")
    lines.append("=" * 80)

    # Title and subtitle
    title = event.get("title", "N/A")
    subtitle = event.get("subtitle", "")
    lines.append(f"\n📌 {title}")
    if subtitle:
        lines.append(f"   {subtitle}")

    # Basic info
    series = event.get("series_ticker", "N/A")
    category = event.get("category", "N/A")
    status = event.get("status", "unknown")
    mutually_exclusive = event.get("mutually_exclusive", False)

    status_icon = "🟢" if status == "open" else "🔴" if status == "closed" else "⚫"
    lines.append(f"\n{status_icon} Status: {status.upper()}")
    lines.append(f"📊 Series: {series}")
    lines.append(f"📂 Category: {category}")

    if mutually_exclusive:
        lines.append("🔒 Mutually Exclusive: Yes")
    else:
        lines.append("🔓 Mutually Exclusive: No")

    # Strike details if present
    strike_details = event.get("strike_details")
    if strike_details:
        lines.append("\n⚡ Strike Details:")
        for key, value in strike_details.items():
            if value:
                lines.append(f"   {key}: {value}")

    # Markets if included
    if markets:
        lines.append(f"\n📊 Markets ({len(markets)}):")
        lines.append("─" * 60)
        for i, market in enumerate(markets[:10], 1):  # Show first 10
            lines.append(f"   {i}. {format_market_in_event(market)}")

        if len(markets) > 10:
            lines.append(f"   ... and {len(markets) - 10} more markets")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)


@click.command()
@click.argument("event_ticker")
@click.option("--with-markets", is_flag=True, help="Include nested markets in response")
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(event_ticker: str, with_markets: bool, output_json: bool):
    """
    Get detailed information for a specific event.

    EVENT_TICKER is the event identifier (e.g., KXELONMARS-99).

    Events are collections of related markets.
    No authentication required.
    """
    try:
        # Get event details from API
        with KalshiClient() as client:
            data = client.get_event(event_ticker, with_nested_markets=with_markets)

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(data, indent=2))
        else:
            # Human-readable output
            formatted = format_event_detail(data)
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
