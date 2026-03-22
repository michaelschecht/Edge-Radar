#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Market Details Script

Get detailed information for a specific Kalshi prediction market.
Completely self-contained with embedded HTTP client.

Usage:
    uv run market.py TICKER
    uv run market.py KXBTCD-25NOV0612-T102499.99
    uv run market.py TICKER --json
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
    """Minimal HTTP client for Kalshi API - market details functionality"""

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

    def get_market(self, ticker: str) -> dict[str, Any]:
        """
        Get detailed information for a specific market.

        Args:
            ticker: Market ticker symbol

        Returns:
            Complete market details including prices, volume, status

        Raises:
            Exception if API call fails
        """
        try:
            response = self.client.get(f"/markets/{ticker}")
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


def format_timestamp(timestamp_str: str) -> str:
    """Format ISO timestamp to readable string"""
    if not timestamp_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return timestamp_str


def format_market_detail(market: dict[str, Any]) -> str:
    """
    Format market details for human-readable output.

    Args:
        market: Market data from API

    Returns:
        Formatted string for display
    """
    lines = []
    lines.append("\n" + "=" * 80)
    lines.append(f"Market: {market.get('ticker', 'N/A')}")
    lines.append("=" * 80)

    # Title and subtitle
    title = market.get("title", "N/A")
    subtitle = market.get("subtitle", "")
    lines.append(f"\n📌 {title}")
    if subtitle:
        lines.append(f"   {subtitle}")

    # Status and category
    status = market.get("status", "unknown")
    category = market.get("category", "N/A")
    status_icon = "🟢" if status == "active" else "🔴" if status == "closed" else "⚫"
    lines.append(f"\n{status_icon} Status: {status.upper()}")
    lines.append(f"📂 Category: {category}")

    # Current prices
    lines.append("\n💰 Current Prices:")
    yes_bid = market.get("yes_bid", 0)
    yes_ask = market.get("yes_ask", 0)
    no_bid = market.get("no_bid", 0)
    no_ask = market.get("no_ask", 0)
    last_price = market.get("last_price", 0)

    lines.append(f"   YES: Bid {yes_bid}¢ | Ask {yes_ask}¢")
    lines.append(f"   NO:  Bid {no_bid}¢ | Ask {no_ask}¢")
    lines.append(f"   Last Trade: {last_price}¢")

    # Trading activity
    lines.append("\n📊 Trading Activity:")
    volume = market.get("volume", 0)
    volume_24h = market.get("volume_24h", 0)
    open_interest = market.get("open_interest", 0)
    liquidity = market.get("liquidity", 0)

    lines.append(f"   Total Volume: ${volume/100:,.2f}")
    lines.append(f"   24h Volume: ${volume_24h/100:,.2f}")
    lines.append(f"   Open Interest: ${open_interest/100:,.2f}")
    lines.append(f"   Liquidity: ${liquidity/100:,.2f}")

    # Schedule
    lines.append("\n📅 Schedule:")
    open_time = format_timestamp(market.get("open_time"))
    close_time = format_timestamp(market.get("close_time"))
    expiration_time = format_timestamp(market.get("expiration_time"))

    lines.append(f"   Opens: {open_time}")
    lines.append(f"   Closes: {close_time}")
    lines.append(f"   Expires: {expiration_time}")

    # Result if settled
    result = market.get("result")
    if result:
        lines.append(f"\n✅ Result: {result}")

    # Rules if present
    rules_primary = market.get("rules_primary", "").strip()
    if rules_primary:
        lines.append("\n📋 Rules:")
        # Wrap long rules text
        import textwrap

        wrapped = textwrap.wrap(rules_primary, width=70)
        for line in wrapped[:5]:  # Limit to 5 lines
            lines.append(f"   {line}")
        if len(wrapped) > 5:
            lines.append("   ...")

    lines.append("\n" + "=" * 80)
    return "\n".join(lines)


@click.command()
@click.argument("ticker")
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(ticker: str, output_json: bool):
    """
    Get detailed information for a specific market.

    TICKER is the market ticker symbol (e.g., KXBTCD-25NOV0612-T102499.99)

    Returns comprehensive market details including prices, volume, and status.
    No authentication required.
    """
    try:
        # Get market details from API
        with KalshiClient() as client:
            data = client.get_market(ticker)

        # Handle nested market object if present
        market = data.get("market", data)

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(market, indent=2))
        else:
            # Human-readable output
            formatted = format_market_detail(market)
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
