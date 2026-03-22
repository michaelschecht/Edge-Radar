# Kalshi Betting Guide

Complete reference for placing bets, filtering by sport, managing positions, and understanding how the system finds and sizes opportunities.

---

## Table of Contents

- [Quick Reference](#quick-reference)
- [Betting by Sport](#betting-by-sport)
- [All Sport Filters](#all-sport-filters)
- [Market Categories](#market-categories)
- [Placing Bets](#placing-bets)
- [Bet Sizing](#bet-sizing)
- [Risk Gates](#risk-gates)
- [Monitoring Positions](#monitoring-positions)
- [Settling Bets & Checking Results](#settling-bets--checking-results)
- [Edge Detection Explained](#edge-detection-explained)
- [Advanced Usage](#advanced-usage)
- [Environment Variables Reference](#environment-variables-reference)
- [Examples: Full Session Walkthrough](#examples-full-session-walkthrough)

---

## Quick Reference

```bash
# Preview opportunities (no money risked)
python scripts/kalshi_executor.py run

# Place up to 5 bets
python scripts/kalshi_executor.py run --execute --max-bets 5

# Bet on a specific sport
python scripts/kalshi_executor.py run --filter nba --execute --max-bets 5

# Check your portfolio
python scripts/kalshi_executor.py status

# Settle completed bets and see results
python scripts/kalshi_settler.py settle
python scripts/kalshi_settler.py report
```

---

## Betting by Sport

Use the `--filter` flag to target a specific sport. This limits the market scan and only fetches odds for that sport (saves Odds API quota).

### NBA

```bash
python scripts/kalshi_executor.py run --filter nba                          # Preview
python scripts/kalshi_executor.py run --filter nba --execute --max-bets 5   # Execute
python scripts/edge_detector.py scan --filter nba                           # Research only
```

**Markets:** Game winners, point spreads, totals, player props (3-pointers, rebounds, assists, steals, points, blocks), MVP, Rookie of the Year, Defensive Player of the Year.

### NHL

```bash
python scripts/kalshi_executor.py run --filter nhl                          # Preview
python scripts/kalshi_executor.py run --filter nhl --execute --max-bets 3   # Execute
```

**Markets:** Game winners, spreads, totals, player props (goals, assists, points, first goal scorer), Hart Trophy, Norris Trophy, Calder Trophy.

### MLB

```bash
python scripts/kalshi_executor.py run --filter mlb                          # Preview
python scripts/kalshi_executor.py run --filter mlb --execute --max-bets 5   # Execute
```

**Markets:** Game winners (moneyline), playoff qualifiers.

### NFL

```bash
python scripts/kalshi_executor.py run --filter nfl                          # Preview
python scripts/kalshi_executor.py run --filter nfl --execute --max-bets 5   # Execute
```

**Markets:** Game winners, spreads, totals, draft. *(Seasonal -- active Aug through Feb.)*

### NCAA Men's Basketball (March Madness)

```bash
python scripts/kalshi_executor.py run --filter ncaamb                          # Preview
python scripts/kalshi_executor.py run --filter ncaamb --execute --max-bets 5   # Execute
python scripts/edge_detector.py scan --filter ncaamb --save                    # Save to watchlist
```

**Markets:** Game winners, point spreads, totals, Most Outstanding Player.

### NCAA Women's Basketball

```bash
python scripts/kalshi_executor.py run --filter ncaawb                          # Preview
python scripts/kalshi_executor.py run --filter ncaawb --execute --max-bets 5   # Execute
```

**Markets:** Game winners.

### NCAA Football

```bash
python scripts/kalshi_executor.py run --filter ncaafb                          # Preview
python scripts/kalshi_executor.py run --filter ncaafb --execute --max-bets 5   # Execute
```

**Markets:** Game winners. *(Seasonal -- active Aug through Jan.)*

### MLS (Major League Soccer)

```bash
python scripts/kalshi_executor.py run --filter mls                          # Preview
python scripts/kalshi_executor.py run --filter mls --execute --max-bets 3   # Execute
```

**Markets:** Game winners, spreads, totals.

### European Soccer (Individual Leagues)

```bash
python scripts/kalshi_executor.py run --filter soccer     # ALL soccer leagues combined
python scripts/kalshi_executor.py run --filter ucl         # Champions League
python scripts/kalshi_executor.py run --filter epl         # Premier League
python scripts/kalshi_executor.py run --filter laliga      # La Liga (Spain)
python scripts/kalshi_executor.py run --filter seriea      # Serie A (Italy)
python scripts/kalshi_executor.py run --filter bundesliga  # Bundesliga (Germany)
python scripts/kalshi_executor.py run --filter ligue1      # Ligue 1 (France)
```

**Markets:** Outright league/tournament winners.

### UFC / MMA

```bash
python scripts/kalshi_executor.py run --filter ufc                          # Preview
python scripts/kalshi_executor.py run --filter ufc --execute --max-bets 3   # Execute
```

**Markets:** Fight winners.

### Boxing

```bash
python scripts/kalshi_executor.py run --filter boxing                          # Preview
python scripts/kalshi_executor.py run --filter boxing --execute --max-bets 3   # Execute
```

**Markets:** Fight winners.

### Formula 1

```bash
python scripts/kalshi_executor.py run --filter f1                          # Preview
python scripts/kalshi_executor.py run --filter f1 --execute --max-bets 3   # Execute
```

**Markets:** Drivers championship, constructors championship.

### NASCAR

```bash
python scripts/kalshi_executor.py run --filter nascar                          # Preview
python scripts/kalshi_executor.py run --filter nascar --execute --max-bets 3   # Execute
```

**Markets:** Individual race winners.

### PGA Golf

```bash
python scripts/kalshi_executor.py run --filter pga                          # Preview
python scripts/kalshi_executor.py run --filter pga --execute --max-bets 3   # Execute
```

**Markets:** Tournament winners.

### IPL Cricket

```bash
python scripts/kalshi_executor.py run --filter ipl                          # Preview
python scripts/kalshi_executor.py run --filter ipl --execute --max-bets 3   # Execute
```

**Markets:** Outright winner.

### Esports

```bash
python scripts/kalshi_executor.py run --filter esports   # All esports
python scripts/kalshi_executor.py run --filter cs2       # Counter-Strike 2 only
python scripts/kalshi_executor.py run --filter lol       # League of Legends only
```

**Markets:** Map winners, match winners.

---

## All Sport Filters

### Complete Filter Reference

**US Major Leagues**

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `nba` | NBA Basketball | Games, spreads, totals, player props, MVP, ROY, DPOY | Yes -- game, spread, total |
| `nhl` | NHL Hockey | Games, spreads, totals, player props, Hart, Norris, Calder | Yes -- game, spread, total |
| `mlb` | MLB Baseball | Games, playoffs | Yes -- game |
| `nfl` | NFL Football | Games, spreads, totals, draft | Yes -- game, spread, total *(seasonal)* |

**College Sports**

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `ncaamb` | NCAA Men's Basketball | Games, spreads, totals, MOP | Yes -- game, spread, total |
| `ncaabb` | NCAA Basketball (additional) | Games | Yes -- game |
| `ncaawb` | NCAA Women's Basketball | Games | No |
| `ncaafb` | NCAA Football | Games | No |

**Soccer / Football**

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `soccer` | All soccer (combined) | All leagues below | No |
| `mls` | MLS | Games, spreads, totals | No |
| `ucl` | Champions League | Outright winner | No |
| `epl` | English Premier League | Outright winner | No |
| `laliga` | La Liga | Outright winner | No |
| `seriea` | Serie A | Outright winner | No |
| `bundesliga` | Bundesliga | Outright winner | No |
| `ligue1` | Ligue 1 | Outright winner | No |

**Combat Sports**

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `ufc` | UFC / MMA | Fight winners | No |
| `boxing` | Boxing | Fight winners | No |

**Motorsports**

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `f1` | Formula 1 | Drivers + constructors championship | No |
| `nascar` | NASCAR | Race winners | No |

**Other Sports**

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `pga` | PGA Golf | Tournament winners | No |
| `ipl` | IPL Cricket | Outright winner | No |

**Esports**

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `cs2` | Counter-Strike 2 | Map + match winners | No |
| `lol` | League of Legends | Map + match winners | No |
| `esports` | All esports | CS2 + LoL combined | No |

> **Edge Detection = "Yes"** means the system can cross-reference sportsbook odds for calculated edge. **"No"** means markets are browsable and bettable, but edge is estimated from market microstructure only (liquidity, spread analysis).

### Raw Ticker Prefixes

You can also pass any raw Kalshi ticker prefix directly for markets not covered above:

```bash
# NHL player goals only
python scripts/edge_detector.py scan --filter KXNHLGOAL

# NBA 3-pointers only
python scripts/edge_detector.py scan --filter KXNBA3PT

# UFC fights
python scripts/edge_detector.py scan --filter KXUFCFIGHT

# Weather markets
python scripts/edge_detector.py scan --filter KXHIGHNY

# S&P 500 / financial markets
python scripts/edge_detector.py scan --filter KXINX
```

**Note:** Edge detection only works for market types with a mapped external odds source (see table above). Raw prefix filters on unsupported markets will scan but won't find edges.

### Odds API Sport Mapping

The system cross-references Kalshi prices against these Odds API sport keys:

| Kalshi Prefix | Odds API Sport Key | Bet Types Supported |
|---------------|-------------------|---------------------|
| KXNBAGAME | `basketball_nba` | Moneyline (h2h) |
| KXNBASPREAD | `basketball_nba` | Spreads |
| KXNBATOTAL | `basketball_nba` | Totals (over/under) |
| KXNCAAMBGAME | `basketball_ncaab` | Moneyline (h2h) |
| KXNCAAMBSPREAD | `basketball_ncaab` | Spreads |
| KXNCAAMBTOTAL | `basketball_ncaab` | Totals (over/under) |
| KXNHLGAME | `icehockey_nhl` | Moneyline (h2h) |
| KXNHLSPREAD | `icehockey_nhl` | Spreads |
| KXNHLTOTAL | `icehockey_nhl` | Totals (over/under) |
| KXMLBGAME | `baseball_mlb` | Moneyline (h2h) |

---

## Market Categories

Every Kalshi market is classified into a category. You can filter by category using the edge detector:

```bash
python scripts/edge_detector.py scan --category game
python scripts/edge_detector.py scan --category spread
python scripts/edge_detector.py scan --category total
python scripts/edge_detector.py scan --category player_prop
python scripts/edge_detector.py scan --category esports
```

| Category | Description | Example |
|----------|-------------|---------|
| `game` | Who wins the game (moneyline) | "New York to win" |
| `spread` | Win by X points | "Kansas wins by over 9.5 Points" |
| `total` | Over/under total points | "Over 146.5 points scored" |
| `player_prop` | Individual player stats | NHL goals, assists, points, blocks |
| `esports` | CS2 and LoL match/map outcomes | "Team A wins Map 1" |
| `other` | Anything not matched above | Weather, politics, economics |

You can combine `--filter` (sport) with `--category` on the edge detector:

```bash
# Only NBA spread markets
python scripts/edge_detector.py scan --filter nba --category spread

# Only NHL game outcomes
python scripts/edge_detector.py scan --filter nhl --category game
```

---

## Placing Bets

### Preview Mode (Default -- Safe)

Always preview first. This scans markets, finds edges, and shows what it *would* bet on without placing any orders:

```bash
python scripts/kalshi_executor.py run
python scripts/kalshi_executor.py run --filter nba
```

### Execute Mode

Add `--execute` to actually place orders with real money:

```bash
python scripts/kalshi_executor.py run --execute --max-bets 5
```

### From Saved Scan

If you already ran the edge detector and saved results, you can execute from that file instead of re-scanning (saves Odds API calls):

```bash
# Step 1: Scan and save
python scripts/edge_detector.py scan --filter ncaamb --save

# Step 2: Review the saved watchlist
# (located at data/watchlists/kalshi_opportunities.json)

# Step 3: Execute from saved file
python scripts/kalshi_executor.py run --from-file --execute --max-bets 3
```

### Key Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--execute` | off | Actually place orders (without this, preview only) |
| `--max-bets N` | 5 | Maximum number of bets per run |
| `--filter SPORT` | none | Filter by sport shortcut or ticker prefix |
| `--min-edge X` | 0.03 | Minimum edge threshold (e.g., 0.05 = 5%) |
| `--unit-size X` | $1.00 | Dollar amount per bet |
| `--from-file` | off | Use saved watchlist instead of fresh scan |
| `--top N` | 20 | Number of opportunities to evaluate |

---

## Bet Sizing

### Fixed Unit Sizing

Every bet targets a fixed dollar amount (the "unit size"). The system calculates how many contracts to buy to hit that amount:

| Contract Price | Contracts (at $1 unit) | Actual Cost |
|----------------|------------------------|-------------|
| $0.02 | 50 | $1.00 |
| $0.05 | 20 | $1.00 |
| $0.08 | 13 | $1.04 |
| $0.13 | 8 | $1.04 |
| $0.25 | 4 | $1.00 |
| $0.50 | 2 | $1.00 |
| $0.76 | 1 | $0.76 |

### Changing Unit Size

```bash
# Default $1 bets
python scripts/kalshi_executor.py run --execute

# $5 bets
python scripts/kalshi_executor.py run --execute --unit-size 5

# $0.50 bets (micro-sizing)
python scripts/kalshi_executor.py run --execute --unit-size 0.50

# $3 bets on NCAA only
python scripts/kalshi_executor.py run --filter ncaamb --execute --unit-size 3
```

The unit size is also configurable globally via `UNIT_SIZE` in `.env`. The `--unit-size` flag overrides it per run.

### Max Bet Cap

No single bet can exceed `MAX_BET_SIZE_PREDICTION` (default $5, set in `.env`). This is a hard cap regardless of unit size.

---

## Risk Gates

Every bet must pass **all** of these checks before execution. If any gate fails, the bet is rejected:

| # | Gate | Rule | Override |
|---|------|------|----------|
| 1 | Daily loss limit | Stop betting if today's realized P&L <= -$250 | `MAX_DAILY_LOSS` in .env |
| 2 | Position limit | Max 10 open positions at once | `MAX_OPEN_POSITIONS` in .env |
| 3 | Minimum edge | Edge must be >= 3% | `MIN_EDGE_THRESHOLD` in .env or `--min-edge` |
| 4 | Minimum score | Composite score must be >= 6.0 | `MIN_COMPOSITE_SCORE` in .env |
| 5 | Confidence | Must be "medium" or "high" | `MIN_CONFIDENCE` in .env |
| 6 | Bankroll check | Bet cost cannot exceed available balance | Automatic |

When a bet is rejected, the executor shows the reason:

```
SKIP KXNBAGAME-...: REJECTED: edge_below_threshold (2.1% < 3.0%)
SKIP KXNHLGAME-...: REJECTED: confidence_too_low (low < medium)
```

---

## Monitoring Positions

### Portfolio Dashboard

```bash
python scripts/kalshi_executor.py status
```

Shows:
- **Environment** -- DEMO or LIVE
- **Balance** -- available cash
- **Portfolio value** -- total account value including open positions
- **Open positions** -- table with ticker, quantity, exposure, P&L, fees
- **Today's activity** -- number of trades, amount wagered, realized P&L
- **Resting orders** -- limit orders waiting to fill

### Direct API Access

For more granular checks:

```bash
# Account balance
python scripts/kalshi_client.py balance

# All open positions
python scripts/kalshi_client.py positions

# Resting (unfilled) orders
python scripts/kalshi_client.py orders

# Browse open markets
python scripts/kalshi_client.py markets --limit 50 --status open

# Look up a specific market
python scripts/kalshi_client.py market --ticker KXNBAGAME-26MAR22LALBOS-LAL
```

---

## Settling Bets & Checking Results

### Settling

After games/events complete, run the settler to pull results from Kalshi and update your local trade log:

```bash
python scripts/kalshi_settler.py settle
```

This checks each open trade against the Kalshi API, determines if the market has resolved, and updates `net_pnl` and `closed_at` in `data/history/kalshi_trades.json`.

### Performance Report

```bash
# Summary stats
python scripts/kalshi_settler.py report

# Per-trade breakdown
python scripts/kalshi_settler.py report --detail
```

**Report includes:**
- Win/loss record and win rate
- Net P&L, total wagered, ROI
- Profit factor (gross wins / gross losses)
- Best and worst trades
- Edge calibration (estimated edge vs. realized edge)
- Breakdown by confidence level and market category

### When Do Markets Settle?

| Market Type | Typical Settlement Time |
|-------------|------------------------|
| NBA / NCAA game outcomes | Minutes to ~1 hour after final score |
| Spreads and totals | Same as game outcomes |
| NHL games | Minutes to ~1 hour after final |
| MLB games | Minutes to ~1 hour after final |
| Player props | Usually within a few hours |
| Esports | Varies, usually within hours |

Kalshi settles automatically once the outcome is confirmed. Your local log only updates when you run `settle`.

---

## Edge Detection Explained

### How It Works

1. **Fetch** odds from 8-12 US sportsbooks (FanDuel, DraftKings, BetMGM, Caesars, etc.) via The Odds API
2. **De-vig** each book's line to remove the house edge, extracting true implied probability
3. **Median** across all books gives a robust consensus fair value
4. **Compare** to Kalshi's current ask price
5. **Edge** = fair value - market price

**Example:** Kalshi prices a team at $0.41, but sportsbook consensus says 73% fair value = **32-cent edge**.

### Edge Detection by Market Type

| Type | Method | Reliability |
|------|--------|-------------|
| Game outcomes (moneyline) | Median de-vigged h2h odds | High -- direct 1:1 comparison |
| Spreads | Adjusted from book spread lines | Medium -- linear approximation of probability curve |
| Totals (over/under) | Adjusted from book total lines | Medium -- linear approximation |
| Player props | Not yet implemented | -- |
| Esports | Not yet implemented | -- |
| Weather / politics / economics | Not yet implemented | -- |

### Composite Score

Each opportunity gets a composite score (0-10) combining:
- Edge magnitude
- Confidence level
- Liquidity (bid/ask spread + volume)

Only opportunities with score >= 6.0 are eligible for execution.

### Deep Dive on a Single Market

```bash
python scripts/edge_detector.py detail KXNBAGAME-26MAR22LALBOS-LAL
```

Shows the full breakdown: matched sportsbook odds, de-vigged probabilities, calculated fair value, and edge.

---

## Advanced Usage

### Raising the Edge Bar

For more selective betting (fewer bets, higher conviction):

```bash
# Only bet when edge >= 5%
python scripts/kalshi_executor.py run --execute --min-edge 0.05

# Only bet when edge >= 10% (very selective)
python scripts/kalshi_executor.py run --execute --min-edge 0.10
```

### Combining Filters

```bash
# NBA spreads only, 5% minimum edge, $3 bets
python scripts/edge_detector.py scan --filter nba --category spread --min-edge 0.05

# Then execute from that saved scan
python scripts/edge_detector.py scan --filter nba --category spread --min-edge 0.05 --save
python scripts/kalshi_executor.py run --from-file --execute --unit-size 3
```

### Scanning Without Betting

Use the edge detector standalone to research without risking anything:

```bash
# What does the system see right now?
python scripts/edge_detector.py scan

# Save to file for later review
python scripts/edge_detector.py scan --save

# Top 50 opportunities across all sports
python scripts/edge_detector.py scan --top 50
```

---

## Environment Variables Reference

All configurable in `.env`:

```env
# --- Connection ---
KALSHI_API_KEY=<key-id>
KALSHI_PRIVATE_KEY_PATH=\keys\live\kalshi_private.key
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2

# --- External Data ---
ODDS_API_KEY=<odds-api-key>

# --- Bet Sizing ---
UNIT_SIZE=1.00                  # Default dollar amount per bet
MAX_BET_SIZE_PREDICTION=5       # Hard cap per single bet

# --- Risk Limits ---
MAX_DAILY_LOSS=250              # Stop all betting if daily P&L hits this
MAX_OPEN_POSITIONS=10           # Max concurrent positions
MIN_EDGE_THRESHOLD=0.03         # 3% minimum edge
MIN_COMPOSITE_SCORE=6.0         # Minimum opportunity score (0-10)
MIN_CONFIDENCE=medium           # Minimum confidence: low, medium, high
KELLY_FRACTION=0.25             # Quarter-Kelly sizing factor

# --- System ---
DRY_RUN=false                   # true = blocks live orders
LOG_LEVEL=INFO                  # DEBUG for verbose output
```

---

## Examples: Full Session Walkthrough

### Morning: NCAA Tournament Day

```bash
# 1. Check your balance and positions
python scripts/kalshi_executor.py status

# 2. Settle any overnight results
python scripts/kalshi_settler.py settle
python scripts/kalshi_settler.py report

# 3. Scan today's NCAA games
python scripts/kalshi_executor.py run --filter ncaamb

# 4. Looks good -- execute top 5
python scripts/kalshi_executor.py run --filter ncaamb --execute --max-bets 5
```

### Evening: NBA Night

```bash
# 1. Quick status check
python scripts/kalshi_executor.py status

# 2. Scan NBA games
python scripts/kalshi_executor.py run --filter nba

# 3. Raise the bar -- only high conviction bets
python scripts/kalshi_executor.py run --filter nba --execute --min-edge 0.05 --max-bets 3

# 4. After games finish, settle
python scripts/kalshi_settler.py settle
python scripts/kalshi_settler.py report --detail
```

### Multi-Sport Scan

```bash
# Scan everything, see what's out there
python scripts/edge_detector.py scan --top 30

# Or scan each sport individually
python scripts/edge_detector.py scan --filter nba
python scripts/edge_detector.py scan --filter nhl
python scripts/edge_detector.py scan --filter ncaamb
```
