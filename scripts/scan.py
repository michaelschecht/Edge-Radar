"""
scan.py — Unified scan entry point for Edge-Radar.

Routes to the correct scanner based on market type:

    python scripts/scan.py sports --filter mlb --date tomorrow --exclude-open
    python scripts/scan.py futures --filter nba-futures --save
    python scripts/scan.py prediction --filter crypto --cross-ref
    python scripts/scan.py polymarket --filter crypto --min-edge 0.05

All flags are forwarded directly to the underlying scanner.
Run any subcommand with --help to see its full flag list.
"""

import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

SCANNERS = {
    "sports":     PROJECT_ROOT / "scripts" / "kalshi"      / "edge_detector.py",
    "futures":    PROJECT_ROOT / "scripts" / "kalshi"      / "futures_edge.py",
    "prediction": PROJECT_ROOT / "scripts" / "prediction"  / "prediction_scanner.py",
    "polymarket": PROJECT_ROOT / "scripts" / "polymarket"  / "polymarket_edge.py",
}

ALIASES = {
    "sport": "sports",
    "pred":  "prediction",
    "poly":  "polymarket",
    "xref":  "polymarket",
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
    remaining = sys.argv[2:]

    # Insert 'scan' subcommand if not already provided
    if not remaining or remaining[0].startswith("-"):
        remaining = ["scan"] + remaining

    cmd = [str(PYTHON), str(script)] + remaining
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    sys.exit(result.returncode)


def print_help():
    print("""Edge-Radar Unified Scanner
=========================

Usage:  python scripts/scan.py <market-type> [flags]

Market types:
  sports       Kalshi sports betting (NBA, NHL, MLB, NFL, NCAA, etc.)
  futures      Championship & season-long futures
  prediction   Crypto, weather, S&P 500, politics
  polymarket   Polymarket cross-reference edge detection

Aliases:  sport, pred, poly, xref

Common flags (all scanners):
  --filter X       Filter by sport/asset/category
  --min-edge N     Minimum edge threshold (default 0.03)
  --top N          Number of top opportunities (default 20)
  --save           Save markdown report
  --execute        Execute bets (requires confirmation)
  --unit-size N    Dollar amount per bet
  --max-bets N     Max bets to place (default 5)
  --date X         Filter by date (today, tomorrow, YYYY-MM-DD, mar31)
  --exclude-open   Skip markets with open positions
  --pick X         Comma-separated row numbers to execute
  --ticker X       Execute specific tickers only

Examples:
  python scripts/scan.py sports --filter mlb --date today --save
  python scripts/scan.py futures --filter nba-futures --top 10
  python scripts/scan.py prediction --filter crypto --cross-ref
  python scripts/scan.py polymarket --filter crypto --min-edge 0.05

Run with <market-type> --help for the full flag list of each scanner.""")


if __name__ == "__main__":
    main()
