---
name: edge-radar
description: Unified Edge-Radar skill for scanning markets, placing wagers, managing portfolio, settling bets, and researching edge across Kalshi sports, futures, prediction markets, and Polymarket cross-reference. Covers all scripts, filters, and workflows.
argument-hint: <action> [market/filter] [flags] — e.g., "scan nba", "bet mlb --unit-size 2", "status", "settle", "detail TICKER"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep
---

# Edge-Radar Skill

You are executing the `/edge-radar` skill. This is the unified command center for all Edge-Radar operations: scanning for edge, placing wagers, managing portfolio, settling bets, and researching markets.

## Parse Arguments

Arguments: `$ARGUMENTS`

Parse the user's intent from the arguments. The skill supports natural language — interpret what the user wants and route to the correct action.

### Action Routing

| User Says | Action | Notes |
|-----------|--------|-------|
| `status`, `portfolio`, `balance`, `positions` | **Status** | Show portfolio dashboard |
| `settle`, `results`, `pnl` | **Settle & Report** | Settle completed bets, show P&L |
| `reconcile`, `sync` | **Reconcile** | Compare local log vs Kalshi API |
| `risk`, `limits`, `dashboard` | **Risk Dashboard** | Full risk check with limits |
| `scan <filter>`, `check <filter>`, `find <filter>` | **Scan** | Preview opportunities (no execution) |
| `bet <filter>`, `play <filter>`, `wager <filter>` | **Scan & Bet** | Scan then prompt to execute |
| `detail <TICKER>`, `lookup <TICKER>` | **Detail** | Deep dive on a single market |
| `odds <sport>` | **Raw Odds** | Show sportsbook odds without edge detection |
| `data <type>` | **Market Data** | Fetch stock/crypto/prediction market data |
| `backtest`, `analyze`, `performance` | **Backtest** | Run backtester on settled trades |
| Any sport/market name alone (e.g., `nba`, `mlb`, `crypto`) | **Scan** | Default to scan for that filter |

### Flag Parsing

| Flag | Default | Description |
|------|---------|-------------|
| `--unit-size N` or `$N` (dollar amount) | `$1.00` | Dollar amount per bet |
| `--max-bets N` | `5` | Maximum bets to place |
| `--min-edge N` | `0.03` global; `0.12` NBA; `0.10` NCAAB | Minimum edge. Per-sport overrides via `MIN_EDGE_THRESHOLD_<SPORT>` env. NBA raised 0.08 → 0.12 in R14 (2026-04-24) after 30-day review showed NBA Brier 0.3306 — worst of all sports. NCAAB kept at 0.10 from 2026-04-18 calibration. |
| `--execute`, `--go`, `--send-it` | off | Skip preview, execute immediately |
| `--dry-run`, `--preview` | on (default) | Preview only, no orders |
| `--save` | off | Save results as markdown report to `reports/` |
| `--date DATE` | (none) | Filter by date: `today`, `tomorrow`, `YYYY-MM-DD`, `mar31`, `03-30` |
| `--exclude-open` | off | Skip markets with existing open positions |
| `--budget X` | (none) | Max total batch cost — `10%` (of bankroll) or `15` (flat dollars). Proportionally scales down contracts to stay within budget while preserving Kelly edge-weighting |
| `--pick '1,3,5'` | (none) | Cherry-pick specific rows from preview |
| `--ticker TICKER` | (none) | Target a specific Kalshi ticker |
| `--category CAT` | (none) | Market type: `game`, `spread`, `total`, `player_prop` |
| `--cross-ref` | off | Cross-reference against Polymarket |
| `--top N` | `20` | Number of opportunities to show |
| `--detail` | off | Show per-trade breakdown (for reports) |
| `--from-file` | off | Load from saved watchlist |
| `--report-dir PATH` | (none) | Override report output directory (used in batch jobs) |

---

## Unified Scanner Entry Point

**All scans should use `scripts/scan.py`** — the unified router that forwards to the correct scanner:

```bash
python scripts/scan.py sports --filter mlb --date today --save
python scripts/scan.py sports --unit-size .5 --max-bets 5 --budget 10% --date today --exclude-open --execute
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py prediction --filter crypto --cross-ref
python scripts/scan.py polymarket --filter crypto
```

