"""
polymarket_exec_client.py — Polymarket US execution client (PM2 write half).

Implements the venue-neutral `MarketClient` contract (see
`scripts/shared/market_client.py`) on top of the **Polymarket US retail API**
(https://api.polymarket.us): Ed25519-signed REST requests, NOT the
international EIP-712 / py-clob-client wallet scheme (the operator's funded
account is the CFTC-regulated US product). Order shape in is the legacy
Edge-Radar form (`ticker`, side yes/no, action buy/sell, `*_price_cents`);
the ticker resolves to a US `marketSlug` through `market_registry`, and
yes/no maps to the order's `outcomeSide` (a single slug covers both sides).

Auth (verified live 2026-07-20 — see docs/setup/polymarket-us-setup.md):
  - Three headers per request: `X-PM-Access-Key` (key_id), `X-PM-Timestamp`
    (ms), `X-PM-Signature` = base64(Ed25519 sign of "{ts}{METHOD}{path}")
    — the body is NOT part of the signed message. Clock must be within 30s.
  - `secret_key` is base64; its first 32 bytes are the Ed25519 seed.

Safety:
  - Dry-run is **two-flag** (PM2c): orders are blocked — returning
    `{"status": "dry_run_blocked", ...}` without touching the network —
    unless BOTH the global `DRY_RUN` and the venue-scoped `POLYMARKET_DRY_RUN`
    are false. The operator runs Kalshi live, so the venue flag (default
    true) is what actually holds Polymarket back until the dry-run edge
    window proves out (ROADMAP Priority 0).
  - Construction is network-free (the signer is built lazily), so the factory
    and dry-run order paths never hit the API.
  - `create_order` refuses (raises) when the registry has no US `market_slug`
    for the ticker — a Gamma-sourced opportunity (the games scanner) or a
    never-scanned market can't be ordered.
  - Settlement reads are PM3; `get_settlements` returns an empty page.

Venue constraint enforced at sizing time (PM2c): markets carry a per-order
minimum (`minimumTradeQty`), captured by the scan into `market_registry` and
`opp.details["min_order_shares"]`; `size_order` bumps counts up to it or
rejects. Sub-minimum orders reaching this client are warned and will be
rejected by the exchange.
"""

import logging

import requests

from app.config import get_config
import market_registry
import polymarket_us_auth

try:
    from logging_setup import setup_logging
    log = setup_logging("polymarket_exec_client")
except Exception:  # pragma: no cover
    log = logging.getLogger("polymarket_exec_client")

_TIMEOUT = 20
# Conservative default per-order minimum (shares); real floor is the market's
# `minimumTradeQty`. See module docstring.
MIN_ORDER_SHARES = 5

# Edge-Radar time-in-force → Polymarket US TimeInForce enum.
_TIF = {
    "good_till_canceled": "TIME_IN_FORCE_GOOD_TILL_CANCEL",
    "good_till_cancelled": "TIME_IN_FORCE_GOOD_TILL_CANCEL",
    "immediate_or_cancel": "TIME_IN_FORCE_IMMEDIATE_OR_CANCEL",
    "fill_or_kill": "TIME_IN_FORCE_FILL_OR_KILL",
    "day": "TIME_IN_FORCE_DAY",
}


def _amount(val) -> float:
    """Coerce a US API money field to float — an Amount object
    (`{"value": "4.98", "currency": "USD"}`), a bare number, or None."""
    if isinstance(val, dict):
        val = val.get("value")
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0


class PolymarketAPIError(Exception):
    """Wraps Polymarket US API failures with a stable type for callers."""


