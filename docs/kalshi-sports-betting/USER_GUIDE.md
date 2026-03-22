# Kalshi Wagering System -- User Guide

---

## Quick Start

```bash
# 1. Check your balance
python scripts/kalshi/kalshi_executor.py status

# 2. Scan for opportunities (preview only, no orders placed)
python scripts/kalshi/kalshi_executor.py run

# 3. Execute top opportunities
python scripts/kalshi/kalshi_executor.py run --execute --max-bets 5

# 4. After games resolve, settle and check results
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report
```

---

## Prerequisites

Before first run, verify these are in place:

1. **Python virtual environment** -- activate with `.venv\Scripts\activate` (Windows)
2. **`.env` file** -- must contain (see `.env.example` for full template):
   ```env
   KALSHI_API_KEY=<your-key-id>
   KALSHI_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
   KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
   ODDS_API_KEY=<your-odds-api-key>
   DRY_RUN=false
   ```
3. **API keys** -- RSA private key in `keys/live/`
4. **Dependencies** -- `requests`, `cryptography`, `python-dotenv`, `rich`

---

## Daily Workflow

### Morning: Scan and Execute

```bash
# Preview what the system would bet on
python scripts/kalshi/kalshi_executor.py run

# Review the output, then execute
python scripts/kalshi/kalshi_executor.py run --execute --max-bets 5
```

The system will:
- Pull all open Kalshi markets (~5000)
- Fetch sportsbook odds from The Odds API
- Calculate fair value for each market
- Filter to opportunities with edge >= 3%
- Size bets using quarter-Kelly
- Show a preview table, then place orders if `--execute` is passed

### During the Day: Monitor

```bash
# Portfolio dashboard
python scripts/kalshi/kalshi_executor.py status
```

Shows: balance, open positions, resting orders, today's wagering activity.

### Evening: Settle and Review

```bash
# Check for resolved markets and update P&L
python scripts/kalshi/kalshi_settler.py settle

# View performance
python scripts/kalshi/kalshi_settler.py report
python scripts/kalshi/kalshi_settler.py report --detail
```

---

## Command Reference

### Edge Detector (`scripts/kalshi/edge_detector.py`)

Scans Kalshi markets and scores them against sportsbook consensus.

```bash
# Full scan, show top 20 opportunities
python scripts/kalshi/edge_detector.py scan

# Raise minimum edge to 5%
python scripts/kalshi/edge_detector.py scan --min-edge 0.05

# Only game outcome markets
python scripts/kalshi/edge_detector.py scan --category game

# Save results to watchlist file
python scripts/kalshi/edge_detector.py scan --save

# Deep dive on a single market
python scripts/kalshi/edge_detector.py detail KXNBAGAME-26MAR20ATLHOU-ATL
```

**Categories:** `game`, `spread`, `total`, `player_prop`, `esports`, `other`

### Executor (`scripts/kalshi/kalshi_executor.py`)

Runs the full pipeline: scan, risk-check, size, execute.

```bash
# Preview mode (safe, no orders)
python scripts/kalshi/kalshi_executor.py run

# Execute with fresh scan
python scripts/kalshi/kalshi_executor.py run --execute

# Execute from last saved scan (skips Odds API call)
python scripts/kalshi/kalshi_executor.py run --from-file --execute

# Limit to 3 bets per run
python scripts/kalshi/kalshi_executor.py run --execute --max-bets 3

# Higher edge threshold
python scripts/kalshi/kalshi_executor.py run --execute --min-edge 0.05

# Filter to a specific sport (see Filtering section below)
python scripts/kalshi/kalshi_executor.py run --filter ncaamb --execute

# Portfolio status
python scripts/kalshi/kalshi_executor.py status
```

### Settlement Tracker (`scripts/kalshi/kalshi_settler.py`)

Resolves settled positions and tracks P&L.

```bash
# Check for settlements and update trade log
python scripts/kalshi/kalshi_settler.py settle

# Performance summary
python scripts/kalshi/kalshi_settler.py report

# Per-trade breakdown table
python scripts/kalshi/kalshi_settler.py report --detail
```

**Report includes:**
- Win/loss record and win rate
- Net P&L, total wagered, ROI
- Profit factor, best/worst trades
- Edge calibration (estimated vs. realized)
- Breakdowns by confidence level and market category

### Kalshi Client (`scripts/kalshi/kalshi_client.py`)

