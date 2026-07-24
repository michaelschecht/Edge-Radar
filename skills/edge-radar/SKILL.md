---
name: edge-radar
description: Unified Edge-Radar skill for scanning markets, placing wagers, managing portfolio, settling bets, and researching edge across Kalshi sports, futures, and prediction markets plus Polymarket US. Covers all scripts, filters, risk gates, and workflows.
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
| `daily-summary`, `morning`, `digest` | **Daily Summary** | Morning P&L digest — yesterday + open exposure + today pending + 7d context |
| `settle`, `results`, `pnl` | **Settle & Report** | Settle completed bets, show P&L |
| `reconcile`, `sync` | **Reconcile** | Compare local log vs Kalshi API |
| `risk`, `limits`, `dashboard` | **Risk Dashboard** | Full risk check with limits |
| `scan <filter>`, `check <filter>`, `find <filter>` | **Scan** | Preview opportunities (no execution) |
| `bet <filter>`, `play <filter>`, `wager <filter>` | **Scan & Bet** | Scan then prompt to execute |
| `detail <TICKER>`, `lookup <TICKER>` | **Detail** | Deep dive on a single market |
| `odds <sport>` | **Raw Odds** | Show sportsbook odds without edge detection |
| `data <type>` | **Market Data** | Fetch stock/crypto/prediction market data |
| `backtest`, `analyze`, `performance` | **Backtest** | Run backtester on settled trades |
| `polymarket`, `poly`, `pm` | **Polymarket Scan** | Polymarket US futures + games — see the Polymarket section below |
| Any sport/market name alone (e.g., `nba`, `mlb`, `crypto`) | **Scan** | Default to scan for that filter |

### Flag Parsing

