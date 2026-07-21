"""
market_registry.py — ticker → Polymarket US market-slug resolution.

The `MarketClient` contract speaks Kalshi-shaped orders (`ticker`, side,
price) but the Polymarket US retail API addresses markets by **`marketSlug`**
(YES/NO is chosen at order time via `outcomeSide`, so a single slug covers
both sides — no per-token bookkeeping). The scanners are the only components
that know a ticker's market, so every scan records the mapping here and the
execution client resolves it at order time.

Namespace status (2026-07-20): the **futures** scanner reads Polymarket US
market data and records genuine US slugs here — those opportunities are
executable. The **games** scanner still reads international Gamma (a
different slug namespace) and deliberately records nothing (its details
carry no `market_slug`/`slug` key), so `create_order` correctly refuses any
games ticker. The games repoint is a deferred seasonal follow-on — see
docs/setup/polymarket-us-setup.md.

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
    """Merge scan opportunities into the registry (called by the scanners).

    Only records opps whose details carry a Polymarket US `market_slug`
    (falls back to a generic `slug` key); opps without one are skipped, so a
    ticker never resolves to a slug we can't actually trade.
    """
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
        market_slug = details.get("market_slug") or details.get("slug") or ""
        if not (getattr(o, "ticker", "") and market_slug):
            continue
        reg[o.ticker] = {
            "market_slug": str(market_slug),
            "condition_id": details.get("condition_id", ""),
            "title": getattr(o, "title", ""),
            # PM2c: exchange-enforced per-order share minimum (0 = unknown;
            # the exec client falls back to its conservative default).
            "min_order_shares": int(details.get("min_order_shares") or 0),
            "recorded_at": now.isoformat(),
        }
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=1)
    tmp.replace(REGISTRY_PATH)


def lookup(ticker: str) -> dict | None:
    """Resolve a synthetic PM ticker to its US market slug, or None."""
    return _load().get(ticker)
