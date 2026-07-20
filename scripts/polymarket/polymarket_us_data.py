"""
polymarket_us_data.py — read-only Polymarket US market-data client.

Sources the *market* side for the US futures scanner directly from the venue
the operator actually trades on (api.polymarket.us), replacing the international
Gamma read layer. Two reasons this matters (discovered 2026-07-20):

  1. Edge must be priced on US quotes, not international Gamma quotes — they are
     separate order books with potentially different prices.
  2. Only the US `marketSlug` can address an order; the execution registry needs
     it. Reading US data means the slug comes for free (no cross-venue matching).

Championship futures are individual per-team Yes/No markets grouped by their
`question` (e.g. every "World Series Champion" team-market). The tradeable YES
ask is `bestAskQuote` (== the Yes `marketSides` price); `bestBidQuote` is the
YES bid. The `outcomes`/`outcomePrices` arrays are NOT used — their order is
inconsistent (sometimes Yes-first, sometimes No-first).

Auth is the same Ed25519 scheme as the exec client (shared polymarket_us_auth);
these endpoints require signed headers despite being market data.
"""

import re

import requests

from app.config import get_config
import polymarket_us_auth

_TIMEOUT = 25
_PAGE = 500
_MAX_PAGES = 8  # 8 * 500 = 4000 open markets — covers the full futures board


class PolymarketUSData:
    """Signed read-only client for the US market-data endpoints."""

    def __init__(self, key_id: str | None = None, secret_key: str | None = None,
                 host: str | None = None):
        cfg = get_config()
        self.key_id = key_id or cfg.polymarket.key_id
        self.secret_key = secret_key or cfg.polymarket.secret_key
        self.host = (host or cfg.polymarket.host).rstrip("/")
        self._signer = None
        if not self.key_id or not self.secret_key:
            raise FileNotFoundError(
                "Polymarket credentials not configured. Set POLYMARKET_KEY_ID "
                "and POLYMARKET_SECRET_KEY in .env — generate them at "
                "https://polymarket.us/developer (see "
                "docs/setup/polymarket-us-setup.md).")

    def _get(self, path: str) -> dict:
        if self._signer is None:
            self._signer = polymarket_us_auth.load_signer(self.secret_key)
        # Sign the bare path (no query string); send the query in the URL.
        headers = polymarket_us_auth.signed_headers(
            self.key_id, self._signer, "GET", path.split("?")[0])
        r = requests.get(self.host + path, headers=headers, timeout=_TIMEOUT)
        r.raise_for_status()
        return r.json() if r.content else {}

    def fetch_open_futures(self) -> list[dict]:
        """All open championship-futures markets (paginated). One market per
        team; group by `question` to reconstruct a championship."""
        out: list[dict] = []
        for off in range(0, _MAX_PAGES * _PAGE, _PAGE):
            data = self._get(f"/v1/markets?closed=false&limit={_PAGE}&offset={off}")
            markets = data.get("markets") or []
            out.extend(m for m in markets
                       if not m.get("closed")
                       and m.get("sportsMarketType") == "futures")
            if len(markets) < _PAGE:
                break
        return out


# ── Grouping / candidate extraction (pure — unit-testable without the API) ────

def _yes_side(market: dict) -> dict:
    for s in market.get("marketSides") or []:
        if s.get("description") == "Yes":
            return s
    return {}


def _amount(val) -> float:
    """Coerce a US money field (Amount object or bare number) to float."""
    if isinstance(val, dict):
        val = val.get("value")
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def question_matches(question: str, terms: tuple[str, ...],
                     exclude: tuple[str, ...] = ()) -> bool:
    """True if any term's words all appear as whole words in `question` and no
    `exclude` word is present. Whole-word matching keeps "nba champion" from
    matching "WNBA Champion"; `exclude` drops near-misses like conference
    champions ("NBA Eastern Conference Champion")."""
    words = _words(question)
    if words & set(exclude):
        return False
    return any(w and w <= words
               for w in (_words(t) for t in terms))


def championship_candidates(markets: list[dict], terms: tuple[str, ...],
                            league: str | None = None,
                            exclude: tuple[str, ...] = ()) -> list[dict]:
    """Extract per-team candidate dicts for the championship identified by
    `terms` (matched on each market's `question`), optionally scoped to a
    team `league`. Shape matches what `detect_edge_futures_polymarket` consumes,
    plus the US `market_slug`."""
    out: list[dict] = []
    for m in markets:
        if not question_matches(m.get("question", ""), terms, exclude):
            continue
        ys = _yes_side(m)
        team = ys.get("team") or {}
        if league and team.get("league") != league:
            continue
        name = team.get("name") or m.get("title") or ""
        ask = _amount(m.get("bestAskQuote")) or _amount(ys.get("price"))
        if not name or ask <= 0:
            continue
        out.append({
            "candidate": name,
            "yes_price": round(ask, 4),
            "yes_bid": round(_amount(m.get("bestBidQuote")), 4),
            "market_slug": m.get("slug", ""),
            "condition_id": "",
            "clob_token_ids": [],
            "volume": 0.0,
            "league": team.get("league"),
        })
    return out
