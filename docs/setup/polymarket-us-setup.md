# Polymarket US — API Setup & Integration Status

> **Status (2026-07-20):** Account funded + verified. API keys **not yet generated**.
> Execution code (`PolymarketClient`) **needs a rewrite** — see [Code rework required](#code-rework-required).
> Read-only edge detection (PM1) is **unaffected** and keeps working.

---

## TL;DR — the finding that reshaped PM2

The operator's funded Polymarket account is the **CFTC-regulated "Polymarket US"** product,
accessible **only via the iOS app** (Polymarket support confirmed the website is a separate,
unavailable product). It exposes a **retail API** with a **completely different auth model**
than the international exchange the code was originally built against:

| | International (what the code has today) | **Polymarket US (the operator's account)** |
|:--|:--|:--|
| Auth model | EIP-712 wallet signing | **Ed25519 API keys** |
| SDK | `py-clob-client` | **`polymarket-us` (`polymarket-us-python`)** |
| API host | `https://clob.polymarket.com` | **`https://api.polymarket.us`** |
| Credentials | private key + funder address + `signature_type` | **`key_id` (UUID) + `secret_key` (base64 Ed25519)** |
| Key export | `polymarket.com/settings` / `reveal.magic.link` | **`polymarket.us/developer` portal** |

**Consequence:** the entire PM2b execution client (`scripts/polymarket/polymarket_exec_client.py`,
built on `py-clob-client`) and its `app/config.py` credentials **cannot reach the regulated
account** and must be rebuilt on the `polymarket-us` SDK. This supersedes the old **PM2c-0
"wallet identity mismatch"** diagnosis in `docs/ROADMAP.md` (the $0 "empty twin" wasn't a
wrong login — it was the wrong *product/API entirely*).

---

## Part A — Generate your API keys (operator, ~5 min)

Requires the funded, KYC-verified account (already done).

1. On the **Polymarket US iOS app**, confirm the account is funded (the balance you expect).
2. Go to **https://polymarket.us/developer** and sign in / authorize with that same account.
3. **Generate an API key.** You'll get two values:
   - **Key ID** — a UUID (e.g. `3f2a…-…-…`)
   - **Secret Key** — a Base64-encoded **Ed25519** private key
4. **Save the secret key immediately — it is shown only once.** If you lose it, revoke and
   regenerate.

## Part B — Put them in `.env`

```env
POLYMARKET_KEY_ID=<the UUID>
POLYMARKET_SECRET_KEY=<the base64 Ed25519 secret>
```

Notes:
- `.env` is gitignored — never commit these. The old `POLYMARKET_PRIVATE_KEY /
  _FUNDER_ADDRESS / _SIGNATURE_TYPE` vars are retired (dead scheme) and were removed.
- **Clock matters:** Ed25519 requests carry a millisecond timestamp and reject on **>30s**
  drift. Make sure the machine's clock is NTP-synced before live calls.

## Part C — Verify (after the code rework lands)

Once `PolymarketClient` is rebuilt (below), a read-only balance/positions probe confirms the
keys resolve to the funded account. Until then, verification isn't wired.

---

## Code rework required

`.env` alone does **not** make execution work — this is real code, tracked as the PM2c-0
resolution:

- [ ] Add `polymarket-us` to `requirements.txt`; drop `py-clob-client` if unused elsewhere.
- [ ] Rewrite `scripts/polymarket/polymarket_exec_client.py` (`PolymarketClient`) on the
      `polymarket_us` SDK while keeping the `MarketClient` contract
      (`get_balance_dollars`, `get_positions`, `create_order`, `get_orders`, `cancel_order`,
      `get_fills`, `get_settlements`). Map order shape → SDK (`client.orders.create({...})`
      with `marketSlug`/`intent`/`type`/`price`/`quantity`/`tif`); balance via
      `client.account.balances()`; positions via `client.portfolio.positions()`.
- [ ] Rework the `polymarket` section of `app/config.py`: `key_id` + `secret_key` (+ host)
      instead of `private_key` / `funder_address` / `signature_type`.
- [ ] Re-check the ticker→market resolution: US uses **`marketSlug`**, not CLOB `token_id`,
      so the scan-time `market_registry` mapping likely changes.
- [ ] Update PM2b tests (currently assert the `py-clob-client` path).
- [ ] Keep the DRY_RUN safety behavior identical (`dry_run_blocked`, no network on init).

Scope this before writing it — the order/market model differs enough from Kalshi/CLOB that
the mapping deserves its own pass.

---

## Reference

**SDK init**
```python
import os
from polymarket_us import PolymarketUS

client = PolymarketUS(
    key_id=os.environ["POLYMARKET_KEY_ID"],
    secret_key=os.environ["POLYMARKET_SECRET_KEY"],
)
```

**Manual auth (no SDK)** — three headers per request against `https://api.polymarket.us`:

| Header | Value |
|:--|:--|
| `X-PM-Access-Key` | your Key ID |
| `X-PM-Timestamp` | current time in **milliseconds** |
| `X-PM-Signature` | base64 Ed25519 signature of `"{timestamp}{METHOD}{path}"` (no body) |
| `Content-Type` | `application/json` |

Signing: decode the secret from base64 (first 32 bytes = seed), sign the message string,
base64-encode the result. Timestamp must be within **30s** of server time.

**Sources**
- Official SDK: https://github.com/Polymarket/polymarket-us-python
- Auth docs: https://docs.polymarket.us/api-reference/authentication
- Docs index: https://docs.polymarket.us
- Developer portal: https://polymarket.us/developer
