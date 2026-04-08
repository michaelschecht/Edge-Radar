# Kalshi Sports Betting Guide

Consolidated guide for sports betting on Kalshi: scanning markets, detecting edges, placing bets, and tracking results.

For complete CLI flags and command examples, see [Scripts Reference](../SCRIPTS_REFERENCE.md).
For risk gates and parameters, see [Architecture](../ARCHITECTURE.md).
For enhancement history and planned features, see [Roadmap](../enhancements/ROADMAP.md).
See also: [Futures Guide](../kalshi-futures-betting/FUTURES_GUIDE.md) | [Prediction Markets Guide](../kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md)

---

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
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
python scripts/scan.py sports --filter mlb --date today --exclude-open

# 3. Execute the top picks
python scripts/scan.py sports --filter mlb --date today --exclude-open --execute --max-bets 5

# 4. After games resolve, settle and review
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail --save
```

> For the full daily workflow (morning, midday, evening), see [Daily Workflow](../SCRIPTS_REFERENCE.md#daily-workflow) in the Scripts Reference.

---

## Prerequisites

Before first run, verify:

1. **Python virtual environment** -- activate with `.venv\Scripts\activate` (Windows)
2. **`.env` file** -- must contain:
   ```env
   KALSHI_API_KEY=<your-key-id>
   KALSHI_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
   KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
   ODDS_API_KEYS=<your-odds-api-key>
   DRY_RUN=false
   ```
3. **API keys** -- RSA private key in `keys/live/`
4. **Dependencies** -- `pip install -r requirements.txt`

---

## Sport Filters

Use `--filter` to target a specific sport. Supports comma-separated values for multi-sport scans (e.g., `--filter mlb,nhl`). This limits the market scan and only fetches odds for those sports, saving Odds API quota.

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
| `ncaawb` | NCAA Women's Basketball | Games | Yes -- game |
| `ncaafb` | NCAA Football | Games | Yes -- game |

### Soccer / Football

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `soccer` | All soccer (combined) | All leagues below | Yes -- game |
| `mls` | MLS | Games, spreads, totals | Yes -- game, spread, total |
| `ucl` | Champions League | Match winner | Yes -- game |
| `epl` | English Premier League | Match winner | Yes -- game |
| `laliga` | La Liga | Match winner | Yes -- game |
| `seriea` | Serie A | Match winner | Yes -- game |
| `bundesliga` | Bundesliga | Match winner | Yes -- game |
| `ligue1` | Ligue 1 | Match winner | Yes -- game |

### Combat Sports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `ufc` | UFC / MMA | Fight winners | Yes -- game |
| `boxing` | Boxing | Fight winners | Yes -- game |

### Motorsports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `f1` | Formula 1 | Drivers + constructors championship | Yes -- game |
| `nascar` | NASCAR | Race winners | No |

### Other Sports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `pga` | PGA Golf | Tournament winners | Yes -- game |
| `ipl` | IPL Cricket | Match winner | Yes -- game |

### Esports

| Filter | Sport | Key Markets | Edge Detection |
|--------|-------|-------------|----------------|
| `cs2` | Counter-Strike 2 | Map + match winners | No |
| `lol` | League of Legends | Map + match winners | No |
| `esports` | All esports | CS2 + LoL combined | No |

> **Edge Detection = "Yes"** means the system cross-references sportsbook odds via the Odds API for a calculated edge. **"No"** means markets are browsable and bettable, but edge is estimated from market microstructure only (liquidity, spread analysis).

### Raw Ticker Prefixes

You can pass any raw Kalshi ticker prefix directly for markets not covered by named shortcuts:

```bash
python scripts/scan.py sports --filter KXNHLGOAL    # NHL player goals
python scripts/scan.py sports --filter KXNBA3PT     # NBA 3-pointers
python scripts/scan.py sports --filter KXUFCFIGHT   # UFC fights
```

Edge detection only works for market types with a mapped external odds source (see table above). Raw prefix filters on unsupported markets will scan but will not find edges.

---

## How Edge Detection Works

The system estimates "fair value" for Kalshi markets by cross-referencing sportsbook odds:

1. **Fetch** odds from 8-12 US sportsbooks via The Odds API
2. **De-vig** each book's line to remove the house edge
3. **Weighted median** -- sharp books (Pinnacle, Circa) count 3x more than recreational books (DraftKings, FanDuel at 0.7x)
4. **Compare** to Kalshi's current ask price
5. **Edge** = fair value - market price
6. **Validate** with team stats -- win% from ESPN/NHL/MLB APIs adjusts confidence
7. **Sharp money** -- ESPN open vs close odds detect reverse line movement

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
- **Wind > 15 mph** -- reduces passing/kicking accuracy (NFL), fly ball distance (MLB)
- **Rain > 40%** -- reduces scoring in both sports
- **Cold < 32F (NFL) / < 45F (MLB)** -- affects grip and ball flight

Dome stadiums are automatically excluded. Weather data is stored in opportunity details when active.

### Confidence Signals

Confidence (low/medium/high) is set by four factors:
- **Book count + agreement** -- 8+ books with tight consensus = high
- **Book spread range** -- if books disagree by >4 points, confidence drops (signals injury/news)
- **Team stats** -- ESPN/NHL/MLB win% data. Stats that support the bet boost confidence; stats that contradict reduce it
- **Sharp money** -- ESPN open vs close odds detect reverse line movement. When sharps are on our side, confidence goes up

### Odds API Sport Mapping

The system cross-references Kalshi prices against these Odds API sport keys:

| Kalshi Prefix | Odds API Sport Key | Bet Types Supported |
|---------------|-------------------|---------------------|
| KXNBAGAME/SPREAD/TOTAL | `basketball_nba` | Moneyline, spreads, totals |
| KXNHLGAME/SPREAD/TOTAL | `icehockey_nhl` | Moneyline, spreads, totals |
| KXMLBGAME | `baseball_mlb` | Moneyline (h2h) |
| KXNFLGAME/SPREAD/TOTAL | `americanfootball_nfl` | Moneyline, spreads, totals |
| KXNCAAMBGAME/SPREAD/TOTAL | `basketball_ncaab` | Moneyline, spreads, totals |
| KXNCAABBGAME | `basketball_ncaab` | Moneyline (h2h) |
| KXNCAAFBGAME | `americanfootball_ncaaf` | Moneyline (h2h) |
| KXNCAAWBGAME | `basketball_wncaab` | Moneyline (h2h) |
| KXMLSGAME/SPREAD/TOTAL | `soccer_usa_mls` | Moneyline, spreads, totals |
| KXEPL | `soccer_epl` | Moneyline (h2h) |
| KXUCL | `soccer_uefa_champs_league` | Moneyline (h2h) |
| KXLALIGA | `soccer_spain_la_liga` | Moneyline (h2h) |
| KXSERIEA | `soccer_italy_serie_a` | Moneyline (h2h) |
| KXBUNDESLIGA | `soccer_germany_bundesliga` | Moneyline (h2h) |
| KXLIGUE1 | `soccer_france_ligue_one` | Moneyline (h2h) |
| KXUFCFIGHT | `mma_mixed_martial_arts` | Moneyline (h2h) |
| KXBOXING | `boxing_boxing` | Moneyline (h2h) |
| KXF1 | `motorsport_formula_one` | Race winner |
| KXPGATOUR | `golf_pga_championship` | Tournament winner |
| KXIPL | `cricket_ipl` | Moneyline (h2h) |

---

## Market Categories

Every Kalshi market is classified into a category. Filter by category using the `--category` flag.

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
python scripts/scan.py sports --filter nba --category spread
python scripts/scan.py sports --filter nhl --category game
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

No single bet can exceed `MAX_BET_SIZE` (default $100, set in `.env`). This is a hard cap regardless of unit size.

---

## Per-Game Cap

Results are limited to **3 opportunities per game**. When a single matchup (e.g., Michigan vs Alabama) generates edges across multiple spread, total, and game markets, only the top 3 by edge are kept. This prevents one game from dominating the opportunity list.

---

## Composite Score

Each opportunity receives a composite score (0-10) combining four dimensions:

- **Edge magnitude** (40%) -- how large the pricing discrepancy is
- **Confidence level** (30%) -- how many sportsbooks agree on the fair value
- **Liquidity** (20%) -- bid/ask spread and volume on the Kalshi market
- **Time to expiry** (10%) -- nearer events score slightly higher

Only opportunities with a composite score >= 6.0 are eligible for execution. The minimum score is configurable via `MIN_COMPOSITE_SCORE` in `.env`.

---

## Advanced Usage

### Cherry-Picking Specific Bets

Use `--pick` to select specific opportunities by index from the preview table, or `--ticker` to target a specific Kalshi ticker:

```bash
# Pick opportunities #1, #3, and #5 from the preview
python scripts/scan.py sports --filter mlb --execute --pick 1,3,5

