"""
services.py — Thin wrapper around Edge-Radar core functions for the Streamlit UI.

Imports existing scanner, executor, settler, and risk functions.
Captures rich console output so Streamlit can render its own tables.
"""

import os
import sys
from io import StringIO
from pathlib import Path
from contextlib import contextmanager

# Ensure script dirs are on sys.path (mirrors what .pth does for the venv).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
for subdir in ["scripts/kalshi", "scripts/shared", "scripts/prediction",
               "scripts/polymarket"]:
    p = str(PROJECT_ROOT / subdir)
    if p not in sys.path:
        sys.path.insert(0, p)

# PROJECT_ROOT must come *before* `webapp/` on sys.path so that
# `from app.config import ...` resolves to the `app/` package rather than the
# `webapp/app.py` Streamlit entry point. webapp/app.py adds `webapp/` to
# sys.path[0]; we re-insert PROJECT_ROOT here to guarantee it wins.
sys.path.insert(0, str(PROJECT_ROOT))

# ── Env-var registry ────────────────────────────────────────────────────────
# One list, three consumers:
#   1. the Streamlit Cloud secrets bootstrap below (which flat TOML keys to
#      lift into os.environ),
#   2. the Config page (`views/config_page.py`), which renders it as the
#      live "what is actually in force" table,
#   3. anyone reading this file to find out what the app understands.
#
# It previously drifted badly out of sync with `app/config.py` — the Cloud
# deployment silently ignored ~20 knobs (every NO-side global, the live-bet
# gates, both cache groups, all Polymarket credentials) because they simply
# weren't listed here. Keep this in step with `app/config.py`; the test
# `tests/test_webapp_env_registry.py` fails the build when they diverge.
#
# `default` is the code default from `app/config.py` — shown on the Config
# page when nothing overrides it. `secret` masks the value in the UI.

_SPORTS = ("MLB", "NBA", "NHL", "NFL", "NCAAB", "NCAAF", "MLS", "SOCCER")


def _spec(name, group, default, note, secret=False):
    return {"name": name, "group": group, "default": default,
            "note": note, "secret": secret}


