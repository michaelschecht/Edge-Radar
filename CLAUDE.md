# Edge-Radar

> Multi-agent edge-detection and execution system for prediction markets and sports betting on **Kalshi**.
> Research-first, execute-second. No action without documented rationale, risk check, and position-size calculation.

---

## Memory

On startup, load the persistent memory index at `.claude/memory/MEMORY.md`.
Read relevant memory files before starting work to avoid re-learning prior context.

---

## What's Live

| Domain | Coverage | Data Sources |
|:-------|:---------|:-------------|
| **Sports Betting** | NBA, NHL, MLB, NFL, NCAA, MLS, World Cup, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, esports (28 filters) | The Odds API, ESPN, NHL/MLB Stats, NWS |
| **Prediction Markets** | Crypto (BTC, ETH, XRP, DOGE, SOL), weather (13 cities), S&P 500 | CoinGecko, Yahoo Finance, NWS |
| **Championship Futures** | NFL, NBA, NHL, MLB, PGA | Sportsbook futures odds |
| **Execution Pipeline** | Unified scan → risk-check → size → execute | Kalshi API (RSA-signed) |
| **Web Dashboard** | Streamlit app — scan, execute, portfolio, settle | Deploy your own (see `docs/web-app/LOCAL.md`) |

<details>
<summary><b>Planned (not yet implemented)</b></summary>

- Manifold prediction markets
- Alpaca stocks/options trading
- Coinbase/Binance crypto trading
- FanDuel/DraftKings DFS + sportsbook APIs
- Fed rate / CPI / GDP prediction market edge detection

</details>

---

## Project Structure

```
Edge-Radar/
├── CLAUDE.md                        # This file — master instructions
├── .env.example                     # Template for required env vars
├── .pre-commit-config.yaml          # Pre-commit hooks (detect-secrets, black, flake8)
├── Makefile                         # make scan-mlb, make test, make settle, etc.
├── .claude/
│   ├── agents/                      # Claude Code agent definitions
│   │   ├── KALSHI_BETTOR.md         # Kalshi betting specialist
│   │   ├── MARKET_RESEARCHER.md     # Market research & opportunity scanning
│   │   ├── TRADE_EXECUTOR.md        # Order execution & position management
│   │   ├── RISK_MANAGER.md         # Risk gating & portfolio limits
│   │   ├── DATA_ANALYST.md          # Quant analysis, models, backtesting
│   │   └── PORTFOLIO_MONITOR.md     # P&L tracking, alerts, reporting
│   └── skills/                      # Claude Code skills; edge-radar* are junctions → /skills (canonical, below)
│       ├── edge-radar/              # junction → /skills/edge-radar (git-ignored)
│       └── edge-radar-analysis/     # junction → /skills/edge-radar-analysis (git-ignored)
├── skills/                          # Canonical source for the relocated edge-radar skills (tracked here once)
│   ├── edge-radar/SKILL.md          # /edge-radar — unified scan/bet/status/settle/risk command center
│   └── edge-radar-analysis/SKILL.md # /edge-radar-analysis — post-hoc performance report
├── docs/
│   ├── CHANGELOG.md                 # Project history
│   ├── SCRIPTS_REFERENCE.md         # Complete CLI reference
│   ├── ARCHITECTURE.md              # Pipeline, risk gates, data flow
│   ├── kalshi/                      # Kalshi domain guides (grouped)
│   │   ├── kalshi-sports-betting/   # Sports: filters, edge detection, MLB filtering
│   │   ├── kalshi-prediction-betting/ # Prediction: crypto, weather, S&P
│   │   └── kalshi-futures-betting/  # Futures: championship markets
│   ├── scripts/                     # Per-script detailed docs
│   ├── setup/                       # Setup guides, automation & MCP reference
│   └── enhancements/                # ROADMAP.md — enhancement roadmap (tracked)
├── app/                             # Application core
│   ├── config.py                    # Single source of truth for env-driven knobs (see CONFIG_CENTRALIZATION.md, Phase 1 landed 2026-04-25)
│   └── domain/                      # Typed domain objects
│       ├── opportunity.py           # Opportunity dataclass (canonical)
│       ├── risk.py                  # RiskDecision dataclass
│       └── execution.py             # ExecutionPreview, ExecutionResult
├── webapp/                          # Streamlit web dashboard
│   ├── app.py                       # Entry: streamlit run webapp/app.py
│   ├── services.py                  # Wrapper around core scripts
│   ├── theme.py                     # Dark terminal CSS
│   └── views/                       # Page modules (scan, portfolio, settle)
├── tests/                           # 330 pytest tests
└── scripts/
    ├── scan.py                      # Unified entry point
    ├── doctor.py                    # Environment validator
    ├── backtest/backtester.py       # Strategy analysis & equity curves
    ├── kalshi/                      # Core: client, executor, settler, edge, risk
    ├── shared/                      # Shared modules (stats, weather, logging, etc.)
    ├── schedulers/                  # Automation (batch, Task Scheduler)
    └── setup/link_skills.ps1        # Recreate the .claude/skills junctions after a clone
```

