#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Series Details Script

Get detailed information about a specific series.
Completely self-contained with embedded HTTP client.

Usage:
    uv run series.py SERIES_TICKER
    uv run series.py KXHIGHNY
    uv run series.py SERIES_TICKER --json
"""

import json
import sys
import textwrap
from typing import Any

import click
import httpx

# Configuration
API_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_TIMEOUT = 30.0  # seconds
USER_AGENT = "Kalshi-CLI/1.0"


class KalshiClient:
    """Minimal HTTP client for Kalshi API - series details functionality"""

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

    def get_series(self, series_ticker: str) -> dict[str, Any]:
        """
        Get detailed information about a specific series.

        Args:
            series_ticker: Series ticker identifier

        Returns:
            Series details including metadata and settlement sources

        Raises:
            Exception if API call fails
        """
        try:
            response = self.client.get(f"/series/{series_ticker}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise Exception(f"Series not found: {series_ticker}")
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")


def format_series_detail(data: dict[str, Any]) -> str:
    """
    Format series details for human-readable output.

    Args:
        data: Series data from API

    Returns:
        Formatted string for display
    """
    # Handle nested series object if present
    series = data.get("series", data)

    lines = []
    lines.append("\n" + "=" * 60)
    lines.append(f"📚 Series: {series.get('ticker', 'N/A')}")
    lines.append("=" * 60)

    # Title
    title = series.get("title", "N/A")
    lines.append(f"\n📌 {title}")

    # Basic info
    category = series.get("category", "N/A")
    frequency = series.get("frequency", "N/A")
    lines.append(f"\n📂 Category: {category}")
    lines.append(f"🔄 Frequency: {frequency}")

    # Tags
    tags = series.get("tags", [])
    if tags:
        lines.append(f"🏷️  Tags: {', '.join(tags)}")

    # Contract specifications
    contract_url = series.get("contract_url")
    if contract_url:
        lines.append("\n📄 Contract URL:")
        lines.append(f"   {contract_url}")

    # Description
    description = series.get("description", "").strip()
    if description:
        lines.append("\n📝 Description:")
        # Wrap long description text
        wrapped = textwrap.wrap(description, width=70)
        for line in wrapped[:10]:  # Limit to 10 lines
            lines.append(f"   {line}")
        if len(wrapped) > 10:
            lines.append("   ...")

    # Settlement sources
    sources = series.get("settlement_sources", [])
    if sources:
        lines.append("\n⚖️  Settlement Sources:")
        for source in sources:
            name = source.get("name", "N/A")
            url = source.get("url", "N/A")
            lines.append(f"   • {name}")
            if url != "N/A":
                lines.append(f"     {url}")

    # Rules
    rules_primary = series.get("rules_primary", "").strip()
    if rules_primary:
        lines.append("\n📋 Rules:")
        wrapped = textwrap.wrap(rules_primary, width=70)
        for line in wrapped[:8]:  # Limit to 8 lines
            lines.append(f"   {line}")
        if len(wrapped) > 8:
            lines.append("   ...")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)


@click.command()
@click.argument("series_ticker")
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(series_ticker: str, output_json: bool):
    """
    Get information about a specific series.

    SERIES_TICKER is the series identifier (e.g., KXHIGHNY).

    Series are templates used to create markets.
    No authentication required.
    """
    try:
        # Get series details from API
        with KalshiClient() as client:
            data = client.get_series(series_ticker)

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(data, indent=2))
        else:
            # Human-readable output
            formatted = format_series_detail(data)
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
