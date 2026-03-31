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
| `--save` | off | Save results/reports to disk |
| `--date DATE` | (none) | Filter by date: `today`, `tomorrow`, `YYYY-MM-DD`, `mar31` |
| `--exclude-open` | off | Skip markets with existing positions |
| `--pick '1,3,5'` | (none) | Cherry-pick specific rows from preview |
| `--ticker TICKER` | (none) | Target a specific Kalshi ticker |
| `--category CAT` | (none) | Market type: `game`, `spread`, `total`, `player_prop` |
| `--cross-ref` | off | Cross-reference against Polymarket |
| `--top N` | `20` | Number of opportunities to show |
| `--detail` | off | Show per-trade breakdown (for reports) |
| `--from-file` | off | Load from saved watchlist |

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

Report the key numbers clearly: balance, number of open positions, today's P&L, any resting orders. Done.

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

Add `--save` to persist the report as markdown.

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

Full portfolio risk check with limit status.

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

**Sports (game betting):**
```bash
python scripts/kalshi/edge_detector.py scan \
  [--filter <sport>] \
  [--category <game|spread|total|player_prop>] \
  [--min-edge <threshold>] \
  [--top <N>] \
  [--date <DATE>] \
  [--exclude-open] \
  [--save]
```

**Futures (championships):**
```bash
python scripts/kalshi/futures_edge.py scan \
  [--filter <sport>-futures] \
  [--min-edge <threshold>] \
  [--top <N>] \
  [--date <DATE>] \
  [--exclude-open] \
  [--save]
```

**Prediction markets:**
```bash
python scripts/prediction/prediction_scanner.py scan \
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
python scripts/polymarket/polymarket_edge.py scan \
  [--filter <category>] \
  [--min-edge <threshold>] \
  [--min-match <score>] \
  [--top <N>] \
  [--save]
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

Once confirmed, re-run the same scanner command with `--execute` added:

**Sports:**
```bash
python scripts/kalshi/edge_detector.py scan \
  --filter <sport> --execute \
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>] [--date <DATE>] [--exclude-open]
```

**Futures:**
```bash
python scripts/kalshi/futures_edge.py scan \
  --filter <sport>-futures --execute \
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>]
```

**Prediction:**
```bash
python scripts/prediction/prediction_scanner.py scan \
  --filter <category> --execute \
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>]
```

**Polymarket cross-reference:**
```bash
python scripts/polymarket/polymarket_edge.py scan \
  --filter <category> --execute \
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
  [--pick '1,3,5'] [--ticker <TICKER>]
```

**Alternative — Unified executor** (use when loading from file or need `--prediction` shortcut):
```bash
python scripts/kalshi/kalshi_executor.py run \
  [--filter <filter>] [--prediction] [--execute] \
  [--unit-size <N>] [--max-bets <N>] [--min-edge <N>] \
  [--from-file] [--pick '1,3,5'] [--ticker <TICKER>]
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
| `/edge-radar nba` | `edge_detector.py scan --filter nba` |
| `/edge-radar bet mlb --unit-size 2 --max-bets 10` | `edge_detector.py scan --filter mlb --unit-size 2 --max-bets 10` then confirm then `--execute` |
| `/edge-radar mlb --date tomorrow --exclude-open` | `edge_detector.py scan --filter mlb --date tomorrow --exclude-open` |
| `/edge-radar nba --category spread` | `edge_detector.py scan --filter nba --category spread` |
| `/edge-radar nba-futures` | `futures_edge.py scan --filter nba-futures` |
| `/edge-radar superbowl` | `futures_edge.py scan --filter nfl-futures` |
| `/edge-radar crypto` | `prediction_scanner.py scan --filter crypto` |
| `/edge-radar weather --min-edge 0.05` | `prediction_scanner.py scan --filter weather --min-edge 0.05` |
| `/edge-radar polymarket crypto` | `polymarket_edge.py scan --filter crypto` |
| `/edge-radar status` | `kalshi_executor.py status` |
| `/edge-radar settle` | `kalshi_settler.py settle` + `report --detail` |
| `/edge-radar reconcile` | `kalshi_settler.py reconcile` |
| `/edge-radar risk` | `risk_check.py` |
| `/edge-radar detail KXNBAGAME-26MAR25LALBOS-LAL` | `edge_detector.py detail KXNBAGAME-26MAR25LALBOS-LAL` |
| `/edge-radar bet nba --go --unit-size 1 --max-bets 3` | `edge_detector.py scan --filter nba --execute --unit-size 1 --max-bets 3` (no confirmation needed) |
| `/edge-radar scan all` | `edge_detector.py scan` (no filter = all sports) |
| `/edge-radar bet mlb --pick '1,3,5'` | `edge_detector.py scan --filter mlb --execute --pick '1,3,5'` |

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
python scripts/kalshi/kalshi_executor.py status          # Check balance & positions
python scripts/kalshi/kalshi_settler.py settle            # Settle overnight results
python scripts/kalshi/kalshi_settler.py report            # Quick P&L summary
python scripts/kalshi/risk_check.py --report limits       # Check if limits breached
```

### Scanning
```bash
python scripts/kalshi/edge_detector.py scan --filter mlb --date today --exclude-open
python scripts/kalshi/edge_detector.py scan --filter nba
python scripts/kalshi/futures_edge.py scan --filter nba-futures
python scripts/prediction/prediction_scanner.py scan --filter crypto
```

### Executing
```bash
python scripts/kalshi/edge_detector.py scan --filter mlb --execute --unit-size 1 --max-bets 10
python scripts/kalshi/edge_detector.py scan --filter nba --execute --pick '1,3,5'
```

### Evening
```bash
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail --save
python scripts/kalshi/kalshi_settler.py reconcile
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
