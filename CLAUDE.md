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
| **Sports Betting** | NBA, NHL, MLB, NFL, NCAA, MLS, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, esports (27 filters) | The Odds API, ESPN, NHL/MLB Stats, NWS |
| **Prediction Markets** | Crypto (BTC, ETH, XRP, DOGE, SOL), weather (13 cities), S&P 500 | CoinGecko, Yahoo Finance, NWS |
| **Championship Futures** | NFL, NBA, NHL, MLB, PGA | Sportsbook futures odds |
| **Execution Pipeline** | Unified scan → risk-check → size → execute | Kalshi API (RSA-signed) |
| **Web Dashboard** | Streamlit app — scan, execute, portfolio, settle | Deploy your own (see `docs/web-app/SETUP.md`) |

<details>
<summary><b>Planned (not yet implemented)</b></summary>

- Polymarket, Manifold prediction markets
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
│   └── skills/
│       └── edge-radar/SKILL.md      # /edge-radar slash command
├── docs/
│   ├── CHANGELOG.md                 # Project history
│   ├── SCRIPTS_REFERENCE.md         # Complete CLI reference
│   ├── ARCHITECTURE.md              # Pipeline, risk gates, data flow
│   ├── kalshi-sports-betting/       # Sports: filters, edge detection, MLB filtering
│   ├── kalshi-prediction-betting/   # Prediction: crypto, weather, S&P
│   ├── kalshi-futures-betting/      # Futures: championship markets
│   ├── mcp-config/                  # MCP server reference
│   ├── scripts/                     # Per-script detailed docs
│   ├── setup/                       # Setup & automation guides
│   └── enhancements/               # Roadmap (gitignored)
├── app/domain/                      # Typed domain objects
│   ├── opportunity.py               # Opportunity dataclass (canonical)
│   ├── risk.py                      # RiskDecision dataclass
│   └── execution.py                # ExecutionPreview, ExecutionResult
├── webapp/                          # Streamlit web dashboard
│   ├── app.py                       # Entry: streamlit run webapp/app.py
│   ├── services.py                  # Wrapper around core scripts
│   ├── theme.py                     # Dark terminal CSS
│   └── views/                       # Page modules (scan, portfolio, settle)
├── tests/                           # 150 pytest tests
└── scripts/
    ├── scan.py                      # Unified entry point
    ├── doctor.py                    # Environment validator
    ├── backtest/backtester.py       # Strategy analysis & equity curves
    ├── kalshi/                      # Core: client, executor, settler, edge, risk
    ├── polymarket/                  # Cross-market edge detection
    ├── shared/                      # Shared modules (stats, weather, logging, etc.)
    └── schedulers/                  # Automation (batch, Task Scheduler)
```

**Runtime directories** (gitignored, auto-created): `data/`, `logs/`, `reports/`, `.env`

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

### 8 Execution Gates

Before ANY trade executes:

| # | Gate | Type |
|:-:|:-----|:-----|
| 1 | Daily loss limit not breached | Reject |
| 2 | Open position count under max | Reject |
| 3 | Edge >= minimum threshold | Reject |
| 4 | Composite score >= minimum | Reject |
| 5 | Not already holding this market | Reject |
| 6 | Per-event cap not exceeded | Reject |
| 7 | Bet size <= MAX_BET_SIZE | Cap |
| 8 | Single bet <= 3x batch median cost | Cap |

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
MIN_EDGE_THRESHOLD=0.03         # Minimum 3% edge
MIN_COMPOSITE_SCORE=6.0         # Minimum score (0-10)
```

---

## MCP Servers

See `mcp-config/mcp-servers.md` for full setup.

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
python scripts/scan.py prediction --filter crypto --cross-ref
python scripts/scan.py polymarket --filter crypto

# Execute with budget cap
python scripts/scan.py sports --unit-size .5 --max-bets 5 --budget 10% --date today --exclude-open --execute

# Portfolio
python scripts/kalshi/risk_check.py --report positions

# Backtest
python scripts/backtest/backtester.py --simulate --save

# Dashboard (local)
streamlit run webapp/app.py

# Dashboard (live)
# See docs/web-app/SETUP.md for Cloud deployment instructions

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

1. Read `data/positions/open_positions.json` — current exposure
2. Read `data/history/today_trades.json` — today's P&L
3. Check daily loss limit — if breached, **NO** new positions
4. Confirm `DRY_RUN` setting in `.env`
5. Pull latest market data before analysis

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
| Morning | Pull overnight news, check positions, reset daily counters |
| Midday | Scan for opportunities, review open positions |
| Evening | Close day trades, log P&L, update strategy performance |

---

## Tech Stack

| Component | Technology |
|:----------|:-----------|
| Language | Python 3.11+ |
| Import Setup | `.venv/Lib/site-packages/edge_radar.pth` auto-adds script dirs |
| Key Libraries | `pandas`, `numpy`, `scipy`, `alpaca-trade-api`, `polymarket-py` |
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
