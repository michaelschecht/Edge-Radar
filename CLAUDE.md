# Edge-Radar

> Multi-agent edge-detection and execution system for prediction markets and sports betting on **Kalshi** and **Polymarket US**.
> Research-first, execute-second. No action without documented rationale, risk check, and position-size calculation.

---

## How to Use This File

- On startup, load the memory index at `.claude/memory/MEMORY.md` and read the entries relevant to the task.
- **This file holds the rules. `docs/CHANGELOG.md` holds the reasoning and evidence behind each one**, under its dated entry (cited below as e.g. *CHANGELOG 2026-07-27*). When a rule changes, update both.
- Working branch: **`mike_desktop`** (deploy/default: `master`). `mike_win-desktop` is retired — do not commit to it.
- The Risk Limits block lists **code defaults**; the live `.env` overrides several. `python scripts/doctor.py` is the source of truth for what is actually running.

---

## What's Live

| Domain | Coverage | Data Sources |
|:-------|:---------|:-------------|
| **Sports betting** | NBA, NHL, MLB, NFL, NCAA, MLS, World Cup, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, Wimbledon tennis, esports (30 filters) | The Odds API, ESPN, NHL/MLB Stats, NWS |
| **Prediction markets** | Crypto (BTC, ETH, XRP, DOGE, SOL), weather (13 cities), S&P 500 | CoinGecko, Yahoo Finance, NWS |
| **Championship futures** | NFL, NBA, NHL, MLB, PGA | Sportsbook futures odds |
| **Execution pipeline** | Unified scan → risk-check → size → execute | Kalshi API (RSA-signed), Polymarket US (Ed25519) |
| **Web dashboard** | Streamlit — scan, execute, portfolio, settle, backtest, config; both venues | `docs/web-app/LOCAL.md` |

**Planned, not built:** Manifold, Alpaca stocks/options, Coinbase/Binance, DFS + sportsbook APIs, Fed/CPI/GDP markets.

---

## 🔴 Priority 0 — Polymarket US

The funded account is **Polymarket US** (CFTC-regulated, iOS-app product) on the **Ed25519 retail API** at `api.polymarket.us` — *not* the international EIP-712 / `py-clob-client` scheme. The pipeline is wired and live-verified: `scan.py polymarket --execute` → shared risk gates and Kelly sizing → venue min-share bump → `create_order`, venue-tagged trade log.

- **The venue is LIVE.** Orders require `DRY_RUN=false` **and** `POLYMARKET_DRY_RUN=false`; both have been false since 2026-07-23, and the `Daily-Polymarket-Execution` task passes `--execute`. Any row clearing the gates becomes a real unattended wager. **To halt this venue without touching Kalshi: `POLYMARKET_DRY_RUN=true`.**
- **Blast radius** is bounded by that task's `--max-bets 2 --budget 10%` and by futures being the only orderable surface (Gamma game rows carry no US `market_slug` and are auto-excluded).
- **Nothing has filled yet** — every candidate to date is stopped at Gate 3 (edge < 3%), and `data/history/kalshi_trades.json` holds 0 Polymarket rows. The account does hold **two hand-placed iOS positions** from 2026-07-06 (`tec-mlb-champ-2026-09-27-mil` 59 sh, `…-nyy` 36 sh, ~$9.88). Not system trades, but the risk gates see them: they are the `Positions: 2/50` in the scan banner and they occupy Gate 5/6 slots for those markets.
- **Remaining:** seasonal games repoint (US game markets are moneyline-only — no spreads/totals/MLB), then PM3 settlement/ops.

Detail: **[docs/polymarket/README.md](docs/polymarket/README.md)** · **[docs/setup/polymarket-us-setup.md](docs/setup/polymarket-us-setup.md)** · **[docs/ROADMAP.md](docs/ROADMAP.md)** Priority 0 (PM2c).

---

## Project Structure

