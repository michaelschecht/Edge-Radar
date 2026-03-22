"""
config.py
Centralized configuration for all FinAgent scripts.

All tunable parameters are loaded from environment variables with sensible
defaults. Import this module instead of scattering os.getenv() calls.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# ── Risk Limits ──────────────────────────────────────────────────────────────

UNIT_SIZE = float(os.getenv("UNIT_SIZE", "1.00"))
MAX_BET_SIZE = float(os.getenv("MAX_BET_SIZE_PREDICTION", "5"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "250"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "10"))
MIN_EDGE_THRESHOLD = float(os.getenv("MIN_EDGE_THRESHOLD", "0.03"))
MIN_COMPOSITE_SCORE = float(os.getenv("MIN_COMPOSITE_SCORE", "6.0"))
MIN_CONFIDENCE = os.getenv("MIN_CONFIDENCE", "medium")
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))
MAX_CONCENTRATION = float(os.getenv("MAX_POSITION_CONCENTRATION", "0.20"))

# ── System ───────────────────────────────────────────────────────────────────

DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ── API Keys ─────────────────────────────────────────────────────────────────

ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")

# ── Scoring Weights ──────────────────────────────────────────────────────────

EDGE_WEIGHT = 0.4
CONFIDENCE_WEIGHT = 0.3
LIQUIDITY_WEIGHT = 0.2
TIME_WEIGHT = 0.1

# ── Prediction Model Parameters ──────────────────────────────────────────────

# Crypto
CRYPTO_DEFAULT_VOL = {
    "bitcoin": 0.55,
    "ethereum": 0.70,
    "ripple": 0.85,
    "dogecoin": 1.00,
    "solana": 0.90,
}
CRYPTO_VOL_FLOOR = 0.05
CRYPTO_HIGH_CONF_DISTANCE = 0.10
CRYPTO_MED_CONF_DISTANCE = 0.03
CRYPTO_HISTORY_DAYS = 7
COINGECKO_RATE_LIMIT_DELAY = 2  # seconds between API calls

# Weather
WEATHER_MAX_FORECAST_DAYS = 7
WEATHER_BASE_UNCERTAINTY_F = 2.5   # base forecast error in °F
WEATHER_UNCERTAINTY_PER_DAY = 1.0  # additional °F per day of forecast horizon

# S&P 500
SPX_DEFAULT_VOL = 0.18        # fallback if VIX unavailable
SPX_MAX_EXPIRY_DAYS = 14      # skip markets further out

# ── Confidence Ranking ───────────────────────────────────────────────────────

CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


# ── Logging ──────────────────────────────────────────────────────────────────

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
