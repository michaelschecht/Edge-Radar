"""
bootstrap.py
One-liner import that sets up sys.path for all Edge-Radar scripts.

Usage (replaces the 3-line sys.path boilerplate):
    import bootstrap  # noqa: F401

This adds scripts/shared, scripts/kalshi, scripts/prediction,
scripts/schedulers to sys.path and ensures data directories exist.
"""

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_SHARED_DIR = _SCRIPTS_DIR / "shared"

# Add shared first so `import paths` works, then let paths.py add everything else
if str(_SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(_SHARED_DIR))

import paths  # noqa: F401 -- configures all paths + creates data dirs
