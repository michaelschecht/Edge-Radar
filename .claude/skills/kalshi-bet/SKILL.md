---
name: kalshi-bet
description: Place bets on Kalshi markets -- sports, futures, and prediction markets. Handles scan, preview, execute, settle, reconcile, and status. Supports all sports, championship futures (NFL Super Bowl, NBA/NHL conference, MLB, golf), and prediction markets (crypto, weather, S&P 500, mentions, politics).
argument-hint: <sport|futures|prediction> [--max-bets N] [--unit-size $X] [--min-edge 0.05] [--settle] [--status]
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep
---

# Kalshi Bet Skill

You are executing the `/kalshi-bet` skill. Follow these steps precisely.

## Parse Arguments

Arguments: `$ARGUMENTS`

Parse the arguments to determine the action:

| Argument | Meaning |
|----------|---------|
| `status` or `--status` | Show portfolio status only |
| `settle` or `--settle` | Settle completed bets and show report |
| `reconcile` | Compare local log vs Kalshi API |
| **Sports:** `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, `ncaawb`, `ncaafb`, `mls`, `soccer`, `ufc`, `boxing`, `esports` | Scan and bet on that sport |
| **Futures:** `futures`, `nfl-futures`, `superbowl`, `nba-futures`, `nhl-futures`, `mlb-futures`, `golf-futures`, `ncaab-futures` | Scan futures/championship markets |
| **Prediction:** `crypto`, `btc`, `eth`, `weather`, `spx`, `mentions`, `companies`, `politics`, `techscience` | Scan prediction markets |
| `all` or no filter specified | Scan all sports markets |
| `--max-bets N` | Limit number of bets (default: 5) |
| `--unit-size X` | Dollar amount per bet (default: 1.00) |
| `--min-edge X` | Minimum edge threshold (default: 0.03) |
| `--execute` or `--go` | Skip preview, execute immediately |
| `--dry-run` | Force preview only, never execute |

## Action: Status

```bash
python scripts/kalshi/kalshi_executor.py status
```

Report the balance, open positions, and today's activity. Done.

## Action: Settle

```bash
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail
```

Summarize: wins, losses, net P&L, ROI, and highlight best/worst bets. Done.

## Action: Reconcile

```bash
python scripts/kalshi/kalshi_settler.py reconcile
```

Report any discrepancies between local trade log and Kalshi API positions. Done.

## Action: Scan & Bet

### Step 1: Check Status First

```bash
python scripts/kalshi/kalshi_executor.py status
```

If the daily loss limit is breached, **STOP** and inform the user. No betting today.

### Step 2: Determine Scan Type and Build Command

**Sports (game betting):**
```bash
python scripts/kalshi/kalshi_executor.py run \
  [--filter <sport>] \
  [--min-edge <threshold>] \
  [--unit-size <amount>] \
  [--max-bets <N>]
```

**Futures (championships, season-long):**
```bash
python scripts/kalshi/futures_edge.py scan \
  [--filter <sport>-futures] \
  [--min-edge <threshold>] \
  [--top <N>]
```

**Prediction markets (crypto, weather, S&P 500, mentions, politics, etc.):**
```bash
python scripts/prediction/prediction_scanner.py scan \
  [--filter <category>] \
  [--min-edge <threshold>] \
  [--top <N>]
```

Or use the unified executor with `--prediction`:
```bash
python scripts/kalshi/kalshi_executor.py run \
  --prediction \
  [--filter <category>] \
  [--min-edge <threshold>] \
  [--max-bets <N>]
```

**Routing examples:**
- `/kalshi-bet nba` -> `python scripts/kalshi/kalshi_executor.py run --filter nba`
- `/kalshi-bet nfl-futures` -> `python scripts/kalshi/futures_edge.py scan --filter nfl-futures`
- `/kalshi-bet superbowl` -> `python scripts/kalshi/futures_edge.py scan --filter nfl-futures`
- `/kalshi-bet crypto` -> `python scripts/prediction/prediction_scanner.py scan --filter crypto`
- `/kalshi-bet weather --min-edge 0.05` -> `python scripts/prediction/prediction_scanner.py scan --filter weather --min-edge 0.05`
- `/kalshi-bet all --unit-size 3` -> `python scripts/kalshi/kalshi_executor.py run --unit-size 3`

Run the command. This is preview-only first.

### Step 3: Present Results

Show the user the opportunity table from the scan output. Briefly explain:
- How many opportunities were found
- Total estimated cost if all are executed
- The top 2-3 bets and why they have edge (in plain language)
- For futures: note that capital is tied up for weeks/months

### Step 4: Get Confirmation

Unless `--execute` or `--go` was passed in the arguments, **ask the user to confirm** before placing real orders:

> "Ready to execute X bets for ~$Y total. Go ahead?"

### Step 5: Execute

Once confirmed (or if `--execute`/`--go` was in arguments):

**Sports:**
```bash
python scripts/kalshi/kalshi_executor.py run --execute \
  [--filter <sport>] [--min-edge <X>] [--unit-size <X>] [--max-bets <N>]
```

**Futures:**
```bash
python scripts/kalshi/kalshi_executor.py run --filter <sport>-futures --execute --max-bets <N>
```

**Prediction:**
```bash
python scripts/kalshi/kalshi_executor.py run --prediction --filter <category> --execute --max-bets <N>
```

### Step 6: Report

After execution, summarize:
- Number of orders placed
- Total cost
- Updated balance
- Reminder to run `/kalshi-bet settle` after events complete

## Filter Quick Reference

**Sports (game betting):** `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, `ncaabb`, `ncaawb`, `ncaafb`, `mls`, `soccer`, `ucl`, `epl`, `laliga`, `seriea`, `bundesliga`, `ligue1`, `ufc`, `boxing`, `f1`, `nascar`, `pga`, `ipl`, `cs2`, `lol`, `esports`

**Futures:** `futures`, `nfl-futures`, `superbowl`, `nba-futures`, `nhl-futures`, `mlb-futures`, `ncaab-futures`, `golf-futures`

**Prediction:** `crypto`, `btc`, `eth`, `xrp`, `doge`, `sol`, `weather`, `spx`, `sp500`, `mentions`, `lastword`, `nbamention`, `foxnews`, `politicsmention`, `companies`, `bankruptcy`, `ipo`, `politics`, `impeach`, `techscience`, `quantum`, `fusion`

## Risk Limits (Current)

- Max bet: $5 per position
- Unit size: $1.00 default
- Daily loss limit: $250
- Minimum edge: 3%
- Minimum composite score: 6.0

## Standalone Research (No Execution)

```bash
# Sports edge detector
python scripts/kalshi/edge_detector.py scan [--filter <sport>] [--min-edge <X>] [--top <N>] [--save]
python scripts/kalshi/edge_detector.py detail <TICKER>

# Futures scanner
python scripts/kalshi/futures_edge.py scan [--filter <sport>-futures] [--min-edge <X>] [--top <N>]

# Prediction scanner
python scripts/prediction/prediction_scanner.py scan [--filter <category>] [--min-edge <X>] [--top <N>] [--save]
```
