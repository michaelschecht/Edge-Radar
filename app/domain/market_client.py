"""
MarketClient — the venue-neutral execution-client contract (PM2 seam).

The canonical definition lives in scripts/shared/market_client.py (used by
all CLI scripts).  This module re-exports it so that app.domain consumers
get the same Protocol and factory.
"""

import sys
from pathlib import Path

# Ensure scripts/shared is importable (for cases where only app/ is on sys.path)
_shared = str(Path(__file__).resolve().parent.parent.parent / "scripts" / "shared")
if _shared not in sys.path:
    sys.path.insert(0, _shared)

from market_client import MarketClient, get_market_client, VENUES  # noqa: F401

__all__ = ["MarketClient", "get_market_client", "VENUES"]