# Bet on a specific ticker
python scripts/scan.py sports --execute --ticker KXNBAGAME-26MAR22LALBOS-LAL
```

### From Saved Scan

Scan and save results first, then execute from the saved file to avoid re-fetching odds:

```bash
python scripts/scan.py sports --filter ncaamb --save
python scripts/scan.py sports --from-file --execute --max-bets 3
```

Saved opportunities are stored in `data/watchlists/kalshi_opportunities.json`.

### Date & Position Filters

```bash
# Only today's games
python scripts/scan.py sports --filter mlb --date today

# Only tomorrow's games, skip markets you already bet on
python scripts/scan.py sports --filter mlb --date tomorrow --exclude-open
```

`--date` accepts: `today`, `tomorrow`, `YYYY-MM-DD`, `MM-DD`, or shorthand like `mar31`.

### Raising the Edge Bar

For more selective betting (fewer bets, higher conviction):

```bash
python scripts/scan.py sports --min-edge 0.05 --top 10
python scripts/scan.py sports --min-edge 0.10 --top 5
```

### Combining Filters

```bash
# NBA spreads only, 5% minimum edge
python scripts/scan.py sports --filter nba --category spread --min-edge 0.05 --save
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
- Set `ODDS_API_KEYS` in `.env` (supports comma-separated keys for rotation)
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
