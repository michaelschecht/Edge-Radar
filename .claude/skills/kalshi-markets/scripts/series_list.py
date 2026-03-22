#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Series List Script

List all available series (market templates).
Completely self-contained with embedded HTTP client.

Usage:
    uv run series_list.py
    uv run series_list.py --category Politics
    uv run series_list.py --json
"""

import json
import sys
from typing import Any

import click
import httpx

# Configuration
API_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_TIMEOUT = 60.0  # Longer timeout for large series list
USER_AGENT = "Kalshi-CLI/1.0"


class KalshiClient:
    """Minimal HTTP client for Kalshi API - series list functionality"""

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

    def get_series_list(
        self, category: str | None = None, tags: str | None = None
    ) -> dict[str, Any]:
        """
        Get list of all series.

        Args:
            category: Filter by category
            tags: Filter by tags (comma-separated)

        Returns:
            Dict with 'series' array

        Raises:
            Exception if API call fails
        """
        params = {}
        if category:
            params["category"] = category
        if tags:
            params["tags"] = tags

        try:
            response = self.client.get("/series", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")


def format_series_summary(series: dict[str, Any]) -> str:
    """Format a single series for display"""
    ticker = series.get("ticker", "N/A")
    title = series.get("title", "N/A")
    category = series.get("category", "N/A")
    frequency = series.get("frequency", "N/A")
    tags = series.get("tags", [])

    lines = []
    lines.append(f"📈 {ticker}")
    lines.append(f"   {title[:60]}{'...' if len(title) > 60 else ''}")
    lines.append(f"   Category: {category} | Frequency: {frequency}")

    if tags:
        tags_str = ", ".join(tags[:3])
        if len(tags) > 3:
            tags_str += f" (+{len(tags)-3} more)"
        lines.append(f"   Tags: {tags_str}")

    return "\n".join(lines)


def format_series_list(data: dict[str, Any], limit: int = 50) -> str:
    """
    Format series list for human-readable output.

    Args:
        data: Response data with series array
        limit: Number of series to display (rest shown as count)

    Returns:
        Formatted string for display
    """
    series_list = data.get("series", [])
    total_count = len(series_list)

    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("📚 Kalshi Series (Market Templates)")
    lines.append("=" * 60)
    lines.append(f"Total: {total_count} series available\n")

    # Group by category
    categories = {}
    for series in series_list:
        cat = series.get("category", "Uncategorized")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(series)

    # Show summary by category
    lines.append("📂 By Category:")
    lines.append("─" * 40)
    for cat in sorted(categories.keys()):
        count = len(categories[cat])
        lines.append(f"   {cat}: {count} series")
    lines.append("")

    # Show first N series
    display_count = min(limit, total_count)
    lines.append(f"📋 First {display_count} Series:")
    lines.append("─" * 60)

    for i, series in enumerate(series_list[:display_count], 1):
        lines.append(f"{i}. {format_series_summary(series)}")
        lines.append("")

    if total_count > display_count:
        lines.append(f"... and {total_count - display_count} more series")
        lines.append("\nTip: Use --json to get full list for processing")

    lines.append("=" * 60)
    return "\n".join(lines)


@click.command()
@click.option("--category", help="Filter by category (e.g., Politics, Economics)")
@click.option("--tags", help="Filter by tags (comma-separated)")
@click.option(
    "--limit", default=50, type=int, help="Number of series to display in human-readable mode"
)
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(category: str | None, tags: str | None, limit: int, output_json: bool):
    """
    List all available series (market templates).

    Series are templates for creating markets. There are ~6900 series available.
    No authentication required.

    Note: This returns a large dataset. Use filters to narrow results.
    """
    try:
        # Get series list from API
        with KalshiClient() as client:
            data = client.get_series_list(category=category, tags=tags)

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(data, indent=2))
        else:
            # Human-readable output (limited display)
            formatted = format_series_list(data, limit=limit)
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
