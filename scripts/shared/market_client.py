"""
market_client.py — the venue-neutral execution-client contract (PM2 seam).

`MarketClient` is the ~7-method interface the money paths actually use
(executor, settler, risk_check, daily_summary). `KalshiClient` already
satisfies it; the Phase 2 `PolymarketClient` must implement the same surface
so a normalized `Opportunity` can execute on either venue through the
existing risk-gate chain unchanged. See docs/ROADMAP.md Priority 0 (PM2).

Conventions every implementation must honor (set by KalshiClient, the
reference implementation):
  - `get_balance_dollars()` returns dollars (floats), not cents.
  - `create_order()` speaks the legacy Edge-Radar order shape — ticker,
    side ("yes"/"no"), action ("buy"/"sell"), count, *_price_cents — and the
    implementation translates to its venue's native order format internally.
  - `create_order()` must respect DRY_RUN: blocked orders return a dict with
    `status="dry_run_blocked"` instead of hitting the venue.
  - Query methods return the venue's raw response dict; callers already
    handle Kalshi's shapes, so a new venue normalizes to the same keys its
    callers consume (positions/fills/settlements adapters are Phase 3).

The factory `get_market_client(venue)` is the single place a venue name
becomes a client instance — the executor and any future `--venue` plumbing
route through it rather than instantiating `KalshiClient()` directly.
"""

from typing import Protocol, runtime_checkable

# Venues the factory understands. "polymarket" targets the Polymarket US
# retail API (Ed25519-signed); the client refuses only when its API keys are unset.
VENUES = ("kalshi", "polymarket")


@runtime_checkable
class MarketClient(Protocol):
    """Execution-venue client contract (see module docstring for semantics)."""

    def get_balance_dollars(self) -> dict: ...

    def get_positions(
        self,
        limit: int = 100,
        cursor: str | None = None,
        ticker: str | None = None,
        event_ticker: str | None = None,
        count_filter: str | None = None,
    ) -> dict: ...

    def create_order(
        self,
        ticker: str,
        side: str,
        action: str,
        count: int = 1,
        yes_price_cents: int | None = None,
        no_price_cents: int | None = None,
        client_order_id: str | None = None,
        time_in_force: str = "good_till_canceled",
        expiration_ts: int | None = None,
        buy_max_cost: int | None = None,
    ) -> dict: ...

    def get_orders(
        self,
        limit: int = 100,
        cursor: str | None = None,
        ticker: str | None = None,
        status: str | None = None,
    ) -> dict: ...

    def cancel_order(self, order_id: str) -> dict: ...

    def get_fills(
        self,
        limit: int = 100,
        cursor: str | None = None,
        ticker: str | None = None,
    ) -> dict: ...

    def get_settlements(
        self,
        limit: int = 100,
        cursor: str | None = None,
        ticker: str | None = None,
        event_ticker: str | None = None,
        min_ts: int | None = None,
        max_ts: int | None = None,
    ) -> dict: ...


def get_market_client(venue: str = "kalshi") -> MarketClient:
    """Build the execution client for `venue`.

    Imports lazily so a venue's dependency stack (Kalshi RSA signing,
    Polymarket US Ed25519 signing) is only loaded when that venue is selected.
    """
    v = (venue or "kalshi").strip().lower()
    if v == "kalshi":
        from kalshi_client import KalshiClient
        return KalshiClient()
    if v == "polymarket":
        # PM2 write half (Polymarket US retail API). Raises FileNotFoundError
        # with setup guidance when POLYMARKET_KEY_ID / POLYMARKET_SECRET_KEY
        # are unset — same contract as KalshiClient without credentials.
        from polymarket_exec_client import PolymarketClient
        return PolymarketClient()
    raise ValueError(f"Unknown venue {venue!r}. Valid venues: {', '.join(VENUES)}")