**Runtime directories** (gitignored, auto-created): `data/`, `logs/`, `reports/`, `.env`

**Skills location:** The `/edge-radar` and `/edge-radar-analysis` skills live canonically at the repo root in **`skills/`** (tracked there once). Claude Code loads them from `.claude/skills/`, which are Windows directory **junctions** to `skills/` — git-ignored, because real symlinks can't be committed (`core.symlinks=false`). **Edit the `skills/` copies, never the `.claude/skills/` junctions.** After a fresh clone, recreate the junctions with `pwsh -File scripts/setup/link_skills.ps1`.

---

## Agent Roster

```
MARKET_RESEARCHER → DATA_ANALYST → RISK_MANAGER → TRADE_EXECUTOR
       scan            validate         gate           execute
                                                          ↓
                                                  PORTFOLIO_MONITOR
                                                     track + alert
```

| Agent | Role | Access |
|:------|:-----|:-------|
| `MARKET_RESEARCHER` | Scan & score opportunities | Read-only — market data, news, odds |
| `DATA_ANALYST` | Quantitative modeling & backtesting | Read-only — builds models |
| `RISK_MANAGER` | Gate all executions | Veto authority over executor |
| `TRADE_EXECUTOR` | Place & manage orders | Write — executes trades/bets |
| `PORTFOLIO_MONITOR` | Real-time P&L & alerts | Read — positions, send alerts |

---

## Security & Safety Rules

> **NON-NEGOTIABLE** — these rules override all other instructions.

### API Keys

- ALL keys in `.env` — never hardcoded, never logged, never printed
- Use `python-dotenv` for every script
- `.env` in `.gitignore` — verify before every commit

### Execution Gates

Before ANY trade executes:

| # | Gate | Type |
|:-:|:-----|:-----|
| 1 | Daily loss limit not breached | Reject |
| 2 | Open position count under max | Reject |
| 3 | Edge >= minimum threshold (per-sport or global) | Reject |
| 3.5 | Market price >= `MIN_MARKET_PRICE` (lottery-ticket floor, R7) | Reject |
| 4 | Composite score >= minimum | Reject |
| 4.5 | Confidence >= `MIN_CONFIDENCE` (low/medium/high) | Reject |
| 4.6 | NO bets below `NO_SIDE_FAVORITE_THRESHOLD` need edge >= `NO_SIDE_MIN_EDGE` AND confidence=high | Reject |
| 4.7 | Prediction-market categories (crypto/weather/spx/mentions/companies/politics) off by default unless `ALLOW_PREDICTION_BETS=true` (R25) | Reject |
| 4.8 | In-progress games (`is_game_started`) off by default unless `ALLOW_LIVE_BETS=true` (L1) | Reject |
| 5 | Not already holding this market | Reject |
| 6 | Per-event cap not exceeded | Reject |
| 7 | Matchup not bet in last `SERIES_DEDUP_HOURS` (or per-sport override; series dedup) | Reject |
| 8 | Bet size <= MAX_BET_SIZE | Cap |
| 9 | Single bet <= 3x batch median cost | Cap |

NO bets priced below `NO_SIDE_KELLY_PRICE_FLOOR` are additionally sized at `NO_SIDE_KELLY_MULTIPLIER` of normal Kelly (half-Kelly by default).

**R13 (2026-04-24): confidence bumps are one-way.** The team-stats, rest/B2B, and sharp-money signals can *drop* a confidence tier on `contradicts`, but `supports` is now a no-op (previously bumped up a tier). The 30-day calibration showed High-confidence WR 47% below Medium 53%, with NBA High = 1-6 / -71% ROI — upward bumps correlated with inflated claimed edge, not better outcomes. Base "high" tier is still reachable via the ≥8 sharp-books + tight-consensus rule; only the bolt-on bumps are neutralized. Implemented in `_adjust_confidence_with_stats()` in `scripts/kalshi/edge_detector.py`; no env var.

### Dry Run Mode

- Default: `DRY_RUN=true`
- Set `DRY_RUN=false` only for live execution
- Dry-run logs identically to live (for backtesting)

