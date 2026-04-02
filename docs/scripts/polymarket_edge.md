# polymarket_edge.py — Polymarket Cross-Reference Scanner

**Location:** `scripts/polymarket/polymarket_edge.py`

**Via scan.py:** `python scripts/scan.py polymarket [flags]`

**When to use:** Cross-market arbitrage -- finds markets priced differently on Kalshi vs Polymarket. Use when you want to compare prices across exchanges rather than using a model. Also has a `match` command to check if a specific Kalshi market has a Polymarket equivalent.

For most prediction market scanning, use `prediction_scanner.py` with `--cross-ref` instead -- it combines model-based edge detection with Polymarket validation in one step.

**Data source:** Polymarket Gamma API (`gamma-api.polymarket.com`). Free, no API key required. Rate limit: 750 req/10s.

---

## `scan` -- Cross-Market Edge Scan

```bash
python scripts/polymarket/polymarket_edge.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter CAT` | (all) | Category: `crypto`, `weather`, `spx`, `politics`, `companies` |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--min-match N` | `0.45` | Minimum match quality score (0-1) |
| `--top N` | `20` | Number of top opportunities |
| `--date DATE` | (none) | Only show markets on this date |
| `--save` | off | Save to `data/watchlists/polymarket_opportunities.json` |
| `--exclude-open` | off | Skip markets where you already have an open position |
| `--execute` | off | Place orders through executor pipeline |
| `--unit-size N` | (from .env) | Dollar amount per bet |
| `--max-bets N` | `5` | Max bets to place |
| `--pick '1,3'` | (none) | Execute specific rows |
| `--ticker TICKER` | (none) | Execute specific ticker(s) |

### Examples

```bash
# Scan all matchable categories
python scripts/scan.py polymarket

# Crypto cross-reference, execute top 5
python scripts/scan.py polymarket --filter crypto --execute --unit-size 1 --max-bets 5

# Save results, skip open positions
python scripts/scan.py polymarket --save --exclude-open
```

---

## `match` -- Find Polymarket Match for a Kalshi Ticker

```bash
python scripts/polymarket/polymarket_edge.py match TICKER
```

Shows the best Polymarket match for a specific Kalshi market, including match score and price comparison.

```bash
python scripts/polymarket/polymarket_edge.py match KXBTC-28MAR26-T88000
```

---

## How Matching Works

1. Fetch all active Kalshi markets in the filtered category
2. Fetch all active Polymarket markets via Gamma API
3. Fuzzy match by title similarity (TF-IDF + cosine similarity)
4. Filter by `--min-match` quality threshold
5. Compare prices: Kalshi YES price vs Polymarket YES price
6. Surface opportunities where the price gap exceeds `--min-edge`
