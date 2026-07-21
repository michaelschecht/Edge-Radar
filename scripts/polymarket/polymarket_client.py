"""
polymarket_client.py — read-only Polymarket (Gamma API) client.

Phase 1 of the Polymarket integration (docs/ROADMAP.md Priority 0). This is a
**read-only** client: it fetches championship-futures markets and their prices
from the public Gamma API (https://gamma-api.polymarket.com, no auth, no wallet).
It places NO orders — execution is the Polymarket US retail API (Phase 2).
Now used only by the games scanner; the futures scanner reads US data directly.

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


def search_events(query: str, limit: int = 20) -> list[dict]:
    """Full-text event search via Gamma's /public-search (relevance-ranked).

    Unlike paging /events, this finds championship boards regardless of how
    deep they sit in the active-events list (PM1b: the Super Bowl / World
    Series / NBA / NHL events were beyond the first 300 active events)."""
    return _get("/public-search", {"q": query, "limit_per_type": limit})


def find_event(slug: str | None = None, search_terms: tuple[str, ...] = ()) -> dict | None:
    """Locate a championship-future event.

    Tries the exact `slug` first (cheap, precise). Falls back to /public-search
    over each of `search_terms`: keeps open events whose title contains every
    word of at least one term, and prefers the highest-volume match (the real
    outright board, not a low-liquidity prop — e.g. "World Cup Winner" over
    "World Cup: Golden Boot Winner"). Slugs rot each season ("...-2026" closes,
    "...-2027" opens), so this fallback is what keeps discovery working across
    season rollovers without a config change.
    """
    if slug:
        ev = fetch_event_by_slug(slug)
        if ev:
            return ev

    if not search_terms:
        return None
    terms = tuple(t.lower() for t in search_terms)
    best = None
    best_key = (-1.0, -1)
    seen_slugs: set[str] = set()
    for term in terms:
        for e in search_events(term):
            eslug = e.get("slug") or ""
            if eslug in seen_slugs:
                continue
            seen_slugs.add(eslug)
            if e.get("closed") or e.get("active") is False:
                continue
            title = (e.get("title") or "").lower()
            if not any(all(w in title for w in t.split()) for t in terms):
                continue
            key = (_to_float(e.get("volume"), 0.0), len(e.get("markets", []) or []))
            if key > best_key:
                best, best_key = e, key
    if best and best.get("slug"):
        # Search results may carry a truncated markets list — re-fetch the
        # full event by its slug before pricing candidates.
        full = fetch_event_by_slug(best["slug"])
        return full or best
    return best


_TAG_ID_CACHE: dict[str, str] = {}


def get_tag_id(slug: str) -> str | None:
    """Resolve a Gamma tag slug (e.g. "mlb") to its numeric tag id, cached
    per process. Tag ids are stable but discovering them by slug keeps the
    config human-readable."""
    if slug in _TAG_ID_CACHE:
        return _TAG_ID_CACHE[slug]
    try:
        resp = requests.get(
            f"{GAMMA_API}/tags/slug/{slug}",
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        tag_id = str(resp.json().get("id") or "")
    except Exception as e:
        log.warning("Gamma tag lookup for %r failed: %s", slug, e)
        return None
    if tag_id:
        _TAG_ID_CACHE[slug] = tag_id
    return tag_id or None


def fetch_game_events(tag_id: str, limit: int = 100, max_pages: int = 3) -> list[dict]:
    """Fetch open events for a sport tag (PM1d: per-game markets).

    Game events are invisible to title search / default listing order — the
    07-14 spike missed them entirely — but tag_id + open filtering surfaces
    the full slate. Returns raw event dicts; callers filter to actual game
    events (vs props/futures sharing the tag) via `iter_game_rows`.
    """
    out: list[dict] = []
    for page in range(max_pages):
        events = _get("/events", {
            "tag_id": tag_id, "closed": "false", "active": "true",
            "limit": limit, "offset": page * limit,
        })
        if not events:
            break
        out.extend(events)
        if len(events) < limit:
            break
    return out


# The three core game markets our sports model prices. Everything else on a
# game event (NRFI, first-five variants, extra innings, player props) has
# dead 2c/98c books and no consensus source — skipped.
_CORE_GAME_MARKET_TYPES = ("moneyline", "spreads", "totals")


def iter_game_rows(event: dict) -> list[dict]:
    """Normalize a game event's core sub-markets (ML / spread / total).

    Gamma marks each sub-market with `sportsMarketType`; outcomes for
    moneyline/spreads are the two team names (index 0 = the bid/ask side),
    totals are ["Over", "Under"]. `line` carries the spread/total strike and
    `gameStartTime` the actual first pitch / tip-off (the event-level
    startDate is just the listing time).
    """
    rows: list[dict] = []
    for m in event.get("markets", []) or []:
        if m.get("sportsMarketType") not in _CORE_GAME_MARKET_TYPES:
            continue
        if m.get("closed") or m.get("active") is False:
            continue
        outcomes = _parse_json_field(m.get("outcomes"), []) or []
        prices = _parse_json_field(m.get("outcomePrices"), []) or []
        if len(outcomes) != 2:
            continue
        best_bid = _to_float(m.get("bestBid"), 0.0)
        best_ask = _to_float(m.get("bestAsk"), 0.0)
        yes_price = best_ask if best_ask > 0 else _to_float(prices[0] if prices else 0, 0.0)
        if yes_price <= 0 or yes_price >= 1.0:
            continue
        rows.append({
            "market_type": m.get("sportsMarketType"),
            "question": m.get("question", ""),
            "outcomes": [str(o).strip() for o in outcomes],
            "yes_price": yes_price,
            "yes_bid": best_bid,
            "line": _to_float(m.get("line"), 0.0) if m.get("line") is not None else None,
            "book_spread": _to_float(m.get("spread"), 0.0),
            "game_start": m.get("gameStartTime") or "",
            "condition_id": m.get("conditionId", ""),
            "clob_token_ids": _parse_json_field(m.get("clobTokenIds"), []),
            "volume": _to_float(m.get("volume"), 0.0),
        })
    return rows


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