Aliases: `sport` = `sports`, `pred` = `prediction`, `poly`/`xref` = `polymarket`.

The `scan` subcommand is auto-inserted if omitted. All flags are forwarded directly.

### Makefile Shortcuts

For quick access, the Makefile provides 18 targets:

```bash
make scan-mlb          # Scan MLB today, exclude open, save report
make scan-nba          # Scan NBA
make scan-nhl          # Scan NHL
make scan-nfl          # Scan NFL
make scan-sports       # All sports
make scan-futures      # All futures
make scan-predictions  # All prediction markets
make scan-polymarket   # Polymarket cross-reference
make scan-all          # Everything
make status            # Portfolio status
make risk              # Risk dashboard
make settle            # Settle completed bets
make report            # P&L report
make reconcile         # Compare local log vs API
make test              # Run full test suite (100 tests)
make test-quick        # Quick test run
make install           # Install dependencies
make hooks             # Install pre-commit hooks
```

---

## Filter Quick Reference

### Sports (Game Betting) — `edge_detector.py`

| Filter | Sport | Edge Detection |
|--------|-------|----------------|
| `nba` | NBA Basketball | Yes |
| `nhl` | NHL Hockey | Yes |
| `mlb` | MLB Baseball | Yes |
| `nfl` | NFL Football | Yes (seasonal) |
| `ncaamb` | NCAA Men's Basketball | Yes |
| `ncaabb` | NCAA Basketball (additional) | Yes |
| `ncaawb` | NCAA Women's Basketball | Browse only |
| `ncaafb` | NCAA Football | Browse only |
| `mls` | MLS Soccer | Browse only |
| `soccer` | All soccer combined | Browse only |
| `ucl`, `epl`, `laliga`, `seriea`, `bundesliga`, `ligue1` | European leagues | Browse only |
| `ufc`, `boxing` | Combat sports | Browse only |
| `f1`, `nascar` | Motorsports | Browse only |
| `pga` | PGA Golf | Browse only |
| `ipl` | IPL Cricket | Browse only |
| `cs2`, `lol`, `esports` | Esports | Browse only |

### Futures (Championships) — `futures_edge.py`

| Filter | What It Scans | Edge Detection |
|--------|---------------|----------------|
| `futures` | All futures | Yes (where available) |
| `nfl-futures` / `superbowl` | Super Bowl champion | Yes |
| `nba-futures` | NBA Finals + conferences | Yes |
| `nhl-futures` | Stanley Cup + conferences | Yes |
| `mlb-futures` | World Series + playoffs | Yes |
| `ncaab-futures` | NCAAB MOP | Yes |
| `golf-futures` | PGA tournament winners | Yes |

### Prediction Markets — `prediction_scanner.py`

| Filter | Category | Edge Detection | Data Source |
|--------|----------|----------------|-------------|
| `crypto`, `btc`, `eth`, `xrp`, `doge`, `sol` | Crypto prices | Yes | CoinGecko |
| `weather` | Temperature forecasts | Yes | NWS API |
| `spx`, `sp500` | S&P 500 levels | Yes | Yahoo Finance + VIX |
| `mentions`, `lastword`, `nbamention`, `foxnews`, `politicsmention` | TV mentions | Yes | Historical rates |
| `companies`, `bankruptcy`, `ipo` | Corporate events | Partial | Historical baseline |
| `politics`, `impeach` | Political events | Yes | Time-decay model |
| `techscience`, `quantum`, `fusion` | Tech milestones | Yes | Time-decay model |

### Polymarket Cross-Reference — `polymarket_edge.py`

| Filter | Description |
|--------|-------------|
| `polymarket`, `poly`, `xref` | Cross-market edge (Kalshi vs Polymarket) |

### Raw Ticker Prefixes

Any Kalshi ticker prefix works as a filter (e.g., `KXNHLGOAL`, `KXNBA3PT`, `KXUFCFIGHT`).

---

## Action: Status

Show portfolio dashboard — balance, open positions, P&L, resting orders.

```bash
python scripts/kalshi/kalshi_executor.py status
```

Report the key numbers clearly: balance, number of open positions, today's P&L, any resting orders. Positions display Sport, Bet (matchup), Type (ML/Spread/Total/Prop), Pick (e.g., "Spurs win", "Over 220.5"), When, Qty, Cost, P&L. Done.

