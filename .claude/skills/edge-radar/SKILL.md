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
| Any sport/market name alone (e.g., `nba`, `mlb`, `crypto`) | **Scan** | Default to scan for that filter |

### Flag Parsing

| Flag | Default | Description |
|------|---------|-------------|
| `--unit-size N` or `$N` (dollar amount) | `$1.00` | Dollar amount per bet |
| `--max-bets N` | `5` | Maximum bets to place |
| `--min-edge N` | `0.03` | Minimum edge threshold (3%) |
| `--execute`, `--go`, `--send-it` | off | Skip preview, execute immediately |
| `--dry-run`, `--preview` | on (default) | Preview only, no orders |
| `--save` | off | Save results as markdown report to `reports/` |
| `--date DATE` | (none) | Filter by date: `today`, `tomorrow`, `YYYY-MM-DD`, `mar31`, `03-30` |
| `--exclude-open` | off | Skip markets with existing open positions |
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
make test              # Run full test suite (83 tests)
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

Report the key numbers clearly: balance, number of open positions, today's P&L, any resting orders. Positions now display readable matchups and game dates (not raw tickers). Done.

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
```

Add `--save` to persist the report as markdown. Reports include formatted tables with bold values and code-formatted tickers.

Summarize: total settled, wins, losses, net P&L, ROI, best/worst bets. Done.

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

Show the opportunity table from the scan output. Explain:
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
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>] [--date <DATE>] [--exclude-open]
```

**Futures:**
```bash
python scripts/scan.py futures \
  --filter <sport>-futures --execute \
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>]
```

**Prediction:**
```bash
python scripts/scan.py prediction \
  --filter <category> --execute \
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>]
```

**Polymarket cross-reference:**
```bash
python scripts/scan.py polymarket \
  --filter <category> --execute \
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
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
| `/edge-radar bet mlb --pick '1,3,5'` | `scan.py sports --filter mlb --execute --pick '1,3,5'` |

---

## Report Output

When `--save` is used, all scanners generate **markdown reports** with formatted tables:

| Scanner | Report Path |
|---------|-------------|
| Sports | `reports/Sports/{date}_{sport}_sports_scan.md` |
| Futures | `reports/Futures/{date}_{category}_futures_scan.md` |
| Predictions | `reports/Predictions/{date}_{category}_prediction_scan.md` |
| Settle/P&L | `reports/` (markdown with formatted tables) |

Reports include: readable matchups, game date/time, edge%, fair price, market price, confidence, composite score.

---

## Risk Limits (Current)

- **Max bet:** $5 per position (hard cap)
- **Unit size:** $1.00 default
- **Daily loss limit:** $250
- **Minimum edge:** 3%
- **Minimum composite score:** 6.0
- **Max open positions:** 10

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

### Scheduled Morning Scans

Batch files in `scripts/schedulers/morning_scans/` run per-sport scans and save reports:

```bash
scripts/schedulers/morning_scans/mlb_morning_scan.bat
scripts/schedulers/morning_scans/nba_morning_scan.bat
scripts/schedulers/morning_scans/nfl_morning_scan.bat
scripts/schedulers/morning_scans/nhl_morning_scan.bat
```

These use `--report-dir` to save to `reports/Sports/schedulers/<sport>/`.

### Daily Edge Email

```bash
python scripts/custom/send_daily_email.py
```

Sends an HTML-formatted daily report via AgentMail, reading from saved scheduler reports.

### Daily All-Sport Scan

```bash
python scripts/schedulers/automation/daily_sports_scan.py
```

### Windows Task Scheduler (8 AM daily)

```bash
python scripts/schedulers/automation/install_windows_task.py install
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

## Safety Rules

1. **Always check status first** before any scan or bet — if daily loss limit is breached, STOP.
2. **Never execute without confirmation** unless `--execute`/`--go` was explicitly passed.
3. **Preview is the default** — every scan shows a table first, orders only placed with `--execute`.
4. **Position limits enforced** — no single bet exceeds $5, no more than 10 open positions.
5. **API keys are in `.env`** — never print, log, or expose them.
