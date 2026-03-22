# Kalshi API Reference

**Last updated:** 2026-03-18

---

## Environments

| Environment | API Base URL | Web UI |
|---|---|---|
| Demo | `https://demo-api.kalshi.co/trade-api/v2` | https://demo.kalshi.co/ |
| Production | `https://api.elections.kalshi.com/trade-api/v2` | https://kalshi.com/ |

Credentials are **not shared** between environments. Separate accounts, separate keys.

---

## API Keys

**Location:**
```
keys/demo/kalshi_private.key     # Demo RSA private key
keys/live/kalshi_private.key     # Production RSA private key
```

**`.env` config (currently demo):**
```env
KALSHI_API_KEY=<key-id-uuid>
KALSHI_PRIVATE_KEY_PATH=\keys\demo\kalshi_private.key
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2
```

**To switch to production:** Change `KALSHI_PRIVATE_KEY_PATH` to `\keys\live\...`, update `KALSHI_API_KEY` and `KALSHI_BASE_URL`, and set `DRY_RUN=false`.

---

## Authentication

Three headers required on every request:

| Header | Value |
|---|---|
| `KALSHI-ACCESS-KEY` | API Key ID (UUID) |
| `KALSHI-ACCESS-TIMESTAMP` | Unix timestamp in milliseconds |
| `KALSHI-ACCESS-SIGNATURE` | Base64-encoded RSA-PSS SHA256 signature |

**Signature:** `sign(timestamp_ms + HTTP_METHOD + path_without_query_params)`

Implementation: `scripts/kalshi/kalshi_client.py` -- `_sign()` and `_auth_headers()` methods.

---

## Rate Limits

| Tier | Read/sec | Write/sec | Qualification |
|---|---|---|---|
| Basic | 20 | 10 | Auto on signup |
| Advanced | 30 | 30 | Application form |
| Premier | 100 | 100 | 3.75% monthly volume + review |
| Prime | 400 | 400 | 7.5% monthly volume + review |

Write-limited: CreateOrder, CancelOrder, AmendOrder, DecreaseOrder, BatchCreateOrders, BatchCancelOrders.

---

## Endpoints

### Markets

**GET /markets** -- List markets with filters
- `limit` (int, 1-1000), `cursor` (string), `status` (open/closed/settled), `event_ticker`, `series_ticker`, `tickers`

**GET /markets/{ticker}** -- Single market detail
- Returns: ticker, market_type, status, yes/no bid/ask dollars, last_price, volume, open_interest, close_time, rules

### Portfolio

**GET /portfolio/balance** -- Account balance (values in cents)
- Returns: `balance`, `portfolio_value`, `updated_ts`

**GET /portfolio/positions** -- Current positions
- Params: `limit`, `cursor`, `count_filter` (position/total_traded), `ticker`, `event_ticker`
- Returns: `market_positions[]` with ticker, position_fp, exposure, realized_pnl, fees

**GET /portfolio/fills** -- Trade execution history

### Orders

**POST /portfolio/orders** -- Place order
- Required: `ticker`, `side` (yes/no), `action` (buy/sell)
- Optional: `count`, `yes_price` (cents 1-99), `no_price`, `time_in_force` (fill_or_kill/good_till_canceled/immediate_or_cancel), `client_order_id`, `buy_max_cost`, `expiration_ts`
- Returns: Order object with order_id, status, fill details, fees

**GET /portfolio/orders** -- List orders (filter by status: resting/canceled/executed)

**DELETE /portfolio/orders/{order_id}** -- Cancel order

**GET /portfolio/orders/{order_id}** -- Single order detail

---

## Our Client: `scripts/kalshi/kalshi_client.py`

Wraps the raw API with:
- RSA-PSS authentication and request signing
- `.env` config loading and relative path resolution
- DRY_RUN safety gate (blocks live orders unless explicitly allowed)
- Dollar-formatted convenience methods
- Pagination helper (`get_all_open_markets`)
- CLI for quick testing

### CLI

```bash
python scripts/kalshi/kalshi_client.py balance
python scripts/kalshi/kalshi_client.py markets --limit 50 --status open
python scripts/kalshi/kalshi_client.py positions
python scripts/kalshi/kalshi_client.py orders
python scripts/kalshi/kalshi_client.py market --ticker KXTICKER
```

---

## External Links

- API docs: https://docs.kalshi.com/welcome
- API keys: https://docs.kalshi.com/getting_started/api_keys
- Auth guide: https://docs.kalshi.com/getting_started/quick_start_authenticated_requests
- Demo env: https://docs.kalshi.com/getting_started/demo_env
- SDKs: https://docs.kalshi.com/sdks/overview
- Rate limits: https://docs.kalshi.com/getting_started/rate_limits
- Full spec: https://docs.kalshi.com/api-reference
- LLM docs index: https://docs.kalshi.com/llms.txt
