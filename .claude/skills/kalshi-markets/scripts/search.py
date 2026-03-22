#!/usr/bin/env python3
# /// script
# dependencies = [
#     "httpx",
#     "click",
#     "pandas",
# ]
# ///

"""
Kalshi Market Search Script

Search for markets by keyword across titles and descriptions.
Uses a local cache for fast, comprehensive searches across all markets.

The cache is built on first run (takes 2-5 minutes) and refreshed every 6 hours.
Subsequent searches are instant.

Usage:
    uv run search.py bitcoin
    uv run search.py "election"
    uv run search.py keyword --limit 5
    uv run search.py keyword --json
    uv run search.py --rebuild-cache  # Force cache rebuild
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click
import httpx
import pandas as pd

# Configuration
API_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
API_TIMEOUT = 30.0  # seconds
USER_AGENT = "Kalshi-CLI/1.0"
# Use user cache directory for portable installation
# This works regardless of where the script is installed (marketplace, manual, development)
CACHE_DIR = Path.home() / ".cache" / "kalshi-markets"
CACHE_TTL_HOURS = 6


class KalshiSearchCache:
    """Embedded search cache functionality for fast market searches"""

    def __init__(self):
        """Initialize cache manager"""
        self.cache_dir = CACHE_DIR
        self.cache_ttl = timedelta(hours=CACHE_TTL_HOURS)
        self.df_cache = None

    def get_cache_file(self) -> Path | None:
        """Get the most recent cache file"""
        if not self.cache_dir.exists():
            return None

        # Look for CSV cache files with pattern kalshi_markets_*.csv
        cache_files = list(self.cache_dir.glob("kalshi_markets_*.csv"))
        if not cache_files:
            return None

        # Return the most recent file
        return max(cache_files, key=lambda f: f.stat().st_mtime)

    def is_cache_valid(self) -> bool:
        """Check if cache exists and is still valid"""
        cache_file = self.get_cache_file()
        if not cache_file:
            return False

        # Check cache age
        cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
        return cache_age < self.cache_ttl

    def load_cache(self, quiet: bool = False) -> pd.DataFrame | None:
        """Load cache from disk if valid"""
        if not self.is_cache_valid():
            return None

        cache_file = self.get_cache_file()
        if not cache_file:
            return None

        try:
            df = pd.read_csv(cache_file)
            if not quiet:
                print(f"[CACHE] Loaded {len(df)} markets from cache")
            return df
        except Exception as e:
            if not quiet:
                print(f"[CACHE] Failed to load cache: {e}")
            return None

    def save_cache(self, df: pd.DataFrame, quiet: bool = False):
        """Save DataFrame to cache"""
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            # Use timestamp in filename like the CLI does
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            cache_file = self.cache_dir / f"kalshi_markets_{timestamp}.csv"
            df.to_csv(cache_file, index=False)
            if not quiet:
                print(f"[CACHE] Saved {len(df)} markets to cache")
        except Exception as e:
            if not quiet:
                print(f"[CACHE] Failed to save cache: {e}")

    def build_cache(self, client: "KalshiClient", quiet: bool = False) -> pd.DataFrame:
        """Build complete market cache by fetching all series and their markets"""
        if not quiet:
            print("[CACHE BUILD] Starting market data collection...")
            print("[CACHE BUILD] This may take 2-5 minutes on first run...")
            print("[CACHE BUILD] Fetching all series and their markets...")

        # Step 1: Fetch all series
        if not quiet:
            print("[CACHE BUILD] Step 1/2: Fetching series list...")
        series_data = client.get_series_list()
        all_series = series_data.get("series", [])
        if not quiet:
            print(f"[CACHE BUILD] Found {len(all_series)} series to process")

        # Step 2: Fetch markets for each series
        if not quiet:
            print("[CACHE BUILD] Step 2/2: Fetching markets from each series...")
            print("[CACHE BUILD] Filter: status='open' (active tradeable markets only)")

        all_markets = []
        series_with_markets = 0
        errors = 0

        for i, series in enumerate(all_series):
            series_ticker = series.get("ticker")
            series_title = series.get("title", "")
            series_category = series.get("category", "")

            if not quiet and (i + 1) % 100 == 0:
                print(
                    f"[CACHE BUILD] Progress: {i + 1}/{len(all_series)} series ({100*(i+1)/len(all_series):.1f}%)"
                )
                print(f"[CACHE BUILD]   Markets collected: {len(all_markets)}")

            try:
                # Fetch markets for this series (open markets only)
                markets_data = client.get_markets(
                    limit=100, status="open", series_ticker=series_ticker
                )
                series_markets = markets_data.get("markets", [])

                if series_markets:
                    series_with_markets += 1

                # Add series info to each market
                for market in series_markets:
                    market["series_ticker"] = series_ticker
                    market["series_title"] = series_title
                    market["series_category"] = series_category
                    all_markets.append(market)

            except Exception:
                errors += 1
                if errors > 50:
                    if not quiet:
                        print(f"[CACHE BUILD] Too many errors ({errors}), stopping")
                    break
                continue

        if not quiet:
            print("[CACHE BUILD] Collection complete!")
            print(f"[CACHE BUILD]   Total markets: {len(all_markets)}")
            print(f"[CACHE BUILD]   Series with markets: {series_with_markets}")

        # Convert to DataFrame
        df = pd.DataFrame(all_markets) if all_markets else pd.DataFrame()

        # Save to cache
        self.save_cache(df, quiet=quiet)

        return df

    def search(self, keyword: str, limit: int = 10, quiet: bool = False) -> list[dict[str, Any]]:
        """Search markets using cache"""
        # Load or build cache
        if self.df_cache is None:
            self.df_cache = self.load_cache(quiet=quiet)

        if self.df_cache is None:
            # Need to build cache
            if not quiet:
                print("[CACHE] No valid cache found, building...")
            with KalshiClient() as client:
                self.df_cache = self.build_cache(client, quiet=quiet)

        # Perform search
        keyword_lower = keyword.lower()

        # Create mask for matching rows (include series fields for better search)
        mask = (
            self.df_cache["title"].str.lower().str.contains(keyword_lower, na=False)
            | self.df_cache["subtitle"].str.lower().str.contains(keyword_lower, na=False)
            | self.df_cache["ticker"].str.lower().str.contains(keyword_lower, na=False)
        )

        # Add series fields if they exist in the DataFrame
        if "series_title" in self.df_cache.columns:
            mask = mask | self.df_cache["series_title"].str.lower().str.contains(
                keyword_lower, na=False
            )
        if "series_ticker" in self.df_cache.columns:
            mask = mask | self.df_cache["series_ticker"].str.lower().str.contains(
                keyword_lower, na=False
            )

        # Get matching markets
        matches = self.df_cache[mask]

        # Sort by volume and limit results
        if "volume_24h" in matches.columns:
            matches = matches.sort_values("volume_24h", ascending=False)

        matches = matches.head(limit)

        # Convert back to list of dicts
        return matches.to_dict("records")


class KalshiClient:
    """Minimal HTTP client for Kalshi API - search functionality"""

    def __init__(self):
        """Initialize HTTP client"""
        self.client = httpx.Client(
            base_url=API_BASE_URL,
            timeout=API_TIMEOUT,
            headers={"User-Agent": USER_AGENT},
        )

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup"""
        self.client.close()

    def get_series_list(self) -> dict[str, Any]:
        """
        Get list of all series.

        Returns:
            Dict with 'series' array

        Raises:
            Exception if API call fails
        """
        try:
            response = self.client.get("/series")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"API error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error: {str(e)}")

    def get_markets(
        self,
        limit: int = 100,
        status: str | None = "open",
        cursor: str = None,
        series_ticker: str | None = None,
    ) -> dict[str, Any]:
        """
        Get markets for searching.

        Args:
            limit: Number of markets to fetch
            status: Market status filter (None for all statuses)
            cursor: Pagination cursor
            series_ticker: Filter by series ticker

        Returns:
            Dict with markets array and cursor

        Raises:
            Exception if API call fails
        """
        params = {"limit": str(min(limit, 1000))}
        if status is not None:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        if series_ticker:
            params["series_ticker"] = series_ticker

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