ENV_VAR_SPEC: list[dict] = [
    # ── Credentials ─────────────────────────────────────────────────────
    _spec("KALSHI_API_KEY", "Credentials", "", "Kalshi API key ID.", secret=True),
    _spec("KALSHI_PRIVATE_KEY_PATH", "Credentials", "",
          "Path to the RSA private key (local runs)."),
    _spec("KALSHI_PRIVATE_KEY", "Credentials", "",
          "Inline PEM contents — used instead of the path on Streamlit Cloud.",
          secret=True),
    _spec("KALSHI_BASE_URL", "Credentials",
          "https://api.elections.kalshi.com/trade-api/v2", "Kalshi API host."),
    _spec("ODDS_API_KEYS", "Credentials", "",
          "Comma-separated Odds API keys; rotated automatically on quota.",
          secret=True),
    _spec("ODDS_API_KEY", "Credentials", "",
          "Single-key fallback when ODDS_API_KEYS is unset.", secret=True),
    _spec("POLYMARKET_KEY_ID", "Credentials", "",
          "Polymarket US retail API key UUID (Ed25519 scheme).", secret=True),
    _spec("POLYMARKET_SECRET_KEY", "Credentials", "",
          "Base64 Ed25519 private key from polymarket.us/developer.", secret=True),
    _spec("POLYMARKET_API_HOST", "Credentials", "https://api.polymarket.us",
          "Polymarket US retail API host."),

    # Optional split-credential and integration groups. Read by `app/config.py`
    # but not by any dashboard path — listed so the Config page is a complete
    # answer to "what does this system read from the environment", which the
    # 2026-07-14 repo review flagged as a live gap in `.env.example`.
    _spec("KALSHI_PROD_API_KEY", "Credentials", "",
          "Optional prod-pointing key used by make_prod_client().", secret=True),
    _spec("KALSHI_PROD_PRIVATE_KEY_PATH", "Credentials", "",
          "Private key for the prod-pointing client."),
    _spec("KALSHI_PROD_BASE_URL", "Credentials",
          "https://api.elections.kalshi.com/trade-api/v2",
          "Host for the prod-pointing client."),
    _spec("ALPACA_API_KEY", "Integrations", "",
          "scripts fetch_market_data.py only — not used by the dashboard.",
          secret=True),
    _spec("ALPACA_SECRET_KEY", "Integrations", "",
          "Alpaca secret; paper trading by default.", secret=True),
    _spec("ALPACA_BASE_URL", "Integrations", "https://paper-api.alpaca.markets",
          "Alpaca host. Paper endpoint by default."),
    _spec("TELEGRAM_TOKEN", "Integrations", "",
          "scripts/schedulers/automation/telegram_bot.py alerts.", secret=True),
    _spec("TELEGRAM_CHAT_ID", "Integrations", "",
          "Destination chat for Telegram alerts."),

    # ── System ──────────────────────────────────────────────────────────
    _spec("DRY_RUN", "System", "true",
          "Global kill switch. false = real orders on every venue."),
    _spec("POLYMARKET_DRY_RUN", "System", "true",
          "PM2c venue-scoped switch. Polymarket orders need BOTH this and "
          "DRY_RUN false. Set true to halt Polymarket without touching Kalshi."),
    _spec("LOG_LEVEL", "System", "INFO", "DEBUG | INFO | WARNING | ERROR | CRITICAL."),
    _spec("PROJECT_ROOT", "System", "",
          "Overrides the inferred repo root (backtester report dir). Leave "
          "unset unless you know you need it."),

    # ── Risk limits ─────────────────────────────────────────────────────
    _spec("UNIT_SIZE", "Risk limits", "1.00",
          "C11: the LONGSHOT knob. Below ~30c the flat floor "
          "round(UNIT_SIZE/price) binds and Kelly never clears it."),
    _spec("MAX_BET_SIZE", "Risk limits", "100", "Hard cap per single bet (USD)."),
    _spec("MAX_DAILY_LOSS", "Risk limits", "250",
          "Gate 1. Shared across venues — one operator, one daily budget."),
    _spec("MAX_OPEN_POSITIONS", "Risk limits", "50", "Gate 2."),
    _spec("MAX_PER_EVENT", "Risk limits", "2", "Gate 6."),
    _spec("MAX_BET_RATIO", "Risk limits", "3.0",
          "Gate 9. Max single bet as a multiple of the batch median cost."),

    # ── Sizing (Kelly) ──────────────────────────────────────────────────
    _spec("KELLY_FRACTION", "Sizing", "0.25",
          "C11: the FAVORITES knob. Divided by batch size at runtime, so it "
          "is a PORTFOLIO fraction. Keep <= 0.5."),
    _spec("KELLY_EDGE_CAP", "Sizing", "0.15", "Soft-cap on edge inside Kelly only."),
    _spec("KELLY_EDGE_DECAY", "Sizing", "0.5", "Weight on edge above the cap."),
    _spec("NO_SIDE_KELLY_PRICE_FLOOR", "Sizing", "0.35",
          "R1: below this NO price, apply the NO-side multiplier."),
    _spec("NO_SIDE_KELLY_MULTIPLIER", "Sizing", "0.5",
          "R1: half-Kelly on NO bets under the price floor."),
    _spec("NO_SIDE_KELLY_MULTIPLIER_GLOBAL", "Sizing", "1.0",
          "R28: multiplier on EVERY NO bet. 1.0 = off."),

    # ── Reject gates ────────────────────────────────────────────────────
    _spec("MIN_EDGE_THRESHOLD", "Reject gates", "0.03",
          "Gate 3, global floor. Per-sport overrides below win when set."),
    _spec("MIN_MARKET_PRICE", "Reject gates", "0.12",
          "Gate 3.5 (R7) lottery-ticket floor. Pure reject threshold — "
          "independent of every sizing knob. 0 disables."),
    _spec("MAX_BID_ASK_SPREAD", "Reject gates", "0.05",
          "Gate 3.6. Max bid/ask spread in dollars on a $0-1 contract — the "
          "CLAUDE.md 'illiquid (spread > 5%)' Hard Stop, enforced in code as "
          "of 2026-08-18. 0 disables."),
    _spec("MIN_MARKET_VOLUME_24H", "Reject gates", "0",
          "Gate 3.6 companion. Min contracts traded in the trailing 24h; "
          "catches tolerable-spread books that never trade. 0 disables."),
    _spec("MIN_COMPOSITE_SCORE", "Reject gates", "6.0",
          "Gate 4. C10 aligned the futures composite to the sports edge "
          "scale, so this now binds on futures at all."),
    _spec("MIN_CONFIDENCE", "Reject gates", "medium", "Gate 4.5. low | medium | high."),
    _spec("NO_SIDE_FAVORITE_THRESHOLD", "Reject gates", "0.25",
          "Gate 4.6 trigger price. 0 disables the gate."),
    _spec("NO_SIDE_MIN_EDGE", "Reject gates", "0.25",
          "Gate 4.6 required edge (also needs confidence=high)."),
    _spec("NO_SIDE_MIN_EDGE_GLOBAL", "Reject gates", "0.08",
          "Gate 4.6b (R28). Effective NO floor = max(per-sport floor, this)."),
    _spec("ALLOW_PREDICTION_BETS", "Reject gates", "false",
          "Gate 4.7 (R25). true re-enables crypto/weather/spx/mentions/"
          "companies/politics."),
    _spec("ALLOW_LIVE_BETS", "Reject gates", "false",
          "Gate 4.8 (L1). true allows bets on in-progress games."),
    _spec("SERIES_DEDUP_HOURS", "Reject gates", "48",
          "Gate 7. Same-matchup window. 0 disables."),
    _spec("CROSS_CATEGORY_DEDUP", "Reject gates", "false",
          "R8. true collapses ML+Total+Spread on one game to the highest "
          "composite."),
    _spec("MIN_CONSENSUS_BOOKS_NBA", "Reject gates", "8",
          "R29. NBA games under this book count drop to `low` confidence, "
          "which Gate 4.5 then rejects. 0 disables."),
    _spec("RESTING_ORDER_MAX_HOURS", "Reject gates", "24",
          "R4 janitor. Kalshi-only; Polymarket ops are PM3. 0 disables."),
    _spec("REQUIRE_FRESH_CALIBRATION", "Reject gates", "false",
          "true refuses to EXECUTE when the stdev cache disagrees with what "
          "the calibrator would compute from current settled data. Default "
          "false = warn only. Checks recomputation, not cache age — age said "
          "'fresh' throughout the 2026-07-31 no-op."),

    # ── Data quality / freshness ────────────────────────────────────────
    _spec("MAX_LIVE_BOOK_AGE_SECONDS", "Data quality", "1200",
          "L1 Phase 2. Drop in-play books staler than this. 0 disables."),
    _spec("MIN_LIVE_CONSENSUS_BOOKS", "Data quality", "3",
          "L1 Phase 2. Skip an in-progress game the stale filter thinned "
          "below this. 0 disables."),
    _spec("CALIBRATION_STDEVS_TTL_DAYS", "Data quality", "30",
          "C8. Max age of auto-recalibrated per-sport stdevs before falling "
          "back to hardcoded defaults."),
    _spec("TEST_CALIBRATION_STDEVS", "Data quality", "false",
          "Test-only: read the stdev cache regardless of TTL."),

    # ── Caching ─────────────────────────────────────────────────────────
    _spec("ODDS_CACHE_TTL_SECONDS", "Caching", "300",
          "R24b. Pre-game Odds API file cache. 0 disables."),
    _spec("ODDS_CACHE_ENABLED", "Caching", "true", "R24b. false bypasses the file cache."),
    _spec("ODDS_LIVE_TTL_SECONDS", "Caching", "45",
          "L1. Shorter TTL when a sport response has an in-play event."),
    _spec("SCAN_CACHE_TTL_SECONDS", "Caching", "600",
          "R26. Row→ticker mapping so --pick replays instead of rescanning."),
    _spec("SCAN_CACHE_ENABLED", "Caching", "true", "R26. false forces a rescan."),

    # ── Notifications ───────────────────────────────────────────────────
    _spec("NOTIFY_EMAIL", "Notifications", "", "Inbox scheduled reports are sent TO."),
    _spec("AGENTMAIL_INBOX", "Notifications", "",
          "agentmail.to address reports are sent FROM."),
]