Direct API access for debugging and exploration.

```bash
python scripts/kalshi/kalshi_client.py balance
python scripts/kalshi/kalshi_client.py markets --limit 50 --status open
python scripts/kalshi/kalshi_client.py positions
python scripts/kalshi/kalshi_client.py orders
python scripts/kalshi/kalshi_client.py market --ticker KXTICKER
```

---

## Filtering by Sport

Use `--filter` on the executor or edge detector to focus on a specific sport. This scans only matching markets and only fetches odds for that sport (saves Odds API quota).

### Named Shortcuts

| Shortcut | What It Matches | Kalshi Ticker Prefixes |
|---|---|---|
| `ncaamb` | NCAA men's basketball (March Madness) | KXNCAAMBGAME, KXNCAAMBSPREAD, KXNCAAMBTOTAL, KXNCAAMBMOP |
| `nba` | NBA games, spreads, totals, blocks | KXNBAGAME, KXNBASPREAD, KXNBATOTAL, KXNBABLK |
| `nhl` | NHL games, spreads, totals, goals, assists, points | KXNHLGAME, KXNHLSPREAD, KXNHLTOTAL, KXNHLGOAL, KXNHLPTS, KXNHLAST, KXNHLFIRSTGOAL |
| `mlb` | MLB games | KXMLBGAME |
| `esports` | CS2 and League of Legends | KXCS2MAP, KXCS2GAME, KXLOLMAP, KXLOLGAME |

### Examples

```bash
# NCAA tournament only -- preview
python scripts/kalshi/kalshi_executor.py run --filter ncaamb

# NCAA tournament only -- execute
python scripts/kalshi/kalshi_executor.py run --filter ncaamb --execute --max-bets 5

# NBA only
python scripts/kalshi/kalshi_executor.py run --filter nba --execute

# NHL only with higher edge bar
python scripts/kalshi/kalshi_executor.py run --filter nhl --min-edge 0.05

# Edge detector scan with filter
python scripts/kalshi/edge_detector.py scan --filter ncaamb
python scripts/kalshi/edge_detector.py scan --filter nba --save
```

### Raw Ticker Prefix

You can also pass any raw Kalshi ticker prefix to filter on markets that don't have a named shortcut:

```bash
# Weather markets for NYC
python scripts/kalshi/edge_detector.py scan --filter KXHIGHNY

# S&P 500 markets
python scripts/kalshi/edge_detector.py scan --filter KXINX

# All NCAA men's markets (basketball + wrestling + lacrosse)
python scripts/kalshi/edge_detector.py scan --filter KXNCAAM
```

Note: edge detection only works for market types that have an external odds source mapped. Currently that's game outcomes, spreads, and totals for NBA, NHL, MLB, and NCAAB.

---

## How Edge Detection Works

The system estimates "fair value" for Kalshi markets by cross-referencing sportsbook odds:

1. **Fetch** odds from 8-12 US sportsbooks (FanDuel, DraftKings, BetMGM, etc.) via The Odds API
2. **De-vig** each book's line to remove the house edge and extract true implied probability
3. **Median** across all books gives a robust consensus fair value
4. **Compare** to Kalshi's current ask price
5. **Edge** = fair value - market price

If Kalshi prices a team at $0.41 but sportsbooks consensus says 73% fair value, that's a 32-cent edge.

### Supported Market Types

| Type | Method | Accuracy |
|---|---|---|
| Game outcomes (moneyline) | Median de-vigged h2h odds | High -- direct comparison |
| Spreads | Adjusted from book spread lines | Medium -- linear approximation |
| Totals (over/under) | Adjusted from book total lines | Medium -- linear approximation |
| Player props | Not yet implemented | -- |
| Weather, economics | Not yet implemented | -- |

---

## Risk Management

Every order passes through these gates before execution:

| Gate | Rule | Configurable Via |
|---|---|---|
| Daily loss limit | Stop all betting if daily P&L <= -$250 | `MAX_DAILY_LOSS` |
| Position limit | Max 10 concurrent open positions | `MAX_OPEN_POSITIONS` |
| Minimum edge | Only bet if edge >= 3% | `MIN_EDGE_THRESHOLD` |
| Minimum score | Composite score must be >= 6.0 | `MIN_COMPOSITE_SCORE` |
| Confidence | Must be "medium" or "high" | `MIN_CONFIDENCE` |

