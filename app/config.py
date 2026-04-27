"""
app/config.py — single source of truth for every Edge-Radar runtime knob.

Per the CONFIG_CENTRALIZATION enhancement plan (Phase 1): typed dataclasses
group every env-driven setting, each with `from_env()` for one-shot coercion
and `validate()` for impossible combinations.

Scripts should reach config through `get_config()` (memoized) so Streamlit
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
_SUPPORTED_SPORTS: tuple[str, ...] = (
    "mlb", "nba", "nhl", "nfl", "ncaab", "ncaaf", "mls", "soccer",
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
    max_open_positions: int = 10
    max_per_event: int = 2
    max_bet_ratio: float = 3.0

    @classmethod
    def from_env(cls) -> "RiskLimits":
        return cls(
            unit_size=_float("UNIT_SIZE", 1.00),
            max_bet_size=_float("MAX_BET_SIZE", 100.0),
            max_daily_loss=_float("MAX_DAILY_LOSS", 250.0),
            max_open_positions=_int("MAX_OPEN_POSITIONS", 10),
            max_per_event=_int("MAX_PER_EVENT", 2),
            max_bet_ratio=_float("MAX_BET_RATIO", 3.0),
        )


@dataclass(frozen=True)
class GateThresholds:
    min_edge_threshold: float = 0.03
    min_market_price: float = 0.10
    min_composite_score: float = 6.0
    min_confidence: str = "medium"
    series_dedup_hours: int = 48
    resting_order_max_hours: int = 24
    allow_prediction_bets: bool = False
    no_side_favorite_threshold: float = 0.25
    no_side_min_edge: float = 0.25

    @classmethod
    def from_env(cls) -> "GateThresholds":
        return cls(
            min_edge_threshold=_float("MIN_EDGE_THRESHOLD", 0.03),
            min_market_price=_float("MIN_MARKET_PRICE", 0.10),
            min_composite_score=_float("MIN_COMPOSITE_SCORE", 6.0),
            min_confidence=_str("MIN_CONFIDENCE", "medium").strip().lower(),
            series_dedup_hours=_int("SERIES_DEDUP_HOURS", 48),
            resting_order_max_hours=_int("RESTING_ORDER_MAX_HOURS", 24),
            allow_prediction_bets=_bool("ALLOW_PREDICTION_BETS", False),
            no_side_favorite_threshold=_float("NO_SIDE_FAVORITE_THRESHOLD", 0.25),
            no_side_min_edge=_float("NO_SIDE_MIN_EDGE", 0.25),
        )


@dataclass(frozen=True)
class KellyConfig:
    kelly_fraction: float = 0.25
    kelly_edge_cap: float = 0.15
    kelly_edge_decay: float = 0.5
    no_side_kelly_price_floor: float = 0.35
    no_side_kelly_multiplier: float = 0.5

    @classmethod
    def from_env(cls) -> "KellyConfig":
        return cls(
            kelly_fraction=_float("KELLY_FRACTION", 0.25),
            kelly_edge_cap=_float("KELLY_EDGE_CAP", 0.15),
            kelly_edge_decay=_float("KELLY_EDGE_DECAY", 0.5),
            no_side_kelly_price_floor=_float("NO_SIDE_KELLY_PRICE_FLOOR", 0.35),
            no_side_kelly_multiplier=_float("NO_SIDE_KELLY_MULTIPLIER", 0.5),
        )


@dataclass(frozen=True)
class PerSportOverrides:
    """Per-sport overrides for sport-sensitive gate thresholds.

    Only sports with the env var explicitly set appear in each dict. Callers
    should fall back to the corresponding global value in `GateThresholds`
    for any sport not in the dict — preserving the existing fallback idiom.

    - `min_edge`            : `MIN_EDGE_THRESHOLD_<SPORT>` (per-sport edge floor)
    - `series_dedup_hours`  : `SERIES_DEDUP_HOURS_<SPORT>` (R9: MLB/NHL series
      cycles on consecutive days exceed the 48h global default — F12 observed
      a NYM/LAD pair bet at 49h apart that slipped through; both lost)
    """
    min_edge: dict[str, float] = field(default_factory=dict)
    series_dedup_hours: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_env(cls, sports: Iterable[str] = _SUPPORTED_SPORTS) -> "PerSportOverrides":
        min_edge: dict[str, float] = {}
        series_dedup: dict[str, int] = {}
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
        return cls(min_edge=min_edge, series_dedup_hours=series_dedup)


@dataclass(frozen=True)
class System:
    dry_run: bool = True
    log_level: str = "INFO"
    project_root: str = ""  # PROJECT_ROOT override; "" → caller falls back to paths.PROJECT_ROOT

    @classmethod
    def from_env(cls) -> "System":
        return cls(
            dry_run=_bool("DRY_RUN", True),
            log_level=_str("LOG_LEVEL", "INFO").strip().upper(),
            project_root=_str("PROJECT_ROOT", ""),
        )


# ── Aggregate ───────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    kalshi: KalshiCredentials
    kalshi_prod: KalshiProdCredentials
    odds: OddsApiCredentials
    alpaca: AlpacaCredentials
    telegram: TelegramCredentials
    risk: RiskLimits
    gates: GateThresholds
    kelly: KellyConfig
    per_sport: PerSportOverrides
    system: System

    @classmethod
    def from_env(cls) -> "Config":
        cfg = cls(
            kalshi=KalshiCredentials.from_env(),
            kalshi_prod=KalshiProdCredentials.from_env(),
            odds=OddsApiCredentials.from_env(),
            alpaca=AlpacaCredentials.from_env(),
            telegram=TelegramCredentials.from_env(),
            risk=RiskLimits.from_env(),
            gates=GateThresholds.from_env(),
            kelly=KellyConfig.from_env(),
            per_sport=PerSportOverrides.from_env(),
            system=System.from_env(),
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
        if self.gates.min_edge_threshold < 0:
            raise ValueError(
                f"MIN_EDGE_THRESHOLD must be >= 0, got {self.gates.min_edge_threshold}"
            )
        if not 0.0 <= self.gates.min_market_price <= 1.0:
            raise ValueError(
                f"MIN_MARKET_PRICE must be in [0, 1], got {self.gates.min_market_price}"
            )
        if self.system.log_level not in _LOG_LEVELS:
            raise ValueError(
                f"LOG_LEVEL must be one of {sorted(_LOG_LEVELS)}, "
                f"got {self.system.log_level!r}"
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


# ── Memoization ─────────────────────────────────────────────────────────────

_cached: Config | None = None


def get_config() -> Config:
    """Return the process-wide Config, building it on first call.

    Memoized so repeated `from app.config import get_config; cfg = get_config()`
    is cheap. Use `reset_config()` after mutating `os.environ` (e.g. after
    `webapp/services.py` injects Streamlit secrets) to force a re-read.
    """
    global _cached
    if _cached is None:
        _cached = Config.from_env()
    return _cached


def reset_config() -> None:
    """Drop the memoized Config so the next `get_config()` re-reads env.

    Called by tests and by Streamlit Cloud bootstrap after secrets injection.
    """
    global _cached
    _cached = None
