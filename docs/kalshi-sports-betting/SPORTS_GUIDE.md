# Kalshi Sports Betting Guide

Consolidated guide for sports betting on Kalshi: scanning markets, detecting edges, placing bets, and tracking results.

For complete CLI flags and command examples, see [Scripts Reference](../SCRIPTS_REFERENCE.md).
For risk gates and parameters, see [Architecture](../ARCHITECTURE.md).

---

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Daily Workflow](#daily-workflow)
- [Sport Filters](#sport-filters)
- [How Edge Detection Works](#how-edge-detection-works)
- [Market Categories](#market-categories)
- [Bet Sizing](#bet-sizing)
- [Per-Game Cap](#per-game-cap)
- [Composite Score](#composite-score)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Check balance and open positions
python scripts/kalshi/kalshi_executor.py status

# 2. Preview opportunities (no orders placed)
python scripts/kalshi/kalshi_executor.py run

# 3. Execute the top opportunities
python scripts/kalshi/kalshi_executor.py run --execute --max-bets 5

# 4. After games resolve, settle and review
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report
```

---

## Prerequisites

Before first run, verify:

1. **Python virtual environment** -- activate with `.venv\Scripts\activate` (Windows)
2. **`.env` file** -- must contain:
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

Check positions, settle overnight results, scan today's games, review the preview table, then execute.

```bash
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report
python scripts/kalshi/kalshi_executor.py run --filter ncaamb
python scripts/kalshi/kalshi_executor.py run --filter ncaamb --execute --max-bets 5
```

The executor pipeline performs these steps automatically:
1. Pulls all open Kalshi markets (~5000 across all sports)
2. Fetches sportsbook odds from The Odds API
3. Calculates fair value via de-vigging for each matched market
4. Filters to opportunities with edge >= minimum threshold (default 3%)
5. Sizes bets using the configured unit size
6. Shows a preview table; places orders only if `--execute` is passed

### During the Day: Monitor

Run `status` for a portfolio dashboard showing balance, open positions, resting orders, and today's wagering activity. Use direct API access for more granular checks.

```bash
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/kalshi_client.py positions
python scripts/kalshi/kalshi_client.py orders
```

### Evening: Settle and Review

After games finish, pull results from Kalshi, update local P&L, and review performance. Use `--detail` for a per-trade breakdown and `--save` to persist the report to disk.

```bash
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail
python scripts/kalshi/kalshi_settler.py report --detail --save
```

Reports include: win/loss record, net P&L, total wagered, ROI, profit factor, best/worst trades, edge calibration (estimated vs. realized), and breakdowns by confidence level and market category.

### Multi-Sport Scan

Run a broad scan or target individual sports to find the best edges across the board.

```bash
python scripts/kalshi/edge_detector.py scan --top 30
python scripts/kalshi/edge_detector.py scan --filter nba
python scripts/kalshi/edge_detector.py scan --filter nhl
python scripts/kalshi/edge_detector.py scan --filter ncaamb
```

---

## Sport Filters

Use `--filter` on the executor or edge detector to target a specific sport. This limits the market scan and only fetches odds for that sport, saving Odds API quota.

### US Major Leagues

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `nba` | NBA Basketball | Games, spreads, totals, player props, MVP, ROY, DPOY | Yes -- game, spread, total |
| `nhl` | NHL Hockey | Games, spreads, totals, player props, Hart, Norris, Calder | Yes -- game, spread, total |
| `mlb` | MLB Baseball | Games, playoffs | Yes -- game |
| `nfl` | NFL Football | Games, spreads, totals, draft | Yes -- game, spread, total *(seasonal)* |

### College Sports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `ncaamb` | NCAA Men's Basketball | Games, spreads, totals, MOP | Yes -- game, spread, total |
| `ncaabb` | NCAA Basketball (additional) | Games | Yes -- game |
| `ncaawb` | NCAA Women's Basketball | Games | No |
| `ncaafb` | NCAA Football | Games | No |

### Soccer / Football

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

### Combat Sports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `ufc` | UFC / MMA | Fight winners | No |
| `boxing` | Boxing | Fight winners | No |

### Motorsports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `f1` | Formula 1 | Drivers + constructors championship | No |
| `nascar` | NASCAR | Race winners | No |

### Other Sports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `pga` | PGA Golf | Tournament winners | No |
| `ipl` | IPL Cricket | Outright winner | No |

### Esports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `cs2` | Counter-Strike 2 | Map + match winners | No |
| `lol` | League of Legends | Map + match winners | No |
| `esports` | All esports | CS2 + LoL combined | No |

> **Edge Detection = "Yes"** means the system cross-references sportsbook odds for a calculated edge. **"No"** means markets are browsable and bettable, but edge is estimated from market microstructure only (liquidity, spread analysis).

### Raw Ticker Prefixes

You can pass any raw Kalshi ticker prefix directly for markets not covered by named shortcuts:

```bash
python scripts/kalshi/edge_detector.py scan --filter KXNHLGOAL    # NHL player goals
python scripts/kalshi/edge_detector.py scan --filter KXNBA3PT     # NBA 3-pointers
python scripts/kalshi/edge_detector.py scan --filter KXUFCFIGHT   # UFC fights
```

Edge detection only works for market types with a mapped external odds source (see table above). Raw prefix filters on unsupported markets will scan but will not find edges.

---

## How Edge Detection Works

The system estimates "fair value" for Kalshi markets by cross-referencing sportsbook odds:

1. **Fetch** odds from 8-12 US sportsbooks via The Odds API
2. **De-vig** each book's line to remove the house edge
3. **Weighted median** — sharp books (Pinnacle, Circa) count 3x more than recreational books (DraftKings, FanDuel at 0.7x)
4. **Compare** to Kalshi's current ask price
5. **Edge** = fair value - market price
6. **Validate** with team stats — win% from ESPN/NHL/MLB APIs adjusts confidence

### Edge Detection by Market Type

| Type | Method | Reliability |
|------|--------|-------------|
| Game outcomes (moneyline) | Weighted de-vigged h2h odds | High -- direct comparison |
| Spreads | Normal CDF model with sport-specific stdev | High -- proper bell curve |
| Totals (over/under) | Normal CDF model with sport-specific stdev + weather | High -- proper bell curve |
| Player props | Not yet implemented | -- |
| Esports | Not yet implemented | -- |

### Weather Impact (NFL, MLB Totals)

For outdoor NFL and MLB games, the system fetches NWS hourly forecasts for the venue and adjusts total scoring expectations:
- **Wind > 15 mph** — reduces passing/kicking accuracy (NFL), fly ball distance (MLB)
- **Rain > 40%** — reduces scoring in both sports
- **Cold < 32F (NFL) / < 45F (MLB)** — affects grip and ball flight

Dome stadiums are automatically excluded. Weather data is stored in opportunity details when active.

### Confidence Signals

Confidence (low/medium/high) is set by four factors:
- **Book count + agreement** — 8+ books with tight consensus = high
- **Book spread range** — if books disagree by >4 points, confidence drops (signals injury/news)
- **Team stats** — ESPN/NHL/MLB win% data. Stats that support the bet boost confidence; stats that contradict reduce it
- **Sharp money** — ESPN open vs close odds detect reverse line movement. When sharps are on our side, confidence goes up

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

Every Kalshi market is classified into a category. Filter by category using the edge detector's `--category` flag.

| Category | Description | Example |
|----------|-------------|---------|
| `game` | Who wins the game (moneyline) | "New York to win" |
| `spread` | Win by X points | "Kansas wins by over 9.5 Points" |
| `total` | Over/under total points | "Over 146.5 points scored" |
| `player_prop` | Individual player stats | NHL goals, assists, points, blocks |
| `esports` | CS2 and LoL match/map outcomes | "Team A wins Map 1" |
| `other` | Anything not matched above | Weather, politics, economics |

You can combine `--filter` (sport) with `--category`:

```bash
python scripts/kalshi/edge_detector.py scan --filter nba --category spread
python scripts/kalshi/edge_detector.py scan --filter nhl --category game
```

---

## Bet Sizing

Every bet targets a fixed dollar amount (the "unit size"). The system calculates how many contracts to buy to reach that amount.

**Default unit size: $1.00** (set via `UNIT_SIZE` in `.env`, override per run with `--unit-size`).

| Contract Price | Contracts (at $1 unit) | Actual Cost |
|----------------|------------------------|-------------|
| $0.02 | 50 | $1.00 |
| $0.05 | 20 | $1.00 |
| $0.08 | 13 | $1.04 |
| $0.13 | 8 | $1.04 |
| $0.25 | 4 | $1.00 |
| $0.50 | 2 | $1.00 |
| $0.76 | 1 | $0.76 |

No single bet can exceed `MAX_BET_SIZE_PREDICTION` (default $5, set in `.env`). This is a hard cap regardless of unit size.

---

## Per-Game Cap

Results are limited to **3 opportunities per game**. When a single matchup (e.g., Michigan vs Alabama) generates edges across multiple spread, total, and game markets, only the top 3 by edge are kept. This prevents one game from dominating the opportunity list.

---

## Composite Score

Each opportunity receives a composite score (0-10) combining:

- **Edge magnitude** -- how large the pricing discrepancy is
- **Confidence level** -- how many sportsbooks agree on the fair value
- **Liquidity** -- bid/ask spread and volume on the Kalshi market

Only opportunities with a composite score >= 6.0 are eligible for execution. The minimum score is configurable via `MIN_COMPOSITE_SCORE` in `.env`.

---

## Advanced Usage

### Cherry-Picking Specific Bets

Use `--pick` to select specific opportunities by index from the preview table, or `--ticker` to target a specific Kalshi ticker:

```bash
# Pick opportunities #1, #3, and #5 from the preview
python scripts/kalshi/kalshi_executor.py run --execute --pick 1,3,5

# Bet on a specific ticker
python scripts/kalshi/kalshi_executor.py run --execute --ticker KXNBAGAME-26MAR22LALBOS-LAL
```

### From Saved Scan

Scan and save results first, then execute from the saved file to avoid re-fetching odds:

```bash
python scripts/kalshi/edge_detector.py scan --filter ncaamb --save
python scripts/kalshi/kalshi_executor.py run --from-file --execute --max-bets 3
```

Saved opportunities are stored in `data/watchlists/kalshi_opportunities.json`.

### Raising the Edge Bar

For more selective betting (fewer bets, higher conviction):

```bash
python scripts/kalshi/kalshi_executor.py run --execute --min-edge 0.05
python scripts/kalshi/kalshi_executor.py run --execute --min-edge 0.10
```

### Combining Filters

```bash
# NBA spreads only, 5% minimum edge, $3 bets
python scripts/kalshi/edge_detector.py scan --filter nba --category spread --min-edge 0.05 --save
python scripts/kalshi/kalshi_executor.py run --from-file --execute --unit-size 3
```

### Scanning Without Betting

Use the edge detector standalone to research markets without placing any orders:

```bash
python scripts/kalshi/edge_detector.py scan
python scripts/kalshi/edge_detector.py scan --save
python scripts/kalshi/edge_detector.py scan --top 50
```

### Deep Dive on a Single Market

```bash
python scripts/kalshi/edge_detector.py detail KXNBAGAME-26MAR22LALBOS-LAL
```

Shows the full breakdown: matched sportsbook odds, de-vigged probabilities, calculated fair value, and edge.

---

## Troubleshooting

**"Kalshi private key not found"**
- Verify `KALSHI_PRIVATE_KEY_PATH` in `.env` points to an existing `.key` file
- Path is relative to project root

**"Rate limited"**
- Basic tier: 20 reads/sec, 10 writes/sec
- The scanner fetches up to 5 pages of 1000 markets -- stay under limits
- Add delays between runs if hitting limits

**"ODDS_API_KEY not set"**
- Edge detection requires a key from https://the-odds-api.com (free tier: 500 req/month)
- Without it, the scanner runs but finds no opportunities

**Orders show "resting" instead of "executed"**
- Limit order did not find a match at your price
- The order stays open until filled, cancelled, or the market closes
- Check resting orders: `python scripts/kalshi/kalshi_executor.py status`

**Settlement shows 0 settled**
- Markets have not resolved yet -- check `expected_expiration_time` on the market
- Run `settle` again after the game/event completes

**Market settlement timing reference:**

| Market Type | Typical Settlement Time |
|-------------|------------------------|
| NBA / NCAA / NHL / MLB game outcomes | Minutes to ~1 hour after final score |
| Spreads and totals | Same as game outcomes |
| Player props | Usually within a few hours |
| Esports | Varies, usually within hours |

### Reconciliation

If your local trade log seems out of sync (e.g., you placed manual bets on the Kalshi website):

```bash
python scripts/kalshi/kalshi_settler.py reconcile
```

Flags positions that exist locally but not on Kalshi (or vice versa), and quantity mismatches.