def format_search_result(market: dict[str, Any], index: int) -> str:
    """Format a single search result"""
    ticker = market.get("ticker", "N/A")
    title = market.get("title", "N/A")
    yes_bid = market.get("yes_bid", 0)
    yes_ask = market.get("yes_ask", 0)
    last_price = market.get("last_price", 0)
    volume_24h = market.get("volume_24h", 0)
    status = market.get("status", "unknown")

    status_icon = "🟢" if status == "active" else "🔴"

    lines = []
    lines.append(f"{index}. {status_icon} {ticker}")
    lines.append(f"   {title[:70]}{'...' if len(title) > 70 else ''}")

    if yes_bid or yes_ask:
        lines.append(f"   Price: Bid {yes_bid}¢ | Ask {yes_ask}¢ | Last {last_price}¢")

    if volume_24h > 0:
        lines.append(f"   24h Volume: ${volume_24h/100:,.2f}")

    return "\n".join(lines)


def format_search_results(keyword: str, results: list[dict[str, Any]]) -> str:
    """
    Format search results for human-readable output.

    Args:
        keyword: Search keyword
        results: List of matching markets

    Returns:
        Formatted string for display
    """
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append(f"🔍 Search Results for '{keyword}'")
    lines.append("=" * 60)

    if not results:
        lines.append("\nNo markets found matching your search.")
        lines.append("\nTip: Try broader keywords.")
    else:
        lines.append(f"Found {len(results)} matching markets:\n")

        for i, market in enumerate(results, 1):
            lines.append(format_search_result(market, i))
            lines.append("")

        lines.append("─" * 60)
        lines.append("Note: Searches across all ~6900 markets using local cache.")
        lines.append("Cache refreshes automatically every 6 hours.")

    lines.append("=" * 60)
    return "\n".join(lines)