For a more detailed risk dashboard:

```bash
python scripts/kalshi/risk_check.py
```

Add `--save` to either command to persist as markdown report.

---

## Action: Settle & Report

Update trade log with settled results, then show performance report.

```bash
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail
python scripts/kalshi/kalshi_settler.py report --days 7          # Last week only
python scripts/kalshi/kalshi_settler.py report --days 30 --save  # Last month, save to file
```

Add `--save` to persist the report as markdown. Use `--days N` to filter to recent trades.

Reports include: P&L summary, win/loss record, edge calibration, CLV, plus dimensional breakdowns by confidence, category (ML/Spread/Total), sport, and edge bucket (3-5%, 5-10%, 10-15%, 15%+).

Summarize: total settled, wins, losses, net P&L, ROI, best/worst bets, which dimensions are profitable. Done.

---

## Action: Reconcile

Compare local trade log against the Kalshi API to catch discrepancies.

```bash
python scripts/kalshi/kalshi_settler.py reconcile
```

Report any mismatches. Done.

---

## Action: Risk Dashboard

Full portfolio risk check with limit status. Pulls live data from Kalshi API.

```bash
python scripts/kalshi/risk_check.py
```

| Report Flag | Shows |
|-------------|-------|
| `--report all` | Everything (default) |
| `--report positions` | Just open positions |
| `--report pnl` | Just P&L |
| `--report limits` | Just risk limit status |
| `--report watchlist` | Just active watchlist |
| `--gate` | Exit code 1 if limits breached (for automation) |
| `--save` | Save dashboard as markdown |

---

## Action: Detail (Single Market Deep Dive)

```bash
python scripts/kalshi/edge_detector.py detail <TICKER>
```

Shows: matched sportsbook odds, de-vigged probabilities, fair value, edge, and confidence breakdown.

For Polymarket match lookup:

```bash
python scripts/polymarket/polymarket_edge.py match <TICKER>
```

---

## Action: Raw Odds

Show sportsbook odds without running edge detection.

```bash
python scripts/kalshi/fetch_odds.py --market <sport>
```

Sports: `nba`, `nfl`, `mlb`, `nhl`, `ncaafb`, `ncaabb`, `soccer`, `mma`, `all`.

---

## Action: Market Data

Fetch market data for research.

```bash
python scripts/kalshi/fetch_market_data.py --type <type> [--symbols SYM1 SYM2] [--source kalshi|polymarket]
```

Types: `stocks`, `prediction`, `crypto`, `account`, `all`.

---

## Action: Scan (Preview Only)

Run the appropriate scanner based on the filter. **No orders are placed.**

### Step 1: Check Status First

```bash
python scripts/kalshi/kalshi_executor.py status
```

If the daily loss limit is breached, **STOP** and inform the user. No new bets today.

### Step 2: Route to the Correct Scanner

**Use the unified entry point `scan.py`** — it routes to the correct scanner automatically.

**Sports (game betting):**
```bash
python scripts/scan.py sports \
  [--filter <sport>] \
  [--category <game|spread|total|player_prop>] \
  [--min-edge <threshold>] \
  [--top <N>] \
  [--date <DATE>] \
  [--exclude-open] \
  [--report-dir <PATH>] \
  [--save]
```

**Futures (championships):**
```bash
python scripts/scan.py futures \
  [--filter <sport>-futures] \
  [--min-edge <threshold>] \
  [--top <N>] \
  [--date <DATE>] \
  [--exclude-open] \
  [--save]
```

**Prediction markets:**
```bash
python scripts/scan.py prediction \
  [--filter <category>] \
  [--min-edge <threshold>] \
  [--top <N>] \
  [--date <DATE>] \
  [--exclude-open] \
  [--cross-ref] \
  [--save]
```

**Polymarket cross-reference:**
```bash
python scripts/scan.py polymarket \
  [--filter <category>] \
  [--min-edge <threshold>] \
  [--min-match <score>] \
  [--top <N>] \
  [--save]
```

**Direct scanner access** (still works for all scanners):
```bash
python scripts/kalshi/edge_detector.py scan [flags]
python scripts/kalshi/futures_edge.py scan [flags]
python scripts/prediction/prediction_scanner.py scan [flags]
python scripts/polymarket/polymarket_edge.py scan [flags]
```