### Bet Sizing: Fixed Unit

Every bet targets a fixed dollar amount (the "unit size"). The number of contracts is calculated to get as close to that amount as possible.

**Default unit size: $1.00** (set via `UNIT_SIZE` in `.env`)

| Contract Price | Contracts | Actual Cost |
|---|---|---|
| $0.02 | 50 | $1.00 |
| $0.05 | 20 | $1.00 |
| $0.13 | 8 | $1.04 |
| $0.25 | 4 | $1.00 |
| $0.50 | 2 | $1.00 |
| $0.76 | 1 | $0.76 |

Override per run with `--unit-size`:

```bash
# $1 bets (default)
python scripts/kalshi/kalshi_executor.py run --execute

# $5 bets
python scripts/kalshi/kalshi_executor.py run --execute --unit-size 5

# $0.50 bets
python scripts/kalshi/kalshi_executor.py run --execute --unit-size 0.50
```

---

## Configuration

All configurable parameters are in `.env`:

```env
# --- Kalshi Connection ---
KALSHI_API_KEY=<key-id>
KALSHI_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2

# --- External Data ---
ODDS_API_KEY=<odds-api-key>

# --- Risk Limits ---
UNIT_SIZE=1.00                      # Fixed dollar amount per bet
MAX_BET_SIZE_PREDICTION=5           # Hard cap per single bet
MAX_DAILY_LOSS=250                  # Hard stop for the day
MAX_OPEN_POSITIONS=10               # Max concurrent positions
MIN_EDGE_THRESHOLD=0.03             # 3% minimum edge
MIN_COMPOSITE_SCORE=6.0             # Minimum opportunity score
MIN_CONFIDENCE=medium               # low, medium, or high

# --- System ---
DRY_RUN=false                       # Set to true to block live orders
LOG_LEVEL=INFO
```

---

## File Structure

```
scripts/
  kalshi/                         # Kalshi betting scripts
    kalshi_client.py              # Authenticated Kalshi API client
    edge_detector.py              # Market scanning and edge detection
    kalshi_executor.py            # Risk management and order execution
    kalshi_settler.py             # Settlement tracking and P&L reporting
    fetch_odds.py                 # The Odds API integration
    fetch_market_data.py          # Multi-asset market data fetcher
    risk_check.py                 # Portfolio risk dashboard

data/
  watchlists/
    kalshi_opportunities.json     # Latest scored opportunities
  history/
    kalshi_trades.json            # Trade log (all orders placed)
    kalshi_settlements.json       # Settlement history with P&L

keys/
  live/kalshi_private.key         # Production RSA key (never commit)

docs/
  kalshi-sports-betting/
    USER_GUIDE.md                 # This file
    BETTING_GUIDE.md              # Sport-by-sport commands & filters
    KALSHI_STRATEGY_PLAN.md       # System architecture and roadmap
    KALSHI_API_REFERENCE.md       # Kalshi API endpoints and auth
  kalshi-prediction-betting/
    PREDICTION_MARKETS_GUIDE.md   # Economics, crypto, weather, politics
  CHANGELOG.md                    # What was built and when
```

---

## Production Status

The system is configured for **live trading** on Kalshi's production API.

Current risk settings:
- `MAX_BET_SIZE_PREDICTION=5` (max $5 per bet)
- `UNIT_SIZE=1.00` (default $1 per bet)
- `DRY_RUN=false`

To revert to dry-run mode, set `DRY_RUN=true` in `.env`.

---

## Troubleshooting

**"Kalshi private key not found"**
- Check that `KALSHI_PRIVATE_KEY_PATH` in `.env` points to an existing `.key` file
- Path is relative to project root

**"Rate limited"**
- Basic tier allows 20 reads/sec and 10 writes/sec
- The scanner fetches up to 5 pages of 1000 markets -- stay under limits
- Add delays between runs if hitting limits

**"ODDS_API_KEY not set"**
- Edge detection requires a key from https://the-odds-api.com (free tier: 500 req/month)
- Without it, the scanner runs but finds no opportunities

**Orders show "resting" instead of "executed"**
- Limit order didn't find a match at your price
- The order stays open until filled, cancelled, or the market closes
- Check resting orders: `python scripts/kalshi/kalshi_executor.py status`

**Settlement shows 0 settled**
- Markets haven't resolved yet -- check `expected_expiration_time` on the market
- Run `settle` again after game/event completes
