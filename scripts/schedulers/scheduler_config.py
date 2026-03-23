"""
scheduler_config.py
Per-scheduler configuration loaded from environment variables.

Each scheduler has its own interval, filters, max-bets, and enable flag.
Add new scheduler profiles here as you expand to new markets.

Env var naming convention:
    SCHED_{NAME}_ENABLED=true
    SCHED_{NAME}_INTERVAL_MINUTES=15
    SCHED_{NAME}_FILTERS=nba
    SCHED_{NAME}_MAX_BETS=5
    SCHED_{NAME}_PREDICTION=false
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class SchedulerProfile:
    """Configuration for a single scheduler instance."""
    name: str
    enabled: bool = False
    interval_minutes: int = 15
    filters: list[str] = field(default_factory=list)
    max_bets: int = 5
    prediction: bool = False  # True = prediction markets, False = sports

    @classmethod
    def from_env(cls, name: str) -> "SchedulerProfile":
        """Load a scheduler profile from SCHED_{NAME}_* env vars."""
        prefix = f"SCHED_{name.upper()}"
        filters_raw = os.getenv(f"{prefix}_FILTERS", "")
        return cls(
            name=name,
            enabled=os.getenv(f"{prefix}_ENABLED", "false").lower() == "true",
            interval_minutes=int(os.getenv(f"{prefix}_INTERVAL_MINUTES", "15")),
            filters=[f.strip() for f in filters_raw.split(",") if f.strip()],
            max_bets=int(os.getenv(f"{prefix}_MAX_BETS", "5")),
            prediction=os.getenv(f"{prefix}_PREDICTION", "false").lower() == "true",
        )


# ── Registry ────────────────────────────────────────────────────────────────
# Add new scheduler names here. Each one reads its own SCHED_* env vars.
# A scheduler that is not ENABLED will be skipped at startup.

SCHEDULER_NAMES = [
    "nba",
    "nhl",
    "mlb",
    "nfl",
    "ncaa",
    "soccer",
    "crypto",
    "weather",
    "spx",
]


def load_all_profiles() -> list[SchedulerProfile]:
    """Load all registered scheduler profiles from env vars."""
    return [SchedulerProfile.from_env(name) for name in SCHEDULER_NAMES]


def load_enabled_profiles() -> list[SchedulerProfile]:
    """Load only enabled scheduler profiles."""
    return [p for p in load_all_profiles() if p.enabled]