| Flag | Default | Description |
|------|---------|-------------|
| `--unit-size N` or `$N` (dollar amount) | `$1.00` | Dollar amount per bet |
| `--max-bets N` | `5` | Maximum bets to place |
| `--min-edge N` | `0.03` global; `0.04` NBA/NCAAB/MLB | Minimum edge. Per-sport overrides via `MIN_EDGE_THRESHOLD_<SPORT>` env. NBA/NCAAB/MLB run a `0.04` peer floor (lowered from 0.06 on 2026-06-14 — the 06-03/06-05 edge-matching fixes de-inflated edges, so the higher floor was double-correcting the model's ~15% over-claim; 2-4 week experiment, recalibrate on fresh post-fix data). |
| `--execute`, `--go`, `--send-it` | off | Skip preview, execute immediately |
| `--dry-run`, `--preview` | on (default) | Preview only, no orders |
| `--save` | off | Save results as markdown report to `reports/` |
| `--date DATE` | (none) | Filter by date: `today`, `tomorrow`, `YYYY-MM-DD`, `mar31`, `03-30` |
| `--exclude-open` | off | Skip markets with existing open positions |
| `--budget X` | (none) | Max total batch cost — `10%` (of bankroll) or `15` (flat dollars). Proportionally scales down contracts to stay within budget while preserving Kelly edge-weighting |
| `--pick '1,3,5'` | (none) | Cherry-pick specific rows from preview |
| `--ticker TICKER` | (none) | Target a specific Kalshi ticker |
| `--category CAT` | (none) | Market type: `game`, `spread`, `total`, `player_prop` |
| `--top N` | `20` | Number of opportunities to show |
| `--detail` | off | Show per-trade breakdown (for reports) |
| `--from-file` | off | Load from saved watchlist |
| `--report-dir PATH` | (none) | Override report output directory (used in batch jobs) |
| `--rescan` | off | R26 (2026-04-29): force a live rescan even when a fresh scan-cache exists. Default behavior for `--execute --pick/--ticker` is to replay the cached preview so row indices match what you saw — this opts out per-call. |

---

## Unified Scanner Entry Point

**All scans should use `scripts/scan.py`** — the unified router that forwards to the correct scanner:

```bash
python scripts/scan.py sports --filter mlb --date today --save
python scripts/scan.py sports --unit-size .5 --max-bets 5 --budget 10% --date today --exclude-open --execute
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py prediction --filter crypto
python scripts/scan.py polymarket --filter all --min-edge 0.01 --top 40 --save
```

Market types: `sports`, `futures`, `prediction`, `polymarket`.
Aliases: `sport` = `sports`, `pred` = `prediction`, `poly` / `pm` = `polymarket`.

The `scan` subcommand is auto-inserted if omitted. All flags are forwarded directly.

### Makefile Shortcuts

For quick access, the Makefile provides 22 targets:

```bash
make scan-mlb          # Scan MLB today, exclude open, save report
make scan-nba          # Scan NBA
make scan-nhl          # Scan NHL
make scan-nfl          # Scan NFL
make scan-sports       # All sports
make scan-futures      # All futures
make scan-predictions  # All prediction markets
make scan-all          # Everything
make status            # Portfolio status
make risk              # Risk dashboard
make settle            # Settle completed bets
make report            # P&L report
make reconcile         # Compare local log vs API
make backtest          # Full backtest analysis
make backtest-sim      # Strategy-comparison simulation + save
make doctor            # Environment validator (shows the config actually in force)
make test              # Run full test suite (651 tests)
make test-quick        # Quick test run (stop on first failure)
make lint-config       # Guard: block new os.getenv from bypassing app/config.py
make install           # Install dependencies
make hooks             # Install pre-commit hooks
make help              # List all targets
```

> There is **no `make` target for Polymarket** — use `scan.py polymarket` directly.

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
| `pga` | PGA Golf (majors) | Yes — routes to futures (4 majors only) |
| `ipl` | IPL Cricket | Browse only |
| `cs2`, `lol`, `esports` | Esports | Browse only |
| `tennis`, `wimbledon` | ATP + WTA match-winner | Yes — needs date-tolerant matching (`_is_tennis_market()`), since tennis tickers don't carry a reliable start time |
| `wc`, `worldcup` | World Cup (`KXWCSPREAD` etc.) | Yes |

37 filter shortcuts are registered in `FILTER_SHORTCUTS` (`scripts/kalshi/edge_detector.py`) — the table above covers the common ones. When unsure, read that dict rather than guessing.

**Market types per sport.** Most sports scan all three of moneyline / spread / total. **MLB was moneyline-only until 2026-07-20**, when `KXMLBSPREAD` + `KXMLBTOTAL` were wired in (they'd launched on Kalshi after MLB was first integrated in March and were silently absent from the maps). First scan after the fix went 106 → 407 MLB markets. Deep-bracket MLB Unders are a young, uncalibrated sub-population — treat high claimed edges there with suspicion until more settle.

### Futures (Championships) — `futures_edge.py`

| Filter | What It Scans | Edge Detection |
|--------|---------------|----------------|
| `futures` | All futures | Yes (where available) |
| `nfl-futures` / `superbowl` | Super Bowl champion | Yes |
| `nba-futures` | NBA Finals + conferences | Yes |
| `nhl-futures` | Stanley Cup + conferences | Yes |
| `mlb-futures` | World Series + playoffs | Yes |
| `ncaab-futures` | NCAAB MOP | Yes |
| `golf-futures` | Golf major winners (4 majors only) | Yes |

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

### Polymarket US — `polymarket_futures_edge.py` + `polymarket_games_edge.py`

Second venue, live since 2026-07-23. This is the **CFTC-regulated Polymarket US** product (iOS app + KYC), which authenticates with **Ed25519 API keys against `api.polymarket.us`** — *not* the international EIP-712 / `py-clob-client` scheme. If you find yourself reaching for `py-clob-client`, you're on the wrong API.

```bash
python scripts/scan.py polymarket --filter all --min-edge 0.01 --top 40 --save
python scripts/scan.py polymarket --filter futures
python scripts/scan.py polymarket --filter nhl --max-bets 2 --budget 10% --save --execute
```

| Filter | Scans |
|---|---|
| `all` *(default)* | futures + games |
| `futures` | all championship futures |
| `worldcup`, `nfl`, `mlb`, `nba`, `nhl` | that sport's championship future |
| `games` | all per-game markets |
| `mlb-games`, `nfl-games`, `nba-games`, `nhl-games` | that sport's per-game markets |

**Two things constrain this venue — know both before reporting on it:**

1. **Only futures are orderable.** Game rows are Gamma-sourced, carry no US `market_slug`, and are auto-excluded from execution — they exist as dry-run evidence only until the seasonal US repoint. A scan will say so explicitly: `N opportunit(ies) without a US market_slug (Gamma-sourced games) excluded from execution`.
2. **Two-flag execution rule.** Orders place for real only when **`DRY_RUN=false` AND `POLYMARKET_DRY_RUN=false`**. The venue flag defaults to `true`, so Polymarket can be halted without touching Kalshi. **Both are currently false — the venue is live.** Anything else returns `dry_run_blocked`.

Beyond that it uses the **same shared risk gates and Kelly sizing as Kalshi**, plus one venue-specific step: a **minimum-share bump** (`min_order_shares` from the venue's `minimumTradeQty`) applied *after* the sizing caps, which rejects with `below_venue_min_shares` if bumping would breach `MAX_BET_SIZE` or bankroll.

Every run appends to `data/polymarket/dryrun_log.jsonl` (including zero-opportunity runs — that's the edge-proving evidence trail); markdown lands in `reports/Polymarket/` only when rows surface.

> **No Polymarket order has ever filled.** As of 2026-07-23 every observed candidate is rejected at Gate 3 with edges of 1.1–2.6% against the 3% floor. Do not describe this venue as "trading" — it is live but has never transacted. Note also that Gate 1 (daily loss) deliberately spans both venues.

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

## Action: Daily Summary

Morning P&L digest. Joins yesterday's settlements (rolling 24h window) with currently open trade-log positions and today's pending events; optional live Kalshi balance + 7-day rolling context. Empty-day proof-of-life — still renders every section so a zero-bet day shows "the system ran" rather than going silent.

```bash
.venv/Scripts/python.exe scripts/kalshi/daily_summary.py --save
.venv/Scripts/python.exe scripts/kalshi/daily_summary.py --hours 48 --save     # custom window
.venv/Scripts/python.exe scripts/kalshi/daily_summary.py --no-bankroll         # skip Kalshi balance fetch
```

| Flag | Default | Description |
|------|---------|-------------|
| `--hours N` | `24` | Rolling-window size for "yesterday" |
| `--save` | off | Write to `reports/Performance/daily_summary_YYYY-MM-DD.md` |
| `--out PATH` | (none) | Explicit output path (overrides `--save` default) |
| `--no-bankroll` | off | Skip live Kalshi balance fetch (offline-safe) |

Sections: **Yesterday** (W-L, P&L, ROI, per-sport table, top-win/top-loss), **Open Exposure** ($ at risk + per-sport split), **Pending Today** (open positions whose game datetime lands today PST), **Context** (live Kalshi balance + 7-day rolling line: WR, P&L, Brier).

**Automated cadence (U2, 2026-04-30):** `\Edge-Radar\Daily-Summary` runs daily at 4:50 AM PT and `\Edge-Radar\Email-Daily-Summary` emails it at 5:00 AM PT. The digest lands before the 5:05 AM same-day execute so "Open Exposure" reflects overnight carry rather than today's new fills.

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
| `--report reconciliation` | R5 (2026-04-27): trade-log ↔ settlement join audit. Counts, `trade_id` overlap %, orphan-window dates, and per-field coverage matrix for the R5 settlement-schema additions. |
| `--gate` | Exit code 1 if limits breached (for automation) |
| `--save` | Save dashboard as markdown |

---

## Action: Detail (Single Market Deep Dive)

```bash
python scripts/kalshi/edge_detector.py detail <TICKER>
```

Shows: matched sportsbook odds, de-vigged probabilities, fair value, edge, and confidence breakdown.

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
python scripts/kalshi/fetch_market_data.py --type <type> [--symbols SYM1 SYM2] [--source kalshi]
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
  [--save]
```

**Direct scanner access** (still works for all scanners):
```bash
python scripts/kalshi/edge_detector.py scan [flags]
python scripts/kalshi/futures_edge.py scan [flags]
python scripts/prediction/prediction_scanner.py scan [flags]
```

### Step 3: Present Results

The scan table shows: **Sport** (NBA/NHL/MLB/etc.), **Bet** (matchup), **Type** (ML/Spread/Total/Prop), **Pick** (e.g., "Spurs win", "Over 220.5", "Blazers -7.5"), **When**, **Mkt**, **Fair**, **Edge**, **Conf**, **Score**, **Gate** (R18 — `ok` or a short label like `score` / `conf` / `no-fav` / `pred-off` / `live-off` showing which risk gate would reject this row at execute time).

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

> **R26 row-order lock (sports scanner only, 2026-04-29):** When `--execute` is paired with `--pick` or `--ticker`, the executor replays the previous preview's cached rows from `data/cache/last_scan.json` instead of rescanning live. Row indices map to the same tickers the user saw — drift between calls no longer reorders the table. Re-use the same filter args (`--filter`, `--date`, `--exclude-open`, `--min-edge`, `--top`) on both calls; if any change, a bold red banner warns that picks reference a NEW ranking and the executor rescans. Pass `--rescan` to opt out (force live rescan); set `SCAN_CACHE_ENABLED=false` in `.env` to disable globally.

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
| `/edge-radar polymarket` | `scan.py polymarket --filter all --save` |
| `/edge-radar poly futures` | `scan.py polymarket --filter futures` |
| `/edge-radar pm nhl` | `scan.py polymarket --filter nhl` |
| `/edge-radar weather --min-edge 0.05` | `scan.py prediction --filter weather --min-edge 0.05` |
| `/edge-radar status` | `kalshi_executor.py status` |
| `/edge-radar settle` | `kalshi_settler.py settle` + `report --detail` |
| `/edge-radar reconcile` | `kalshi_settler.py reconcile` |
| `/edge-radar risk` | `risk_check.py` |
| `/edge-radar detail KXNBAGAME-26MAR25LALBOS-LAL` | `edge_detector.py detail KXNBAGAME-26MAR25LALBOS-LAL` |
| `/edge-radar bet nba --go --unit-size 1 --max-bets 3` | `scan.py sports --filter nba --execute --unit-size 1 --max-bets 3` (no confirmation needed) |
| `/edge-radar scan all` | `scan.py sports` (no filter = all sports) |
| `/edge-radar scan all --date today` | `scan.py sports --date today` (all sports, today only) |
| `/edge-radar bet all --unit-size .5 --max-bets 10` | `scan.py sports --unit-size .5 --max-bets 10` then confirm then `--execute` |
| `/edge-radar bet mlb --pick '1,3,5'` | `scan.py sports --filter mlb --execute --pick '1,3,5'` (R26: replays last `--filter mlb` preview from `data/cache/last_scan.json`; mismatched filter args trigger a red banner + rescan) |
| Two-call pattern (preview, then pick) | `scan.py sports --filter mlb --exclude-open` (preview), then `scan.py sports --filter mlb --exclude-open --pick '1,3' --execute` — keep the same flags so R26 replays cleanly. Add `--rescan` to force a live rescan. |
| `/edge-radar bet mlb --budget 10% --max-bets 5` | `scan.py sports --filter mlb --budget 10% --max-bets 5` then confirm then `--execute` |
| `/edge-radar bet all --budget 15 --unit-size .5` | `scan.py sports --budget 15 --unit-size .5` then confirm then `--execute` |

---

## Report Output

When `--save` is used, the report format depends on whether `--unit-size` was passed:

**With `--unit-size` (execution report):** Sport, Bet, Type, Pick, Qty, Price, Cost, Edge, total cost.

**Without `--unit-size` (scan report):** Sport, Bet, Type, Pick, When, Mkt, Fair, Edge, Conf, Score, Gate.

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
- **Kelly fraction:** `KELLY_FRACTION` in `.env`. Code default 0.25; **live value is 1** (set 2026-07-22 to size longshots up). Note it is *not* full Kelly — it is divided by `batch_size = min(len(opportunities), --max-bets)`, so at the schedulers' `--max-bets 5` the effective multiplier is **0.20 Kelly**.
- **Unit size:** code default $1.00, **live `.env` is $0.50** (minimum per bet, overridable with `--unit-size`)
- **Max bet size:** code default $100, **live `.env` is $15** (gate 8 — sizing cap, not reject)
- **Bet ratio cap:** code default 3.0x, **live `.env` is 5x** batch median cost (gate 9 — sizing cap, not reject)

> **Always run `make doctor` (or `python scripts/doctor.py`) before quoting a limit.** The live `.env` overrides many shipped defaults — the account is small (~$89 bankroll), so `MAX_DAILY_LOSS` is $30 not $250, and several floors are tuned down accordingly. Quoting the code default as if it were in force is the most common error in this area.
- **Max per event:** 2 positions on the same game (reject gate)
- **Series dedup (C5, 2026-04-18; R9, 2026-04-27):** Reject a new bet if the same matchup (sport + team pair, date-agnostic) was bet within the dedup window. Global default `SERIES_DEDUP_HOURS=48`; per-sport overrides via `SERIES_DEDUP_HOURS_<SPORT>` (live: MLB=72, NHL=72 to cover 3-game series cycles after F12 — a NYM/LAD MLB pair bet 49h apart slipped the global window and both lost). Catches consecutive-night series bleeds like the LA Angels @ NY Yankees Apr 13/14/15 pattern. 0 disables (global or per-sport).
- **Daily loss limit:** code default $250, **live `.env` is $30** (reject gate). Spans both venues by design.
- **Max open positions:** 50 (reject gate)
- **Minimum edge (C3, 2026-04-18; lowered 2026-06-14):** 3% global; **4% MLB/NBA/NCAAB** (per-sport overrides via `MIN_EDGE_THRESHOLD_<SPORT>` env). Lowered 0.06 → 0.04 on 2026-06-14 after the 06-03/06-05 edge-matching fixes de-inflated edges — the higher floor had been double-correcting the model's ~15% over-claim (running as a 2-4 week experiment; recalibrate on fresh post-fix data). Rejection message shows the sport-specific floor in use.
- **Minimum market price (R7, 2026-04-22):** Gate 3.5 rejects bets priced below `MIN_MARKET_PRICE`. Hard floor with no edge/confidence exception — F10 from the 14-day review showed sub-10¢ bets at 1W-3L with the model claiming "+50% edge" on 8-10¢ longshots. `MIN_MARKET_PRICE=0` disables. **The floor has moved twice: 0.06 → 0.12 (2026-07-14, after a 30d window showed sub-15¢ at 0W-21L) → 0.10 (2026-07-22, deliberate re-opening of the longshot lane). Live value is 0.10.** Treat the current setting as an open experiment: full-history sub-15¢ is 6W-47L / 53 bets, and its headline +47.5% ROI is 99% a single trade — the lane is roughly breakeven ex that winner, and −100% in June / −33% in July. Report it with and without the top winner.
- **Minimum composite score:** 6.0 (reject gate, confidence is factored into composite)
- **Minimum confidence (R3, 2026-04-21):** Gate 4.5 rejects opportunities below `MIN_CONFIDENCE` (default `medium`). Values: low | medium | high. Low-confidence bets realized 0W-3L / -105% ROI across two review windows.
- **NO-side favorite guard (R1, 2026-04-21):** Gate 4.6 rejects NO bets priced below `NO_SIDE_FAVORITE_THRESHOLD=0.25` unless edge ≥ `NO_SIDE_MIN_EDGE=0.25` AND confidence=high. Plus a sizing dampener: NO bets priced below `NO_SIDE_KELLY_PRICE_FLOOR=0.35` are sized at `NO_SIDE_KELLY_MULTIPLIER=0.5` of Kelly (half-Kelly). All 13 high-edge losers in the 14-day window were NO-side.
- **NO-side global edge floor (R28, 2026-06-23):** Gate 4.6b. On top of R1's favorite guard, **every** NO bet must clear `NO_SIDE_MIN_EDGE_GLOBAL=0.08` — the effective NO floor is `max(per-sport floor, 8%)`. A 90-day review put NO at −7% ROI against YES at +48%. `NO_SIDE_KELLY_MULTIPLIER_GLOBAL` (default 1.0 = off) can additionally shrink all NO sizing. Set the floor to 0 to disable. This gate is doing real work — it is the binding constraint on most NO-side totals.
- **Live/in-play safety gate (L1, 2026-07):** Gate 4.8 rejects opportunities on already-started games (`is_game_started`) unless `ALLOW_LIVE_BETS=true`. Default off. Preview label: `live-off`. Two supporting knobs for when it *is* enabled: `MAX_LIVE_BOOK_AGE_SECONDS=1200` drops bookmakers whose in-play line is staler than 20 min from the consensus, and `MIN_LIVE_CONSENSUS_BOOKS=3` skips a game whose consensus the stale filter thinned below 3 fresh books (fires only when staleness actually removed books; pre-game is unaffected). `ODDS_LIVE_TTL_SECONDS=45` shortens both cache layers when a sport response contains an in-play event.
- **NBA consensus-book minimum (R29, 2026-06-23):** NBA games with fewer than `MIN_CONSENSUS_BOOKS_NBA=8` agreeing books drop to `low` confidence, which Gate 4.5 then rejects. Filters stale recreational lines. 0 disables.
- **High-confidence composite cap (C4, 2026-06-24):** The sports composite weight caps `high` to `medium` (`{low:3, medium:6, high:6}`), so "high" no longer earns a score premium — it can't float no-signal bets up the `--max-bets` queue or help clear Gate 4. The 306-bet review found High at 41.5% WR / +13.5% ROI vs Medium 53.2% / +44.4%, and — decisively — High losing to Medium *at equal claimed edge* (5–10% bucket: 34% vs 63% WR). A tight ≥8-sharp-book consensus means the price is efficient, so a large model edge against it is more likely model error than signal. The `high` **label** is retained and still gates NO-favorite bets at 4.6. Sizing never used confidence. **Scoped to sports only** — futures and prediction earn "high" by different rules and were explicitly out of scope.
- **Futures composite edge scale (C10, 2026-07-23):** The futures composite used `min(10, edge * 20)` (saturating at a 50% edge) while sports used `min(edge / 0.01, 10)` (saturating at 10%) — one term 5x stricter, dating to a copy-paste on the launch-day commit. Clearing `MIN_COMPOSITE_SCORE=6.0` therefore needed ~11% edge at high confidence / 23% medium / 34% low, against championship futures edges that run 1–4% in practice. **Gate 4 was unreachable**, which explains **0 futures bets in 85 logged trades** and made Polymarket US (futures-only) permanently unexecutable. Both paths (`futures_edge.py`, `polymarket_futures_edge.py`) now use the sports scale. Not a floodgate — replayed against 4 days of live Polymarket evidence it approves none of the 9 observed candidates. The futures `high: 9` weight is deliberately untouched (C4 scoped futures out, and there's still no futures settlement data).
- **Calibration staleness TTL (C8, 2026-06-23):** `CALIBRATION_STDEVS_TTL_DAYS=30` caps how old the auto-recalibrated per-sport stdevs in `data/cache/calibration_stdevs.json` may be before the code falls back to hardcoded defaults. Scans log the age on load (`age 17.8 days`) — worth a glance when edges look off.
- **Prediction-market safety gate (R25, 2026-04-24):** Gate 4.7 rejects opportunities where `opp.category` is `crypto`, `weather`, `spx`, `mentions`, `companies`, or `politics` unless `ALLOW_PREDICTION_BETS=true`. Default off. 2026-04-24 audit surfaced that all 6 prediction modules cache stale data with zero TTL, produce nonsense fair values (Miami weather at $1.00 fair on a 1°F window, crypto +80% "edges" on 4¢ tails), and have placed zero of 173 historical settled bets — no calibration data exists. Kept blocked until R25b (TTL caches) and R25c (rebuild one model with tests) are shipped.
- **Resting-order janitor (R4, 2026-04-21):** At the top of any `--execute` run (non-dry-run), resting orders older than `RESTING_ORDER_MAX_HOURS=24` with zero fills are auto-cancelled. Partial/full fills untouched — settler handles them. Piggybacks on the 5AM daily execute task; no new scheduler. **Kalshi deprecated the v1 order endpoints mid-2026** — both placement and cancel were migrated to v2 (`/portfolio/events/orders`); v1 now returns HTTP 410 `deprecated_v1_order_endpoint`. The v1 **GET** order endpoints remain current. If you see 410s in `logs/kalshi_executor_*.log`, they predate the 2026-07-21 cancel migration.
- **Cross-process trade-log lock (M2, 2026-07-20):** `data/history/kalshi_trades.json` is written under a cross-process lock with merge-safe append, so a settle and an execute running concurrently no longer clobber each other. This is what made the hourly settle task safe.
- **Confidence bumps one-way (R13, 2026-04-24):** `_adjust_confidence_with_stats()` in `edge_detector.py` now drops a tier on `contradicts` but no-ops on `supports`. Applies uniformly to team stats, rest/B2B, and sharp-money signals. 30-day calibration showed High-confidence WR (47%) below Medium (53%) and NBA High at 1-6 / -71% ROI — upward bumps correlated with inflated claimed edge, not better outcomes. Base "high" tier still reachable via the ≥8 sharp-books + tight-consensus rule. No env var.
- **File-backed Odds API response cache (R24b, 2026-04-28):** Two-tier cache for The Odds API responses — in-process dict in front of a new file-backed layer at `data/cache/odds/<sport_key>__<markets>.json`. Survives across CLI invocations so back-to-back scans (scheduler bursts, dashboard re-renders) don't refetch the same sport keys. Knobs: `ODDS_CACHE_TTL_SECONDS=300` (5 min default — longer than typical filter-fiddling, shorter than meaningful pre-game line movement; 0 disables), `ODDS_CACHE_ENABLED=true`. Hits log `Odds API file cache hit for X (age Ns, M events)` so cache age is visible. Distinct from R23's quota cache at `data/cache/odds_api_quota.json` — that tracks per-key remaining requests, this caches the actual sportsbook payloads.
- **File-backed scan cache + row-order lock (R26, 2026-04-29):** Each preview's post-dedup, post-risk-gate, post-budget-cap rows are persisted to `data/cache/last_scan.json`. When `--execute --pick/--ticker` is invoked, the executor replays the cached rows instead of rescanning live — so row indices map to the same tickers the user saw in the preview, even if Kalshi prices or composite scores drift between calls. Knobs: `SCAN_CACHE_TTL_SECONDS=600` (10 min default), `SCAN_CACHE_ENABLED=true`. New `--rescan` CLI flag opts out per-call. **Fingerprint mismatch warning:** if any of `{scanner, filter, category, date, exclude_open, min_edge, top}` differ between the preview and the execute call (e.g. `--exclude-open` dropped on the second call), the executor prints a bold red banner explaining `--pick` row numbers will reference a NEW ranking, lists the differing args, and rescans. Pass `--rescan` to silence the warning intentionally. Banner on hit: `Replaying cached preview (N rows, age Xs)`. Motivated by 2026-04-29 user bug where two back-to-back live scans reordered rows and `--pick '1,3,4,5'` placed the wrong bets.
- **Truthful post-pick cost line (R26 follow-up, 2026-04-29):** When `--pick` or `--ticker` is filtering, the summary now prints `Placing N orders, total cost: $X.XX (selected from M-row menu totaling $Y.YY)` — replacing the old misleading `Total cost: $9.40 of $70.99 available` which showed the menu total even when only 3 of 10 rows were actually placed.

Gates 1-7 (including 3.5, 4.5, 4.6, 4.6b, 4.7, 4.8) reject orders outright. Gates 8-9 downsize and approve, logging the approval subtype (`APPROVED`, `APPROVED_CAPPED_MAX_BET`, `APPROVED_CAPPED_BET_RATIO`, `APPROVED_BUMPED_MIN_SHARES`).

Preview rows carry a **Gate** column (R18) naming the first gate that would reject at execute time: `ok` · `edge` (3) · `price` (3.5) · `score` (4) · `conf` (4.5) · `no-fav` (4.6) · `pred-off` (4.7) · `live-off` (4.8).

> **Where these knobs live (post-2026-04-25):** every env var named in this section is typed, defaulted, and validated in `app/config.py` (the single source of truth — see `CONFIG_CENTRALIZATION_SUMMARY.md` and `docs/CHANGELOG.md` 2026-04-25). User-facing surface is unchanged: still set everything in `.env` (or Streamlit secrets on Cloud); same names, same defaults. The lint guard (`make lint-config`) blocks any new `os.getenv` from sneaking back in.

---

## Daily Workflow Reference

### Morning
```bash
.venv/Scripts/python.exe scripts/kalshi/daily_summary.py --save  # U2 (2026-04-30) — yesterday + open exposure + 7d context
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
python scripts/scan.py prediction --filter crypto
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

Installer profiles (`install_windows_task.py`):

| Profile | Schedule | Description |
|---------|----------|-------------|
| `daily-summary` | 4:50 AM PT | Morning P&L digest (U2, 2026-04-30) — yesterday + open exposure + today pending + 7d context. Emailed at 5:00 AM PT |
| `scan` | 8:00 AM | Preview scan — saves report, no bets |
| `execute` | 8:00 AM | Scan + execute — places live orders |
| `settle` | 11:00 PM | Settle bets, update P&L |
| `next-day` | 9:00 PM | Scan + execute tomorrow's games |
| `calibration` | 2:00 AM, 1st of month | 30-day calibration report (R16) — Brier, calibration curve, prescriptive recommendations |

**What is actually registered** under `\Edge-Radar-MikesAILab\` differs from the installer profiles above — the live schedule has grown well past them. Read it from the machine rather than this table:

```powershell
Get-ScheduledTask -TaskPath "\Edge-Radar-MikesAILab\*" |
  ForEach-Object { $i = $_ | Get-ScheduledTaskInfo
    [PSCustomObject]@{ Task=$_.TaskName; State=[string]$_.State
                       LastRun=$i.LastRunTime; Result=$i.LastTaskResult; NextRun=$i.NextRunTime } } |
  Sort-Object LastRun -Descending | Format-Table -AutoSize
```

As of 2026-07-23 the live execution cadence is four Kalshi runs a day plus one Polymarket run, each paired with an email report ~20 min later:

| Time (PT) | Task | Notes |
|---|---|---|
| 4:50 AM | `Daily-Summary` | emailed 5:00 AM |
| 5:05 AM | `All-Sports-SameDay-Execution` | `--date today` |
| 9:40 AM | `Daily-Polymarket-Execution` | **passes `--execute`** — renamed from `Daily-Polymarket-DryRun`, capped at `--max-bets 2 --budget 10%` |
| 11:00 AM | `All-Sports-NoDateFilter-Midday-Execution` | no date filter — *can bet games several days out* |
| 2:00 PM | `All-Sports-SameDay-Late-Execution` | |
| 8:30 PM | `All-Sports-NextDay-Execution` | `--date tomorrow` |
| hourly :35 | `Hourly-Settle` | U1 (2026-07-20) |
| 11:00 PM | `NightlySettle` + `Reconcile` | nightly backstop |
| weekly/monthly | `Backtest`, `Weekly-Analysis`, `Calibration`, `MonthlyCalibration`, `WeeklyAccountGraph` | |

`Weekly-Futures-Execution` is **Disabled** (the paired `Email-Weekly-Futures` report still runs). `R8-Review` and `U2-Review` are registered with one-shot triggers whose start boundaries have passed — they have **never run and will never fire** until re-registered.

> **The three intraday Kalshi executes each pass `--budget 12%` — this is deliberate** (operator-confirmed 2026-07-23). Stale `.bat` headers had long described a de-escalating 12% → 8% → 5% ladder that was never implemented and is not wanted; the headers were corrected to match the flags. **Don't "fix" these back down to the ladder.** The shared ceiling is ~36% of bankroll per day in theory, but `--budget` is a per-batch cap and Gate 5 (`--exclude-open`) plus series dedup keep real deployment to a few dollars a day.

### Bat Scripts (Manual)

```bash
# Preview only (no bets)
scripts\schedulers\same_day_executions\same_day_scan.bat

# Scan + execute (places live orders)
scripts\schedulers\same_day_executions\same_day_execute.bat
```

Config: `--unit-size .5`, `--max-bets 5`, `--budget 12%`, `--date today`, `--exclude-open`, `--save`.

> `scripts/schedulers/*` is **gitignored** — the `.bat` files are local-only and won't appear in `git status` or diffs. Edits there don't propagate to a fresh clone. Only `scripts/schedulers/automation/*.py` is tracked.

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

Orders are logged to `data/history/kalshi_trades.json` with **fill-based accounting**:
- `requested_contracts` / `requested_cost` — what we asked for
- `filled_contracts` / `filled_cost` — what the exchange actually executed
- `fill_status` — `resting` | `partial` | `filled`
- `venue` — `kalshi` | `polymarket` (added with PM2c; records written before that are Kalshi and lack the field)

Resting orders (zero fills) are excluded from exposure calculations and settlement. The settler, risk dashboard, and P&L reports all use filled values, not requested. Writes go through a cross-process lock (M2) so concurrent settle/execute merge safely.

> **The trade log accumulates orphans that never close out.** Two known kinds: records with `status: "error"` (an API rejection — e.g. six World Cup rows from the 2026-06-20 v1→v2 410 outage, four of which were successfully re-placed two days later) and zero-fill `resting` orders whose market has since closed. Both sit in the log as permanently "open." This does **not** affect risk gating — Gate 5 reads live positions from the Kalshi API, not the log — but it inflates any open-position count derived from the log, so cross-check against `kalshi_executor.py status` before reporting exposure.

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
4. **Fifteen risk gates enforced** — daily loss, position count, edge (per-sport), market price floor (3.5, R7), composite score, min confidence (4.5), NO-side favorite guard (4.6, R1), NO-side global edge floor (4.6b, R28), prediction-market safety (4.7, R25), live/in-play safety (4.8, L1), duplicate ticker, per-event cap, series dedup, max bet size, bet ratio cap — plus the venue min-share bump on Polymarket. All checked before every order, on both venues. Plus the resting-order janitor at the top of every live execute run.
5. **API keys are in `.env`** — never print, log, or expose them.
6. **R26 row-order lock for `--pick`** — when running `--execute --pick/--ticker`, keep filter args identical to the previous preview so the cached row→ticker mapping replays. If anything differs, the executor prints a bold red banner and rescans (different rows). Pass `--rescan` only when you intend a fresh ranking.
7. **R8 cross-category dedup is opt-in** — by default ML+Total+Spread on the same game survive as 3 distinct bets (current behavior). To collapse them per sport, set `CROSS_CATEGORY_DEDUP_<SPORT>=true` (e.g. `CROSS_CATEGORY_DEDUP_NBA=true`); when active, the dedup banner names the sports (`Deduped correlated brackets: 12 -> 8 opportunities (cross-category: ['nba'])`). Per-sport `false` overrides the global flag in either direction.