### Step 3: Present Results

The scan table shows: **Sport** (NBA/NHL/MLB/etc.), **Bet** (matchup), **Type** (ML/Spread/Total/Prop), **Pick** (e.g., "Spurs win", "Over 220.5", "Blazers -7.5"), **When**, **Mkt**, **Fair**, **Edge**, **Conf**, **Score**.

When `--unit-size` is passed, the executor table shows: **Sport**, **Bet**, **Type**, **Pick**, **When**, **Qty**, **Price**, **Cost**, **Edge**.

Explain:
- How many opportunities were found and at what edge threshold
- Top 2-3 picks and why they have edge (plain language)
- Total estimated cost if all were executed
- For futures: note that capital is tied up for weeks/months
- For prediction markets: note settlement timing

---

## Action: Scan & Bet

Same as Scan above, but with execution. Follow all scan steps first, then:

### Step 4: Get Confirmation

Unless `--execute` or `--go` was passed, **always ask the user to confirm** before placing orders:

> "Found X opportunities. Ready to execute Y bets for ~$Z total. Go ahead?"

### Step 5: Execute

Once confirmed, add `--execute` to the scan command. All 4 scanners support `--execute`, `--unit-size`, `--max-bets`, and `--pick` directly.

**Sports:**
```bash
python scripts/scan.py sports \
  --filter <sport> --execute \
  [--unit-size <N>] [--max-bets <N>] [--budget <X>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>] [--date <DATE>] [--exclude-open]
```

**Futures:**
```bash
python scripts/scan.py futures \
  --filter <sport>-futures --execute \
  [--unit-size <N>] [--max-bets <N>] [--budget <X>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>]
```

**Prediction:**
```bash
python scripts/scan.py prediction \
  --filter <category> --execute \
  [--unit-size <N>] [--max-bets <N>] [--budget <X>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>]
```

**Polymarket cross-reference:**
```bash
python scripts/scan.py polymarket \
  --filter <category> --execute \
  [--unit-size <N>] [--max-bets <N>] [--budget <X>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>]
```

### Step 6: Report

After execution, summarize:
- Number of orders placed and total cost
- Updated balance
- Reminder to run `/edge-radar settle` after events complete

---

## Routing Examples

| User Says | Command |
|-----------|---------|
| `/edge-radar nba` | `scan.py sports --filter nba` |
| `/edge-radar bet mlb --unit-size 2 --max-bets 10` | `scan.py sports --filter mlb --unit-size 2 --max-bets 10` then confirm then `--execute` |
| `/edge-radar mlb --date tomorrow --exclude-open` | `scan.py sports --filter mlb --date tomorrow --exclude-open` |
| `/edge-radar nba --category spread` | `scan.py sports --filter nba --category spread` |
| `/edge-radar nba-futures` | `scan.py futures --filter nba-futures` |
| `/edge-radar superbowl` | `scan.py futures --filter nfl-futures` |
| `/edge-radar crypto` | `scan.py prediction --filter crypto` |
| `/edge-radar weather --min-edge 0.05` | `scan.py prediction --filter weather --min-edge 0.05` |
| `/edge-radar polymarket crypto` | `scan.py polymarket --filter crypto` |
| `/edge-radar status` | `kalshi_executor.py status` |
| `/edge-radar settle` | `kalshi_settler.py settle` + `report --detail` |
| `/edge-radar reconcile` | `kalshi_settler.py reconcile` |
| `/edge-radar risk` | `risk_check.py` |
| `/edge-radar detail KXNBAGAME-26MAR25LALBOS-LAL` | `edge_detector.py detail KXNBAGAME-26MAR25LALBOS-LAL` |
| `/edge-radar bet nba --go --unit-size 1 --max-bets 3` | `scan.py sports --filter nba --execute --unit-size 1 --max-bets 3` (no confirmation needed) |
| `/edge-radar scan all` | `scan.py sports` (no filter = all sports) |
| `/edge-radar scan all --date today` | `scan.py sports --date today` (all sports, today only) |
| `/edge-radar bet all --unit-size .5 --max-bets 10` | `scan.py sports --unit-size .5 --max-bets 10` then confirm then `--execute` |
| `/edge-radar bet mlb --pick '1,3,5'` | `scan.py sports --filter mlb --execute --pick '1,3,5'` |
| `/edge-radar bet mlb --budget 10% --max-bets 5` | `scan.py sports --filter mlb --budget 10% --max-bets 5` then confirm then `--execute` |
| `/edge-radar bet all --budget 15 --unit-size .5` | `scan.py sports --budget 15 --unit-size .5` then confirm then `--execute` |

