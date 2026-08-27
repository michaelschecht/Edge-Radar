"""
app/config.py — single source of truth for every Edge-Radar runtime knob.

Per the CONFIG_CENTRALIZATION enhancement plan (Phase 1): typed dataclasses
group every env-driven setting, each with `from_env()` for one-shot coercion
and `validate()` for impossible combinations.

Scripts should reach config through `get_config()` (memoized) so a
secrets injected after import time can be picked up via `reset_config()`.

This module deliberately does NOT call `load_dotenv()` — current scripts
already do that, and double-loading is harmless but noisy. `get_config()`
reads from `os.environ` at the moment of first access.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Iterable


# ── Coercion helpers ────────────────────────────────────────────────────────

_TRUTHY = {"true", "1", "yes", "on"}
_CONFIDENCE_LEVELS = {"low", "medium", "high"}
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
# Sports that can carry a `MIN_EDGE_THRESHOLD_<SPORT>` / `SERIES_DEDUP_HOURS_<SPORT>`
# / `CROSS_CATEGORY_DEDUP_<SPORT>` override. **The names must match what
# `ticker_display._detect_sport()` returns**, or the env var is silently never
# read.
#
# 2026-08-25: this list held only the first eight. Everything below the divider
# is reachable by `_detect_sport` and scanned by the detectors, but had no way to
# get a per-sport floor — the override simply did nothing. Found when trying to
# floor World Cup out after the calibration study (43 settled bets, -43.2% ROI):
# `_detect_sport("KXWCSPREAD-...")` returns "worldcup", which was not here, so
# `MIN_EDGE_THRESHOLD_WORLDCUP` was ignored.
_SUPPORTED_SPORTS: tuple[str, ...] = (
    "mlb", "nba", "nhl", "nfl", "ncaab", "ncaaf", "mls", "soccer",
    # ── previously orphaned ──
    "worldcup", "ufc", "boxing", "golf", "nascar", "ipl", "esports", "tennis",
)


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in _TRUTHY


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name}={raw!r} is not a valid float") from exc


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name}={raw!r} is not a valid int") from exc


def _str(name: str, default: str) -> str:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw


def _list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.getenv(name, "") or ""
    items = [piece.strip() for piece in raw.split(",") if piece.strip()]
    if items:
        return items
    return list(default) if default else []


# ── Credential groups ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class KalshiCredentials:
    api_key: str = ""
    # Note: default empty string mirrors `os.getenv("KALSHI_PRIVATE_KEY_PATH", "")`
    # in kalshi_client.py — an unset env var must fall through to the
    # "credentials not configured" error path, not a "file not found at
    # <default-path>" path. `.env.example` ships the recommended path
    # (`keys/live/kalshi_private.key`); users with a typical `.env` always
    # have this set.
    private_key_path: str = ""
    private_key_inline: str = ""  # KALSHI_PRIVATE_KEY (PEM content for cloud)
    base_url: str = "https://api.elections.kalshi.com/trade-api/v2"

    @classmethod
    def from_env(cls) -> "KalshiCredentials":
        return cls(
            api_key=_str("KALSHI_API_KEY", ""),
            private_key_path=_str("KALSHI_PRIVATE_KEY_PATH", ""),
            private_key_inline=_str("KALSHI_PRIVATE_KEY", ""),
            base_url=_str("KALSHI_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2").rstrip("/"),
        )


@dataclass(frozen=True)
class KalshiProdCredentials:
    """Distinct prod-pointing credentials used by `make_prod_client()`."""
    api_key: str = ""
    private_key_path: str = ""
    base_url: str = "https://api.elections.kalshi.com/trade-api/v2"

    @classmethod
    def from_env(cls) -> "KalshiProdCredentials":
        return cls(
            api_key=_str("KALSHI_PROD_API_KEY", ""),
            private_key_path=_str("KALSHI_PROD_PRIVATE_KEY_PATH", ""),
            base_url=_str("KALSHI_PROD_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2").rstrip("/"),
        )


@dataclass(frozen=True)
class PolymarketCredentials:
    """PM2 execution credentials — Polymarket US retail API (Ed25519).

    The operator's funded account is the CFTC-regulated **Polymarket US**
    product (iOS-app only). Its retail API authenticates with Ed25519 API
    keys — **not** the international EIP-712 / py-clob-client wallet scheme.
    `key_id` is a UUID and `secret_key` is the base64-encoded Ed25519 private
    key, both generated once at https://polymarket.us/developer. Requests are
    signed per-call (see `polymarket_exec_client`); there is no on-chain
    wallet, funder address, or signature type. Full setup + the verified auth
    contract: docs/setup/polymarket-us-setup.md.

    `dry_run` (env `POLYMARKET_DRY_RUN`, default **true**) is the PM2c
    venue-scoped safety: Polymarket orders are blocked unless BOTH the global
    `DRY_RUN` and `POLYMARKET_DRY_RUN` are false. The operator runs Kalshi
    live (`DRY_RUN=false`), so without this flag, wiring the Polymarket
    execution pipeline would have gone live instantly — the phased plan
    requires the dry-run edge window to prove out first (ROADMAP Priority 0).
    """
    key_id: str = ""
    secret_key: str = ""
    host: str = "https://api.polymarket.us"
    dry_run: bool = True

    @classmethod
    def from_env(cls) -> "PolymarketCredentials":
        return cls(
            key_id=_str("POLYMARKET_KEY_ID", ""),
            secret_key=_str("POLYMARKET_SECRET_KEY", ""),
            host=_str("POLYMARKET_API_HOST", "https://api.polymarket.us").rstrip("/"),
            dry_run=_bool("POLYMARKET_DRY_RUN", True),
        )


@dataclass(frozen=True)
class OddsApiCredentials:
    keys: list[str] = field(default_factory=list)
    single_key: str = ""  # ODDS_API_KEY — fallback used by odds_api.py

    @classmethod
    def from_env(cls) -> "OddsApiCredentials":
        return cls(
            keys=_list("ODDS_API_KEYS"),
            single_key=_str("ODDS_API_KEY", ""),
        )


@dataclass(frozen=True)
class AlpacaCredentials:
    api_key: str = ""
    secret_key: str = ""
    base_url: str = "https://paper-api.alpaca.markets"

    @classmethod
    def from_env(cls) -> "AlpacaCredentials":
        return cls(
            api_key=_str("ALPACA_API_KEY", ""),
            secret_key=_str("ALPACA_SECRET_KEY", ""),
            base_url=_str("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
        )


@dataclass(frozen=True)
class TelegramCredentials:
    token: str = ""
    chat_id: str = ""

    @classmethod
    def from_env(cls) -> "TelegramCredentials":
        return cls(
            token=_str("TELEGRAM_TOKEN", ""),
            chat_id=_str("TELEGRAM_CHAT_ID", ""),
        )


# ── Operational groups ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class RiskLimits:
    unit_size: float = 1.00
    max_bet_size: float = 100.0
    max_daily_loss: float = 250.0
    max_open_positions: int = 50
    max_per_event: int = 2
    max_bet_ratio: float = 3.0

    @classmethod
    def from_env(cls) -> "RiskLimits":
        return cls(
            unit_size=_float("UNIT_SIZE", 1.00),
            max_bet_size=_float("MAX_BET_SIZE", 100.0),
            max_daily_loss=_float("MAX_DAILY_LOSS", 250.0),
            max_open_positions=_int("MAX_OPEN_POSITIONS", 50),
            max_per_event=_int("MAX_PER_EVENT", 2),
            max_bet_ratio=_float("MAX_BET_RATIO", 3.0),
        )


@dataclass(frozen=True)
class GateThresholds:
    min_edge_threshold: float = 0.03
    min_market_price: float = 0.12
    min_composite_score: float = 6.0
    min_confidence: str = "medium"
    series_dedup_hours: int = 48
    resting_order_max_hours: int = 24
    allow_prediction_bets: bool = False
    allow_live_bets: bool = False
    no_side_favorite_threshold: float = 0.25
    no_side_min_edge: float = 0.25
    no_side_min_edge_global: float = 0.08
    min_consensus_books_nba: int = 8
    calibration_stdevs_ttl_days: int = 30
    cross_category_dedup: bool = False
    max_live_book_age_seconds: int = 1200
    min_live_consensus_books: int = 3
    require_fresh_calibration: bool = False
    max_bid_ask_spread: float = 0.05
    min_market_volume_24h: int = 0
    # S5 (2026-08-26): Gate 3.7 -- max days between now and a GAME market's
    # event date. Futures are exempt by category; their "event" is a season.
    # Ships at 0 (off) so a fresh clone's behaviour is unchanged and the 2099
    # tickers in the test suite stay valid; the live `.env` sets 14. Every one
    # of the 26 NFL positions that reached 31% of bankroll was bought 25+ days
    # out (median 35, max 112) -- far enough that nothing settled for months
    # while exposure kept stacking, and no other gate measures a standing total.
    max_days_to_event_for_game_markets: int = 0
    # Exchange taker-fee rate, folded into the Gate 3 edge floor and into Kelly
    # sizing since 2026-08-25 (fees were previously invisible end to end: not
    # modelled pre-trade, and the v2 create-order response carries no fee field
    # so nothing captured them post-trade either). Kalshi's published rate; it
    # has changed before, hence the knob. 0 disables fee awareness entirely.
    kalshi_fee_rate: float = 0.07

    @classmethod
    def from_env(cls) -> "GateThresholds":
        return cls(
            min_edge_threshold=_float("MIN_EDGE_THRESHOLD", 0.03),
            min_market_price=_float("MIN_MARKET_PRICE", 0.12),
            min_composite_score=_float("MIN_COMPOSITE_SCORE", 6.0),
            min_confidence=_str("MIN_CONFIDENCE", "medium").strip().lower(),
            series_dedup_hours=_int("SERIES_DEDUP_HOURS", 48),
            resting_order_max_hours=_int("RESTING_ORDER_MAX_HOURS", 24),
            allow_prediction_bets=_bool("ALLOW_PREDICTION_BETS", False),
            allow_live_bets=_bool("ALLOW_LIVE_BETS", False),
            no_side_favorite_threshold=_float("NO_SIDE_FAVORITE_THRESHOLD", 0.25),
            no_side_min_edge=_float("NO_SIDE_MIN_EDGE", 0.25),
            no_side_min_edge_global=_float("NO_SIDE_MIN_EDGE_GLOBAL", 0.08),
            min_consensus_books_nba=_int("MIN_CONSENSUS_BOOKS_NBA", 8),
            calibration_stdevs_ttl_days=_int("CALIBRATION_STDEVS_TTL_DAYS", 30),
            cross_category_dedup=_bool("CROSS_CATEGORY_DEDUP", False),
            max_live_book_age_seconds=_int("MAX_LIVE_BOOK_AGE_SECONDS", 1200),
            min_live_consensus_books=_int("MIN_LIVE_CONSENSUS_BOOKS", 3),
            require_fresh_calibration=_bool("REQUIRE_FRESH_CALIBRATION", False),
            max_bid_ask_spread=_float("MAX_BID_ASK_SPREAD", 0.05),
            min_market_volume_24h=_int("MIN_MARKET_VOLUME_24H", 0),
            max_days_to_event_for_game_markets=_int("MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS", 0),
            kalshi_fee_rate=_float("KALSHI_FEE_RATE", 0.07),
        )


@dataclass(frozen=True)
class KellyConfig:
    kelly_fraction: float = 0.25
    kelly_edge_cap: float = 0.15
    kelly_edge_decay: float = 0.5
    no_side_kelly_price_floor: float = 0.35
    # F4 (2026-08-25): mirror of the floor, on the expensive end. NO bets priced
    # at or above this get the same `no_side_kelly_multiplier`. 0 disables.
    # Default 0 keeps shipped behaviour; the live .env sets 0.50.
    no_side_kelly_price_ceiling: float = 0.0
    no_side_kelly_multiplier: float = 0.5
    no_side_kelly_multiplier_global: float = 1.0

    @classmethod
    def from_env(cls) -> "KellyConfig":
        return cls(
            kelly_fraction=_float("KELLY_FRACTION", 0.25),
            kelly_edge_cap=_float("KELLY_EDGE_CAP", 0.15),
            kelly_edge_decay=_float("KELLY_EDGE_DECAY", 0.5),
            no_side_kelly_price_floor=_float("NO_SIDE_KELLY_PRICE_FLOOR", 0.35),
            no_side_kelly_price_ceiling=_float("NO_SIDE_KELLY_PRICE_CEILING", 0.0),
            no_side_kelly_multiplier=_float("NO_SIDE_KELLY_MULTIPLIER", 0.5),
            no_side_kelly_multiplier_global=_float("NO_SIDE_KELLY_MULTIPLIER_GLOBAL", 1.0),
        )


@dataclass(frozen=True)
class PerSportOverrides:
    """Per-sport overrides for sport-sensitive gate thresholds.

    Only sports with the env var explicitly set appear in each dict. Callers
    should fall back to the corresponding global value in `GateThresholds`
    for any sport not in the dict — preserving the existing fallback idiom.

    - `min_edge`              : `MIN_EDGE_THRESHOLD_<SPORT>` (per-sport edge floor)
    - `series_dedup_hours`    : `SERIES_DEDUP_HOURS_<SPORT>` (R9: MLB/NHL series
      cycles on consecutive days exceed the 48h global default — F12 observed
      a NYM/LAD pair bet at 49h apart that slipped through; both lost)
    - `cross_category_dedup`  : `CROSS_CATEGORY_DEDUP_<SPORT>` (R8: when true,
      collapse ML+Total+Spread on the same game to one bet for that sport;
      sports not present in the dict fall back to the global
      `CROSS_CATEGORY_DEDUP` value)
    """
    min_edge: dict[str, float] = field(default_factory=dict)
    series_dedup_hours: dict[str, int] = field(default_factory=dict)
    cross_category_dedup: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def from_env(cls, sports: Iterable[str] = _SUPPORTED_SPORTS) -> "PerSportOverrides":
        min_edge: dict[str, float] = {}
        series_dedup: dict[str, int] = {}
        cross_cat: dict[str, bool] = {}
        for sport in sports:
            raw_edge = os.getenv(f"MIN_EDGE_THRESHOLD_{sport.upper()}")
            if raw_edge is not None and raw_edge != "":
                try:
                    min_edge[sport] = float(raw_edge)
                except ValueError:
                    # Match current kalshi_executor behavior: skip bad values.
                    pass

            raw_dedup = os.getenv(f"SERIES_DEDUP_HOURS_{sport.upper()}")
            if raw_dedup is not None and raw_dedup != "":
                try:
                    series_dedup[sport] = int(raw_dedup)
                except ValueError:
                    pass

            raw_xcat = os.getenv(f"CROSS_CATEGORY_DEDUP_{sport.upper()}")
            if raw_xcat is not None and raw_xcat != "":
                cross_cat[sport] = raw_xcat.strip().lower() in _TRUTHY
        return cls(
            min_edge=min_edge,
            series_dedup_hours=series_dedup,
            cross_category_dedup=cross_cat,
        )


@dataclass(frozen=True)
class System:
    dry_run: bool = True
    log_level: str = "INFO"
    project_root: str = ""  # PROJECT_ROOT override; "" → caller falls back to paths.PROJECT_ROOT
    test_calibration_stdevs: bool = False

    @classmethod
    def from_env(cls) -> "System":
        return cls(
            dry_run=_bool("DRY_RUN", True),
            log_level=_str("LOG_LEVEL", "INFO").strip().upper(),
            project_root=_str("PROJECT_ROOT", ""),
            test_calibration_stdevs=_bool("TEST_CALIBRATION_STDEVS", False),
        )


@dataclass(frozen=True)
class OddsCacheConfig:
    """File-backed cache for Odds API responses (R24b).

    Survives across CLI invocations so back-to-back `scan.py` calls don't
    refetch the same sport keys. Files live under `data/cache/odds/`.

    `live_ttl_seconds` (L1) is a shorter TTL applied — to both the file cache
    and the in-process cache — whenever a sport response contains at least one
    in-play event (`commence_time < now`). In-progress games then refetch on a
    seconds-fresh cadence so their edge compares Kalshi's live price against
    *current* book odds, not a frozen pre-game snapshot (the F44 phantom-edge
    bug). Pre-game responses keep the longer `ttl_seconds` (quota-friendly).
    """
    ttl_seconds: int = 300
    live_ttl_seconds: int = 45
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "OddsCacheConfig":
        return cls(
            ttl_seconds=_int("ODDS_CACHE_TTL_SECONDS", 300),
            live_ttl_seconds=_int("ODDS_LIVE_TTL_SECONDS", 45),
            enabled=_bool("ODDS_CACHE_ENABLED", True),
        )


@dataclass(frozen=True)
class ScanCacheConfig:
    """File-backed cache of the last preview's row→ticker mapping (R26).

    Locks the row order between `scan.py … --filter X` (preview) and the
    follow-up `scan.py … --pick 1,3 --execute`. Without it, a second live
    scan can reorder rows on price/score drift, executing the wrong picks.

    File: `data/cache/last_scan.json`. TTL default 600s = 10 minutes
    (long enough to read the table and pick rows, short enough that a
    user returning hours later gets a fresh scan). 0 disables.
    """
    ttl_seconds: int = 600
    enabled: bool = True

    @classmethod
    def from_env(cls) -> "ScanCacheConfig":
        return cls(
            ttl_seconds=_int("SCAN_CACHE_TTL_SECONDS", 600),
            enabled=_bool("SCAN_CACHE_ENABLED", True),
        )


# ── Aggregate ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    kalshi: KalshiCredentials
    kalshi_prod: KalshiProdCredentials
    polymarket: PolymarketCredentials
    odds: OddsApiCredentials
    alpaca: AlpacaCredentials
    telegram: TelegramCredentials
    risk: RiskLimits
    gates: GateThresholds
    kelly: KellyConfig
    per_sport: PerSportOverrides
    system: System
    odds_cache: OddsCacheConfig
    scan_cache: ScanCacheConfig

    @classmethod
    def from_env(cls) -> "Config":
        cfg = cls(
            kalshi=KalshiCredentials.from_env(),
            kalshi_prod=KalshiProdCredentials.from_env(),
            polymarket=PolymarketCredentials.from_env(),
            odds=OddsApiCredentials.from_env(),
            alpaca=AlpacaCredentials.from_env(),
            telegram=TelegramCredentials.from_env(),
            risk=RiskLimits.from_env(),
            gates=GateThresholds.from_env(),
            kelly=KellyConfig.from_env(),
            per_sport=PerSportOverrides.from_env(),
            system=System.from_env(),
            odds_cache=OddsCacheConfig.from_env(),
            scan_cache=ScanCacheConfig.from_env(),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        """Raise ValueError on impossible combinations.

        Conservative: only flag combinations that are *guaranteed* to break
        the pipeline, not values that are merely unusual. A user setting
        MIN_EDGE_THRESHOLD=0.30 is surprising but legal.
        """
        if self.risk.max_bet_size < self.risk.unit_size:
            raise ValueError(
                f"MAX_BET_SIZE ({self.risk.max_bet_size}) must be >= "
                f"UNIT_SIZE ({self.risk.unit_size})"
            )
        if self.risk.unit_size <= 0:
            raise ValueError(f"UNIT_SIZE must be > 0, got {self.risk.unit_size}")
        if self.risk.max_daily_loss < 0:
            raise ValueError(
                f"MAX_DAILY_LOSS must be >= 0, got {self.risk.max_daily_loss}"
            )
        if self.risk.max_open_positions < 0:
            raise ValueError(
                f"MAX_OPEN_POSITIONS must be >= 0, got {self.risk.max_open_positions}"
            )
        if self.risk.max_per_event < 0:
            raise ValueError(
                f"MAX_PER_EVENT must be >= 0, got {self.risk.max_per_event}"
            )
        if self.gates.min_confidence not in _CONFIDENCE_LEVELS:
            raise ValueError(
                f"MIN_CONFIDENCE must be one of {sorted(_CONFIDENCE_LEVELS)}, "
                f"got {self.gates.min_confidence!r}"
            )
        if not 0.0 <= self.kelly.kelly_fraction <= 1.0:
            raise ValueError(
                f"KELLY_FRACTION must be in [0, 1], got {self.kelly.kelly_fraction}"
            )
        if self.gates.no_side_min_edge_global < 0:
            raise ValueError(
                f"NO_SIDE_MIN_EDGE_GLOBAL must be >= 0, got {self.gates.no_side_min_edge_global}"
            )
        if not 0.0 <= self.kelly.no_side_kelly_multiplier_global <= 1.0:
            raise ValueError(
                f"NO_SIDE_KELLY_MULTIPLIER_GLOBAL must be in [0, 1], got {self.kelly.no_side_kelly_multiplier_global}"
            )
        if self.gates.min_consensus_books_nba < 0:
            raise ValueError(
                f"MIN_CONSENSUS_BOOKS_NBA must be >= 0, got {self.gates.min_consensus_books_nba}"
            )
        if self.gates.calibration_stdevs_ttl_days <= 0:
            raise ValueError(
                f"CALIBRATION_STDEVS_TTL_DAYS must be > 0, got {self.gates.calibration_stdevs_ttl_days}"
            )
        if self.gates.max_live_book_age_seconds < 0:
            raise ValueError(
                f"MAX_LIVE_BOOK_AGE_SECONDS must be >= 0, got {self.gates.max_live_book_age_seconds}"
            )
        if self.gates.min_live_consensus_books < 0:
            raise ValueError(
                f"MIN_LIVE_CONSENSUS_BOOKS must be >= 0, got {self.gates.min_live_consensus_books}"
            )
        if self.gates.min_edge_threshold < 0:
            raise ValueError(
                f"MIN_EDGE_THRESHOLD must be >= 0, got {self.gates.min_edge_threshold}"
            )
        if not 0.0 <= self.gates.min_market_price <= 1.0:
            raise ValueError(
                f"MIN_MARKET_PRICE must be in [0, 1], got {self.gates.min_market_price}"
            )
        if not 0.0 <= self.gates.max_bid_ask_spread <= 1.0:
            raise ValueError(
                f"MAX_BID_ASK_SPREAD must be in [0, 1], got {self.gates.max_bid_ask_spread}"
            )
        if self.gates.min_market_volume_24h < 0:
            raise ValueError(
                f"MIN_MARKET_VOLUME_24H must be >= 0, got {self.gates.min_market_volume_24h}"
            )
        if self.gates.max_days_to_event_for_game_markets < 0:
            raise ValueError(
                "MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS must be >= 0, got "
                f"{self.gates.max_days_to_event_for_game_markets}"
            )
        if self.system.log_level not in _LOG_LEVELS:
            raise ValueError(
                f"LOG_LEVEL must be one of {sorted(_LOG_LEVELS)}, "
                f"got {self.system.log_level!r}"
            )
        if self.odds_cache.ttl_seconds < 0:
            raise ValueError(
                f"ODDS_CACHE_TTL_SECONDS must be >= 0, got {self.odds_cache.ttl_seconds}"
            )
        if self.odds_cache.live_ttl_seconds < 0:
            raise ValueError(
                f"ODDS_LIVE_TTL_SECONDS must be >= 0, got {self.odds_cache.live_ttl_seconds}"
            )
        if self.scan_cache.ttl_seconds < 0:
            raise ValueError(
                f"SCAN_CACHE_TTL_SECONDS must be >= 0, got {self.scan_cache.ttl_seconds}"
            )

    def edge_threshold_for_sport(self, sport: str) -> float:
        """Resolve per-sport edge floor with fallback to global.

        Mirrors the current `_PER_SPORT_MIN_EDGE.get(sport, MIN_EDGE_THRESHOLD)`
        idiom in `kalshi_executor.py` so Phase 2 migration is mechanical.
        """
        if not sport:
            return self.gates.min_edge_threshold
        return self.per_sport.min_edge.get(
            sport.strip().lower(), self.gates.min_edge_threshold
        )

    def cross_category_dedup_for(self, sport: str | None) -> bool:
        """Resolve per-sport cross-category dedup flag with fallback to global (R8).

        Returns True iff ML + Total + Spread on the same game should collapse
        to a single bet for this sport. ``None`` or unknown sport falls back
        to the global `CROSS_CATEGORY_DEDUP`.
        """
        if not sport:
            return self.gates.cross_category_dedup
        return self.per_sport.cross_category_dedup.get(
            sport.strip().lower(), self.gates.cross_category_dedup
        )


# ── Memoization ─────────────────────────────────────────────────────────────

_cached: Config | None = None


def get_config() -> Config:
    """Return the process-wide Config, building it on first call.

    Memoized so repeated `from app.config import get_config; cfg = get_config()`
    is cheap. Use `reset_config()` after mutating `os.environ` to force a
    re-read.
    """
    global _cached
    if _cached is None:
        _cached = Config.from_env()
    return _cached


def reset_config() -> None:
    """Drop the memoized Config so the next `get_config()` re-reads env.

    Called by tests and by any host that mutates `os.environ` after import.
    """
    global _cached
    _cached = None