# Per-sport overrides expand mechanically — one row per (prefix, sport).
ENV_VAR_SPEC += [
    _spec(f"MIN_EDGE_THRESHOLD_{s}", "Per-sport overrides", "",
          f"Gate 3 floor for {s}; falls back to MIN_EDGE_THRESHOLD.")
    for s in _SPORTS
] + [
    _spec(f"SERIES_DEDUP_HOURS_{s}", "Per-sport overrides", "",
          f"R9 dedup window for {s}; falls back to SERIES_DEDUP_HOURS.")
    for s in _SPORTS
] + [
    _spec(f"CROSS_CATEGORY_DEDUP_{s}", "Per-sport overrides", "",
          f"R8 override for {s}; falls back to CROSS_CATEGORY_DEDUP.")
    for s in _SPORTS
]

ENV_VAR_NAMES: tuple[str, ...] = tuple(s["name"] for s in ENV_VAR_SPEC)

# Names never rendered in full on the Config page.
SECRET_ENV_VARS: frozenset[str] = frozenset(
    s["name"] for s in ENV_VAR_SPEC if s["secret"]
)

# On Streamlit Cloud, inject secrets into os.environ so all existing
# os.getenv() calls in scripts (odds_api, edge_detector, etc.) work
# without modification. Must run before any script imports.
#
# Supports two TOML layouts:
#   Nested:    [kalshi] / api_key = "..."    → mapped via _secrets_map
#   Flat:      KALSHI_API_KEY = "..."        → every name in ENV_VAR_NAMES
try:
    import streamlit as st
    _secrets_map = {
        "ODDS_API_KEY": lambda: st.secrets["odds"]["api_key"],
        "ODDS_API_KEYS": lambda: st.secrets["odds"]["api_keys"],
        "KALSHI_API_KEY": lambda: st.secrets["kalshi"]["api_key"],
        "KALSHI_PRIVATE_KEY": lambda: st.secrets["kalshi"]["private_key"],
        "KALSHI_BASE_URL": lambda: st.secrets["kalshi"]["base_url"],
        # PM2: nested [polymarket] block, mirroring the [kalshi] layout.
        "POLYMARKET_KEY_ID": lambda: st.secrets["polymarket"]["key_id"],
        "POLYMARKET_SECRET_KEY": lambda: st.secrets["polymarket"]["secret_key"],
        "POLYMARKET_API_HOST": lambda: st.secrets["polymarket"]["host"],
        "POLYMARKET_DRY_RUN": lambda: st.secrets["polymarket"]["dry_run"],
        "DRY_RUN": lambda: st.secrets["DRY_RUN"],
    }
    for env_var, getter in _secrets_map.items():
        if env_var not in os.environ:  # config-bootstrap
            try:
                os.environ[env_var] = str(getter())  # config-bootstrap
            except (KeyError, FileNotFoundError):
                pass
    for key in ENV_VAR_NAMES:
        if key not in os.environ:  # config-bootstrap
            try:
                os.environ[key] = str(st.secrets[key])  # config-bootstrap
            except (KeyError, FileNotFoundError):
                pass