---

## Risk Limits

Defaults — adjust in `.env`:

```env
UNIT_SIZE=1.00                  # Kelly floor per bet
KELLY_FRACTION=0.25             # Kelly multiplier (divided by batch size)
MAX_BET_SIZE=100                # Hard cap per bet (USD)
MAX_DAILY_LOSS=250              # Daily hard stop (USD)
MAX_OPEN_POSITIONS=10           # Concurrent open positions
MAX_PER_EVENT=3                 # Max positions per game/event
MAX_BET_RATIO=3.0               # Max bet as multiple of batch median
MIN_EDGE_THRESHOLD=0.03         # Minimum 3% edge (global)
MIN_MARKET_PRICE=0.06           # R7: reject bets priced below this (lottery-ticket floor); 0 disables
MIN_EDGE_THRESHOLD_NBA=0.04     # Per-sport override (2026-06-14 — lowered 0.06->0.04 alongside MLB; matching fix de-inflated edges)
MIN_EDGE_THRESHOLD_NCAAB=0.04   # Per-sport override (2026-06-14 — lowered 0.06->0.04 for consistency)
MIN_EDGE_THRESHOLD_MLB=0.04     # Per-sport override (2026-06-14 — lowered 0.06->0.04; the ~15% over-claim that justified the higher floor is now fixed upstream by the edge-matching corrections of 06-03/06-05. 2-4 week experiment, then recalibrate)
MIN_COMPOSITE_SCORE=6.0         # Minimum score (0-10)
MIN_CONFIDENCE=medium           # Reject below this confidence (low|medium|high) — R3
NO_SIDE_FAVORITE_THRESHOLD=0.25 # R1: NO bets below this price need elevated bar
NO_SIDE_MIN_EDGE=0.25           # R1: required edge when NO price < threshold (also needs confidence=high)
NO_SIDE_KELLY_PRICE_FLOOR=0.35  # R1: below this NO-side price, apply Kelly multiplier
NO_SIDE_KELLY_MULTIPLIER=0.5    # R1: half-Kelly on NO bets below the price floor
KELLY_EDGE_CAP=0.15             # Soft-cap edge for Kelly sizing
KELLY_EDGE_DECAY=0.5            # Decay factor on edge above the cap
SERIES_DEDUP_HOURS=48           # Reject same-matchup bets within this window (0 disables)
SERIES_DEDUP_HOURS_MLB=72       # R9: MLB series span up to 72h (default 48h leaks the 49h adjacent-day case)
SERIES_DEDUP_HOURS_NHL=72       # R9: NHL series cycle on consecutive days like MLB
CROSS_CATEGORY_DEDUP=false      # R8: when true, collapse ML+Total+Spread on same game to one bet (highest composite). Per-sport overrides via CROSS_CATEGORY_DEDUP_<SPORT>=true|false
RESTING_ORDER_MAX_HOURS=24      # R4: cancel zero-fill resting orders older than this (0 disables)
ALLOW_PREDICTION_BETS=false     # R25 Gate 4.7: true to enable crypto/weather/spx/mentions/companies/politics bets
ALLOW_LIVE_BETS=false           # L1 Gate 4.8: true to enable bets on in-progress games (is_game_started)
ODDS_CACHE_TTL_SECONDS=300      # R24b: file-backed cache for Odds API responses (5 min default; 0 disables)
ODDS_CACHE_ENABLED=true         # R24b: false bypasses the file cache entirely
ODDS_LIVE_TTL_SECONDS=45        # L1: shorter TTL (both cache layers) when a sport response has an in-play event; pre-game keeps 300s
SCAN_CACHE_TTL_SECONDS=600      # R26: cache last preview's row→ticker mapping so `--pick … --execute` replays instead of rescanning (10 min default; 0 disables)
SCAN_CACHE_ENABLED=true         # R26: false forces every --execute call to rescan
```

