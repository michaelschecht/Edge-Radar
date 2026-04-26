"""
doctor.py — Startup validation for Edge-Radar.

Verifies that the environment is correctly configured before you waste
time debugging cryptic errors mid-scan.

Usage:
    python scripts/doctor.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "shared"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from rich.console import Console
from rich.table import Table

from app.config import get_config

console = Console()
cfg = get_config()

PASS = "[green]PASS[/green]"
FAIL = "[red]FAIL[/red]"
WARN = "[yellow]WARN[/yellow]"

issues = []


def check(name: str, ok: bool, detail: str = "", warn_only: bool = False):
    """Print a check result and track failures."""
    if ok:
        console.print(f"  {PASS}  {name}")
    elif warn_only:
        console.print(f"  {WARN}  {name} — {detail}")
    else:
        console.print(f"  {FAIL}  {name} — {detail}")
        issues.append(name)


def main():
    console.print("\n[bold]Edge-Radar Doctor[/bold]\n")

    # ── Python version
    console.print("[bold]Environment[/bold]")
    v = sys.version_info
    check("Python 3.11+", v.major == 3 and v.minor >= 11,
          f"Found {v.major}.{v.minor}.{v.micro} — need 3.11+")
    check("Running from venv", hasattr(sys, "real_prefix") or sys.prefix != sys.base_prefix,
          "Not in a virtual environment", warn_only=True)

    # ── Required env vars
    console.print("\n[bold]Credentials[/bold]")
    kalshi_key = cfg.kalshi.api_key
    check("KALSHI_API_KEY set", bool(kalshi_key), "Missing — required for all Kalshi operations")

    key_path = cfg.kalshi.private_key_path
    if key_path:
        full_path = PROJECT_ROOT / key_path if not Path(key_path).is_absolute() else Path(key_path)
        check("KALSHI_PRIVATE_KEY_PATH exists", full_path.exists(),
              f"File not found: {full_path}")
    else:
        check("KALSHI_PRIVATE_KEY_PATH set", False, "Missing — required for Kalshi auth")

    key_count = len(cfg.odds.keys)
    check("ODDS_API_KEYS set", key_count > 0, "Missing — required for sportsbook odds")
    if key_count > 0:
        check(f"  Odds API keys loaded: {key_count}", True)

    # ── Data directories
    console.print("\n[bold]Data Directories[/bold]")
    for name, path in [
        ("data/history/", PROJECT_ROOT / "data" / "history"),
        ("data/watchlists/", PROJECT_ROOT / "data" / "watchlists"),
        ("data/positions/", PROJECT_ROOT / "data" / "positions"),
        ("logs/", PROJECT_ROOT / "logs"),
        ("reports/Sports/", PROJECT_ROOT / "reports" / "Sports"),
    ]:
        exists = path.exists()
        if not exists:
            path.mkdir(parents=True, exist_ok=True)
            check(name, True, detail="Created")
        else:
            check(name, True)

    # ── System settings
    console.print("\n[bold]Configuration[/bold]")
    if cfg.system.dry_run:
        check("DRY_RUN = true (safe mode)", True)
    else:
        check("DRY_RUN = false (LIVE EXECUTION)", True)
        console.print("    [red bold]Orders will be placed with real money![/red bold]")

    check(f"UNIT_SIZE = ${cfg.risk.unit_size:.2f}", True)
    check(f"KELLY_FRACTION = {cfg.kelly.kelly_fraction:g}", True)
    check(f"MAX_DAILY_LOSS = ${cfg.risk.max_daily_loss:.0f}", True)
    check(f"MAX_OPEN_POSITIONS = {cfg.risk.max_open_positions}", True)
    check(f"MAX_PER_EVENT = {cfg.risk.max_per_event}", True)

    # ── Kalshi API connectivity
    console.print("\n[bold]API Connectivity[/bold]")
    if kalshi_key and key_path:
        try:
            from kalshi_client import KalshiClient
            client = KalshiClient()
            bal = client.get_balance_dollars()
            balance = bal.get("balance", 0)
            check(f"Kalshi API connected (balance: ${balance:,.2f})", True)
        except Exception as e:
            check("Kalshi API connected", False, str(e)[:80])
    else:
        check("Kalshi API connected", False, "Skipped — credentials missing")

    # Odds API — just check if keys parse, don't burn a request
    if key_count > 0:
        try:
            from odds_api import get_status
            status = get_status()
            check(f"Odds API keys loaded ({status['total_keys']} keys)", True)
        except Exception as e:
            check("Odds API keys loaded", False, str(e)[:80])
    else:
        check("Odds API keys loaded", False, "Skipped — no keys configured")

    # ── Pre-commit hooks
    console.print("\n[bold]Development Tools[/bold]")
    hooks_dir = PROJECT_ROOT / ".git" / "hooks" / "pre-commit"
    check("Pre-commit hooks installed", hooks_dir.exists(),
          "Run 'make hooks' to install", warn_only=True)

    # ── Summary
    console.print()
    if not issues:
        console.print("[bold green]All checks passed.[/bold green] Ready to scan.\n")
        return 0
    else:
        console.print(f"[bold red]{len(issues)} issue(s) found:[/bold red]")
        for issue in issues:
            console.print(f"  [red]- {issue}[/red]")
        console.print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
