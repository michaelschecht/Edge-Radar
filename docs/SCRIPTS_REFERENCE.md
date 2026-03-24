# Scripts Reference

Complete guide to every script, when to use it, and what flags are available.

---

## Table of Contents

- [Daily Workflow](#daily-workflow)
- [kalshi_executor.py — Main Execution Pipeline](#kalshi_executorpy--main-execution-pipeline)
- [edge_detector.py — Sports Edge Scanner](#edge_detectorpy--sports-edge-scanner)
- [futures_edge.py — Futures & Championship Scanner](#futures_edgepy--futures--championship-scanner)
- [prediction_scanner.py — Prediction Market Scanner](#prediction_scannerpy--prediction-market-scanner)
- [kalshi_settler.py — Settlement & P&L Reporting](#kalshi_settlerpy--settlement--pl-reporting)
- [risk_check.py — Portfolio Risk Dashboard](#risk_checkpy--portfolio-risk-dashboard)
- [kalshi_client.py — API Client CLI](#kalshi_clientpy--api-client-cli)
- [fetch_odds.py — Odds API Explorer](#fetch_oddspy--odds-api-explorer)
- [fetch_market_data.py — Market Data Fetcher](#fetch_market_datapy--market-data-fetcher)
- [run_schedulers.py — Automated Scheduler](#run_schedulerspy--automated-scheduler)

---

## Daily Workflow

### Morning

```bash
# 1. Check portfolio state and open positions
python scripts/kalshi/kalshi_executor.py status

# 2. Settle any overnight results
python scripts/kalshi/kalshi_settler.py settle

# 3. Check if daily loss limit is breached
python scripts/kalshi/risk_check.py --report limits
```

### Scanning for Opportunities

```bash
# 4. Scan sports (preview only — no money risked)
python scripts/kalshi/kalshi_executor.py run --filter nba
python scripts/kalshi/kalshi_executor.py run --filter ncaamb
python scripts/kalshi/kalshi_executor.py run --filter nhl

# 5. Scan futures
python scripts/kalshi/kalshi_executor.py run --filter nba-futures
python scripts/kalshi/kalshi_executor.py run --filter nhl-futures
python scripts/kalshi/kalshi_executor.py run --filter nfl-futures

# 6. Scan prediction markets
python scripts/kalshi/kalshi_executor.py run --prediction --filter crypto
python scripts/kalshi/kalshi_executor.py run --prediction --filter weather
```

### Executing Bets

```bash
# 7. Execute top picks from a scan
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --max-bets 5 --unit-size 1

# 8. Cherry-pick specific rows from preview
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --pick '1,3,5'

# 9. Execute a specific ticker
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --ticker KXNBAGAME-26MAR25LALBOS-LAL
```

### End of Day

```bash
# 10. Settle completed bets
python scripts/kalshi/kalshi_settler.py settle

# 11. Generate report (console + save to file)
python scripts/kalshi/kalshi_settler.py report --detail --save

# 12. Reconcile local log vs Kalshi API
python scripts/kalshi/kalshi_settler.py reconcile
```

---

## kalshi_executor.py — Main Execution Pipeline

**Location:** `scripts/kalshi/kalshi_executor.py`

**When to use:** This is the primary entry point for scanning and executing bets. It handles sports, futures, and prediction markets through a single interface, applies all risk checks, and sizes positions.

### `run` — Scan and Execute

```bash
python scripts/kalshi/kalshi_executor.py run [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter FILTER` | (none) | Sport or market filter. Sports: `nba`, `nhl`, `mlb`, `ncaamb`, `nfl`, `soccer`, `esports`. Futures: `nba-futures`, `nhl-futures`, `nfl-futures`, `mlb-futures`, `golf-futures`, `futures` (all). Raw prefix: `KXNBA`, `KXSB`, etc. |
| `--prediction` | off | Use prediction market scanner instead of sports |
| `--execute` | off | Actually place orders (without this, preview only) |
| `--unit-size N` | `$1.00` | Dollar amount per bet |
| `--min-edge N` | `0.03` | Minimum edge threshold (3%) |
| `--max-bets N` | `5` | Maximum number of bets to place per run |
| `--top N` | `20` | Number of opportunities to scan |
| `--from-file` | off | Load from saved watchlist instead of fresh scan |
| `--pick '1,3,5'` | (none) | Execute only specific rows from the preview table |
| `--ticker TICKER` | (none) | Execute only specific ticker(s) |

**Examples:**

```bash
# Preview NBA opportunities with $2 unit size
python scripts/kalshi/kalshi_executor.py run --filter nba --unit-size 2

# Execute top 3 NCAAB bets at $0.50 each
python scripts/kalshi/kalshi_executor.py run --filter ncaamb --execute --unit-size 0.5 --max-bets 3

# Scan futures with higher edge bar
python scripts/kalshi/kalshi_executor.py run --filter nba-futures --min-edge 0.10

# Execute crypto predictions
python scripts/kalshi/kalshi_executor.py run --prediction --filter crypto --execute --max-bets 3

# Execute specific rows after previewing
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --pick '1,4,7'
```

### `status` — Portfolio Dashboard

```bash
python scripts/kalshi/kalshi_executor.py status
```

Shows: balance, portfolio value, open positions, today's P&L, resting orders.

No flags.

---

## edge_detector.py — Sports Edge Scanner

**Location:** `scripts/kalshi/edge_detector.py`

**When to use:** Standalone sports scanner with more detail than the executor. Use for research and deep dives on individual markets. For scanning + execution, use `kalshi_executor.py run` instead.

**Features:** Normal CDF spread/total model with sport-specific stdev, sharp book weighting (Pinnacle 3x), team stats confidence signal (ESPN/NHL/MLB), weather adjustment for NFL/MLB outdoor totals, per-game cap (top 3 per matchup).

### `scan` — Batch Scan

```bash
python scripts/kalshi/edge_detector.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter FILTER` | (none) | Same sport/futures filters as executor |
| `--category CAT` | (none) | Filter by market type: `game`, `spread`, `total`, `player_prop`, `esports`, `other` |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--top N` | `20` | Number of top opportunities |
| `--save` | off | Save results to `data/watchlists/kalshi_opportunities.json` |

**Examples:**

```bash
# Scan only NBA game outcomes (no spreads/totals)
python scripts/kalshi/edge_detector.py scan --filter nba --category game

# Scan all sports with 10% min edge, save results
python scripts/kalshi/edge_detector.py scan --min-edge 0.10 --save

# Scan top 50 opportunities across all sports
python scripts/kalshi/edge_detector.py scan --top 50
```

### `detail` — Single Market Deep Dive

```bash
python scripts/kalshi/edge_detector.py detail TICKER
```

Shows the full breakdown for one market: matched sportsbook odds, de-vigged probabilities, fair value, and edge.

```bash
python scripts/kalshi/edge_detector.py detail KXNBAGAME-26MAR25LALBOS-LAL
```

---

## futures_edge.py — Futures & Championship Scanner

**Location:** `scripts/kalshi/futures_edge.py`

**When to use:** Dedicated futures scanner with bet-type labels. Can also route into the executor pipeline for sizing and execution.

### `scan` — Scan Futures

```bash
python scripts/kalshi/futures_edge.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter FILTER` | (all futures) | `nfl-futures`, `nba-futures`, `nhl-futures`, `mlb-futures`, `ncaab-futures`, `golf-futures`, `futures` (all) |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--top N` | `20` | Number of top opportunities |
| `--unit-size N` | (from .env) | Dollar amount per bet — routes through executor pipeline |
| `--max-bets N` | `5` | Max bets to place |
| `--execute` | off | Place orders through executor pipeline |
| `--pick '1,3'` | (none) | Execute specific rows |
| `--ticker TICKER` | (none) | Execute specific ticker(s) |

**Examples:**

```bash
# Preview all futures
python scripts/kalshi/futures_edge.py scan

# NHL futures with $3 sizing
python scripts/kalshi/futures_edge.py scan --filter nhl-futures --unit-size 3

# Execute top NBA futures picks
python scripts/kalshi/futures_edge.py scan --filter nba-futures --unit-size 2 --execute --max-bets 3

# High-edge futures only
python scripts/kalshi/futures_edge.py scan --min-edge 0.15 --top 50
```

**Scan-only mode** (no `--unit-size` or `--execute`): shows a compact table with Bet Type, Candidate, Side, Market Price, Fair Value, Edge, Confidence, Score, and Books.

**Executor mode** (with `--unit-size` or `--execute`): routes through the full executor pipeline with risk checks, sizing, and the standard preview/execute table.

---

## prediction_scanner.py — Prediction Market Scanner

**Location:** `scripts/prediction/prediction_scanner.py`

**When to use:** Standalone prediction market scanner. For scanning + execution, use `kalshi_executor.py run --prediction` instead.

### `scan` — Scan Prediction Markets

```bash
python scripts/prediction/prediction_scanner.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter FILTER` | (all) | `crypto`, `btc`, `eth`, `xrp`, `doge`, `sol`, `weather`, `spx`, `mentions`, `companies`, `politics` |
| `--category CAT` | (none) | Filter by category: `crypto`, `weather`, `spx`, `mentions`, `companies`, `politics` |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--top N` | `20` | Number of top opportunities |
| `--save` | off | Save to `data/watchlists/prediction_opportunities.json` |

**Examples:**

```bash
# Scan all prediction markets
python scripts/prediction/prediction_scanner.py scan

# Crypto only with 5% edge bar
python scripts/prediction/prediction_scanner.py scan --filter crypto --min-edge 0.05

# Weather predictions, save to watchlist
python scripts/prediction/prediction_scanner.py scan --filter weather --save

# S&P 500 binary options
python scripts/prediction/prediction_scanner.py scan --filter spx
```

---

## kalshi_settler.py — Settlement & P&L Reporting

**Location:** `scripts/kalshi/kalshi_settler.py`

**When to use:** After games/events have resolved, to update your trade log with results and generate performance reports.

### `settle` — Update Trade Log

```bash
python scripts/kalshi/kalshi_settler.py settle
```

Polls the Kalshi API for settlements, matches to your trade log, calculates P&L per trade, and updates records. No flags.

Run this after games complete to move trades from "open" to "settled" with realized P&L.

### `report` — Performance Report

```bash
python scripts/kalshi/kalshi_settler.py report [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--detail` | off | Show per-trade breakdown table |
| `--save` | off | Save to `reports/Accounts/Kalshi/kalshi_report_YYYY-MM-DD.txt` |

**Examples:**

```bash
# Quick summary
python scripts/kalshi/kalshi_settler.py report

# Full detail with file export
python scripts/kalshi/kalshi_settler.py report --detail --save
```

**Report includes:** win/loss record, net P&L, ROI, profit factor, best/worst trades, edge calibration (estimated vs. realized), breakdowns by confidence level and category.

### `reconcile` — Verify Trade Integrity

```bash
python scripts/kalshi/kalshi_settler.py reconcile
```

Compares your local trade log against the Kalshi API to find:
- Trades in your log but not on Kalshi (demo/cancelled)
- Positions on Kalshi not in your log (placed manually)
- Quantity mismatches between local and API

No flags. Run periodically to keep your trade log accurate.

---

## risk_check.py — Portfolio Risk Dashboard

**Location:** `scripts/kalshi/risk_check.py`

**When to use:** Quick portfolio health check, or as a gate in automation pipelines.

```bash
python scripts/kalshi/risk_check.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--report TYPE` | `all` | `all`, `positions`, `pnl`, `limits`, `watchlist` |
| `--gate` | off | Exit code 1 if any risk limit is breached (for automation) |

**Examples:**

```bash
# Full dashboard
python scripts/kalshi/risk_check.py

# Just check if limits are breached (for scripts/schedulers)
python scripts/kalshi/risk_check.py --gate

# Show only open positions
python scripts/kalshi/risk_check.py --report positions

# Show only P&L
python scripts/kalshi/risk_check.py --report pnl
```

---

## kalshi_client.py — API Client CLI

**Location:** `scripts/kalshi/kalshi_client.py`

**When to use:** Low-level API queries. Useful for debugging and checking raw market data.

```bash
python scripts/kalshi/kalshi_client.py COMMAND [flags]
```

| Command | Description |
|---------|-------------|
| `balance` | Show account balance |
| `markets` | List open markets |
| `positions` | Show open positions |
| `orders` | Show order history |
| `market` | Get details for a single market (requires `--ticker`) |

| Flag | Default | Description |
|------|---------|-------------|
| `--ticker TICKER` | (none) | Market ticker (for `market` command) |
| `--limit N` | `20` | Number of results |
| `--status STATUS` | `open` | Market status filter |

**Examples:**

```bash
# Check balance
python scripts/kalshi/kalshi_client.py balance

# Browse markets
python scripts/kalshi/kalshi_client.py markets --limit 50

# Get details for a specific market
python scripts/kalshi/kalshi_client.py market --ticker KXNBAGAME-26MAR25LALBOS-LAL

# Check open positions
python scripts/kalshi/kalshi_client.py positions
```

---

## fetch_odds.py — Odds API Explorer

**Location:** `scripts/kalshi/fetch_odds.py`

**When to use:** Explore raw sportsbook odds without running edge detection. Useful for research and verifying what The Odds API returns.

```bash
python scripts/kalshi/fetch_odds.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--market SPORT` | `nba` | `nba`, `nfl`, `mlb`, `nhl`, `ncaafb`, `ncaabb`, `soccer`, `mma`, `all` |
| `--min-edge N` | from .env | Minimum edge threshold |
| `--dry-run` | off | Print results without saving |
| `--save` | off | Save opportunities to watchlist |

---

## fetch_market_data.py — Market Data Fetcher

**Location:** `scripts/kalshi/fetch_market_data.py`

**When to use:** Pull market data for stocks, crypto, or prediction markets. Research tool.

```bash
python scripts/kalshi/fetch_market_data.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--type TYPE` | `stocks` | `stocks`, `prediction`, `crypto`, `account`, `all` |
| `--symbols SYM [SYM ...]` | `AAPL NVDA TSLA SPY QQQ` | Tickers to fetch |
| `--limit N` | `20` | Number of prediction market results |
| `--save` | off | Save snapshot to data/ |
| `--source SOURCE` | `polymarket` | `polymarket` or `kalshi` |

---

## run_schedulers.py — Automated Scheduler

**Location:** `scripts/schedulers/run_schedulers.py`

**When to use:** Launch automated recurring scans. Schedulers must be enabled in `.env` first. See `docs/schedulers/SCHEDULER_GUIDE.md`.

```bash
python scripts/schedulers/run_schedulers.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--list` | off | Show all registered scheduler profiles and exit |
| `--only NAME` | (none) | Launch a single scheduler (e.g., `--only nba`) |

**Examples:**

```bash
# See what's configured
python scripts/schedulers/run_schedulers.py --list

# Launch all enabled schedulers
python scripts/schedulers/run_schedulers.py

# Launch just the NBA scheduler
python scripts/schedulers/run_schedulers.py --only nba
```

**Before using:** Set `SCHED_{NAME}_ENABLED=true` in `.env` for each scheduler you want to run. See [Scheduler Guide](schedulers/SCHEDULER_GUIDE.md).

---

## daily_sports_scan.py — Daily Morning Report

**Location:** `scripts/schedulers/daily_sports_scan.py`

**When to use:** Generate a daily morning report scanning MLB, NBA, NHL, and NFL for the top betting opportunities. Run manually or as a daemon at 8:00 AM PST.

```bash
python scripts/schedulers/daily_sports_scan.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--top N` | `25` | Number of top opportunities to include |
| `--daemon` | off | Run as daemon — scans at 8:00 AM PST daily |

**Examples:**

```bash
# Run once now, top 25
python scripts/schedulers/daily_sports_scan.py

# Top 50 opportunities
python scripts/schedulers/daily_sports_scan.py --top 50

# Run as daemon (8 AM PST daily, runs once immediately on start)
python scripts/schedulers/daily_sports_scan.py --daemon
```

**Output:** Report saved to `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md` with edge, fair value, confidence, team stats, sharp money signals, and weather notes.
