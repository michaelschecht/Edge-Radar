#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Market Orderbook Script

Get the current orderbook for a specific Kalshi prediction market.
Completely self-contained with embedded HTTP client.

Usage:
    uv run orderbook.py TICKER
    uv run orderbook.py TICKER --depth 5
    uv run orderbook.py TICKER --json
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
    """Minimal HTTP client for Kalshi API - orderbook functionality"""

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

    def get_market_orderbook(self, ticker: str, depth: int = 10) -> dict[str, Any]:
        """
        Get the orderbook for a specific market.

        Args:
            ticker: Market ticker symbol
            depth: Orderbook depth (0 = all levels, 1-100 for specific depth)

        Returns:
            Dict with 'orderbook' containing yes/no bid arrays

        Raises:
            Exception if API call fails
        """
        params = {}
        if depth > 0:
            params["depth"] = str(depth)

        try:
            response = self.client.get(f"/markets/{ticker}/orderbook", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Market not found: {ticker}")
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")


def format_orderbook_level(price: int, quantity: int) -> str:
    """Format a single orderbook level"""
    return f"  {price:>5}¢  │  {quantity:>10,} contracts"


def format_orderbook(ticker: str, data: dict[str, Any], depth: int) -> str:
    """
    Format orderbook for human-readable output.

    Args:
        ticker: Market ticker
        data: Response data with orderbook
        depth: Display depth limit

    Returns:
        Formatted string for display
    """
    orderbook = data.get("orderbook", {})
    yes_orders = orderbook.get("yes", [])
    no_orders = orderbook.get("no", [])

    lines = []
    lines.append("\n" + "=" * 60)
    lines.append(f"📊 Orderbook for {ticker}")
    lines.append("=" * 60)

    # YES side
    lines.append("\n✅ YES Side (Bids to buy YES):")
    lines.append("  Price  │   Quantity")
    lines.append("─" * 30)

    if yes_orders:
        display_count = depth if depth > 0 else len(yes_orders)
        for order in yes_orders[:display_count]:
            if len(order) >= 2:
                lines.append(format_orderbook_level(order[0], order[1]))

        if len(yes_orders) > display_count:
            lines.append(f"  ... {len(yes_orders) - display_count} more levels ...")
    else:
        lines.append("  (no orders)")

    # NO side
    lines.append("\n❌ NO Side (Bids to buy NO):")
    lines.append("  Price  │   Quantity")
    lines.append("─" * 30)

    if no_orders:
        display_count = depth if depth > 0 else len(no_orders)
        for order in no_orders[:display_count]:
            if len(order) >= 2:
                lines.append(format_orderbook_level(order[0], order[1]))

        if len(no_orders) > display_count:
            lines.append(f"  ... {len(no_orders) - display_count} more levels ...")
    else:
        lines.append("  (no orders)")

    # Summary
    lines.append("\n" + "─" * 60)

    # Calculate spread if we have orders
    if yes_orders and no_orders:
        yes_best = yes_orders[0][0] if yes_orders[0] else 0
        implied_prob = yes_best  # YES bid price is the implied probability
        lines.append(f"📈 Implied Probability: {implied_prob}%")

    lines.append(f"📊 Total Levels: YES={len(yes_orders)}, NO={len(no_orders)}")

    lines.append("=" * 60)
    return "\n".join(lines)


@click.command()
@click.argument("ticker")
@click.option(
    "--depth", default=10, type=int, help="Orderbook depth (0=all levels, 1-100 for specific depth)"
)
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(ticker: str, depth: int, output_json: bool):
    """
    Get orderbook for a specific market.

    TICKER is the market ticker symbol.

    Shows bid levels for both YES and NO sides of the market.
    No authentication required.
    """
    try:
        # Validate depth
        if depth < 0 or depth > 100:
            raise ValueError("Depth must be between 0 and 100")

        # Get orderbook from API
        with KalshiClient() as client:
            data = client.get_market_orderbook(ticker, depth)

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(data, indent=2))
        else:
            # Human-readable output
            formatted = format_orderbook(ticker, data, depth)
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