---

## Report Output

When `--save` is used, the report format depends on whether `--unit-size` was passed:

**With `--unit-size` (execution report):** Sport, Bet, Type, Pick, Qty, Price, Cost, Edge, total cost.

**Without `--unit-size` (scan report):** Sport, Bet, Type, Pick, When, Mkt, Fair, Edge, Conf, Score.

| Scanner | Report Path |
|---------|-------------|
| Sports (scan) | `reports/Sports/{date}_{sport}_sports_scan.md` |
| Sports (execution) | `reports/Sports/{date}_{sport}_sports_execution.md` |
| Futures | `reports/Futures/{date}_{category}_futures_scan.md` |
| Predictions | `reports/Predictions/{date}_{category}_prediction_scan.md` |
| Settle/P&L | `reports/Accounts/Kalshi/` |
| Automated | `reports/Sports/schedulers/same-day-executions/` |

---

## Risk Limits (Current)

- **Sizing:** Batch-aware Kelly — `(KELLY_FRACTION / batch_size) * trusted_edge(edge) * bankroll`, with flat unit size as floor. When placing N bets simultaneously, each gets `fraction/N` to prevent over-committing.
- **Kelly edge soft-cap (C1, 2026-04-18):** `trusted_edge()` damps the edge used in Kelly sizing above `KELLY_EDGE_CAP=0.15`. Excess is multiplied by `KELLY_EDGE_DECAY=0.5` (e.g., 25% claimed edge sizes like 20%). Raw edge unchanged in gates, reports, and rationale. Calibration showed claimed edges ≥25% realize -35% ROI — this downsizes likely-fake signals.
- **Budget cap:** `--budget X` caps the total batch cost. Accepts `10%` (of bankroll) or `15` (flat dollars). When the batch exceeds the budget, contracts are proportionally scaled down while preserving Kelly edge-weighting (higher-edge bets keep more size). Each bet keeps at least 1 contract.
- **Kelly fraction:** Configurable via `KELLY_FRACTION` in `.env` (default: 0.25)
- **Unit size:** $0.50 default (minimum per bet, overridable with `--unit-size`)
- **Max bet size:** $100 per position (gate 8 — sizing cap, not reject)
- **Bet ratio cap:** 3.0x batch median cost (gate 9 — sizing cap, not reject)
- **Max per event:** 2 positions on the same game (reject gate)
- **Series dedup (C5, 2026-04-18):** Reject a new bet if the same matchup (sport + team pair, date-agnostic) was bet within the last `SERIES_DEDUP_HOURS=48`. Catches consecutive-night series bleeds like the LA Angels @ NY Yankees Apr 13/14/15 pattern. 0 disables.
- **Daily loss limit:** $250 (reject gate)
- **Max open positions:** 50 (reject gate)
- **Minimum edge (C3, 2026-04-18; R14, 2026-04-24):** 3% global; **12% NBA**, **10% NCAAB** (per-sport overrides via `MIN_EDGE_THRESHOLD_<SPORT>` env). NBA bumped 0.08 → 0.12 in R14 after 30-day calibration showed NBA Brier 0.3306 — worst of all sports. Rejection message shows the sport-specific floor in use.
- **Minimum market price (R7, 2026-04-22):** Gate 3.5 rejects bets priced below `MIN_MARKET_PRICE` (default **$0.10**). Hard floor with no edge/confidence exception — F10 from the 14-day review showed sub-10¢ bets at 1W-3L with the model claiming "+50% edge" on 8-10¢ longshots. `MIN_MARKET_PRICE=0` disables.
- **Minimum composite score:** 6.0 (reject gate, confidence is factored into composite)
- **Minimum confidence (R3, 2026-04-21):** Gate 4.5 rejects opportunities below `MIN_CONFIDENCE` (default `medium`). Values: low | medium | high. Low-confidence bets realized 0W-3L / -105% ROI across two review windows.
- **NO-side favorite guard (R1, 2026-04-21):** Gate 4.6 rejects NO bets priced below `NO_SIDE_FAVORITE_THRESHOLD=0.25` unless edge ≥ `NO_SIDE_MIN_EDGE=0.25` AND confidence=high. Plus a sizing dampener: NO bets priced below `NO_SIDE_KELLY_PRICE_FLOOR=0.35` are sized at `NO_SIDE_KELLY_MULTIPLIER=0.5` of Kelly (half-Kelly). All 13 high-edge losers in the 14-day window were NO-side.
- **Resting-order janitor (R4, 2026-04-21):** At the top of any `--execute` run (non-dry-run), resting orders older than `RESTING_ORDER_MAX_HOURS=24` with zero fills are auto-cancelled. Partial/full fills untouched — settler handles them. Piggybacks on the 5AM daily execute task; no new scheduler.
- **Confidence bumps one-way (R13, 2026-04-24):** `_adjust_confidence_with_stats()` in `edge_detector.py` now drops a tier on `contradicts` but no-ops on `supports`. Applies uniformly to team stats, rest/B2B, and sharp-money signals. 30-day calibration showed High-confidence WR (47%) below Medium (53%) and NBA High at 1-6 / -71% ROI — upward bumps correlated with inflated claimed edge, not better outcomes. Base "high" tier still reachable via the ≥8 sharp-books + tight-consensus rule. No env var.

