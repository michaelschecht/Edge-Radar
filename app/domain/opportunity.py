"""
Opportunity — a scored betting/trading opportunity.

This is the primary domain object that flows through the entire pipeline:
scanner -> risk check -> execution -> settlement.

The canonical definition lives in scripts/shared/opportunity.py (used by
all CLI scripts).  This module re-exports it so that app.domain consumers
get the same class.
"""

import sys
from pathlib import Path

# Ensure scripts/shared is importable (for cases where only app/ is on sys.path)
_shared = str(Path(__file__).resolve().parent.parent.parent / "scripts" / "shared")
if _shared not in sys.path:
    sys.path.insert(0, _shared)

from opportunity import Opportunity  # noqa: F401

__all__ = ["Opportunity"]
