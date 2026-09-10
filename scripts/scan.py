"""
scan.py — Unified scan entry point for Edge-Radar.

Routes to the correct scanner based on market type:

    python scripts/scan.py sports --filter mlb --date tomorrow --exclude-open
    python scripts/scan.py futures --filter nba-futures --save
    python scripts/scan.py prediction --filter crypto

All flags are forwarded directly to the underlying scanner.
Run any subcommand with --help to see its full flag list.
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

SCANNERS = {
    "sports":     PROJECT_ROOT / "scripts" / "kalshi"      / "edge_detector.py",
    "futures":    PROJECT_ROOT / "scripts" / "kalshi"      / "futures_edge.py",
    "prediction": PROJECT_ROOT / "scripts" / "prediction"  / "prediction_scanner.py",
    "polymarket": PROJECT_ROOT / "scripts" / "polymarket"  / "polymarket_futures_edge.py",
}

ALIASES = {
    "sport": "sports",
    "pred":  "prediction",
    "poly":  "polymarket",
    "pm":    "polymarket",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print_help()
        sys.exit(0)

    market_type = sys.argv[1].lower()
    market_type = ALIASES.get(market_type, market_type)

    if market_type not in SCANNERS:
        print(f"Unknown market type: '{sys.argv[1]}'")
        print(f"Valid types: {', '.join(SCANNERS)}")
        sys.exit(1)

    script = SCANNERS[market_type]
    remaining, profile = _extract_profile(sys.argv[2:])

    # Insert 'scan' subcommand if not already provided
    if not remaining or remaining[0].startswith("-"):
        remaining = ["scan"] + remaining

    # P1: the profile travels to the scanner as an env var, not a flag — the
    # scanners take no `--profile` of their own, and `app.config` applies the
    # `.env.<name>` overlay on first `get_config()` in the child. A fresh
    # process is exactly the right boundary: nothing is memoized across it, and
    # `load_dotenv()` in the child will not override what we set here.
    env = dict(os.environ)  # config-bootstrap: building a CHILD env, not reading a setting
    if profile:
        env["EDGE_RADAR_PROFILE"] = profile

    cmd = [str(PYTHON), str(script)] + remaining
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), env=env)
    sys.exit(result.returncode)


def _extract_profile(args: list[str]) -> tuple[list[str], str | None]:
    """Pull `--profile <name>` / `--profile=<name>` out of the forwarded flags.

    Consumed here rather than forwarded: every scanner would otherwise need its
    own identical argparse entry, and one that forgot would run the base `.env`
    against whatever wallet the operator thought they had selected.
    """
    out: list[str] = []
    profile: str | None = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--profile":
            if i + 1 >= len(args) or args[i + 1].startswith("-"):
                print("--profile needs a name, e.g. --profile longshot")
                sys.exit(2)
            profile = args[i + 1]
            i += 2
            continue
        if arg.startswith("--profile="):
            profile = arg.split("=", 1)[1]
            if not profile:
                print("--profile needs a name, e.g. --profile longshot")
                sys.exit(2)
            i += 1
            continue
        out.append(arg)
        i += 1
    return out, profile


def print_help():
    print("""Edge-Radar Unified Scanner
=========================

Usage:  python scripts/scan.py <market-type> [flags]

Market types:
  sports       Kalshi sports betting (NBA, NHL, MLB, NFL, NCAA, etc.)
  futures      Championship & season-long futures
  prediction   Crypto, weather, S&P 500, politics
  polymarket   Polymarket US futures + games (execution wired; orders blocked
               until DRY_RUN=false AND POLYMARKET_DRY_RUN=false)

Aliases:  sport, pred, poly, pm

Common flags (all scanners):
  --filter X       Filter by sport/asset/category
  --min-edge N     Minimum edge threshold (default 0.03)
  --top N          Number of top opportunities (default 20)
  --save           Save markdown report
  --execute        Execute bets (requires confirmation)
  --unit-size N    Dollar amount per bet
  --max-bets N     Max bets to place (default 5)
  --budget X       Max total cost per batch (e.g. '10%' or '15')
  --date X         Filter by date (today, tomorrow, YYYY-MM-DD, mar31)
  --exclude-open   Skip markets with open positions
  --pick X         Comma-separated row numbers to execute
  --ticker X       Execute specific tickers only

Examples:
  python scripts/scan.py sports --filter mlb --date today --save
  python scripts/scan.py futures --filter nba-futures --top 10
  python scripts/scan.py prediction --filter crypto
  python scripts/scan.py polymarket --filter worldcup

Run with <market-type> --help for the full flag list of each scanner.""")


if __name__ == "__main__":
    main()
