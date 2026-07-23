# 🔌 Polymarket US API Reference

<p align="center">
  <img src="https://img.shields.io/badge/Host-api.polymarket.us-0078d4?style=for-the-badge&labelColor=09090b" alt="Host">
  <img src="https://img.shields.io/badge/Auth-Ed25519-8b5cf6?style=for-the-badge&labelColor=09090b" alt="Ed25519">
  <img src="https://img.shields.io/badge/Paths-%2Fv1%20prefixed-f59e0b?style=for-the-badge&labelColor=09090b" alt="v1">
</p>

Reference for the **CFTC-regulated Polymarket US retail API** — the product the funded account actually uses. Verified live 2026-07-20.

---

> [!CAUTION]
> **This is not the API most Polymarket documentation describes.** The international exchange and the US product are entirely different systems. Building against the wrong one produces an authenticated client that reads a **$0 "empty twin"** account — which is exactly what happened before this was diagnosed.

| | International | **Polymarket US** (this account) |
|:--|:--|:--|
| Auth model | EIP-712 wallet signing | **Ed25519 API keys** |
| SDK | `py-clob-client` | `polymarket-us` *(not adopted — see below)* |
| Host | `clob.polymarket.com` | **`api.polymarket.us`** |
| Credentials | private key + funder address + `signature_type` | **`key_id` (UUID) + `secret_key` (base64 Ed25519)** |
| Market addressing | CLOB `token_id` | **`marketSlug`** |
| Key export | `polymarket.com/settings` | **`polymarket.us/developer`** |
| Access | web | **iOS app only** |

**Implementation decision:** built **raw** on `cryptography` + `requests` (both already installed) rather than adding the `polymarket-us` SDK dependency. A read-only probe proved the signing scheme works with no SDK. Shared signer lives in `scripts/polymarket/polymarket_us_auth.py`.

---

## Authentication

Four headers per request. Paths are **`/v1`-prefixed** (a bare `/account/balances` returns **404**).

| Header | Value |
|:-------|:------|
| `X-PM-Access-Key` | your Key ID |
| `X-PM-Timestamp` | current time in **milliseconds** |
| `X-PM-Signature` | base64 Ed25519 signature of `"{timestamp}{METHOD}{path}"` |
| `Content-Type` | `application/json` |

### The three details that cost debugging time

1. **The key is the first 32 bytes.** The base64 `secret_key` decodes to **64 bytes** (seed + public key). Ed25519 wants only the leading **32-byte seed**.
2. **The body is not signed.** The signed message is exactly `"{ts_ms}{METHOD}{path}"` — no payload, and **no query string**. Sign the bare path, then send the query in the URL.
3. **Clock drift is fatal past 30s.** The timestamp is validated server-side. Make sure the machine is NTP-synced before live calls.

```python
# scripts/polymarket/polymarket_us_auth.py (shape)
seed = base64.b64decode(secret_key)[:32]          # 64 bytes -> take the seed
msg  = f"{ts_ms}{method.upper()}{path}"           # body excluded, query excluded
sig  = base64.b64encode(Ed25519PrivateKey.from_private_bytes(seed).sign(msg.encode()))
```

---

## Endpoints in use

| Method | Path | Purpose |
|:-------|:-----|:--------|
| `GET` | `/v1/account/balances` | Buying power + balances |
| `GET` | `/v1/portfolio/positions` | Open positions, keyed by `marketSlug` |
| `GET` | `/v1/markets?closed=false&limit=&offset=` | Market catalog (paginated) |
| `POST` | `/v1/orders` | Place an order |
| `GET` | `/v1/orders` | Open orders |
| `DELETE` | `/v1/orders/{id}` | Cancel an order |
| `GET` | `/v1/portfolio/activities` | Fills / activity history |

---

## Response shapes

### Balances

`balances[]` with `currentBalance`, `buyingPower`, `assetAvailable`, `openOrders`, `marginRequirement`, `unsettledFunds`, `balanceReservation`.