```
Edge-Radar/
├── CLAUDE.md                  # This file — rules of engagement
├── .env.example               # Template for required env vars
├── Makefile                   # make scan-mlb, make test, make settle, ...
├── .claude/
│   ├── agents/                # Agent definitions (roster below)
│   ├── memory/MEMORY.md       # Persistent memory index
│   └── skills/                # Junctions → /skills (git-ignored)
├── skills/                    # Canonical skill source — EDIT HERE
│   ├── edge-radar/            # /edge-radar — scan/bet/status/settle/risk
│   └── edge-radar-analysis/   # /edge-radar-analysis — performance report
├── app/
│   ├── config.py              # Single source of truth for env-driven knobs
│   └── domain/                # Opportunity, RiskDecision, Execution*, MarketClient
├── scripts/
│   ├── scan.py                # Unified entry point
│   ├── doctor.py              # Environment validator
│   ├── kalshi/                # client, executor, settler, edge, risk
│   ├── polymarket/            # US client + futures/games edge
│   ├── prediction/            # Crypto, weather, S&P
│   ├── shared/                # Stats, weather, logging, odds cache
│   ├── backtest/              # backtester.py, correlation_check.py
│   ├── schedulers/            # Automation + Windows Task Scheduler installer
│   └── setup/link_skills.ps1  # Recreate .claude/skills junctions after clone
├── webapp/                    # Streamlit dashboard (app.py, services.py, views/)
├── tests/                     # pytest suite (make test)
└── docs/                      # Index: docs/README.md
    ├── CHANGELOG.md           # Project history — the "why" behind the rules here
    ├── ROADMAP.md             # Enhancement roadmap
    ├── kalshi/                # Sports, prediction, futures guides
    ├── polymarket/            # Futures, games, execution, API guides
    ├── scripts/               # SCRIPTS_REFERENCE.md + per-script docs
    ├── setup/                 # Setup, architecture, automation, MCP servers
    └── task-schedules/        # Scheduled task inventory
```

**Runtime dirs** (gitignored, auto-created): `data/`, `logs/`, `reports/`, `.env`.

