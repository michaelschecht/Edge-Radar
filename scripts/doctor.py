"""
doctor.py — Startup validation for Edge-Radar.

Verifies that the environment is correctly configured before you waste
time debugging cryptic errors mid-scan.

Usage:
    python scripts/doctor.py
    python scripts/doctor.py --verify-eligibility   # S3: probe venue eligibility
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

    # Gate 2b (S4): the only gates that measure a standing total. Printed first
    # because they are the ones with no per-order equivalent to fall back on --
    # with both at 0, nothing anywhere caps total capital deployed.
    if cfg.risk.max_open_exposure_pct > 0:
        check("Gate 2b  MAX_OPEN_EXPOSURE_PCT = "
              f"{cfg.risk.max_open_exposure_pct:.0%} of equity", True)
    else:
        check("Gate 2b  MAX_OPEN_EXPOSURE_PCT = 0", False,
              "DISABLED — nothing caps TOTAL capital deployed (S4)", warn_only=True)

    if cfg.risk.max_segment_exposure_pct > 0:
        check("Gate 2b  MAX_SEGMENT_EXPOSURE_PCT = "
              f"{cfg.risk.max_segment_exposure_pct:.0%} of equity per sport", True)
    else:
        check("Gate 2b  MAX_SEGMENT_EXPOSURE_PCT = 0", False,
              "DISABLED — one sport may hold the whole book (S4)", warn_only=True)

    check(f"Gate 3   MIN_EDGE_THRESHOLD = {gates.min_edge_threshold:.1%}", True)
    per_sport_edge = dict(cfg.per_sport.min_edge)
    # A floor >= 1.0 means the sport is switched OFF (the F3 idiom). Print those
    # on their own WARN line rather than mixed into the override list: a narrow
    # terminal truncates the right-hand end, and a switched-off sport scrolling
    # off the edge is exactly the "printed != executing" failure doctor exists
    # to prevent. Also states the sport-name contract, since a name that does
    # not match `_detect_sport()` is a silent no-op, not an error.
    disabled = {k: v for k, v in per_sport_edge.items() if v >= 1.0}
    overrides = {k: v for k, v in per_sport_edge.items() if v < 1.0}
    if overrides:
        joined = "  ".join(f"{k}={v:.1%}" for k, v in sorted(overrides.items()))
        check(f"           per-sport: {joined}", True)
    if disabled:
        names = ", ".join(sorted(disabled))
        check(f"           sports OFF (floor >= 100%, unreachable): {names}", False,
              "no bet in these sports can clear Gate 3", warn_only=True)

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

    if gates.max_days_to_event_for_game_markets > 0:
        check("Gate 3.7 MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS = "
              f"{gates.max_days_to_event_for_game_markets} (futures exempt)", True)
    else:
        check("Gate 3.7 MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS = 0", False,
              "DISABLED — game markets can be bought any distance out (S5)", warn_only=True)

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
    # ── S3: venue/product eligibility. Fails CLOSED -- `unknown` blocks live
    #   orders exactly like `blocked` does, so it is reported as an issue, not a
    #   warning. The 2026-08-20 geolocation block produced 16 rejected orders
    #   over six days precisely because nothing surfaced this state.
    console.print("\n[bold]Venue Eligibility (S3)[/bold]")
    try:
        import venue_eligibility as vel
        cache = vel.load()
        if not cache:
            check("Venue eligibility recorded", False,
                  "nothing verified yet -- live orders will be BLOCKED "
                  "(fails closed). Run: python scripts/doctor.py "
                  "--verify-eligibility")
        for key in sorted(cache):
            venue, _, product = key.partition(":")
            st, why = vel.status(venue, product)
            if st == "ok":
                check(f"{venue}/{product}: eligible ({why})", True)
            elif st == "blocked":
                check(f"{venue}/{product}: BLOCKED", False, why)
            else:
                check(f"{venue}/{product}: unknown", False,
                      f"{why} -- live orders blocked (fails closed)")
    except Exception as e:
        check("Venue eligibility check", False, str(e)[:120])

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


PROBE_TICKER_HINT = (
    "Pass a sports ticker that is currently open, e.g. "
    "KXMLBGAME-26AUG271900NYYBOS-NYY"
)


def verify_eligibility(ticker: str | None = None) -> int:
    """S3: prove eligibility by placing a 1c unfillable order, then cancelling.

    **This places a REAL order.** One contract at 1 cent -- far enough below any
    live book that it cannot fill -- and it is cancelled immediately. That is
    the only way to learn whether the venue will accept an order for a product
    without waiting for a genuine bet to be rejected, which is how the
    2026-08-20 block was found six days and 16 orders late.

    Deliberately NOT automatic and NOT scheduled: auto-retry against a venue
    that is refusing orders is exactly the behaviour this whole item exists to
    stop. An operator runs it after re-verifying on the venue's website.
    """
    import venue_eligibility as vel
    from app.config import get_config as _get_config

    if _get_config().system.dry_run:
        console.print("[yellow]DRY_RUN=true -- the probe cannot reach the "
                      "venue, so it would prove nothing. Set DRY_RUN=false to "
                      "verify eligibility.[/yellow]")
        return 1

    if not ticker:
        console.print(f"[red]--verify-eligibility needs --ticker.[/red] "
                      f"{PROBE_TICKER_HINT}")
        return 1

    from kalshi_client import KalshiClient
    client = KalshiClient()
    product = "sports"
    console.print(f"[bold]Probing {ticker} (1 contract @ $0.01, will not "
                  f"fill)...[/bold]")
    try:
        resp = client.create_order(
            ticker=ticker, side="yes", action="buy", count=1,
            yes_price_cents=1, time_in_force="good_till_canceled",
        )
        order = resp.get("order", resp)
        order_id = order.get("order_id") or order.get("id")
        vel.record_success("kalshi", product,
                           evidence=f"probe accepted ({ticker})")
        console.print(f"  [green]ACCEPTED[/green] order_id={order_id} -- "
                      f"kalshi/{product} marked eligible")
        if order_id:
            try:
                client.cancel_order(
                    order_id,
                    exchange_index=order.get("exchange_index"),
                )
                console.print("  [green]Cancelled cleanly.[/green]")
            except Exception as e:
                console.print(f"  [red]COULD NOT CANCEL: {e}[/red]")
                console.print("  [red bold]Cancel this order manually.[/red bold]")
                return 1
        return 0
    except Exception as e:
        raw = getattr(e, "message", None) or str(e)
        if vel.record_rejection("kalshi", product, raw):
            console.print(f"  [red]BLOCKED[/red] {vel.actionable_reason(raw)}")
            console.print(f"  [dim]kalshi/{product} recorded as blocked; live "
                          f"orders will refuse until this is re-run and "
                          f"accepted.[/dim]")
        else:
            console.print(f"  [yellow]Probe failed, but the error is not "
                          f"structural -- eligibility unchanged.[/yellow]")
            console.print(f"  [dim]{vel.actionable_reason(raw)}[/dim]")
        return 1


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Edge-Radar environment validator")
    ap.add_argument("--verify-eligibility", action="store_true",
                    help="S3: place a 1c unfillable probe order to verify the "
                         "venue will accept orders, then cancel it. Places a "
                         "REAL order; requires DRY_RUN=false.")
    ap.add_argument("--ticker", help=PROBE_TICKER_HINT)
    args = ap.parse_args()
    if args.verify_eligibility:
        sys.exit(verify_eligibility(args.ticker))
    sys.exit(main())