class PolymarketClient:
    """Authenticated Polymarket US execution client (MarketClient-conformant)."""

    def __init__(
        self,
        key_id: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ):
        cfg = get_config()
        self.key_id = key_id or cfg.polymarket.key_id
        self.secret_key = secret_key or cfg.polymarket.secret_key
        self.host = (host or cfg.polymarket.host).rstrip("/")
        # Two-flag dry-run (PM2c): live only when BOTH the global DRY_RUN and
        # the venue-scoped POLYMARKET_DRY_RUN are false. The getattr default
        # keeps a config missing the venue flag on the safe (blocked) side.
        self.dry_run = cfg.system.dry_run or getattr(
            cfg.polymarket, "dry_run", True)

        if not self.key_id or not self.secret_key:
            raise FileNotFoundError(
                "Polymarket credentials not configured. Set POLYMARKET_KEY_ID "
                "and POLYMARKET_SECRET_KEY in .env — generate them at "
                "https://polymarket.us/developer (see "
                "docs/setup/polymarket-us-setup.md)."
            )

        # Ed25519 signer built lazily — construction stays network- and
        # crypto-free so the factory and dry-run paths are cheap.
        self._priv = None

        log.info(
            "PolymarketClient initialized — key_id=%s..., host=%s, dry_run=%s",
            self.key_id[:8], self.host, self.dry_run,
        )

    # ── Signing / transport ───────────────────────────────────────────────────

    def _signer(self):
        """Build (once) the Ed25519 private key from the base64 secret."""
        if self._priv is None:
            self._priv = polymarket_us_auth.load_signer(self.secret_key)
        return self._priv

    def _signed_request(self, method: str, path: str,
                        json_body: dict | None = None) -> dict:
        """Send an Ed25519-signed request. `path` must be the exact request
        path (no query string — the signed message is "{ts}{METHOD}{path}"
        and the body is not signed)."""
        headers = polymarket_us_auth.signed_headers(
            self.key_id, self._signer(), method, path)
        try:
            resp = requests.request(method, self.host + path, headers=headers,
                                    json=json_body, timeout=_TIMEOUT)
            resp.raise_for_status()
        except requests.HTTPError as e:
            body = getattr(e.response, "text", "")[:300]
            raise PolymarketAPIError(
                f"{method} {path} -> {e.response.status_code}: {body}")
        except Exception as e:
            raise PolymarketAPIError(f"{method} {path} failed: {e}")
        return resp.json() if resp.content else {}

    # ── Portfolio & balance ──────────────────────────────────────────────────

    def get_balance_dollars(self) -> dict:
        """USD buying power / balance + best-effort open-position value.

        `balanceReservation` is reported for visibility but does NOT reduce
        buying power (confirmed against the documented formula + live data).
        """
        data = self._signed_request("GET", "/v1/account/balances")
        balances = data.get("balances") or []
        usd = next((b for b in balances if b.get("currency") == "USD"),
                   balances[0] if balances else {})
        balance = float(usd.get("currentBalance") or 0)
        buying_power = float(usd.get("buyingPower") or 0)
        reservation = float(usd.get("balanceReservation") or 0)

        portfolio_value = 0.0
        try:
            positions = self.get_positions().get("positions") or {}
            rows = positions.values() if isinstance(positions, dict) else positions
            # The US Portfolio API names the mark-to-market field `cashValue`;
            # `currentValue` was assumed at build time and never exists, so this
            # silently summed to $0.00 against real open exposure until
            # 2026-07-25. `currentValue` is kept as a fallback in case the venue
            # ever returns it.
            portfolio_value = round(sum(
                _amount(p.get("cashValue") or p.get("currentValue"))
                for p in rows), 2)
        except Exception:  # balance is load-bearing; value is best-effort
            log.warning("Polymarket position-value fetch failed; reporting 0")

        return {"balance": round(balance, 2),
                "buying_power": round(buying_power, 2),
                "reservation": round(reservation, 2),
                "portfolio_value": portfolio_value,
                "updated_ts": None}

    def get_positions(self, limit: int = 100, cursor: str | None = None,
                      ticker: str | None = None, event_ticker: str | None = None,
                      count_filter: str | None = None) -> dict:
        """Open positions from the US Portfolio API.

        Returns the raw venue shape under `positions` (an object keyed by
        `marketSlug`) PLUS a Kalshi-shaped `market_positions` list (PM2c) so
        the executor pipeline's duplicate-ticker gate (Gate 5), per-event
        counts, and `show_status` consume Polymarket positions unchanged.
        The normalized `ticker` is `PM-{marketSlug}` — the same convention
        the scanners use to mint tickers, so an open position matches the
        scanner ticker for the same market exactly.
        """
        data = self._signed_request("GET", "/v1/portfolio/positions")
        raw = data.get("positions", data)
        market_positions = []
        rows = raw.items() if isinstance(raw, dict) else (
            (p.get("marketSlug", ""), p) for p in raw or [])
        for slug, p in rows:
            slug = slug or (p.get("marketMetadata") or {}).get("slug", "")
            net = _amount(p.get("netPosition"))
            if not slug or net == 0:
                continue
            market_positions.append({
                "ticker": f"PM-{slug}"[:64],
                "market_slug": slug,
                "position_fp": str(net),
                "market_exposure_dollars": str(_amount(p.get("cost"))),
                "realized_pnl_dollars": str(_amount(p.get("realized"))),
            })
        return {"positions": raw, "market_positions": market_positions}

    # ── Orders ────────────────────────────────────────────────────────────────

    def create_order(self, ticker: str, side: str, action: str, count: int = 1,
                     yes_price_cents: int | None = None,
                     no_price_cents: int | None = None,
                     client_order_id: str | None = None,
                     time_in_force: str = "good_till_canceled",
                     expiration_ts: int | None = None,
                     buy_max_cost: int | None = None) -> dict:
        """Place a limit order for the given Edge-Radar-shaped order.

        Resolves `ticker` → US `marketSlug` via the scan-time registry; the
        yes/no side becomes the order's `outcomeSide` (one slug serves both
        sides). A NO price is used directly (it is already the NO outcome's
        price — no 1-minus translation).
        """
        if self.dry_run:
            log.warning("[DRY RUN] Polymarket order blocked — DRY_RUN=true")
            return {"status": "dry_run_blocked", "ticker": ticker, "side": side}

        if side not in ("yes", "no"):
            raise ValueError(f"side must be 'yes' or 'no', got {side!r}")
        if action not in ("buy", "sell"):
            raise ValueError(f"action must be 'buy' or 'sell', got {action!r}")
        price_cents = yes_price_cents if side == "yes" else no_price_cents
        if price_cents is None:
            raise ValueError(f"{side}_price_cents required for a {side.upper()} order")

        entry = market_registry.lookup(ticker)
        market_slug = (entry or {}).get("market_slug")
        if not market_slug:
            raise PolymarketAPIError(
                f"No US market_slug in the registry for {ticker!r}. Polymarket "
                "US addresses markets by slug, and the edge scanners currently "
                "record international Gamma data — reconcile before live orders "
                "(see docs/setup/polymarket-us-setup.md).")

        try:
            min_shares = int(entry.get("min_order_shares") or MIN_ORDER_SHARES)
        except (TypeError, ValueError):
            min_shares = MIN_ORDER_SHARES
        if count < min_shares:
            log.warning(
                "Polymarket order for %s is %d share(s) — below the market's "
                "%d-share minimum; the exchange will likely reject it.",
                ticker, count, min_shares)

        body = {
            "marketSlug": market_slug,
            "type": "ORDER_TYPE_LIMIT",
            "price": {"value": f"{price_cents / 100:.2f}", "currency": "USD"},
            "quantity": float(count),
            "outcomeSide": "OUTCOME_SIDE_YES" if side == "yes" else "OUTCOME_SIDE_NO",
            "action": "ORDER_ACTION_BUY" if action == "buy" else "ORDER_ACTION_SELL",
            "tif": _TIF.get(time_in_force, "TIME_IN_FORCE_GOOD_TILL_CANCEL"),
        }
        resp = self._signed_request("POST", "/v1/orders", json_body=body)
        log.info("Polymarket order placed: %s %s %s x%d @ %d¢ → %s",
                 action, side, ticker, count, price_cents,
                 (resp or {}).get("orderId", "?"))
        return resp or {}

    def get_orders(self, limit: int = 100, cursor: str | None = None,
                   ticker: str | None = None, status: str | None = None) -> dict:
        data = self._signed_request("GET", "/v1/orders")
        return {"orders": data.get("orders", data if isinstance(data, list) else [])}

    def cancel_order(self, order_id: str) -> dict:
        return self._signed_request("DELETE", f"/v1/orders/{order_id}")

    def get_fills(self, limit: int = 100, cursor: str | None = None,
                  ticker: str | None = None) -> dict:
        data = self._signed_request("GET", "/v1/portfolio/activities")
        return {"fills": data.get("activities", data if isinstance(data, list) else [])}

    def get_settlements(self, limit: int = 100, cursor: str | None = None,
                        ticker: str | None = None, event_ticker: str | None = None,
                        min_ts: int | None = None, max_ts: int | None = None) -> dict:
        """PM3: US resolution + redemption history feeding the venue-tagged
        trade log. Empty until that lands."""
        return {"settlements": []}
