# prediction_scanner.py — Prediction Market Scanner

**Location:** `scripts/prediction/prediction_scanner.py`

**Via scan.py:** `python scripts/scan.py prediction [flags]`

**When to use:** Non-sports prediction markets -- crypto (BTC, ETH, XRP, DOGE, SOL), weather, S&P 500, politics, TV mentions, companies. Uses model-specific edge detection (CoinGecko for crypto, NWS for weather, Yahoo Finance for S&P).

---

## `scan` -- Scan Prediction Markets

```bash
python scripts/prediction/prediction_scanner.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter FILTER` | (all) | `crypto`, `btc`, `eth`, `xrp`, `doge`, `sol`, `weather`, `spx`, `mentions`, `companies`, `politics` |
| `--category CAT` | (none) | Filter by category: `crypto`, `weather`, `spx`, `mentions`, `companies`, `politics` |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--top N` | `20` | Number of top opportunities |
| `--date DATE` | (none) | Only show markets on this date (`today`, `tomorrow`, `YYYY-MM-DD`, `mar31`) |
| `--save` | off | Save to `data/watchlists/prediction_opportunities.json` |
| `--exclude-open` | off | Skip markets where you already have an open position |
| `--execute` | off | Place orders through executor pipeline |
| `--unit-size N` | (from .env) | Dollar amount per bet |
| `--max-bets N` | `5` | Max bets to place |
| `--pick '1,3'` | (none) | Execute specific rows |
| `--ticker TICKER` | (none) | Execute specific ticker(s) |

### Examples

```bash
# Scan all prediction markets
python scripts/scan.py prediction

# Crypto only, execute at $1 per bet
python scripts/scan.py prediction --filter crypto --execute --unit-size 1

# Weather predictions, save to watchlist
python scripts/scan.py prediction --filter weather --save

# Skip open positions
python scripts/scan.py prediction --exclude-open

# Tomorrow's crypto markets only
python scripts/scan.py prediction --filter crypto --date tomorrow
```

---

## Edge Detection by Category

| Category | Data Source | Model |
|----------|-----------|-------|
| **Crypto** (BTC, ETH, XRP, DOGE, SOL) | CoinGecko API | Current price + 24h volatility vs strike |
| **Weather** (13 US cities) | NWS (National Weather Service) | Forecast temperature vs Kalshi strike |
| **S&P 500** | Yahoo Finance + VIX | Current level + implied vol vs strike |
| **Mentions** | Historical settlement rates | Base-rate model |
| **Companies** | Historical baselines | Bankruptcy/IPO timing models |
| **Politics** | Time-decay model | Event base rates |

---

## Output

Console table with: Title, Date, Cat., Side, Mkt, Fair, Edge, Conf., Score.