```
buyingPower = currentBalance + assetAvailable − openOrders − marginRequirement
```

> [!IMPORTANT]
> **`balanceReservation` is *not* in that formula** and does **not** reduce buying power. Confirmed live: `buyingPower == currentBalance` with a nonzero reservation present. The full funded balance is tradable. It is reported for visibility only.

### Positions

`positions` is an **object keyed by `marketSlug`** (not an array), each carrying `netPosition`, `qtyBought` / `qtySold`, `cost.value`, `realized.value`, and `marketMetadata.slug`.

This is the finding that drives the whole registry design: **US resolves markets by `marketSlug`, not by CLOB `token_id`.**

### Money fields

Monetary values arrive as an **Amount object**, a bare number, or `null` — all three occur:

```json
{"value": "4.98", "currency": "USD"}
```

Both clients coerce through a shared `_amount()` helper rather than assuming a shape.

### Market catalog

Futures markets are identified by `sportsMarketType == "futures"`. Each team is an independent Yes/No market; group by `question` to reconstruct a championship board.

| Field | Meaning |
|:------|:--------|
| `slug` | The `marketSlug` used to place orders |
| `bestAskQuote` | Tradeable **YES ask** |
| `bestBidQuote` | YES bid |
| `marketSides[]` | Per-side detail; the `Yes` entry mirrors `bestAskQuote` |
| `minimumTradeQty` | Exchange-enforced per-order share minimum |
| `question` | The grouping key for a championship |

> [!WARNING]
> Ignore the `outcomes` / `outcomePrices` arrays — their ordering is inconsistent (sometimes Yes-first, sometimes No-first), so index-based reads silently invert prices on an unpredictable subset of markets. Always read `bestAskQuote` / `marketSides`.

---

## Order body

```json
{
  "marketSlug": "tec-nba-champ-2027-06-18-w-sas",
  "type": "ORDER_TYPE_LIMIT",
  "price": {"value": "0.20", "currency": "USD"},
  "quantity": 5.0,
  "outcomeSide": "OUTCOME_SIDE_YES",
  "action": "ORDER_ACTION_BUY",
  "tif": "TIME_IN_FORCE_GOOD_TILL_CANCEL"
}
```

Time-in-force values: `TIME_IN_FORCE_GOOD_TILL_CANCEL`, `TIME_IN_FORCE_IMMEDIATE_OR_CANCEL`, `TIME_IN_FORCE_FILL_OR_KILL`, `TIME_IN_FORCE_DAY`.

---

## Credentials

```env
POLYMARKET_KEY_ID=<UUID from the developer portal>
POLYMARKET_SECRET_KEY=<base64 Ed25519 secret>
POLYMARKET_DRY_RUN=true
```

Generate at **https://polymarket.us/developer**. The secret is shown **once** — save it immediately; if lost, revoke and regenerate. `.env` is gitignored; never commit these.

The old `POLYMARKET_PRIVATE_KEY` / `_FUNDER_ADDRESS` / `_SIGNATURE_TYPE` variables belonged to the retired international scheme and have been removed.

Full walkthrough: **[Polymarket US Setup](../../setup/polymarket-us-setup.md)**.

---

## Sources

- Auth docs — https://docs.polymarket.us/api-reference/authentication
- Docs index — https://docs.polymarket.us
- Developer portal — https://polymarket.us/developer
- Official SDK (reference only, not adopted) — https://github.com/Polymarket/polymarket-us-python

---

<p align="center">
  <b><a href="../README.md">← Polymarket Index</a></b> ·
  <b><a href="../polymarket-execution/EXECUTION_GUIDE.md">Execution Guide</a></b> ·
  <b><a href="../../setup/polymarket-us-setup.md">Setup Guide</a></b> ·
  <b><a href="../../kalshi/kalshi-sports-betting/KALSHI_API_REFERENCE.md">Kalshi API Reference</a></b>
</p>
