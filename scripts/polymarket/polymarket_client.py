"""
polymarket_client.py — read-only Polymarket (Gamma API) client.

Phase 1 of the Polymarket integration (docs/ROADMAP.md Priority 0). This is a
**read-only** client: it fetches championship-futures markets and their prices
from the public Gamma API (https://gamma-api.polymarket.com, no auth, no wallet).
It places NO orders — order placement is Phase 2 (CLOB / py-clob-client).

Gamma data model (verified live 2026-07-14):
  - A championship future (e.g. "World Cup Winner") is an **event** with a
    `markets` list of binary sub-markets, one per candidate.
  - Each sub-market carries `groupItemTitle` (the candidate name, e.g. "Spain"),
    `question`, `outcomes` ('["Yes","No"]'), `outcomePrices` ('["0.22","0.78"]'),
    `bestBid`/`bestAsk` (the Yes-token book), `conditionId`, `clobTokenIds`,
    `volume`, `liquidity`, and per-sub-market `active`/`closed` flags.
  - Eliminated candidates are `closed=True` with price 0/1 and must be skipped.
"""

import json
import logging

import requests

try:
    from logging_setup import setup_logging
    log = setup_logging("polymarket_client")
except Exception:  # pragma: no cover - fallback if shared logging unavailable
    log = logging.getLogger("polymarket_client")

GAMMA_API = "https://gamma-api.polymarket.com"
_USER_AGENT = "Edge-Radar/1.0 (+polymarket-futures-phase1)"
_TIMEOUT = 20
# Gamma /markets and /events cap responses at 100 rows; paginate with offset.
_PAGE = 100


def _parse_json_field(value, default=None):
    """Gamma returns several array fields as JSON *strings* (e.g. outcomes,
    outcomePrices, clobTokenIds). Parse defensively — return `default` on any
    malformed value rather than raising."""
    if value is None:
        return default
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return default
    return default


def _to_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def _get(path: str, params: dict) -> list:
    """GET a Gamma endpoint, tolerating both list and {data:[...]} envelopes.
    Returns [] on any error (read-only scanner must never crash the pipeline)."""
    try:
        resp = requests.get(
            f"{GAMMA_API}{path}",
            params=params,
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("data") or data.get("markets") or data.get("events") or []
        return []
    except Exception as e:
        log.warning("Gamma GET %s failed: %s", path, e)
        return []


def fetch_event_by_slug(slug: str) -> dict | None:
    """Fetch a single event by its Gamma slug (most robust lookup)."""
    events = _get("/events", {"slug": slug, "closed": "false"})
    return events[0] if events else None


def find_event(slug: str | None = None, search_terms: tuple[str, ...] = ()) -> dict | None:
    """Locate a championship-future event.

    Tries the exact `slug` first (cheap, precise). Falls back to a keyword scan
    over a few pages of active events matching any of `search_terms` in the
    event title, preferring the event with the most sub-markets (the real
    outright board, not a one-off prop).
    """
    if slug:
        ev = fetch_event_by_slug(slug)
        if ev:
            return ev

    if not search_terms:
        return None
    terms = tuple(t.lower() for t in search_terms)
    best = None
    for page in range(3):  # up to 300 active events
        events = _get("/events", {"closed": "false", "active": "true",
                                   "limit": _PAGE, "offset": page * _PAGE})
        if not events:
            break
        for e in events:
            title = (e.get("title") or "").lower()
            if any(t in title for t in terms):
                n = len(e.get("markets", []))
                if best is None or n > len(best.get("markets", [])):
                    best = e
        if len(events) < _PAGE:
            break
    return best


def iter_future_candidates(event: dict) -> list[dict]:
    """Normalize an event's sub-markets into candidate dicts for edge detection.

    Skips sub-markets that are closed/inactive or degenerate (Yes price ≤0 or
    ≥1 — i.e. an eliminated or already-decided candidate). The `yes_price` is
    the Yes-token **ask** (what we'd pay to back the candidate); `yes_bid` is
    the best bid, used for the bid/ask liquidity estimate.
    """
    out: list[dict] = []
    for m in event.get("markets", []) or []:
        if m.get("closed") or m.get("active") is False:
            continue
        prices = _parse_json_field(m.get("outcomePrices"), []) or []
        best_ask = _to_float(m.get("bestAsk"), 0.0)
        best_bid = _to_float(m.get("bestBid"), 0.0)
        # Prefer the live ask; fall back to the outcomePrices[0] mid.
        yes_price = best_ask if best_ask > 0 else _to_float(prices[0] if prices else 0, 0.0)
        if yes_price <= 0 or yes_price >= 1.0:
            continue

        candidate = (m.get("groupItemTitle") or "").strip()
        if not candidate:
            # Fall back to parsing "Will <X> win ..." from the question.
            q = m.get("question", "")
            if q.lower().startswith("will "):
                candidate = q[5:].split(" win")[0].strip()
        if not candidate:
            continue

        out.append({
            "candidate": candidate,
            "yes_price": yes_price,
            "yes_bid": best_bid,
            "condition_id": m.get("conditionId", ""),
            "clob_token_ids": _parse_json_field(m.get("clobTokenIds"), []),
            "volume": _to_float(m.get("volume"), 0.0),
            "liquidity": _to_float(m.get("liquidity"), 0.0),
            "question": m.get("question", ""),
        })
    return out
