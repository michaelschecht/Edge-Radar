# Scripts Reference

Complete guide to every script, when to use it, and what flags are available.

For domain-specific guides: [Sports](kalshi-sports-betting/SPORTS_GUIDE.md) | [Futures](kalshi-futures-betting/FUTURES_GUIDE.md) | [Predictions](kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md) | [Architecture](ARCHITECTURE.md) | [Roadmap](enhancements/ROADMAP.md)

---

## Table of Contents

- [Which Script Should I Use?](#which-script-should-i-use)
- [scan.py -- Unified Scanner](#scanpy--unified-scanner)
- [Daily Workflow](#daily-workflow)
- [Script Reference (detailed docs)](#script-reference)
- [Utility Scripts](#utility-scripts)
- [Scheduling Your Own Scans](#scheduling-your-own-scans)

---

## Which Script Should I Use?

### "I want to scan for bets"

Use `scripts/scan.py` as the unified entry point. All flags are forwarded to the underlying scanner.

| Market | Command | Detailed Docs |
|--------|---------|---------------|
| **Sports** (NBA, MLB, NHL, NFL, NCAA, etc.) | `scan.py sports --filter mlb` | [edge_detector.md](scripts/edge_detector.md) |
| **Championship Futures** (World Series, Super Bowl, etc.) | `scan.py futures --filter nba-futures` | [futures_edge.md](scripts/futures_edge.md) |
| **Prediction Markets** (crypto, weather, S&P 500, politics) | `scan.py prediction --filter crypto` | [prediction_scanner.md](scripts/prediction_scanner.md) |
| **Polymarket Cross-Reference** (Kalshi vs Polymarket prices) | `scan.py polymarket --filter crypto` | [polymarket_edge.md](scripts/polymarket_edge.md) |

### "I want to scan AND execute"

Add `--execute` to any scan. Without it, you get a preview table. With it, orders are placed.

```bash
# Preview first (no money risked)
python scripts/scan.py sports --filter mlb --unit-size 1 --max-bets 10

# Then execute (add --execute)
python scripts/scan.py sports --filter mlb --unit-size 1 --max-bets 10 --execute
```

### "I want to check my portfolio"

| What | Command | Detailed Docs |
|------|---------|---------------|
| Quick status (balance, positions, P&L) | `kalshi_executor.py status` | [kalshi_executor.md](scripts/kalshi_executor.md) |
| Full risk dashboard (limits, positions, resting orders) | `risk_check.py` | [risk_check.md](scripts/risk_check.md) |
| Just open positions | `risk_check.py --report positions` | [risk_check.md](scripts/risk_check.md) |
| Save a snapshot as markdown | Add `--save` to either command | |

### "I want to settle bets and see results"

```bash
python scripts/kalshi/kalshi_settler.py settle          # Update trade log with results
python scripts/kalshi/kalshi_settler.py report --detail  # See P&L breakdown
python scripts/kalshi/kalshi_settler.py report --detail --save  # Save as markdown
```

See [kalshi_settler.md](scripts/kalshi_settler.md) for full details.

---

## scan.py -- Unified Scanner

**Location:** `scripts/scan.py`

Single entry point for all scanners. Routes to the correct scanner based on market type. All flags are forwarded directly.

```bash
python scripts/scan.py <market-type> [flags]
```

| Market Type | Aliases | Routes To |
|-------------|---------|-----------|
| `sports` | `sport` | `edge_detector.py scan` |
| `futures` | -- | `futures_edge.py scan` |
| `prediction` | `pred` | `prediction_scanner.py scan` |
| `polymarket` | `poly`, `xref` | `polymarket_edge.py scan` |

### Common Flags (all scanners)

| Flag | Default | Description |
|------|---------|-------------|
| `--filter X` | *(none)* | Filter by sport/asset/category (e.g., `mlb`, `nba`, `crypto`, `weather`) |
| `--min-edge N` | `0.03` | Minimum edge threshold to surface an opportunity |
| `--top N` | `20` | Number of top opportunities to display |
| `--date X` | *(all dates)* | Filter by game date (`today`, `tomorrow`, `YYYY-MM-DD`, `mar31`) |
| `--save` | off | Save a markdown report to `reports/` |
| `--exclude-open` | off | Skip markets where you already have an open position |
| `--execute` | off | Execute bets through the pipeline (dry run without this) |
| `--unit-size N` | `UNIT_SIZE` env var | Dollar amount per bet |
| `--max-bets N` | `5` | Maximum number of bets to place |
| `--pick X` | *(all)* | Comma-separated row numbers to execute (e.g., `'1,3,5'`) |
| `--ticker X` | *(all)* | Execute only specific tickers |
| `--category X` | *(all)* | Filter to a market category: `game`, `spread`, `total`, `player_prop`, `esports`, `other` |
| `--report-dir X` | *(auto)* | Override report output directory for `--save` |

> **Note:** The `scan` subcommand is auto-inserted if omitted. Some scanners accept additional flags (e.g., `--cross-ref` for polymarket). Run `<market-type> --help` for the full flag list.

### Examples

```bash
python scripts/scan.py sports --filter mlb --date today --save
python scripts/scan.py sports --filter nba --category total --date tomorrow
python scripts/scan.py futures --filter nba-futures --top 10
python scripts/scan.py prediction --filter crypto --cross-ref
python scripts/scan.py polymarket --filter crypto --min-edge 0.05
```

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
# 4. Scan sports (preview only -- no money risked)
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
# 11. Settle completed bets
python scripts/kalshi/kalshi_settler.py settle

# 12. Generate report (console + save to file)
python scripts/kalshi/kalshi_settler.py report --detail --save

# 13. Reconcile local log vs Kalshi API
python scripts/kalshi/kalshi_settler.py reconcile
```

---

## Script Reference

Each script has a dedicated doc with full flag tables, examples, methodology, and output format.

### Scanners

| Script | Purpose | Docs |
|--------|---------|------|
| `edge_detector.py` | Sports edge detection (NBA, MLB, NHL, NFL, NCAA, etc.) | [edge_detector.md](scripts/edge_detector.md) |
| `futures_edge.py` | Championship & season-long futures | [futures_edge.md](scripts/futures_edge.md) |
| `prediction_scanner.py` | Crypto, weather, S&P 500, politics | [prediction_scanner.md](scripts/prediction_scanner.md) |
| `polymarket_edge.py` | Polymarket cross-reference edge | [polymarket_edge.md](scripts/polymarket_edge.md) |

### Execution & Portfolio

| Script | Purpose | Docs |
|--------|---------|------|
| `kalshi_executor.py` | Portfolio status + execution library | [kalshi_executor.md](scripts/kalshi_executor.md) |
| `kalshi_settler.py` | Settlement, P&L reporting, reconciliation | [kalshi_settler.md](scripts/kalshi_settler.md) |
| `risk_check.py` | Portfolio risk dashboard & limits gating | [risk_check.md](scripts/risk_check.md) |

---

## Utility Scripts

### kalshi_client.py -- API Client CLI

**Location:** `scripts/kalshi/kalshi_client.py`

Low-level API queries for debugging and checking raw market data.

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

### fetch_odds.py -- Odds API Explorer

**Location:** `scripts/kalshi/fetch_odds.py`

Explore raw sportsbook odds without running edge detection.

```bash
python scripts/kalshi/fetch_odds.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--market SPORT` | `nba` | `nba`, `nfl`, `mlb`, `nhl`, `ncaafb`, `ncaabb`, `soccer`, `mma`, `all` |
| `--min-edge N` | from .env | Minimum edge threshold |
| `--dry-run` | off | Print results without saving |
| `--save` | off | Save opportunities to watchlist |

### fetch_market_data.py -- Market Data Fetcher

**Location:** `scripts/kalshi/fetch_market_data.py`

Pull market data for stocks, crypto, or prediction markets.

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

### daily_sports_scan.py -- Daily Morning Report

**Location:** `scripts/schedulers/automation/daily_sports_scan.py`

Generate a morning edge report scanning MLB, NBA, NHL, and NFL.

```bash
python scripts/schedulers/automation/daily_sports_scan.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--top N` | `25` | Number of top opportunities to include |
| `--daemon` | off | Run as background daemon -- scans at 8:00 AM PST daily |

**Output:** Report saved to `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md`.

### install_windows_task.py -- Windows Task Scheduler Setup

**Location:** `scripts/schedulers/automation/install_windows_task.py`

```bash
python scripts/schedulers/automation/install_windows_task.py install   # Create the task
python scripts/schedulers/automation/install_windows_task.py status    # Check if installed
python scripts/schedulers/automation/install_windows_task.py run       # Trigger now (test)
python scripts/schedulers/automation/install_windows_task.py remove    # Remove the task
```

---

## Scheduling Your Own Scans

For recurring scans (e.g., MLB every morning, NBA every evening), use Windows Task Scheduler or cron directly with `scan.py`:

```bash
# MLB daily scan at 10 AM -- finds edge, skips open positions, executes up to 10 bets
python scripts/scan.py sports --filter mlb --unit-size 1 --max-bets 10 --exclude-open --save --execute

# NBA daily scan at 6 PM
python scripts/scan.py sports --filter nba --unit-size 1 --max-bets 10 --exclude-open --save --execute

# Settle results at 11 PM
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail --save
```

To set these up in Windows Task Scheduler, use `schtasks`:

```bash
# MLB morning scan at 10 AM daily
schtasks /Create /TN "Edge-Radar\MLB-Scan" /TR "\".venv\Scripts\python.exe\" \"scripts\scan.py\" sports --filter mlb --unit-size 1 --max-bets 10 --exclude-open --save --execute" /SC DAILY /ST 10:00

# NBA evening scan at 6 PM daily
schtasks /Create /TN "Edge-Radar\NBA-Scan" /TR "\".venv\Scripts\python.exe\" \"scripts\scan.py\" sports --filter nba --unit-size 1 --max-bets 10 --exclude-open --save --execute" /SC DAILY /ST 18:00
```