except Exception:
    pass

import streamlit as st

# Invalidate any cfg cache so subsequent `get_config()` calls in downstream
# imports see the post-bootstrap `os.environ` state. In the current flow this
# is defensive — the bootstrap runs before any of the imports below trigger
# `get_config()` in migrated modules — but it makes the contract explicit:
# `app.config` is the single read-side, and `reset_config()` is the seam
# whenever something writes to `os.environ` after potentially priming the cache.
from app.config import get_config, reset_config
reset_config()

from kalshi_client import KalshiClient
from edge_detector import scan_all_markets, FILTER_SHORTCUTS
from futures_edge import scan_futures_markets
from prediction_scanner import scan_prediction_markets
from kalshi_executor import (
    execute_pipeline, reload_risk_config, preflight_gate_status, UNIT_SIZE,
)
from kalshi_settler import settle_trades, generate_report
from risk_check import (
    fetch_balance, fetch_positions, fetch_resting_orders,
    get_today_trades, load_watchlist,
)
from trade_log import load_trade_log, get_today_pnl
from ticker_display import (
    filter_by_date, resolve_date_arg, filter_exclude_tickers,
    parse_game_datetime, format_bet_label, format_pick_label,
    sport_from_ticker, bet_type_from_ticker, is_game_started,
)

# Module-level constants imported by `views/scan_page.py` and
# `views/portfolio_page.py`. Only the source has changed; downstream code
# continues to import them as plain names.
_cfg = get_config()
MAX_DAILY_LOSS = _cfg.risk.max_daily_loss
MAX_OPEN_POSITIONS = _cfg.risk.max_open_positions
MAX_PER_EVENT = _cfg.risk.max_per_event
MIN_EDGE_THRESHOLD = _cfg.gates.min_edge_threshold
MIN_COMPOSITE_SCORE = _cfg.gates.min_composite_score
DRY_RUN = _cfg.system.dry_run


@contextmanager
def capture_console():
    """Capture stdout (rich prints to stdout) and return the output."""
    buf = StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        yield buf
    finally:
        sys.stdout = old_stdout


def get_client(venue: str = "kalshi"):
    """Create an authenticated execution client for `venue`.

    Kalshi: on Streamlit Cloud, reads credentials from st.secrets["kalshi"];
    locally, from .env as usual.

    Polymarket: routes through the venue-neutral `get_market_client` factory
    (PM2 seam) so the webapp builds the same `PolymarketClient` the CLI does —
    Ed25519 retail API, no separate secrets path needed because the bootstrap
    above already lifted POLYMARKET_KEY_ID / POLYMARKET_SECRET_KEY into the
    process environment.

    Raises FileNotFoundError with a clear message if credentials are missing.
    """
    import streamlit as st

    v = (venue or "kalshi").strip().lower()

    if v != "kalshi":
        from market_client import get_market_client
        return get_market_client(v)

    # Try to pull credentials from Streamlit secrets (Cloud deployment)
    try:
        kalshi_secrets = st.secrets["kalshi"]
        return KalshiClient(
            api_key=kalshi_secrets.get("api_key"),
            private_key_content=kalshi_secrets.get("private_key"),
            base_url=kalshi_secrets.get("base_url"),
        )
    except (KeyError, FileNotFoundError):
        pass

    # Fall back to .env-based config (local dev)
    return KalshiClient()


# ── Venue helpers (PM2c) ────────────────────────────────────────────────────

def venue_for_market_type(market_type: str) -> str:
    """Which execution venue a scan's market type executes on."""
    return "polymarket" if market_type == "polymarket" else "kalshi"


def polymarket_order_mode() -> tuple[bool, str]:
    """(orders_live, human description) for the Polymarket two-flag state.

    Mirrors `polymarket_futures_edge._order_mode` so the dashboard banner and
    the CLI preview footer can never disagree about whether real money is on
    the line. Read live (not snapshotted at import) and fails safe to
    "blocked" if the config can't be read.
    """
    try:
        cfg = get_config()
        global_dry = bool(cfg.system.dry_run)
        venue_dry = bool(getattr(cfg.polymarket, "dry_run", True))
    except Exception:
        return False, "order mode unknown — assuming blocked"
    if not global_dry and not venue_dry:
        return True, "DRY_RUN=false AND POLYMARKET_DRY_RUN=false"
    blockers = [n for n, v in (("DRY_RUN", global_dry),
                               ("POLYMARKET_DRY_RUN", venue_dry)) if v]
    return False, "blocked by " + " and ".join(f"{b}=true" for b in blockers)


