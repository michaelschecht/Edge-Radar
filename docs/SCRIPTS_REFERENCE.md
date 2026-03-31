# Scripts Reference

Complete guide to every script, when to use it, and what flags are available.

---

## Table of Contents

- [Which Script Should I Use?](#which-script-should-i-use)
- [scan.py — Unified Scanner](#scanpy--unified-scanner)
- [Daily Workflow](#daily-workflow)
- [edge_detector.py — Sports Edge Scanner](#edge_detectorpy--sports-edge-scanner)
- [futures_edge.py — Futures & Championship Scanner](#futures_edgepy--futures--championship-scanner)
- [prediction_scanner.py — Prediction Market Scanner](#prediction_scannerpy--prediction-market-scanner)
- [polymarket_edge.py — Polymarket Cross-Reference Scanner](#polymarket_edgepy--polymarket-cross-reference-scanner)
- [kalshi_executor.py — Unified Executor](#kalshi_executorpy--unified-executor)
- [kalshi_settler.py — Settlement & P&L Reporting](#kalshi_settlerpy--settlement--pl-reporting)
- [risk_check.py — Portfolio Risk Dashboard](#risk_checkpy--portfolio-risk-dashboard)
- [kalshi_client.py — API Client CLI](#kalshi_clientpy--api-client-cli)
- [fetch_odds.py — Odds API Explorer](#fetch_oddspy--odds-api-explorer)
- [fetch_market_data.py — Market Data Fetcher](#fetch_market_datapy--market-data-fetcher)
- [daily_sports_scan.py — Daily Morning Report](#daily_sports_scanpy--daily-morning-report)
- [Scheduling Your Own Scans](#scheduling-your-own-scans)

---

## Which Script Should I Use?

### "I want to scan for bets"

Use `scripts/scan.py` as the unified entry point, or call a dedicated scanner directly. All flags are forwarded.

| Market | Unified | Direct Script |
|--------|---------|---------------|
| **Sports** (NBA, MLB, NHL, NFL, NCAA, etc.) | `scan.py sports --filter mlb` | `edge_detector.py scan --filter mlb` |
| **Championship Futures** (World Series, Super Bowl, etc.) | `scan.py futures --filter nba-futures` | `futures_edge.py scan --filter nba-futures` |
| **Prediction Markets** (crypto, weather, S&P 500, politics) | `scan.py prediction --filter crypto` | `prediction_scanner.py scan --filter crypto` |
| **Polymarket Cross-Reference** (Kalshi vs Polymarket prices) | `scan.py polymarket --filter crypto` | `polymarket_edge.py scan --filter crypto` |

All scanners share the same flags: `--execute`, `--unit-size`, `--max-bets`, `--pick`, `--ticker`, `--save`, `--date`, `--exclude-open`.

### "I want to scan AND execute"

Add `--execute` to any scanner. Without it, you get a preview table. With it, orders are placed.

```bash
# Preview first (no money risked)
python scripts/scan.py sports --filter mlb --unit-size 1 --max-bets 10

# Then execute (add --execute)
python scripts/scan.py sports --filter mlb --unit-size 1 --max-bets 10 --execute
```

### "I want to check my portfolio"

| What | Script |
|------|--------|
| Quick status (balance, positions, P&L) | `kalshi_executor.py status` |
| Full risk dashboard (limits, positions, resting orders, watchlist) | `risk_check.py` |
| Just open positions | `risk_check.py --report positions` |
| Save a snapshot as markdown | Add `--save` to either command |

### "I want to settle bets and see results"

```bash
python scripts/kalshi/kalshi_settler.py settle          # Update trade log with results
python scripts/kalshi/kalshi_settler.py report --detail  # See P&L breakdown
python scripts/kalshi/kalshi_settler.py report --detail --save  # Save as markdown
```

### When to use `kalshi_executor.py run` vs the dedicated scanners

`kalshi_executor.py run` is the **legacy unified entry point**. It calls the scanners internally. Use it when you need:

- `--prediction` — Scan prediction markets without remembering the prediction_scanner path
- `--from-file` — Load a previously saved watchlist instead of scanning fresh
- `--cross-ref` — Cross-reference against Polymarket (prediction markets only)

For everything else, **use the dedicated scanners directly** — they show more detail, support `--category` filtering (game/spread/total), and the output is clearer.

---

## scan.py — Unified Scanner

**Location:** `scripts/scan.py`

**When to use:** Single entry point for all scanners. Routes to the correct scanner based on market type. All flags are forwarded directly.

```bash
python scripts/scan.py <market-type> [flags]
```

| Market Type | Aliases | Routes To |
|-------------|---------|-----------|
| `sports` | `sport` | `edge_detector.py scan` |
| `futures` | — | `futures_edge.py scan` |
| `prediction` | `pred` | `prediction_scanner.py scan` |
| `polymarket` | `poly`, `xref` | `polymarket_edge.py scan` |

**Examples:**

```bash
python scripts/scan.py sports --filter mlb --date today --save
python scripts/scan.py futures --filter nba-futures --top 10
python scripts/scan.py prediction --filter crypto --cross-ref
python scripts/scan.py polymarket --filter crypto --min-edge 0.05
```

The `scan` subcommand is auto-inserted if omitted. Use `<market-type> --help` to see the full flag list for each scanner.

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
python scripts/scan.py sports --filter nba
python scripts/scan.py sports --filter mlb
python scripts/scan.py sports --filter nhl

# 5. Only tomorrow's games, skip open positions
python scripts/scan.py sports --filter mlb --date tomorrow --exclude-open

# 6. Scan futures
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py futures --filter nhl-futures

# 7. Scan prediction markets
python scripts/scan.py prediction --filter crypto
python scripts/scan.py prediction --filter weather
```

### Executing Bets

```bash
# 8. Execute top picks from a scan
python scripts/scan.py sports --filter mlb --execute --max-bets 10 --unit-size 1

# 9. Cherry-pick specific rows from preview
python scripts/scan.py sports --filter nba --execute --pick '1,3,5'

# 10. Execute a specific ticker
python scripts/scan.py sports --filter nba --execute --ticker KXNBAGAME-26MAR25LALBOS-LAL
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

## kalshi_executor.py — Unified Executor

**Location:** `scripts/kalshi/kalshi_executor.py`

**When to use:** Unified entry point that wraps the dedicated scanners. Use when you need `--prediction`, `--from-file`, or `--cross-ref` flags. For most scanning, use the dedicated scanners directly (`edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`) — they support all the same execution flags and show more detail.

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
| `--date DATE` | (none) | Only show games on this date (`today`, `tomorrow`, `YYYY-MM-DD`, `mar31`) |
| `--exclude-open` | off | Skip markets where you already have an open position |

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
python scripts/kalshi/kalshi_executor.py status [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--save` | off | Save status report as markdown to `reports/Accounts/Kalshi/kalshi_status_YYYY-MM-DD.md` |

Shows: balance, portfolio value, open positions (readable matchups + dates), today's P&L, resting orders.

```bash
# Console only
python scripts/kalshi/kalshi_executor.py status

# Console + save markdown report
python scripts/kalshi/kalshi_executor.py status --save
```

---

## edge_detector.py — Sports Edge Scanner

**Location:** `scripts/kalshi/edge_detector.py`

**When to use:** Primary script for sports betting. Scan for edge, filter by sport/date/category, preview opportunities, and execute — all from one command. Use this for NBA, MLB, NHL, NFL, NCAA, soccer, UFC, and all other sports markets.

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
| `--execute` | off | Place orders through executor pipeline |
| `--unit-size N` | (from .env) | Dollar amount per bet — routes through executor pipeline |
| `--max-bets N` | `5` | Max bets to place |
| `--pick '1,3'` | (none) | Execute specific rows |
| `--ticker TICKER` | (none) | Execute specific ticker(s) |
| `--date DATE` | (none) | Only show games on this date (`today`, `tomorrow`, `YYYY-MM-DD`, `mar31`) |
| `--exclude-open` | off | Skip markets where you already have an open position |

**Examples:**

```bash
# Scan only NBA game outcomes (no spreads/totals)
python scripts/kalshi/edge_detector.py scan --filter nba --category game

# Tomorrow's MLB games only, skip open positions
python scripts/kalshi/edge_detector.py scan --filter mlb --date tomorrow --exclude-open

# Execute top 10 MLB picks at $1 each
python scripts/kalshi/edge_detector.py scan --filter mlb --execute --unit-size 1 --max-bets 10

# Scan all sports with 10% min edge, save results
python scripts/kalshi/edge_detector.py scan --min-edge 0.10 --save
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

**When to use:** Championship and season-long markets — World Series, Super Bowl, Stanley Cup, NBA Finals, conference winners, PGA Tour. Uses N-way de-vigging across all candidates (not just 2-way). Use this instead of `edge_detector.py` for any futures/outright market.

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
| `--save` | off | Save results to `data/watchlists/futures_opportunities.json` |
| `--date DATE` | (none) | Only show markets on this date (`today`, `tomorrow`, `YYYY-MM-DD`, `mar31`) |
| `--exclude-open` | off | Skip markets where you already have an open position |

**Examples:**

```bash
# Preview all futures
python scripts/kalshi/futures_edge.py scan

# NHL futures with $3 sizing
python scripts/kalshi/futures_edge.py scan --filter nhl-futures --unit-size 3

# Execute top NBA futures picks
python scripts/kalshi/futures_edge.py scan --filter nba-futures --unit-size 2 --execute --max-bets 3

# Save futures scan to watchlist
python scripts/kalshi/futures_edge.py scan --filter mlb-futures --save
```

**Scan-only mode** (no `--unit-size` or `--execute`): shows a compact table with Bet Type, Candidate, Date, Side, Market Price, Fair Value, Edge, Confidence, and Score.

**Executor mode** (with `--unit-size` or `--execute`): routes through the full executor pipeline with risk checks, sizing, and the standard preview/execute table.

---

## prediction_scanner.py — Prediction Market Scanner

**Location:** `scripts/prediction/prediction_scanner.py`

**When to use:** Non-sports prediction markets — crypto (BTC, ETH, XRP, DOGE, SOL), weather, S&P 500, politics, TV mentions, companies. Uses model-specific edge detection (CoinGecko for crypto, NWS for weather, Yahoo Finance for S&P). Supports `--cross-ref` to validate edge against Polymarket prices.

### `scan` — Scan Prediction Markets

```bash
python scripts/prediction/prediction_scanner.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter FILTER` | (all) | `crypto`, `btc`, `eth`, `xrp`, `doge`, `sol`, `weather`, `spx`, `mentions`, `companies`, `politics`, `polymarket`, `poly`, `xref` |
| `--category CAT` | (none) | Filter by category: `crypto`, `weather`, `spx`, `mentions`, `companies`, `politics` |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--top N` | `20` | Number of top opportunities |
| `--save` | off | Save to `data/watchlists/prediction_opportunities.json` |
| `--cross-ref` | off | Cross-reference Kalshi prices against Polymarket for additional edge signals |
| `--execute` | off | Place orders through executor pipeline |
| `--unit-size N` | (from .env) | Dollar amount per bet |
| `--max-bets N` | `5` | Max bets to place |
| `--pick '1,3'` | (none) | Execute specific rows |
| `--ticker TICKER` | (none) | Execute specific ticker(s) |
| `--date DATE` | (none) | Only show markets on this date (`today`, `tomorrow`, `YYYY-MM-DD`, `mar31`) |
| `--exclude-open` | off | Skip markets where you already have an open position |

**Examples:**

```bash
# Scan all prediction markets
python scripts/prediction/prediction_scanner.py scan

# Crypto only, execute at $1 per bet
python scripts/prediction/prediction_scanner.py scan --filter crypto --execute --unit-size 1

# Weather predictions, save to watchlist
python scripts/prediction/prediction_scanner.py scan --filter weather --save

# Cross-reference against Polymarket, skip open positions
python scripts/prediction/prediction_scanner.py scan --cross-ref --exclude-open

# Tomorrow's crypto markets only
python scripts/prediction/prediction_scanner.py scan --filter crypto --date tomorrow
```

---

## polymarket_edge.py — Polymarket Cross-Reference Scanner

**Location:** `scripts/polymarket/polymarket_edge.py`

**When to use:** Cross-market arbitrage — finds markets priced differently on Kalshi vs Polymarket. Use when you want to compare prices across exchanges rather than using a model. Also has a `match` command to check if a specific Kalshi market has a Polymarket equivalent. For most prediction market scanning, use `prediction_scanner.py` with `--cross-ref` instead — it combines model-based edge detection with Polymarket validation in one step.

**Data source:** Polymarket Gamma API (`gamma-api.polymarket.com`). Free, no API key required. Rate limit: 750 req/10s.

### `scan` — Cross-Market Edge Scan

```bash
python scripts/polymarket/polymarket_edge.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter CAT` | (all) | Category: `crypto`, `weather`, `spx`, `politics`, `companies` |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--min-match N` | `0.45` | Minimum match quality score (0-1) |
| `--top N` | `20` | Number of top opportunities |
| `--save` | off | Save to `data/watchlists/polymarket_opportunities.json` |
| `--execute` | off | Place orders through executor pipeline |
| `--unit-size N` | (from .env) | Dollar amount per bet |
| `--max-bets N` | `5` | Max bets to place |
| `--pick '1,3'` | (none) | Execute specific rows |
| `--ticker TICKER` | (none) | Execute specific ticker(s) |
| `--date DATE` | (none) | Only show markets on this date |
| `--exclude-open` | off | Skip markets where you already have an open position |

**Examples:**

```bash
# Scan all matchable categories
python scripts/polymarket/polymarket_edge.py scan

# Crypto cross-reference, execute top 5
python scripts/polymarket/polymarket_edge.py scan --filter crypto --execute --unit-size 1 --max-bets 5

# Save results, skip open positions
python scripts/polymarket/polymarket_edge.py scan --save --exclude-open
```

### `match` — Find Polymarket Match for a Kalshi Ticker

```bash
python scripts/polymarket/polymarket_edge.py match TICKER
```

Shows the best Polymarket match for a specific Kalshi market, including match score and price comparison.

```bash
python scripts/polymarket/polymarket_edge.py match KXBTC-28MAR26-T88000
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
| `--save` | off | Save markdown report to `reports/Accounts/Kalshi/kalshi_report_YYYY-MM-DD.md` |

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

**When to use:** Comprehensive portfolio dashboard with risk limits, position details, P&L, and watchlist. Pulls live data from the Kalshi API. Shows readable matchups and game dates. Use `--report positions` for just open bets, or `--gate` in automation to block execution when limits are breached. For a quick balance/positions check, `kalshi_executor.py status` is faster.

```bash
python scripts/kalshi/risk_check.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--report TYPE` | `all` | `all`, `positions`, `pnl`, `limits`, `watchlist` |
| `--gate` | off | Exit code 1 if any risk limit is breached (for automation) |
| `--save` | off | Save dashboard as markdown to `reports/Accounts/Kalshi/kalshi_dashboard_YYYY-MM-DD.md` |

**Examples:**

```bash
# Full dashboard
python scripts/kalshi/risk_check.py

# Full dashboard + save markdown
python scripts/kalshi/risk_check.py --save

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

## daily_sports_scan.py — Daily Morning Report

**Location:** `scripts/schedulers/automation/daily_sports_scan.py`

**When to use:** Generate a morning edge report scanning MLB, NBA, NHL, and NFL. Run manually or schedule with Windows Task Scheduler / cron.

```bash
python scripts/schedulers/automation/daily_sports_scan.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--top N` | `25` | Number of top opportunities to include |
| `--daemon` | off | Run as background daemon — scans at 8:00 AM PST daily |

**Examples:**

```bash
# Run once now, top 25
python scripts/schedulers/automation/daily_sports_scan.py

# Top 50 opportunities
python scripts/schedulers/automation/daily_sports_scan.py --top 50
```

**Output:** Report saved to `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md` with edge, fair value, confidence, team stats, sharp money signals, and weather notes.

---

## install_windows_task.py — Windows Task Scheduler Setup

**Location:** `scripts/schedulers/automation/install_windows_task.py`

**When to use:** Install the daily morning scan as a Windows Scheduled Task that runs automatically at 8:00 AM.

```bash
python scripts/schedulers/automation/install_windows_task.py install   # Create the task
python scripts/schedulers/automation/install_windows_task.py status    # Check if installed
python scripts/schedulers/automation/install_windows_task.py run       # Trigger now (test)
python scripts/schedulers/automation/install_windows_task.py remove    # Remove the task
```

---

## Scheduling Your Own Scans

For recurring scans (e.g., MLB every morning, NBA every evening), use Windows Task Scheduler or cron directly with the scanner scripts:

```bash
# MLB daily scan at 10 AM — finds edge, skips open positions, executes up to 10 bets
python scripts/kalshi/edge_detector.py scan --filter mlb --unit-size 1 --max-bets 10 --exclude-open --save --execute

# NBA daily scan at 6 PM
python scripts/kalshi/edge_detector.py scan --filter nba --unit-size 1 --max-bets 10 --exclude-open --save --execute

# Settle results at 11 PM
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail --save
```

To set these up in Windows Task Scheduler, use `schtasks`:

```bash
# MLB morning scan at 10 AM daily
schtasks /Create /TN "Edge-Radar\MLB-Scan" /TR "\".venv\Scripts\python.exe\" \"scripts\kalshi\edge_detector.py\" scan --filter mlb --unit-size 1 --max-bets 10 --exclude-open --save --execute" /SC DAILY /ST 10:00

# NBA evening scan at 6 PM daily
schtasks /Create /TN "Edge-Radar\NBA-Scan" /TR "\".venv\Scripts\python.exe\" \"scripts\kalshi\edge_detector.py\" scan --filter nba --unit-size 1 --max-bets 10 --exclude-open --save --execute" /SC DAILY /ST 18:00
```