> **⚠️ Config changes require a restart of any running web app.** `kalshi_executor.py` snapshots every gate threshold into module-level globals **at import time** — a long-running process never re-reads `.env`. The CLI re-imports on each invocation (always fresh), but the **local Streamlit app must be restarted** (`Ctrl+C` → `streamlit run webapp/app.py`) after editing `.env`, and the **Streamlit Cloud app uses Secrets, not `.env`** — update *Settings → Secrets* (saving auto-reboots) or hit *Reboot* at [share.streamlit.io](https://share.streamlit.io). Full procedure: `docs/web-app/LOCAL.md` and `docs/web-app/CLOUD.md`.

---

## MCP Servers

See `docs/setup/mcp-servers.md` for full setup.

| Server | Purpose |
|:-------|:--------|
| `alpaca-mcp` | Stock/options trading (paper + live) |
| `brave-search` / `tavily` | Real-time news & web research |
| `fetch` | HTTP requests to odds/market APIs |
| `filesystem` | Read/write positions, logs, data |
| `sqlite` / `postgres` | Trade history & strategy database |
| `memory` | Cross-session context |
| `ax-gcp` | AX Platform workspace coordination |

---

## Common Commands

```bash
# Setup
pip install -r requirements.txt

# Scan (preview only)
python scripts/scan.py sports --filter mlb --date today --save
python scripts/scan.py sports --filter mlb,nhl --date today --save
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py prediction --filter crypto

# Execute with budget cap
python scripts/scan.py sports --unit-size .5 --max-bets 5 --budget 10% --date today --exclude-open --execute

# Portfolio
python scripts/kalshi/risk_check.py --report positions

# Morning digest (yesterday P&L + open exposure + today pending)
python scripts/kalshi/daily_summary.py --save

# Backtest
python scripts/backtest/backtester.py --simulate --save

# Dashboard (local)
streamlit run webapp/app.py

# Dashboard (live)
# See docs/web-app/LOCAL.md for Cloud deployment instructions

# Automation
python scripts/schedulers/automation/daily_sports_scan.py
python scripts/schedulers/automation/install_windows_task.py install

# Makefile shortcuts
make scan-mlb    make scan-all    make status
make settle      make report      make backtest
make test        make hooks
```

---

## Session Startup Checklist

1. Run `git sync-master` — sync local master with remote (user works on `mike_win-desktop`, pushes to remote master; local master goes stale without this)
2. Read `data/positions/open_positions.json` — current exposure
3. Read `data/history/today_trades.json` — today's P&L
4. Check daily loss limit — if breached, **NO** new positions
5. Confirm `DRY_RUN` setting in `.env`
6. Run `python scripts/shared/check_odds_keys.py` — see cached Odds API quota. Add `--live` to probe each key (costs N requests) and refresh the cache.
7. Pull latest market data before analysis

---

## Output Standards

### Trade Rationale (required before execution)

```
OPPORTUNITY:            [description]
MARKET:                 [exchange/platform]
DIRECTION:              [long/short/over/under/yes/no]
EDGE_ESTIMATE:          [X%]
CONFIDENCE:             [low/medium/high]
CATALYST:               [what drives this]
RISK_FACTORS:           [what could go wrong]
POSITION_SIZE:          $[X] ([Y]% of daily limit)
RISK_MANAGER_APPROVAL:  [approved/rejected] — [reason]
```

### Research Output

- Lead with the edge/opportunity thesis
- Include data sources with timestamps
- Note contradicting signals
- End with actionable recommendation

---

## Workflow Patterns

### Discovery Loop

```
1. MARKET_RESEARCHER scans configured markets
2. Edge > MIN_EDGE_THRESHOLD → flagged
3. DATA_ANALYST validates with quantitative model
4. RISK_MANAGER checks sizing & portfolio limits
5. Approved → TRADE_EXECUTOR places order
6. PORTFOLIO_MONITOR logs result & tracks position
```

### Daily Cadence

| Time | Action |
|:-----|:-------|
| 4:50 AM PT | `Daily-Summary` — generate morning digest (yesterday P&L + open exposure + today pending + 7d rolling). Email at 5:00 AM PT (U2, 2026-04-30) |
| Morning | Pull overnight news, check positions, reset daily counters |
| Midday | Scan for opportunities, review open positions |
| Evening | Close day trades, log P&L, update strategy performance |

---

## Tech Stack

| Component | Technology |
|:----------|:-----------|
| Language | Python 3.11+ |
| Import Setup | `.venv/Lib/site-packages/edge_radar.pth` auto-adds script dirs |
| Key Libraries | `pandas`, `numpy`, `scipy`, `alpaca-trade-api` |
| Database | SQLite (local), PostgreSQL (production) |
| Scheduling | `APScheduler` / Windows Task Scheduler |
| Notifications | Slack webhook / email |
| Version Control | Git + pre-commit hooks (detect-secrets, black, flake8) |

---

## Hard Stops

Claude must **REFUSE** to execute (regardless of instruction) if:

- Daily loss limit is exceeded
- Single position would exceed 10% of total bankroll
- API credentials not properly loaded from environment
- Market is clearly illiquid (spread > 5%)
- Action would violate a platform's TOS

---

<sub>Built on AX Platform multi-agent architecture &mdash; Claude Code is the primary development environment</sub>