def is_executable(opp) -> bool:
    """Can this opportunity actually reach `create_order`?

    Kalshi rows always can. Polymarket rows need a US `market_slug`: the games
    scanner reads international Gamma, a different slug namespace that the US
    retail API cannot address, so those rows are dry-run evidence only. The
    CLI applies exactly this filter before `execute_pipeline`.
    """
    details = getattr(opp, "details", None) or {}
    if details.get("venue") != "polymarket":
        return True
    return bool(details.get("market_slug"))


# ── Sport filter options ────────────────────────────────────────────────────

SPORT_FILTERS = sorted([
    k for k in FILTER_SHORTCUTS
    if not k.endswith("-futures") and k not in ("futures", "superbowl")
])

CATEGORY_OPTIONS = ["all", "game", "spread", "total", "player_prop", "esports", "other"]

DATE_OPTIONS = ["all dates", "today", "tomorrow"]

SUPPORTED_MARKET_TYPES = ("sports", "futures", "prediction", "polymarket")


# ── Scan ────────────────────────────────────────────────────────────────────

# 60s TTL chosen because:
#   - Kalshi prices can move within a minute on live markets, so we don't
#     want stale results showing stale edges after anyone acts on them.
#   - 60s still absorbs the typical "click scan, look, click scan again"
#     exploratory loop that used to fire a full Odds API fetch per click.
#   - If the user executes a bet and re-scans within the window, the cached
#     result still includes the just-bet opportunity as a candidate row.
#     Mild staleness; they can change any filter or wait 60s to refresh.
# The `_client` parameter is underscore-prefixed per Streamlit convention so
# it's excluded from the cache key — KalshiClient is not hashable.
@st.cache_data(ttl=60, show_spinner=False)
def run_scan(
    _client: KalshiClient,
    market_type: str = "sports",
    ticker_filter: str | None = None,
    category_filter: str | None = None,
    date_filter: str | None = None,
    min_edge: float = MIN_EDGE_THRESHOLD,
    top_n: int = 20,
    exclude_open: bool = False,
) -> tuple[list, str]:
    """
    Run a scan for the given market type and return (opportunities, console_output).

    market_type dispatches to the matching scanner:
      - "sports"     → edge_detector.scan_all_markets (respects date_filter, category_filter)
      - "futures"    → futures_edge.scan_futures_markets (date_filter and category_filter ignored)
      - "prediction" → prediction_scanner.scan_prediction_markets (date_filter ignored)
      - "polymarket" → polymarket_futures_edge.scan_polymarket_futures and/or
                       polymarket_games_edge.scan_polymarket_games, routed by
                       the filter exactly as `scan.py polymarket` does
                       (date_filter and category_filter ignored). `_client` is
                       unused on this path — Polymarket market data comes from
                       its own read clients, not the passed execution client.

    Cached for 60 seconds via `st.cache_data` (R24a) so repeat scan clicks
    with identical filters reuse the same Odds API + Kalshi results. Odds
    API quota was being burned by repeat clicks re-running the full fetch
    every time. Call `st.cache_data.clear()` or pass a different filter to
    force a refresh.
    """
    if market_type not in SUPPORTED_MARKET_TYPES:
        raise ValueError(
            f"Unsupported market_type: {market_type!r}. "
            f"Must be one of {SUPPORTED_MARKET_TYPES}."
        )

    # Re-read risk-gate config so the scan's Gate-preview column reflects any
    # `.env`/Secrets edits since this long-running server started. See
    # `kalshi_executor.reload_risk_config`.
    reload_risk_config()

    resolved_date = None
    if date_filter and date_filter != "all dates":
        resolved_date = resolve_date_arg(date_filter)

    with capture_console() as buf:
        if market_type == "sports":
            opportunities = scan_all_markets(
                _client,
                min_edge=min_edge,
                category_filter=category_filter,
                ticker_filter=ticker_filter,
                top_n=top_n,
                date_filter=resolved_date,
            )
            if opportunities and resolved_date:
                opportunities = filter_by_date(opportunities, resolved_date)

        elif market_type == "futures":
            opportunities = scan_futures_markets(
                _client,
                min_edge=min_edge,
                ticker_filter=ticker_filter,
                top_n=top_n,
            )

        elif market_type == "polymarket":
            opportunities = _scan_polymarket(
                min_edge=min_edge,
                ticker_filter=ticker_filter,
                top_n=top_n,
            )

        else:  # prediction
            opportunities = scan_prediction_markets(
                _client,
                min_edge=min_edge,
                category_filter=category_filter,
                ticker_filter=ticker_filter,
                top_n=top_n,
            )

        if opportunities and exclude_open:
            positions = _client.get_positions(limit=200, count_filter="position")
            open_tickers = {p.get("ticker", "") for p in positions.get("market_positions", [])}
            opportunities = filter_exclude_tickers(opportunities, open_tickers)

    return opportunities, buf.getvalue()


