# Polymarket US — API Setup & Integration Status

> **Status (2026-07-20):** Account funded + verified; auth verified live. `PolymarketClient`
> rebuilt on the US retail API, futures scanner repointed to US data, and the **execution
> pipeline is fully wired** (`scan.py polymarket --execute`) — all live-verified.
> **Orders stay `dry_run_blocked`** until BOTH `DRY_RUN=false` and `POLYMARKET_DRY_RUN=false`
> (see [Execution pipeline](#execution-pipeline--done-2026-07-20-pm2c-635-tests-live-verified-in-preview));
> flip the venue flag only after the daily dry-run window proves edge.

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

### Futures repoint — DONE 2026-07-20 (US market data; live-verified)

The **futures** scanner now reads the US market-data API directly, so edge is priced on the
quotes that will actually fill and the US `market_slug` is recorded for execution:

- `polymarket_us_auth.py` — shared Ed25519 signer (used by exec + data clients).
- `polymarket_us_data.py` — signed read client: paginates `GET /v1/markets?closed=false`,
  keeps `sportsMarketType=="futures"`, groups by `question`, extracts per-team candidates
  (YES ask = `bestAskQuote`, `market_slug`, league). Whole-word question matching + `exclude`
  words isolate a championship (e.g. keeps "2027 NBA Champion", drops "WNBA Champion" and
  conference boards).
- `polymarket_futures_edge.py` — `PM_FUTURES` reworked to US championships (MLB World Series,
  NFL, NBA, NHL — keyed by `question` + optional `league`); sources candidates from US data,
  keeps the Odds-API consensus pricing, and records the real US slug to the registry.
- Live proof: matched all 4 championships (30/32/30/32 teams), found Spurs NBA-champ +3.6%
  edge, and registered `PM-tec-nba-champ-2027-06-18-w-sas → tec-nba-champ-2027-06-18-w-sas`.
  620 tests pass.

### Execution pipeline — DONE 2026-07-20 (PM2c; 635 tests; live-verified in preview)

`python scripts/scan.py polymarket --filter futures --execute` now routes US-slug futures
opportunities through the shared `execute_pipeline` (`venue="polymarket"`) — the same risk
gates, Kelly sizing, and ratio/budget caps as Kalshi — then `create_order` on the US API.
`--unit-size / --budget / --max-bets / --min-bets / --pick / --ticker` all work.

- **Two-flag dry-run (the PM2c safety):** orders return `dry_run_blocked` unless **BOTH**
  `DRY_RUN=false` **and** `POLYMARKET_DRY_RUN=false` (new env var, default **true**). The
  operator runs Kalshi live (`DRY_RUN=false`), so the venue flag is what holds Polymarket
  back until the dry-run edge window proves out. Flip it deliberately, never as a side
  effect.
- **Venue minimum order size:** each market's `minimumTradeQty` is captured at scan time
  into `opp.details["min_order_shares"]` and the registry. `size_order` bumps sub-minimum
  counts up to it (post-caps, so a capped count can't slip under) or rejects
  (`below_venue_min_shares`) when the bump would breach `MAX_BET_SIZE`/bankroll; the
  pipeline drops rows the ratio/budget caps push back below minimum.
- **Positions normalized:** `get_positions` also returns Kalshi-shaped `market_positions`
  with `PM-{marketSlug}` tickers (matching the scanner's ticker convention), so Gate 5
  (duplicate ticker), per-event counts, and `kalshi_executor.py status --venue polymarket`
  consume Polymarket positions unchanged.
- **Trade log:** records carry `venue` (`"polymarket"`/`"kalshi"`; absent = kalshi on old
  records). Gate 1 (daily loss) intentionally spans venues — one operator, one risk budget.
- **Excluded from execution:** games opportunities (Gamma-sourced, no US slug) are filtered
  out automatically; the Kalshi resting-order janitor is skipped for non-Kalshi venues.
- Live verification (2026-07-20, preview mode): balance $60.12, 2 US positions counted,
  four championships priced, the one live edge (Spurs) correctly gate-rejected on
  composite score.

### Polymarket US inventory reality (why futures, not games)

A full catalog sweep (3,000 open markets) found the US product is **not** a mirror of
international Gamma:

- **No per-game MLB/NBA/NHL/NFL ML+spread+total markets** like Gamma's. US game markets are
  **moneyline-only** and **seasonal** (NBA/NHL/NFL/CBB/CFB/UFC/soccer) — zero open today
  (offseason). **No spreads or totals anywhere**, and **no MLB per-game** at all.
- **Futures are the deep, always-on surface** (~2,500 open: every league champion, division,
  awards, plus soccer leagues, F1, NASCAR, golf, tennis).

So PM1d's games edge detection (built on Gamma's MLB ML/spread/total) does **not** map to US.
Execution went **futures-first**. The games repoint is a deferred, seasonal follow-on:
moneyline-only, wired per-league as seasons start (like NCAAB), with spreads/totals/MLB
dropped. The games scanner still reads Gamma today (dry-run only; not executable on US).

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
