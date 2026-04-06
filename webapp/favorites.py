"""
favorites.py — Save and load favorite scan configurations.

Stores favorites as a JSON file in data/webapp/favorites.json.
"""

import json
from pathlib import Path

FAVORITES_PATH = Path(__file__).resolve().parent.parent / "data" / "webapp" / "favorites.json"


def load_favorites() -> list[dict]:
    """Load saved favorite scan configs."""
    if not FAVORITES_PATH.exists():
        return []
    try:
        with open(FAVORITES_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_favorite(fav: dict):
    """Append a favorite scan config. Deduplicates by name."""
    favs = load_favorites()
    # Replace existing with same name
    favs = [f for f in favs if f.get("name") != fav.get("name")]
    favs.append(fav)
    _write(favs)


def delete_favorite(name: str):
    """Remove a favorite by name."""
    favs = load_favorites()
    favs = [f for f in favs if f.get("name") != name]
    _write(favs)


def _write(favs: list[dict]):
    """Write favorites to disk."""
    FAVORITES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(FAVORITES_PATH, "w") as f:
        json.dump(favs, f, indent=2)
