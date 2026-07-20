"""
polymarket_exec_client.py — Polymarket execution client (PM2 write half).

Implements the venue-neutral `MarketClient` contract (see
`scripts/shared/market_client.py`) on top of `py-clob-client`: EIP-712
wallet-signed orders against the Polymarket CLOB, portfolio reads via the
public Data API. Order shape in is the legacy Edge-Radar form (`ticker`,
side yes/no, action buy/sell, `*_price_cents`); the ticker resolves to a
CLOB `token_id` through `market_registry` (written by the scanners), with
side → token index structural (yes = token 0, no = token 1).

Account model (operator decisions 2026-07-20): email/Magic proxy wallet —
`POLYMARKET_PRIVATE_KEY` is the key exported from Polymarket settings,
`POLYMARKET_FUNDER_ADDRESS` the proxy address holding the USDC,
`signature_type=1`. The account balance IS the trading bankroll.

Safety:
  - DRY_RUN honored exactly like KalshiClient: blocked orders return
    `{"status": "dry_run_blocked", ...}` without touching the network.
  - The CLOB client is built lazily on first use, so constructing this class
    (e.g. via the factory) performs no network I/O and dry-run order paths
    never need the CLOB at all.
  - Settlement reads are PM3 (Data API redemption history + venue-tagged
    trade log); `get_settlements` returns an empty page until then.

Polymarket venue constraint worth knowing at sizing time: most markets have
a 5-share minimum order (`orderMinSize`). At Edge-Radar's ~$1 unit size a
50c contract sizes to 2 shares — below the minimum. `create_order` logs a
warning; PM2c (execution pipeline wiring) must bump counts to the venue
minimum or skip.
"""

import logging

import requests

from app.config import get_config
import market_registry

try:
    from logging_setup import setup_logging
    log = setup_logging("polymarket_exec_client")
except Exception:  # pragma: no cover
    log = logging.getLogger("polymarket_exec_client")

DATA_API = "https://data-api.polymarket.com"
_TIMEOUT = 20
POLYGON_CHAIN_ID = 137
# Typical Polymarket per-order minimum (shares); see module docstring.
MIN_ORDER_SHARES = 5


class PolymarketAPIError(Exception):
    """Wraps CLOB/Data API failures with a stable type for callers."""