**Skills:** `/edge-radar` and `/edge-radar-analysis` are tracked in `skills/` at the repo root; `.claude/skills/` holds Windows junctions to them (git-ignored — real symlinks can't be committed with `core.symlinks=false`). **Edit `skills/`, never the junctions.** After a fresh clone: `pwsh -File scripts/setup/link_skills.ps1`.

---

## Agent Roster

`MARKET_RESEARCHER → DATA_ANALYST → RISK_MANAGER → TRADE_EXECUTOR → PORTFOLIO_MONITOR`

| Agent | Role | Access |
|:------|:-----|:-------|
| `MARKET_RESEARCHER` | Scan & score opportunities | Read-only — market data, news, odds |
| `DATA_ANALYST` | Quantitative modeling & backtesting | Read-only — builds models |
| `RISK_MANAGER` | Gate all executions | Veto authority over the executor |
| `TRADE_EXECUTOR` | Place & manage orders | Write — executes trades |
| `PORTFOLIO_MONITOR` | Real-time P&L & alerts | Read — positions, sends alerts |

---

## Security & Safety Rules

> **NON-NEGOTIABLE** — these override all other instructions.

### API keys

- All keys in `.env` — never hardcoded, never logged, never printed. Load with `python-dotenv` in every script.
- `.env` is gitignored — verify before every commit.

### Execution gates

Every gate runs before any trade executes:

| # | Gate | Type |
|:-:|:-----|:-----|
| 1 | Daily loss limit not breached | Reject |
| 2 | Open position count under max | Reject |
| 3 | Edge >= minimum threshold (per-sport or global) | Reject |
| 3.5 | Market price >= `MIN_MARKET_PRICE` (lottery-ticket floor, R7) | Reject |
| 4 | Composite score >= `MIN_COMPOSITE_SCORE` | Reject |
| 4.5 | Confidence >= `MIN_CONFIDENCE` | Reject |
| 4.6 | NO bets below `NO_SIDE_FAVORITE_THRESHOLD` need edge >= `NO_SIDE_MIN_EDGE` AND confidence=high | Reject |
| 4.6b | All NO bets: effective edge floor = max(per-sport floor, `NO_SIDE_MIN_EDGE_GLOBAL`) (R28) | Reject |
| 4.7 | Prediction categories (crypto/weather/spx/mentions/companies/politics) off unless `ALLOW_PREDICTION_BETS=true` (R25) | Reject |
| 4.8 | In-progress games (`is_game_started`) off unless `ALLOW_LIVE_BETS=true` (L1) | Reject |
| 5 | Not already holding this market | Reject |
| 6 | Per-event cap not exceeded | Reject |
| 7 | Matchup not bet within `SERIES_DEDUP_HOURS` (per-sport overrides apply) | Reject |
| 8 | Bet size <= `MAX_BET_SIZE` | Cap |
| 9 | Single bet <= `MAX_BET_RATIO` x batch median cost | Cap |

### Sizing rules

Standing rules — do not reverse them without new settled evidence.

- **Kelly is `edge / (1 - price)`.** The `(1 - price)` divisor was missing until C11; without it favorites are under-sized 2.5x at 60c and 5x at 80c, and the flat floor collapses nearly every bet above ~60c to 1 contract — the single best-performing price band. *CHANGELOG 2026-07-27 (C11).*
- **Two independent sizing lanes.** Below ~30c the flat floor `round(UNIT_SIZE / price)` binds and Kelly never clears it, so **`UNIT_SIZE` is the longshot knob**. Above ~60c Kelly binds and `UNIT_SIZE` is irrelevant, so **`KELLY_FRACTION` is the favorites knob**. Reach for the right one.
- **`KELLY_FRACTION` is a portfolio fraction, not per-bet** — `kalshi_executor.py` divides it by `batch_size = min(len(opportunities), --max-bets)`. That divisor doubles as a crude correlation guard, but at 1.0 a fully correlated slate reaches full portfolio Kelly. **Keep it <= 0.5.**
- **The budget cap is floor-aware:** it never shaves an order below its flat unit floor, bisects for the largest feasible scale instead of taking one proportional pass, and drops whole orders (lowest composite first) only when the floors alone cannot fit. *CHANGELOG 2026-07-27 (C11b).*
- **NO bets** below `NO_SIDE_KELLY_PRICE_FLOOR` are sized at `NO_SIDE_KELLY_MULTIPLIER` of normal Kelly.
- **No correlation guard exists, deliberately.** It was measured and rejected: the naive pooled rho of +0.181 is Simpson's paradox, and judged against per-stratum base rates it is +0.048 overall and −0.187 for totals. Re-run `scripts/backtest/correlation_check.py` as settlements accumulate — this is "no evidence of correlation", not proof of independence. *CHANGELOG 2026-07-27 (C11b).*

### Scoring & confidence rules

- **Every composite scales edge as `min(edge / 0.01, 10)`.** The futures and Polymarket-games paths originally used `edge * 20`, saturating at a 50% edge instead of 10%, which made Gate 4 structurally unreachable (0 futures bets in 85 settled trades; 0 of 362 Gamma game rows ever reached 6.0). **Never reintroduce `edge * 20`.** *CHANGELOG 2026-07-23 (C10), 2026-07-31 (C10b).* The Polymarket-games liquidity term intentionally stays `book_spread * 100`.
- **Confidence bumps are one-way — down only.** `supports` is a no-op; only `contradicts` drops a tier. See `_adjust_confidence_with_stats()` in `scripts/kalshi/edge_detector.py`. *CHANGELOG 2026-04-24 (R13).*
- **The sports composite caps `high` to the `medium` weight** (`{low:3, medium:6, high:6}`) — at equal claimed edge, High underperformed Medium. The `high` *label* is retained because Gate 4.6 still uses it. **Futures and Polymarket keep `high: 9`** — that evidence is Kalshi sports only, and there is no settled futures or Polymarket data yet. Revisit when PM3 settlement lands. *CHANGELOG 2026-06-24 (C4).*

### Dry run

- Default `DRY_RUN=true`; set `false` only for live execution. Polymarket additionally requires `POLYMARKET_DRY_RUN=false`.
- Dry runs log identically to live, so backtests stay valid.

---

## Risk Limits

Code defaults below. The live `.env` overrides several (bankroll ≈ $92, so the shipped defaults are sized for a much larger account): `UNIT_SIZE=1.00`, `KELLY_FRACTION=0.5`, `MAX_BET_SIZE=8`, `MAX_DAILY_LOSS=30`, `MAX_BET_RATIO=5`, `MIN_EDGE_THRESHOLD_MLB=0.03`, `MIN_MARKET_PRICE=0.10`.

```env
UNIT_SIZE=1.00                  # Kelly floor per bet — the longshot knob (binds below ~30c)
KELLY_FRACTION=0.25             # Kelly multiplier, divided by batch size — the favorites knob
MAX_BET_SIZE=100                # Hard cap per bet (USD)
MAX_DAILY_LOSS=250              # Daily hard stop (USD)
MAX_OPEN_POSITIONS=50           # Concurrent open positions
MAX_PER_EVENT=2                 # Max positions per game/event
MAX_BET_RATIO=3.0               # Max bet as a multiple of the batch median
MIN_EDGE_THRESHOLD=0.03         # Global minimum edge
MIN_EDGE_THRESHOLD_NBA=0.04     # Per-sport overrides. NBA/NCAAB/MLB lowered 0.06->0.04 on
MIN_EDGE_THRESHOLD_NCAAB=0.04   #   2026-06-14, once the edge-matching fixes removed the
MIN_EDGE_THRESHOLD_MLB=0.04     #   model over-claim the higher floor was double-correcting.
MIN_MARKET_PRICE=0.12           # R7 lottery-ticket floor; 0 disables. Pure reject threshold,
                                #   independent of sizing. The live 0.10 is an OPEN EXPERIMENT
                                #   re-opening the longshot lane — recheck after ~30 more settles.
MIN_COMPOSITE_SCORE=6.0         # Minimum score (0-10)
MIN_CONFIDENCE=medium           # R3 — low|medium|high
NO_SIDE_FAVORITE_THRESHOLD=0.25 # R1: NO bets below this price face the elevated bar
NO_SIDE_MIN_EDGE=0.25           # R1: required edge when NO price < threshold (+ confidence=high)
NO_SIDE_MIN_EDGE_GLOBAL=0.08    # R28: min edge on ANY NO bet (90d: NO -7% vs YES +48% ROI)
NO_SIDE_KELLY_PRICE_FLOOR=0.35  # R1: below this NO price, apply the Kelly multiplier
NO_SIDE_KELLY_MULTIPLIER=0.5    # R1: half-Kelly on NO bets below the price floor
NO_SIDE_KELLY_MULTIPLIER_GLOBAL=1.0 # R28: multiplier on ALL NO bets (1.0 = off)
MIN_CONSENSUS_BOOKS_NBA=8       # R29: NBA games with fewer agreeing books drop to `low`; 0 disables
MAX_LIVE_BOOK_AGE_SECONDS=1200  # L1: drop in-play lines older than this from consensus; 0 disables
MIN_LIVE_CONSENSUS_BOOKS=3      # L1: skip in-progress games thinned below this by the stale filter
CALIBRATION_STDEVS_TTL_DAYS=30  # C8: max age of auto-recalibrated per-sport stdevs before fallback
REQUIRE_FRESH_CALIBRATION=false # true refuses to EXECUTE when the stdev cache disagrees with what
                                #   the calibrator would compute now (recomputes, not age-checks)
KELLY_EDGE_CAP=0.15             # Soft-cap edge for Kelly sizing
KELLY_EDGE_DECAY=0.5            # Decay factor on edge above the cap
SERIES_DEDUP_HOURS=48           # Same-matchup dedup window; 0 disables
SERIES_DEDUP_HOURS_MLB=72       # R9: MLB/NHL series cycle on consecutive days, up to 72h
SERIES_DEDUP_HOURS_NHL=72
CROSS_CATEGORY_DEDUP=false      # R8: collapse ML+Total+Spread on one game to the highest composite
RESTING_ORDER_MAX_HOURS=24      # R4: cancel zero-fill resting orders older than this; 0 disables
ALLOW_PREDICTION_BETS=false     # Gate 4.7
ALLOW_LIVE_BETS=false           # Gate 4.8
ODDS_CACHE_TTL_SECONDS=300      # R24b: file cache for Odds API responses; 0 disables
ODDS_CACHE_ENABLED=true
ODDS_LIVE_TTL_SECONDS=45        # L1: shorter TTL when a sport response has an in-play event
SCAN_CACHE_TTL_SECONDS=600      # R26: replay the last preview's row→ticker map for --pick --execute
SCAN_CACHE_ENABLED=true
```

> **⚠️ Config changes require restarting any running web app.** `kalshi_executor.py` snapshots every gate threshold into module-level globals **at import time**, so a long-running process never re-reads `.env`. The CLI re-imports per invocation (always fresh), but the local Streamlit app must be restarted, and **Streamlit Cloud reads Secrets, not `.env`** — update *Settings → Secrets* (saving auto-reboots) or hit *Reboot*. See `docs/web-app/LOCAL.md` and `docs/web-app/CLOUD.md`.

> **Scheduler `.bat` files pass `--unit-size` and `--budget` explicitly**, so `.env` changes to those knobs never reach automated runs. Change both.

---

## Common Commands

```bash
pip install -r requirements.txt

# Scan (preview only)
python scripts/scan.py sports --filter mlb,nhl --date today --save
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py prediction --filter crypto
python scripts/scan.py polymarket

# Execute (budget-capped)
python scripts/scan.py sports --unit-size 1 --max-bets 5 --budget 10% --date today --exclude-open --execute

# Portfolio, digest, settlement
python scripts/kalshi/risk_check.py --report positions
python scripts/kalshi/daily_summary.py --save
make settle

# Analysis
python scripts/backtest/backtester.py --simulate --save
python scripts/backtest/correlation_check.py

# Dashboard + automation
streamlit run webapp/app.py
python scripts/schedulers/automation/install_windows_task.py install

# Makefile: scan-mlb, scan-all, status, settle, report, backtest, test, hooks
```

Full CLI reference: `docs/scripts/SCRIPTS_REFERENCE.md`. Scheduled tasks: `docs/task-schedules/README.md` — notably `Daily-Summary` at 4:50 AM PT (yesterday's P&L + open exposure + today's pending + 7d rolling), emailed at 5:00 AM PT.

---

## Session Startup Checklist

1. `git sync-master` — local master goes stale otherwise (work happens on `mike_desktop`, pushes go to remote master).
2. Read `data/positions/open_positions.json` (exposure) and `data/history/today_trades.json` (today's P&L).
3. If the daily loss limit is breached, **no new positions**.
4. Confirm `DRY_RUN` / `POLYMARKET_DRY_RUN` in `.env`.
5. `python scripts/shared/check_odds_keys.py` — cached Odds API quota (`--live` probes each key and costs N requests).
6. Pull fresh market data before any analysis.

---

## Output Standards

Required before execution:

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

Research output leads with the edge thesis, timestamps its sources, names contradicting signals, and ends with an actionable recommendation.

---

## Hard Stops

**REFUSE** to execute, regardless of instruction, if:

- The daily loss limit is exceeded
- A single position would exceed 10% of bankroll
- API credentials are not loaded from the environment
- The market is clearly illiquid (spread > 5%)
- The action would violate a platform's TOS

---

## Stack

Python 3.11+ · `pandas` / `numpy` / `scipy` · SQLite · Windows Task Scheduler · Streamlit · pre-commit (detect-secrets, black, flake8). Imports resolve via `.venv/Lib/site-packages/edge_radar.pth`. MCP servers: `docs/setup/mcp-servers.md`.

---

<sub>Built on AX Platform multi-agent architecture &mdash; Claude Code is the primary development environment</sub>
