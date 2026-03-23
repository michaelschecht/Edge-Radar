"""
paths.py
Standardized path setup for all Edge-Radar scripts.

Adds the project root and script directories to sys.path so that
cross-package imports work regardless of where scripts are invoked from.

Usage (at the top of any entry-point script):
    from pathlib import Path
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    # -- OR simply: --
    # import scripts.shared.paths  (auto-configures on import)
"""

import sys
from pathlib import Path

# Project root: Edge-Radar/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Script directories
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
KALSHI_DIR = SCRIPTS_DIR / "kalshi"
PREDICTION_DIR = SCRIPTS_DIR / "prediction"
SHARED_DIR = SCRIPTS_DIR / "shared"
SCHEDULERS_DIR = SCRIPTS_DIR / "schedulers"

# Data directories
DATA_DIR = PROJECT_ROOT / "data"
TRADE_LOG_PATH = DATA_DIR / "history" / "kalshi_trades.json"
SETTLEMENT_LOG_PATH = DATA_DIR / "history" / "kalshi_settlements.json"
SPORTS_OPPORTUNITIES_PATH = DATA_DIR / "watchlists" / "kalshi_opportunities.json"
PREDICTION_OPPORTUNITIES_PATH = DATA_DIR / "watchlists" / "prediction_opportunities.json"

# Ensure data directories exist
for d in [DATA_DIR / "history", DATA_DIR / "watchlists", DATA_DIR / "positions"]:
    d.mkdir(parents=True, exist_ok=True)

# Add script directories to sys.path (idempotent)
for p in [str(SCRIPTS_DIR), str(KALSHI_DIR), str(PREDICTION_DIR), str(SHARED_DIR), str(SCHEDULERS_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)