class PolymarketClient:
    """Authenticated Polymarket execution client (MarketClient-conformant)."""

    def __init__(
        self,
        private_key: str | None = None,
        funder_address: str | None = None,
        signature_type: int | None = None,
        host: str | None = None,
    ):
        cfg = get_config()
        self.private_key = private_key or cfg.polymarket.private_key
        self.funder_address = funder_address or cfg.polymarket.funder_address
        self.signature_type = (signature_type if signature_type is not None
                               else cfg.polymarket.signature_type)
        self.host = (host or cfg.polymarket.host).rstrip("/")
        self.dry_run = cfg.system.dry_run

        if not self.private_key or not self.funder_address:
            raise FileNotFoundError(
                "Polymarket credentials not configured. Set "
                "POLYMARKET_PRIVATE_KEY (exported from Polymarket Settings → "
                "Export Private Key) and POLYMARKET_FUNDER_ADDRESS (the "
                "account's deposit/profile address) in .env."
            )

        # Built lazily — construction must stay network-free (DRY_RUN order
        # paths and factory smoke tests never need the CLOB).
        self._clob_instance = None

        log.info(
            "PolymarketClient initialized — funder=%s..., sig_type=%s, dry_run=%s",
            self.funder_address[:8], self.signature_type, self.dry_run,
        )

    # ── CLOB plumbing ─────────────────────────────────────────────────────────

    def _clob(self):
        """Create (once) and return the authenticated py-clob-client."""
        if self._clob_instance is None:
            from py_clob_client.client import ClobClient
            client = ClobClient(
                self.host,
                key=self.private_key,
                chain_id=POLYGON_CHAIN_ID,
                signature_type=self.signature_type,
                funder=self.funder_address,
            )
            # L1/L2 auth: derive (or create) the API creds bound to the wallet.
            client.set_api_creds(client.create_or_derive_api_creds())
            self._clob_instance = client
        return self._clob_instance

    # ── Portfolio & balance ──────────────────────────────────────────────────

    def get_balance_dollars(self) -> dict:
        """USDC balance (dollars) + open-position value via the Data API."""
        try:
            from py_clob_client.clob_types import BalanceAllowanceParams, AssetType
            resp = self._clob().get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
            balance = int(resp.get("balance", 0)) / 1e6  # USDC has 6 decimals
        except Exception as e:
            raise PolymarketAPIError(f"balance query failed: {e}")

        portfolio_value = 0.0
        try:
            positions = self.get_positions().get("positions", [])
            portfolio_value = round(
                sum(float(p.get("currentValue") or 0) for p in positions), 2)
        except Exception:  # balance is the load-bearing number; value is best-effort
            log.warning("Polymarket position-value fetch failed; reporting 0")

        return {"balance": round(balance, 2),
                "portfolio_value": portfolio_value,
                "updated_ts": None}

    def get_positions(self, limit: int = 100, cursor: str | None = None,
                      ticker: str | None = None, event_ticker: str | None = None,
                      count_filter: str | None = None) -> dict:
        """Open positions from the public Data API (raw venue shape under
        the Kalshi-style envelope; field adapters are PM3)."""
        try:
            resp = requests.get(
                f"{DATA_API}/positions",
                params={"user": self.funder_address, "limit": limit,
                        "sizeThreshold": 0.1},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            positions = resp.json() or []
        except Exception as e:
            raise PolymarketAPIError(f"positions query failed: {e}")
        return {"positions": positions if isinstance(positions, list) else []}

    # ── Orders ────────────────────────────────────────────────────────────────

    def create_order(self, ticker: str, side: str, action: str, count: int = 1,
                     yes_price_cents: int | None = None,
                     no_price_cents: int | None = None,
                     client_order_id: str | None = None,
                     time_in_force: str = "good_till_canceled",
                     expiration_ts: int | None = None,
                     buy_max_cost: int | None = None) -> dict:
        """Place a CLOB limit order for the given Edge-Radar-shaped order.

        Resolves `ticker` via the scan-time market registry; "yes" trades
        token 0, "no" trades token 1, each at its own side's price (a NO
        price is already the second token's price — no 1-minus translation,
        unlike Kalshi's single-book YES-perspective API).
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
        if not entry or len(entry.get("clob_token_ids") or []) < 2:
            raise PolymarketAPIError(
                f"No registry entry for {ticker!r} — run a Polymarket scan "
                "first (the scanners record ticker → CLOB token mappings).")
        token_id = entry["clob_token_ids"][0 if side == "yes" else 1]

        if count < MIN_ORDER_SHARES:
            log.warning(
                "Polymarket order for %s is %d share(s) — below the typical "
                "%d-share venue minimum; the CLOB will likely reject it.",
                ticker, count, MIN_ORDER_SHARES)

        try:
            from py_clob_client.clob_types import OrderArgs, OrderType
            from py_clob_client.order_builder.constants import BUY, SELL
            args = OrderArgs(
                token_id=str(token_id),
                price=round(price_cents / 100.0, 3),
                size=float(count),
                side=BUY if action == "buy" else SELL,
            )
            signed = self._clob().create_order(args)
            resp = self._clob().post_order(signed, OrderType.GTC)
        except Exception as e:
            raise PolymarketAPIError(f"order placement failed: {e}")

        log.info("Polymarket order placed: %s %s %s x%d @ %d¢ → %s",
                 action, side, ticker, count, price_cents,
                 (resp or {}).get("orderID", "?"))
        return resp or {}

    def get_orders(self, limit: int = 100, cursor: str | None = None,
                   ticker: str | None = None, status: str | None = None) -> dict:
        try:
            orders = self._clob().get_orders()
        except Exception as e:
            raise PolymarketAPIError(f"orders query failed: {e}")
        return {"orders": orders if isinstance(orders, list) else []}

    def cancel_order(self, order_id: str) -> dict:
        try:
            resp = self._clob().cancel(order_id)
        except Exception as e:
            raise PolymarketAPIError(f"cancel failed: {e}")
        return resp if isinstance(resp, dict) else {"canceled": resp}

    def get_fills(self, limit: int = 100, cursor: str | None = None,
                  ticker: str | None = None) -> dict:
        try:
            trades = self._clob().get_trades()
        except Exception as e:
            raise PolymarketAPIError(f"fills query failed: {e}")
        return {"fills": trades if isinstance(trades, list) else []}

    def get_settlements(self, limit: int = 100, cursor: str | None = None,
                        ticker: str | None = None, event_ticker: str | None = None,
                        min_ts: int | None = None, max_ts: int | None = None) -> dict:
        """PM3: UMA-oracle resolution + redemption history via the Data API,
        feeding the venue-tagged trade log. Empty until that lands."""
        return {"settlements": []}
