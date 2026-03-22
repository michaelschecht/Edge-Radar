#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
# ]
# ///

"""
Kalshi Exchange Status Script

Check if the Kalshi exchange and trading are active.
Completely self-contained with embedded HTTP client.

Usage:
    uv run status.py
    uv run status.py --json
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
    """Minimal HTTP client for Kalshi API - just what we need for status"""

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

    def get_exchange_status(self) -> dict[str, Any]:
        """
        Get the current exchange status.

        Returns:
            Dict with exchange_active, trading_active, and estimated_resume_time

        Raises:
            Exception if API call fails
        """
        try:
            response = self.client.get("/exchange/status")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")


def format_status(status_data: dict[str, Any]) -> str:
    """
    Format status data for human-readable output.

    Args:
        status_data: The status response from API

    Returns:
        Formatted string for display
    """
    lines = []
    lines.append("\nKalshi Exchange Status")
    lines.append("=" * 40)

    exchange_active = status_data.get("exchange_active", None)
    trading_active = status_data.get("trading_active", None)
    resume_time = status_data.get("exchange_estimated_resume_time")

    # Exchange status
    if exchange_active is True:
        lines.append("📈 Exchange: ACTIVE ✓")
    elif exchange_active is False:
        lines.append("🔴 Exchange: INACTIVE ✗")
    else:
        lines.append("❓ Exchange: Unknown")

    # Trading status
    if trading_active is True:
        lines.append("💹 Trading:  ACTIVE ✓")
    elif trading_active is False:
        lines.append("🔴 Trading:  INACTIVE ✗")
    else:
        lines.append("❓ Trading:  Unknown")

    # Resume time if available
    if resume_time:
        lines.append(f"🕐 Resume:   {resume_time}")

    lines.append("=" * 40)
    return "\n".join(lines)


@click.command()
@click.option(
    "--json", "output_json", is_flag=True, help="Output as JSON instead of human-readable format"
)
def main(output_json: bool):
    """
    Check Kalshi exchange status.

    Returns current exchange and trading status.
    No authentication required.
    """
    try:
        # Get status from API
        with KalshiClient() as client:
            status_data = client.get_exchange_status()

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(status_data, indent=2))
        else:
            # Human-readable output
            formatted = format_status(status_data)
            click.echo(formatted)

        # Exit code based on status
        if status_data.get("trading_active"):
            sys.exit(0)
        else:
            sys.exit(1)  # Non-zero if trading inactive

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
