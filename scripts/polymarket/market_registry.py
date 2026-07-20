"""
market_registry.py — ticker → CLOB-token resolution for Polymarket execution.

The `MarketClient` contract speaks Kalshi-shaped orders (`ticker`, side,
price) but the Polymarket CLOB needs a `token_id`. The scanners are the only
components that know the mapping (they read it off Gamma), so every scan
records its opportunities here; the execution client resolves tickers from
this file at order time. Side → token index is structural: our synthetic
"yes" is always outcome/token 0 and "no" is token 1 (see
`polymarket_games_edge._build_opp` / `polymarket_futures_edge`).

Entries expire after `MAX_AGE_DAYS` so the file can't grow without bound and
a stale mapping can't place an order on a long-gone market.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

REGISTRY_PATH = (Path(__file__).resolve().parent.parent.parent
                 / "data" / "polymarket" / "market_registry.json")
MAX_AGE_DAYS = 7


def _load() -> dict:
    try:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_opportunities(opps: list) -> None:
    """Merge scan opportunities into the registry (called by the scanners)."""
    if not opps:
        return
    now = datetime.now(timezone.utc)
    reg = _load()
    # Prune expired entries on every write.
    cutoff = (now - timedelta(days=MAX_AGE_DAYS)).isoformat()
    reg = {k: v for k, v in reg.items()
           if (v.get("recorded_at") or "") >= cutoff}
    for o in opps:
        details = getattr(o, "details", None) or {}
        token_ids = details.get("clob_token_ids") or []
        if not (getattr(o, "ticker", "") and token_ids):
            continue
        reg[o.ticker] = {
            "condition_id": details.get("condition_id", ""),
            "clob_token_ids": [str(t) for t in token_ids],
            "title": getattr(o, "title", ""),
            "recorded_at": now.isoformat(),
        }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1)
    tmp.replace(REGISTRY_PATH)


def lookup(ticker: str) -> dict | None:
    """Resolve a synthetic PM ticker to its CLOB tokens, or None."""
    return _load().get(ticker)