def _scan_polymarket(min_edge: float, ticker_filter: str | None,
                     top_n: int) -> list:
    """Run the Polymarket scan, routing the filter the same way the CLI does.

    `_route_filter` is the single source of truth for what a Polymarket filter
    string means (futures vs games vs both), so the dashboard and
    `scan.py polymarket --filter X` can never disagree about which surfaces a
    filter covers.
    """
    from polymarket_futures_edge import _route_filter, scan_polymarket_futures

    futures_filter, game_sports = _route_filter(ticker_filter)
    opportunities: list = []

    if futures_filter:
        opportunities += scan_polymarket_futures(
            min_edge=min_edge, ticker_filter=futures_filter, top_n=top_n,
        )
    if game_sports:
        # Lazy import: pulls the edge_detector consensus stack, which a
        # futures-only scan doesn't need.
        from polymarket_games_edge import scan_polymarket_games
        opportunities += scan_polymarket_games(
            min_edge=min_edge, sports=game_sports, top_n=top_n,
        )

    opportunities.sort(key=lambda o: o.composite_score, reverse=True)
    return opportunities[:top_n]


# ── Execute ─────────────────────────────────────────────────────────────────

def run_execute(
    client,
    opportunities: list,
    unit_size: float = UNIT_SIZE,
    max_bets: int = 5,
    min_bets: int | None = None,
    budget: float | None = None,
    pick_indices: list[int] | None = None,
    execute: bool = False,
    venue: str = "kalshi",
) -> tuple[list, str]:
    """
    Run the execution pipeline and return (sized_orders, console_output).

    pick_indices: 0-based indices into the opportunities list to execute.
    venue: "kalshi" or "polymarket" (PM2c). `client` must be the client for
        that venue. Gates, sizing, and caps are venue-neutral; only the
        Kalshi-shaped resting-order janitor is skipped off-venue.
    """
    # Re-read risk-gate config before sizing/gating so the long-running webapp
    # honors `.env`/Secrets edits without a restart. Without this, a server
    # started before a floor change keeps approving sub-floor bets (e.g. a $0.05
    # wager while the live MIN_MARKET_PRICE is 0.06). See
    # `kalshi_executor.reload_risk_config`.
    reload_risk_config()

    if pick_indices is not None:
        opportunities = [opportunities[i] for i in pick_indices if i < len(opportunities)]

    # PM2c: drop rows that can never reach create_order (Gamma-sourced games
    # carry no US market_slug). Mirrors the CLI, which filters before calling
    # execute_pipeline — without this the pipeline sizes and gates rows that
    # would raise at order time.
    if venue == "polymarket":
        opportunities = [o for o in opportunities if is_executable(o)]

    # Convert budget percentage to fraction
    budget_val = None
    if budget is not None:
        if budget <= 1:
            budget_val = budget
        elif budget <= 100:
            budget_val = budget / 100
        else:
            budget_val = budget

    with capture_console() as buf:
        sized_orders = execute_pipeline(
            client=client,
            opportunities=opportunities,
            execute=execute,
            max_bets=max_bets,
            unit_size=unit_size,
            budget=budget_val,
            min_bets=min_bets,
            venue=venue,
        )

    return sized_orders or [], buf.getvalue()


# ── Portfolio ───────────────────────────────────────────────────────────────

def get_portfolio_data(client, venue: str = "kalshi") -> dict:
    """Fetch all portfolio data for one venue in a single call.

    `daily_pnl` and `daily_limit` are deliberately NOT split by venue: Gate 1
    reads the shared trade log, so the daily loss budget spans Kalshi and
    Polymarket together (one operator, one risk budget). `today_trades` is
    filtered to the venue so each tab shows its own activity, but the limit
    bar below it is the shared one.
    """
    bal = fetch_balance(client)
    positions = fetch_positions(client)
    resting = fetch_resting_orders(client)
    all_today_trades, daily_pnl = get_today_trades()

    # Rows logged before the PM2c venue tag default to Kalshi, matching
    # `log_trade`'s own `.get("venue", "kalshi")` fallback.
    today_trades = [t for t in all_today_trades
                    if (t.get("venue") or "kalshi") == venue]

    data = {
        "venue": venue,
        "balance": bal.get("balance", 0),
        "portfolio_value": bal.get("portfolio_value", 0),
        "positions": positions,
        "resting_orders": resting,
        "open_count": len(positions),
        "today_trades": today_trades,
        "daily_pnl": daily_pnl,
        "daily_limit": MAX_DAILY_LOSS,
        "max_positions": MAX_OPEN_POSITIONS,
        "dry_run": DRY_RUN,
    }

    if venue == "polymarket":
        # The US retail API reports buying power separately from balance, and
        # reservations that do NOT reduce it — both are absent on Kalshi.
        data["buying_power"] = bal.get("buying_power", 0)
        data["reservation"] = bal.get("reservation", 0)
        live, mode = polymarket_order_mode()
        data["orders_live"] = live
        data["order_mode"] = mode
        # The Kalshi-shaped `market_positions` list the executor's gates read
        # carries only cost and realized P&L. The venue's own per-position
        # payload also has `cashValue` (mark-to-market), so keep it around for
        # a display that can show unrealized P&L rather than a column of zeros.
        try:
            data["raw_positions"] = client.get_positions().get("positions") or {}
        except Exception:
            data["raw_positions"] = {}
    return data


