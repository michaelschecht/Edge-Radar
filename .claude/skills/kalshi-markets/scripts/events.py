#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Events List Script

List events (collections of related markets) from Kalshi.
Completely self-contained with embedded HTTP client.

Usage:
    uv run events.py
    uv run events.py --limit 5
    uv run events.py --status closed
    uv run events.py --series-ticker KXHIGHNY
    uv run events.py --json
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
    """Minimal HTTP client for Kalshi API - events functionality"""

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

    def get_events(
        self,
        limit: int = 10,
        status: str | None = None,
        series_ticker: str | None = None,
        with_nested_markets: bool = False,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """
        Get list of events.

        Args:
            limit: Number of events to return (1-200)
            status: Event status filter (open, closed, settled)
            series_ticker: Filter by series ticker
            with_nested_markets: Include nested markets in response
            cursor: Pagination cursor

        Returns:
            Dict with 'events' array and optional 'cursor'

        Raises:
            Exception if API call fails
        """
        params = {"limit": str(limit)}
        if status:
            params["status"] = status
        if series_ticker:
            params["series_ticker"] = series_ticker
        if with_nested_markets:
            params["with_nested_markets"] = "true"
        if cursor:
            params["cursor"] = cursor

        try:
            response = self.client.get("/events", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")


def format_event_summary(event: dict[str, Any], index: int) -> str:
    """Format a single event for display"""
    event_ticker = event.get("event_ticker", "N/A")
    title = event.get("title", "N/A")
    category = event.get("category", "N/A")
    series_ticker = event.get("series_ticker", "N/A")
    status = event.get("status", "unknown")

    # Status icon
    status_icon = "🟢" if status == "open" else "🔴" if status == "closed" else "⚫"

    lines = []
    lines.append(f"{index}. {status_icon} {event_ticker}")
    lines.append(f"   📌 {title[:70]}{'...' if len(title) > 70 else ''}")
    lines.append(f"   📂 Category: {category} | Series: {series_ticker}")

    # Show market count if available
    markets = event.get("markets", [])
    if markets:
        lines.append(f"   📊 {len(markets)} markets")

    # Mutually exclusive indicator
    mutually_exclusive = event.get("mutually_exclusive", False)
    if mutually_exclusive:
        lines.append("   🔒 Mutually Exclusive")

    return "\n".join(lines)


def format_events_list(data: dict[str, Any]) -> str:
    """
    Format events list for human-readable output.

    Args:
        data: Response data with events array

    Returns:
        Formatted string for display
    """
    events = data.get("events", [])
    cursor = data.get("cursor", "")

    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("📁 Kalshi Events")
    lines.append("=" * 60)
    lines.append(f"Found {len(events)} events\n")

    for i, event in enumerate(events, 1):
        lines.append(format_event_summary(event, i))
        lines.append("")  # Blank line between events

    if cursor:
        lines.append("─" * 60)
        lines.append(f"📄 More results available. Use --cursor {cursor[:20]}...")

    lines.append("=" * 60)
    return "\n".join(lines)


@click.command()
@click.option("--limit", default=10, type=int, help="Number of events to return (1-200)")
@click.option(
    "--status", type=click.Choice(["open", "closed", "settled"]), help="Event status filter"
)
@click.option("--series-ticker", help="Filter by series ticker")
@click.option("--with-markets", is_flag=True, help="Include nested markets in response")
@click.option("--cursor", help="Pagination cursor for next page")
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(
    limit: int,
    status: str | None,
    series_ticker: str | None,
    with_markets: bool,
    cursor: str | None,
    output_json: bool,
):
    """
    List events (collections of related markets).

    Events group related markets together, such as all markets
    for a specific date or competition.
    No authentication required.
    """
    try:
        # Validate limit
        if limit < 1 or limit > 200:
            raise ValueError("Limit must be between 1 and 200")

        # Get events from API
        with KalshiClient() as client:
            data = client.get_events(
                limit=limit,
                status=status,
                series_ticker=series_ticker,
                with_nested_markets=with_markets,
                cursor=cursor,
            )

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(data, indent=2))
        else:
            # Human-readable output
            formatted = format_events_list(data)
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