Gates 1-7 (including 3.5, 4.5, 4.6) reject orders outright. Gates 8-9 downsize and approve, logging the approval subtype (`APPROVED`, `APPROVED_CAPPED_MAX_BET`, `APPROVED_CAPPED_BET_RATIO`).

---

## Daily Workflow Reference

### Morning
```bash
make status                    # Check balance & positions
make settle                    # Settle overnight results
make report                    # Quick P&L summary
make risk                      # Check if limits breached
```

### Scanning
```bash
make scan-mlb                  # MLB today, exclude open, save
make scan-nba                  # NBA scan
make scan-futures              # All futures
make scan-predictions          # Prediction markets
make scan-all                  # Everything
```

Or with full control:
```bash
python scripts/scan.py sports --filter mlb --date today --exclude-open --save
python scripts/scan.py sports --filter nba
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py prediction --filter crypto --cross-ref
```

### Executing
```bash
python scripts/scan.py sports --filter mlb --execute --unit-size 1 --max-bets 10
python scripts/scan.py sports --filter mlb --execute --unit-size .5 --max-bets 5 --budget 10%
python scripts/scan.py sports --filter nba --execute --pick '1,3,5'
```

### Evening
```bash
make settle                    # Settle completed bets
make report                    # Detailed P&L
make reconcile                 # Compare local vs API
```

---

## Automation

See **[Automation Guide](docs/setup/AUTOMATION_GUIDE.md)** for the full setup walkthrough.

### Windows Task Scheduler (Recommended)

```powershell
# Install morning execution + nightly settlement
python scripts/schedulers/automation/install_windows_task.py install execute
python scripts/schedulers/automation/install_windows_task.py install settle

# Or install all four tasks at once
python scripts/schedulers/automation/install_windows_task.py install all

# Check task status
python scripts/schedulers/automation/install_windows_task.py status

# Trigger a task immediately (test)
python scripts/schedulers/automation/install_windows_task.py run execute
```

| Profile | Schedule | Description |
|---------|----------|-------------|
| `scan` | 8:00 AM | Preview scan — saves report, no bets |
| `execute` | 8:00 AM | Scan + execute — places live orders |
| `settle` | 11:00 PM | Settle bets, update P&L |
| `next-day` | 9:00 PM | Scan + execute tomorrow's games |
| `calibration` | 2:00 AM, 1st of month | 30-day calibration report (R16) — Brier, calibration curve, prescriptive recommendations |

### Bat Scripts (Manual)

```bash
# Preview only (no bets)
scripts\schedulers\same_day_executions\same_day_scan.bat

# Scan + execute (places live orders)
scripts\schedulers\same_day_executions\same_day_execute.bat
```

Config: `--unit-size .5`, `--max-bets 5`, `--budget 15%`, `--date today`, `--exclude-open`, `--save`.

### Per-Sport Scan-Only Scripts