def format_positions_for_display(positions: list[dict]) -> list[dict]:
    """Convert raw Kalshi position dicts to display-friendly rows.

    Kalshi API fields:
        position_fp: str — signed contract count (positive=YES, negative=NO)
        total_traded_dollars: str — cost basis
        market_exposure_dollars: str — current market value
        fees_paid_dollars: str — fees paid
        realized_pnl_dollars: str — realized P&L
    """
    rows = []
    for p in positions:
        ticker = p.get("ticker", "")
        title = p.get("title", ticker)

        # position_fp is a string like "3.00" (YES) or "-3.00" (NO)
        position_fp = float(p.get("position_fp", 0))
        side = "YES" if position_fp > 0 else "NO"
        qty = abs(int(position_fp))

        cost = float(p.get("total_traded_dollars", 0))
        exposure = float(p.get("market_exposure_dollars", 0))
        fees = float(p.get("fees_paid_dollars", 0))

        # Avg price per contract
        avg_price = cost / qty if qty > 0 else 0

        # Unrealized P&L: exposure - cost - fees
        pnl = exposure - cost - fees

        rows.append({
            "Sport": sport_from_ticker(ticker),
            "Bet": format_bet_label(ticker, title),
            "Type": bet_type_from_ticker(ticker),
            "Side": side,
            "Qty": qty,
            "Avg Price": f"${avg_price:.2f}",
            "Cost": f"${cost:.2f}",
            "Value": f"${exposure:.2f}",
            "P&L": f"${pnl:+.2f}",
        })
    return rows


def format_polymarket_positions_for_display(
    market_positions: list[dict], raw_positions=None
) -> list[dict]:
    """Convert Polymarket US positions to display rows.

    Deliberately NOT run through `format_positions_for_display`: the two
    venues agree on `ticker` / `position_fp` and nothing else.

    - Polymarket's `market_exposure_dollars` is the *cost basis*, not market
      value. Feeding it to the Kalshi formula (`exposure - cost - fees`) would
      print $0.00 unrealized on every row. Mark-to-market is `cashValue` in
      the venue's own per-position payload, so unrealized comes from there and
      is left blank when the raw payload isn't available.
    - Every money field is an Amount object (`{"value": "4.98", "currency":
      "USD"}`), not a number — hence `_pm_amount` rather than `float()`.
    - `marketMetadata.title` is the *event* ("World Series Champion"), shared
      by every team in the field, so the team name is appended to make rows
      distinguishable.
    - Ticker-parsing helpers (`sport_from_ticker`, `format_bet_label`) are
      skipped — they read Kalshi ticker grammar and return noise for
      `PM-{slug}`.
    """
    from polymarket_exec_client import _amount as _pm_amount

    raw = raw_positions or {}
    by_slug = raw if isinstance(raw, dict) else {
        (p.get("marketSlug") or ""): p for p in raw
    }

    rows = []
    for p in market_positions:
        slug = p.get("market_slug", "")
        net = float(p.get("position_fp", 0) or 0)
        cost = float(p.get("market_exposure_dollars", 0) or 0)
        realized = float(p.get("realized_pnl_dollars", 0) or 0)

        detail = by_slug.get(slug) or {}
        meta = detail.get("marketMetadata") or {}
        title = meta.get("title") or meta.get("question") or slug
        team = (meta.get("team") or {}).get("name") or meta.get("outcome")
        label = f"{title} — {team}" if team else title

        has_value = "cashValue" in detail or "currentValue" in detail
        cash = _pm_amount(detail.get("cashValue", detail.get("currentValue")))
        fees = _pm_amount(detail.get("fees"))
        qty = abs(int(net))
        avg = cost / qty if qty else 0.0

        rows.append({
            "Market": label,
            "Slug": slug,
            "Side": "YES" if net > 0 else "NO",
            "Qty": qty,
            "Avg Price": f"${avg:.2f}",
            "Cost": f"${cost:.2f}",
            "Value": f"${cash:.2f}" if has_value else "—",
            # Matches the Kalshi column's definition: value - cost - fees.
            "Unrealized": f"${cash - cost - fees:+.2f}" if has_value else "—",
            "Realized": f"${realized:+.2f}",
        })
    return rows


# ── Settle ──────────────────────────────────────────────────────────────────

