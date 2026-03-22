---
name: kalshi-bet
description: Place bets on Kalshi prediction markets. Use when the user wants to scan for opportunities and execute bets on a specific sport (nba, ncaamb, nhl, mlb, esports) or across all markets. Handles the full pipeline -- scan, preview, execute, settle, and report.
argument-hint: <sport> [--max-bets N] [--unit-size $X] [--min-edge 0.05] [--settle] [--status]
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
| `nba`, `ncaamb`, `nhl`, `mlb`, `esports` | Scan and bet on that sport |
| `all` or no sport specified | Scan all markets |
| `--max-bets N` | Limit number of bets (default: 5) |
| `--unit-size X` | Dollar amount per bet (default: 1.00) |
| `--min-edge X` | Minimum edge threshold (default: 0.03) |
| `--execute` or `--go` | Skip preview, execute immediately |
| `--dry-run` | Force preview only, never execute |

## Working Directory

All scripts must be run from the project root:
```
cd /path/to/Finance_Agent_Pro  # run from repo root
```

## Action: Status

If the user requested status:

```bash
python scripts/kalshi/kalshi_executor.py status
```

Report the balance, open positions, and today's activity. Done.

## Action: Settle

If the user requested settlement:

```bash
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail
```

Summarize: wins, losses, net P&L, ROI, and highlight best/worst bets. Done.

## Action: Scan & Bet

### Step 1: Check Status First

Always start by checking current state:

```bash
python scripts/kalshi/kalshi_executor.py status
```

If the daily loss limit is breached, **STOP** and inform the user. No betting today.

### Step 2: Preview Scan

Build the scan command from the parsed arguments:

```bash
python scripts/kalshi/kalshi_executor.py run \
  [--filter <sport>] \
  [--min-edge <threshold>] \
  [--unit-size <amount>] \
  [--max-bets <N>] \
  [--top <N>]
```

**Examples:**
- `/kalshi-bet nba` -> `python scripts/kalshi/kalshi_executor.py run --filter nba`
- `/kalshi-bet ncaamb --min-edge 0.05` -> `python scripts/kalshi/kalshi_executor.py run --filter ncaamb --min-edge 0.05`
- `/kalshi-bet all --unit-size 3` -> `python scripts/kalshi/kalshi_executor.py run --unit-size 3`

Run the command. This is preview-only (no `--execute` flag).

### Step 3: Present Results

Show the user the opportunity table from the scan output. Briefly explain:
- How many opportunities were found
- Total estimated cost if all are executed
- The top 2-3 bets and why they have edge (in plain language)

### Step 4: Get Confirmation

Unless `--execute` or `--go` was passed in the arguments, **ask the user to confirm** before placing real orders:

> "Ready to execute X bets for ~$Y total. Go ahead?"

### Step 5: Execute

Once confirmed (or if `--execute`/`--go` was in arguments), re-run with `--execute`:

```bash
python scripts/kalshi/kalshi_executor.py run \
  --execute \
  [--filter <sport>] \
  [--min-edge <threshold>] \
  [--unit-size <amount>] \
  [--max-bets <N>]
```

### Step 6: Report

After execution, summarize:
- Number of orders placed
- Total cost
- Updated balance
- Reminder to run `/kalshi-bet settle` after events complete

## Sport Filter Reference

**US Major Leagues**

| Filter | Sport |
|--------|-------|
| `nba` | NBA -- games, spreads, totals, player props, awards |
| `nhl` | NHL -- games, spreads, totals, player props, awards |
| `mlb` | MLB -- games, playoffs |
| `nfl` | NFL -- games, spreads, totals, draft *(seasonal)* |

**College Sports**

| Filter | Sport |
|--------|-------|
| `ncaamb` | NCAA Men's Basketball -- games, spreads, totals, MOP |
| `ncaabb` | NCAA Basketball (additional) -- games |
| `ncaawb` | NCAA Women's Basketball -- games |
| `ncaafb` | NCAA Football -- games *(seasonal)* |

**Soccer**

| Filter | Sport |
|--------|-------|
| `soccer` | All soccer leagues combined |
| `mls` | MLS -- games, spreads, totals |
| `ucl` | Champions League | `epl` | Premier League |
| `laliga` | La Liga | `seriea` | Serie A |
| `bundesliga` | Bundesliga | `ligue1` | Ligue 1 |

**Combat Sports / Motorsports / Other**

| Filter | Sport |
|--------|-------|
| `ufc` | UFC/MMA fights | `boxing` | Boxing fights |
| `f1` | Formula 1 | `nascar` | NASCAR |
| `pga` | PGA Golf | `ipl` | IPL Cricket |

**Esports**

| Filter | Sport |
|--------|-------|
| `cs2` | Counter-Strike 2 | `lol` | League of Legends |
| `esports` | All esports combined |

## Risk Limits (Current)

- Max bet: $5 per position
- Unit size: $1.00 default
- Daily loss limit: $250
- Max open positions: 10
- Minimum edge: 3%
- Minimum composite score: 6.0

## Edge Detector (Standalone Research)

If the user just wants to research without the execution pipeline:

```bash
python scripts/kalshi/edge_detector.py scan [--filter <sport>] [--category <type>] [--min-edge <X>] [--top <N>] [--save]
```

Categories: `game`, `spread`, `total`, `player_prop`, `esports`

```bash
# Deep dive on a specific market
python scripts/kalshi/edge_detector.py detail <TICKER>
```
