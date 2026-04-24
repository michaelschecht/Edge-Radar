"""
check_odds_keys.py — Inspect Odds API key quota.

Two modes:

    # Default: read the persistent quota cache (free, no API calls).
    # As accurate as the last scan / R23 persistence write.
    python scripts/shared/check_odds_keys.py

    # Live probe: hit /v4/sports against every configured key and update
    # the cache with fresh x-requests-remaining values. Costs 1 request
    # per key (10 keys == 10 requests).
    python scripts/shared/check_odds_keys.py --live

The live probe writes results to `data/cache/odds_api_quota.json` via the
same `report_remaining()` / `mark_exhausted()` helpers the scanners use,
so the on-disk cache stays consistent with what downstream runs will see.
"""

import argparse
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

# Ensure shared dir is on sys.path when invoked as a script
_SHARED = Path(__file__).resolve().parent
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))

load_dotenv()
from odds_api import (  # noqa: E402
    _keys, _load_keys, _remaining, _QUOTA_CACHE_PATH,
    mark_exhausted, report_remaining,
)

PROBE_URL = "https://api.the-odds-api.com/v4/sports"


def _probe_key(key: str) -> tuple[int, str, str]:
    """Hit /v4/sports with this key. Returns (status, remaining, used)."""
    try:
        resp = requests.get(PROBE_URL, params={"apiKey": key}, timeout=10)
        rem = resp.headers.get("x-requests-remaining", "?")
        used = resp.headers.get("x-requests-used", "?")
        return resp.status_code, rem, used
    except requests.RequestException as e:
        return 0, "ERR", str(e)[:40]


def _print_row(idx: int, key: str, status: object, remaining: object, used: object):
    print(f"  {idx:<3} ...{key[-6:]:<8} {str(status):<8} {str(remaining):<12} {str(used):<8}")


def _print_header():
    print(f"  {'#':<3} {'key':<11} {'status':<8} {'remaining':<12} {'used':<8}")
    print("  " + "-" * 50)


def cmd_cache_view():
    _load_keys()
    if not _keys:
        print("No Odds API keys configured (check ODDS_API_KEYS / ODDS_API_KEY in .env).")
        return 1

    print(f"Configured keys: {len(_keys)}")
    print(f"Cache file:      {_QUOTA_CACHE_PATH}")
    print(f"Cache exists:    {_QUOTA_CACHE_PATH.exists()}")
    if not _remaining:
        print("\n(No cached quota data yet. Run with --live to probe.)")
        return 0

    print()
    _print_header()
    total_remaining = 0
    for i, key in enumerate(_keys):
        rem = _remaining.get(key)
        rem_display = "unknown" if rem is None else str(rem)
        _print_row(i, key, "cached", rem_display, "")
        if isinstance(rem, int) and rem > 0:
            total_remaining += rem

    print()
    print(f"Total remaining across healthy keys: {total_remaining}")
    return 0


def cmd_live_probe():
    _load_keys()
    if not _keys:
        print("No Odds API keys configured (check ODDS_API_KEYS / ODDS_API_KEY in .env).")
        return 1

    print(f"Probing {len(_keys)} keys against {PROBE_URL} (this costs 1 request per key)...\n")
    _print_header()
    total_remaining = 0
    for i, key in enumerate(_keys):
        status, rem, used = _probe_key(key)
        _print_row(i, key, status, rem, used)
        # Update the persistent cache with whatever we learned
        if status == 401:
            mark_exhausted(key)
        else:
            try:
                report_remaining(key, int(rem))
                if int(rem) > 0:
                    total_remaining += int(rem)
            except (ValueError, TypeError):
                pass
        time.sleep(0.3)  # gentle on the API

    print()
    print(f"Total remaining across healthy keys: {total_remaining}")
    print(f"Cache updated: {_QUOTA_CACHE_PATH}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Inspect Odds API key quota (cache view by default; --live to probe).",
    )
    parser.add_argument(
        "--live", action="store_true",
        help="Probe each key via /v4/sports (costs 1 request per key) and update the cache.",
    )
    args = parser.parse_args()
    return cmd_live_probe() if args.live else cmd_cache_view()


if __name__ == "__main__":
    sys.exit(main())