def run_settle(client: KalshiClient) -> tuple[dict, str]:
    """Run settlement and return (result, console_output)."""
    with capture_console() as buf:
        result = settle_trades(client)
    return result, buf.getvalue()


def run_report(detail: bool = False, days: int | None = None) -> tuple[str, str]:
    """Generate P&L report and return (markdown_content, console_output)."""
    with capture_console() as buf:
        md = generate_report(detail=detail, save=False, days=days)
    return md or "", buf.getvalue()


# ── Settlement History ──────────────────────────────────────────────────

def get_settlement_history(limit: int = 50) -> list[dict]:
    """Load recent settlements from the settlement log."""
    from trade_log import load_settlement_log
    settlements = load_settlement_log()
    # Most recent first
    settlements.sort(key=lambda s: s.get("settled_at", ""), reverse=True)
    return settlements[:limit]


# ── Helpers ─────────────────────────────────────────────────────────────────

_CATEGORY_LABELS = {
    "game": "ML", "spread": "Spread", "total": "Total",
    "player_prop": "Prop", "esports": "Esports", "futures": "Futures",
}


def gate_statuses(opportunities: list) -> list[str]:
    """Preflight each opportunity against the risk gates (read-only).

    Same call the CLI preview uses. Wrapped so a failure in the preflight can
    never take down a scan — "-" means the check was unavailable, not that the
    row passes.
    """
    try:
        return [preflight_gate_status(o) for o in opportunities]
    except Exception:
        return ["-"] * len(opportunities)


def opportunities_to_rows(opportunities: list, with_gates: bool = True) -> list[dict]:
    """Convert Opportunity objects to display-friendly dicts.

    Polymarket rows are built from `details` rather than by parsing the
    ticker: `PM-{slug}` carries no Kalshi ticker grammar, so
    `sport_from_ticker` / `format_bet_label` / `parse_game_datetime` return
    noise for it. They also get an `Exec` column — the US retail API can only
    address markets that carry a `market_slug`, so Gamma-sourced game rows are
    evidence, not orders.
    """
    gates = gate_statuses(opportunities) if with_gates else [""] * len(opportunities)
    any_polymarket = any(
        (getattr(o, "details", None) or {}).get("venue") == "polymarket"
        for o in opportunities
    )

    rows = []
    for i, opp in enumerate(opportunities):
        details = getattr(opp, "details", None) or {}
        is_pm = details.get("venue") == "polymarket"

        if is_pm:
            row = {
                "#": i + 1,
                "Sport": details.get("sport") or details.get("bet_type", "Futures"),
                "Bet": details.get("bet_type", opp.title),
                "Type": _CATEGORY_LABELS.get(opp.category, opp.category.title()),
                "Pick": details.get("candidate", opp.side.upper()),
                "When": (details.get("game_start") or "")[:16],
                "Started": "",
            }
        else:
            row = {
                "#": i + 1,
                "Sport": sport_from_ticker(opp.ticker),
                "Bet": format_bet_label(opp.ticker, opp.title),
                "Type": _CATEGORY_LABELS.get(opp.category, opp.category.title()),
                "Pick": format_pick_label(opp.ticker, opp.title, opp.side, opp.category),
                "When": parse_game_datetime(opp.ticker),
                "Started": "LIVE" if is_game_started(opp.ticker) else "",  # R27/F44
            }

        row.update({
            "Price": f"${opp.market_price:.2f}",
            "Fair": f"${opp.fair_value:.2f}",
            "Edge": f"+{opp.edge:.1%}",
            "Conf": opp.confidence.title(),
            "Score": f"{opp.composite_score:.1f}",
        })
        if with_gates:
            row["Gate"] = gates[i]
        if any_polymarket:
            row["Exec"] = "YES" if is_executable(opp) else "—"
        rows.append(row)
    return rows


# ── Config introspection (Config page) ──────────────────────────────────────

def env_var_rows() -> list[dict]:
    """Render `ENV_VAR_SPEC` against the live process env.

    Answers the question the executor's import-time snapshot makes hard to
    answer from the outside: what is actually in force right now, and did it
    come from `.env` / Secrets or from the code default?

    Reads the raw environment rather than `get_config()` on purpose — the
    typed config coerces values and substitutes defaults, which erases exactly
    the distinction this page exists to show ("set to 0.10" vs "falling back
    to 0.12"). It is display-only; nothing here feeds a betting decision.
    """
    rows = []
    for spec in ENV_VAR_SPEC:
        name = spec["name"]
        raw = os.environ.get(name)  # config-bootstrap: raw read is the point
        is_set = raw is not None and raw != ""

        if is_set and name in SECRET_ENV_VARS:
            shown = f"set ({len(raw)} chars)"
        elif is_set:
            shown = raw
        elif spec["default"]:
            shown = spec["default"]
        else:
            shown = "—"

        rows.append({
            "Variable": name,
            "Value": shown,
            "Source": "set" if is_set else ("default" if spec["default"] else "unset"),
            "Group": spec["group"],
            "Notes": spec["note"],
        })
    return rows
