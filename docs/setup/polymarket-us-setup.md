# Polymarket US — API Setup & Integration Status

> **Status (2026-07-20):** Account funded + verified. API keys generated and in `.env`.
> **Auth verified live** — a read-only Ed25519-signed probe hit the funded account
> (see [Verified live](#verified-live-2026-07-20)). Execution code (`PolymarketClient`)
> **needs a rewrite** — see [Code rework required](#code-rework-required).
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

## Part C — Verify

Done 2026-07-20 via a standalone read-only probe (raw `cryptography` + `requests`, no SDK).
See [Verified live](#verified-live-2026-07-20) for the confirmed endpoints and response
shapes. A permanent balance/positions check lands with the `PolymarketClient` rewrite below.

---

## Verified live (2026-07-20)

A read-only Ed25519-signed probe authenticated to the **funded** account (every earlier
`py-clob-client` attempt hit $0 — this confirms the retail-API path is the correct one):

- **Host + versioning:** `https://api.polymarket.us`, paths are **`/v1`-prefixed**
  (`GET /v1/account/balances` → 200; bare `/account/balances` → 404).
- **Signing (confirmed working):** `X-PM-Signature` = base64(Ed25519 sign of
  `"{ts_ms}{METHOD}{path}"`), key = **first 32 bytes** of the base64-decoded secret
  (the secret decodes to 64 bytes = seed+pubkey). Headers `X-PM-Access-Key` (key_id),
  `X-PM-Timestamp` (ms). Clock must be within 30s.
- **Balance shape** (`GET /v1/account/balances`): `balances[]` with `currentBalance`,
  `buyingPower`, `assetAvailable`, `openOrders`, `marginRequirement`, `unsettledFunds`,
  `balanceReservation`. **`buyingPower = currentBalance + assetAvailable − openOrders −
  marginRequirement`** — `balanceReservation` is **not** in the formula and does **not**
  reduce buying power (confirmed live: buyingPower == currentBalance with a nonzero
  reservation present). Full funded balance is tradable.
- **Positions shape** (`GET /v1/portfolio/positions`): `positions` is an object **keyed by
  `marketSlug`**, each with `netPosition`, `qtyBought`/`qtySold`, `cost.value`,
  `realized.value`, `marketMetadata.slug`. → **US resolves markets by `marketSlug`, not CLOB
  `token_id`** — this is what drives the `market_registry` change below.

---

## Code rework — DONE 2026-07-20 (608 tests pass; reads verified live)

The `PolymarketClient` was rebuilt on the US retail API using **raw `cryptography` +
`requests`** (no SDK dependency). Verified live: `get_balance_dollars` → $60.12 buying power,
`get_positions` → 2 real MLB-champ positions.

- [x] `app/config.py` `PolymarketCredentials` → `key_id` / `secret_key` / `host`
      (`api.polymarket.us`), env `POLYMARKET_KEY_ID` / `POLYMARKET_SECRET_KEY`.
- [x] `polymarket_exec_client.py` rewritten on `_signed_request` (Ed25519 header scheme),
      keeping the 7-method `MarketClient` contract. Endpoints: `GET /v1/account/balances`,
      `GET /v1/portfolio/positions`, `POST /v1/orders`, `DELETE /v1/orders/{id}`,
      `GET /v1/orders`, `GET /v1/portfolio/activities`.
- [x] Order body maps side→`outcomeSide`, action→`action`, price→`{value,currency}` Amount,
      tif→`TIME_IN_FORCE_*`. DRY_RUN still returns `dry_run_blocked`, init stays network-free.
- [x] `market_registry` → `market_slug` (US addresses by slug; one slug per market).
- [x] Tests rewritten to the US scheme (mock `_signed_request`, no network).

### ⚠️ Remaining blocker before live orders — slug namespace reconciliation

The edge scanners read the **international Gamma** API; its market slugs are a **different
namespace** than Polymarket US (US position slug seen live: `tec-mlb-champ-2026-09-27-mil`).
So the registry has no valid US `market_slug` yet, and `create_order` **correctly refuses**
every live order until that's resolved. Options to reconcile (needs a decision):

1. Point the execution-side market lookup at the **US market-data API** (`api.polymarket.us`
   markets/search) instead of Gamma, so tickers resolve to real US slugs.
2. Build a Gamma-event → US-slug mapping layer.

Until then: reads work, DRY_RUN dry-run scans work, but **no live order can be placed** — which
matches the operator gate (live orders only after the dry-run edge window proves out).

---

## Reference

**Decision (2026-07-20): build raw, not on the SDK.** The read-only probe proved the
signed-request scheme works with just `cryptography` + `requests` (already installed), so
`PolymarketClient` will implement auth directly rather than adding the `polymarket-us`
dependency. SDK init is kept below only as an alternative reference.

**Read-only endpoints (verified):**
- `GET /v1/account/balances` — buying power + balances
- `GET /v1/portfolio/positions` — open positions, keyed by `marketSlug`

**Auth** — four headers per request against `https://api.polymarket.us` (`/v1`-prefixed paths):

| Header | Value |
|:--|:--|
| `X-PM-Access-Key` | your Key ID |
| `X-PM-Timestamp` | current time in **milliseconds** |
| `X-PM-Signature` | base64 Ed25519 signature of `"{timestamp}{METHOD}{path}"` (no body) |
| `Content-Type` | `application/json` |

Signing: decode the secret from base64 (first 32 bytes = seed), sign the message string,
base64-encode the result. Timestamp must be within **30s** of server time.

**SDK init (alternative, not adopted):**
```python
from polymarket_us import PolymarketUS
client = PolymarketUS(key_id=..., secret_key=...)   # client.account.balances(), client.portfolio.positions()
```

**Sources**
- Official SDK (reference only): https://github.com/Polymarket/polymarket-us-python
- Auth docs: https://docs.polymarket.us/api-reference/authentication
- Docs index: https://docs.polymarket.us
- Developer portal: https://polymarket.us/developer