@click.command()
@click.argument("keyword", required=False)
@click.option("--limit", default=10, type=int, help="Maximum number of results to return")
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output as JSON instead of human-readable format",
)
@click.option("--rebuild-cache", is_flag=True, help="Force rebuild of the market cache")
def main(keyword: str, limit: int, output_json: bool, rebuild_cache: bool):
    """
    Search for markets by keyword using cached data.

    KEYWORD is the search term to look for in market titles and descriptions.

    Uses a local cache for fast searches across all ~6900 markets.
    Cache is built on first run (2-5 minutes) and refreshed every 6 hours.
    No authentication required.
    """
    try:
        # Initialize cache
        cache = KalshiSearchCache()

        # Handle cache rebuild
        if rebuild_cache:
            if not output_json:
                click.echo("Rebuilding market cache...")

            # Delete existing cache files
            if cache.cache_dir.exists():
                for old_cache in cache.cache_dir.glob("kalshi_markets_*.csv"):
                    old_cache.unlink()

            # Rebuild
            with KalshiClient() as client:
                cache.build_cache(client, quiet=output_json)

            if not output_json:
                click.echo("✅ Cache rebuilt successfully!")

            if not keyword:
                sys.exit(0)

        # Require keyword for search
        if not keyword:
            raise ValueError("Keyword is required for search (or use --rebuild-cache)")

        if not keyword.strip():
            raise ValueError("Keyword cannot be empty")

        # Search using cache
        results = cache.search(keyword, limit=limit, quiet=output_json)

        # Output results
        if output_json:
            # JSON output for automation/MCP
            click.echo(json.dumps(results, indent=2))
        else:
            # Human-readable output
            formatted = format_search_results(keyword, results)
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
