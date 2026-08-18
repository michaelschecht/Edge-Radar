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

    # ── Reject gates
    #
    # CLAUDE.md points here as "the source of truth for what is actually
    # running", but this block only ever printed sizing knobs -- every reject
    # gate was invisible, so a disabled safety gate looked identical to an
    # enforced one. Added 2026-08-18 alongside Gate 3.6 (L2), whose whole
    # lesson was that a rule nobody can see is a rule nobody checks.
    #
    # A gate switched OFF reports WARN, not PASS: 0/permissive is a legitimate
    # setting, but it should never scroll by looking like a healthy default.
    console.print("\n[bold]Reject Gates[/bold]")

    gates, kelly = cfg.gates, cfg.kelly

    check(f"Gate 3   MIN_EDGE_THRESHOLD = {gates.min_edge_threshold:.1%}", True)
    per_sport_edge = dict(cfg.per_sport.min_edge)
    if per_sport_edge:
        overrides = "  ".join(f"{k}={v:.1%}" for k, v in sorted(per_sport_edge.items()))
        check(f"           per-sport: {overrides}", True)

    if gates.min_market_price > 0:
        check(f"Gate 3.5 MIN_MARKET_PRICE = ${gates.min_market_price:.2f}", True)
    else:
        check("Gate 3.5 MIN_MARKET_PRICE = 0", False,
              "DISABLED — no lottery-ticket floor (R7)", warn_only=True)

    if gates.max_bid_ask_spread > 0:
        check(f"Gate 3.6 MAX_BID_ASK_SPREAD = ${gates.max_bid_ask_spread:.2f}", True)
    else:
        check("Gate 3.6 MAX_BID_ASK_SPREAD = 0", False,
              "DISABLED — illiquid books can execute (L2)", warn_only=True)

    if gates.min_market_volume_24h > 0:
        check(f"Gate 3.6 MIN_MARKET_VOLUME_24H = {gates.min_market_volume_24h}", True)
    else:
        # Ships at 0; off is the documented default, so this is informational.
        check("Gate 3.6 MIN_MARKET_VOLUME_24H = 0 (off by default)", True)

    check(f"Gate 4   MIN_COMPOSITE_SCORE = {gates.min_composite_score:g}", True)
    check(f"Gate 4.5 MIN_CONFIDENCE = {gates.min_confidence}", True)
    check(f"Gate 4.6 NO_SIDE_FAVORITE_THRESHOLD = ${gates.no_side_favorite_threshold:.2f} "
          f"/ NO_SIDE_MIN_EDGE = {gates.no_side_min_edge:.0%}", True)
    check(f"Gate 4.6b NO_SIDE_MIN_EDGE_GLOBAL = {gates.no_side_min_edge_global:.0%}", True)

    if gates.allow_prediction_bets:
        check("Gate 4.7 ALLOW_PREDICTION_BETS = true", False,
              "OPEN — crypto/weather/spx/politics can execute (R25)", warn_only=True)
    else:
        check("Gate 4.7 ALLOW_PREDICTION_BETS = false", True)

    if gates.allow_live_bets:
        check("Gate 4.8 ALLOW_LIVE_BETS = true", False,
              "OPEN — in-progress games can execute (L1)", warn_only=True)
    else:
        check("Gate 4.8 ALLOW_LIVE_BETS = false", True)

    if gates.series_dedup_hours > 0:
        check(f"Gate 7   SERIES_DEDUP_HOURS = {gates.series_dedup_hours}h", True)
    else:
        check("Gate 7   SERIES_DEDUP_HOURS = 0", False,
              "DISABLED — same matchup can be re-bet freely", warn_only=True)
    per_sport_dedup = dict(cfg.per_sport.series_dedup_hours)
    if per_sport_dedup:
        overrides = "  ".join(f"{k}={v}h" for k, v in sorted(per_sport_dedup.items()))
        check(f"           per-sport: {overrides}", True)

    check(f"Gate 8/9 MAX_BET_SIZE = ${cfg.risk.max_bet_size:.0f} "
          f"/ MAX_BET_RATIO = {cfg.risk.max_bet_ratio:g}x median", True)

    # Sizing knob that is not a gate but silently reshapes every order.
    check(f"         KELLY_EDGE_CAP = {kelly.kelly_edge_cap:.0%} "
          f"(decay {kelly.kelly_edge_decay:g})", True)

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