```
scripts/schedulers/same_day_scans/     # Today's games by sport
scripts/schedulers/next_day_scans/     # Tomorrow's games by sport
```

---

## Low-Level API Access

For debugging or raw market queries:

```bash
python scripts/kalshi/kalshi_client.py balance
python scripts/kalshi/kalshi_client.py positions
python scripts/kalshi/kalshi_client.py orders
python scripts/kalshi/kalshi_client.py markets --limit 50
python scripts/kalshi/kalshi_client.py market --ticker <TICKER>
```

---

## Edge Detection Signals

The scanner uses 9 signals to detect mispriced contracts:

| Signal | Source | What It Does |
|--------|--------|-------------|
| Normal CDF Model | Math | Spread/total probabilities via bell curve with sport-specific stdev |
| Sharp Book Weighting | Odds API | Pinnacle 3x, DraftKings 0.7x — sharp lines pull consensus |
| Team Stats | ESPN/NHL/MLB APIs | Win%, goal/run differential validates book fair value |
| Sharp Money | ESPN | Open-vs-close odds detect reverse line movement |
| Pitcher Matchups | MLB Stats API | ERA, FIP, WHIP, K/9, rest days — adjusts total stdev |
| Rest Days / B2B | ESPN | NBA/NHL back-to-back detection — fatigue adjusts stdev + confidence |
| Weather | NWS | 61 NFL/MLB venue forecasts adjust total expectations |
| Book Disagreement | Odds API | >4pt spread range flags injury news |
| CLV Tracking | Kalshi | Closing line value validates model accuracy over time |

MLB pitcher data is fetched in parallel (ThreadPoolExecutor, 8 workers) for speed.

---

## Trade Logging

Orders are logged with **fill-based accounting**:
- `requested_contracts` / `requested_cost` — what we asked for
- `filled_contracts` / `filled_cost` — what Kalshi actually executed
- `fill_status` — `resting` | `partial` | `filled`

Resting orders (zero fills) are excluded from exposure calculations and settlement. The settler, risk dashboard, and P&L reports all use filled values, not requested.

---

## Calibration

```bash
python scripts/kalshi/model_calibration.py --save        # Full calibration report
python scripts/kalshi/model_calibration.py --days 30     # Last 30 days only
```

Reports: Brier score, calibration curve (predicted vs realized), dimension breakdowns, confidence x category cross-tab, prioritized recommendations.

---

## Backtesting

```bash
python scripts/backtest/backtester.py                        # Full analysis
python scripts/backtest/backtester.py --simulate --save       # Strategy comparison + save
python scripts/backtest/backtester.py --sport mlb             # MLB only
python scripts/backtest/backtester.py --category total        # Totals only
python scripts/backtest/backtester.py --confidence medium     # Medium confidence only
python scripts/backtest/backtester.py --min-edge 0.10         # Edge >= 10%
python scripts/backtest/backtester.py --after 2026-04-01      # Recent trades only
```

Reports: equity curve, max drawdown, Sharpe ratio, profit factor, win/lose streaks, breakdowns by sport/category/confidence/edge bucket, calibration curve (predicted prob vs actual win rate), strategy simulation comparing filter strategies.

Flags: `--sport`, `--category`, `--confidence`, `--min-edge`, `--after`, `--simulate`, `--save`, `--quiet`.

---

## Web Dashboard

```bash
streamlit run webapp/app.py
```

3 pages: Scan & Execute (with confirmation dialog), Portfolio (auto-refresh, P&L color coding), Settle & Report (settlement history, CSV export). Dark terminal theme, favorites, quick-scan sidebar.

---

## Safety Rules

1. **Always check status first** before any scan or bet — if daily loss limit is breached, STOP.
2. **Never execute without confirmation** unless `--execute`/`--go` was explicitly passed.
3. **Preview is the default** — every scan shows a table first, orders only placed with `--execute`.
4. **Twelve risk gates enforced** — daily loss, position count, edge (per-sport), market price floor (3.5, R7 — $0.10), score, min confidence (4.5), NO-side favorite guard (4.6), duplicate ticker, per-event cap, series dedup, max bet size, bet ratio cap. All checked before every order. Plus the resting-order janitor at the top of every live execute run.
5. **API keys are in `.env`** — never print, log, or expose them.
