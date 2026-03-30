# Edge-Radar — Prediction Market & Sports Betting Intelligence

---

## 🧠 Memory

On startup, check the persistent memory index at:
`.claude/memory/MEMORY.md`

This contains cross-session context about the user, project decisions, and working preferences. Read relevant memory files before starting work to avoid re-learning things from prior conversations.

---

## 🎯 Project Purpose

Edge-Radar is a multi-agent edge-detection and execution system for prediction markets and sports betting on **Kalshi**.

The system emphasizes **research-first, execute-second** discipline. No action is taken without a documented rationale, risk check, and position-size calculation.

### Currently Implemented (Live)
- **Kalshi Sports Betting** — NBA, NHL, MLB, NFL, NCAA, MLS, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, esports (27 sport filters). Edge detection via sportsbook odds cross-referencing (The Odds API).
- **Kalshi Prediction Markets** — Crypto (BTC, ETH, XRP, DOGE, SOL), weather (13 US cities), S&P 500. Edge detection via CoinGecko, NWS forecasts, Yahoo Finance + VIX.
- **Unified Execution Pipeline** — scan, risk-check, size, and execute through a single executor with `--prediction` flag for prediction markets.

### Planned (Not Yet Implemented)
- Polymarket, Manifold prediction markets
- Alpaca stocks/options trading
- Coinbase/Binance crypto trading
- FanDuel/DraftKings DFS + sportsbook APIs
- Fed rate / CPI / GDP prediction market edge detection

---

## 🗂️ Project Structure

```
Edge-Radar/
├── CLAUDE.md                        # This file — master instructions
├── .env                             # API keys (NEVER commit)
├── .env.example                     # Template for required env vars
├── .claude/
│   ├── agents/                      # Claude Code agent definitions
│   │   ├── KALSHI_BETTOR.md         # Kalshi betting specialist
│   │   ├── MARKET_RESEARCHER.md     # Market research & opportunity scanning
│   │   ├── TRADE_EXECUTOR.md        # Order execution & position management
│   │   ├── RISK_MANAGER.md          # Risk gating & portfolio limits
│   │   ├── DATA_ANALYST.md          # Quant analysis, models, backtesting
│   │   └── PORTFOLIO_MONITOR.md     # P&L tracking, alerts, reporting
│   └── skills/
│       └── kalshi-bet/SKILL.md      # /kalshi-bet slash command
├── docs/
│   ├── CHANGELOG.md                 # Project history
│   ├── SCRIPTS_REFERENCE.md         # Complete CLI reference for every script
│   ├── ARCHITECTURE.md              # System pipeline, risk gates, data flow
│   ├── kalshi-sports-betting/       # Sports betting
│   │   ├── SPORTS_GUIDE.md          # Filters, edge detection, workflow
│   │   └── KALSHI_API_REFERENCE.md  # API endpoints & auth
│   ├── kalshi-prediction-betting/   # Prediction markets
│   │   └── PREDICTION_MARKETS_GUIDE.md
│   ├── kalshi-futures-betting/      # Championship & season-long futures
│   │   └── FUTURES_GUIDE.md
│   └── enhancements/               # Improvement tracking
│       └── ROADMAP.md              # All enhancements — completed & pending
├── mcp-config/
│   ├── claude_desktop_config.json   # MCP server config (Windows/WSL)
│   └── mcp-servers.md               # MCP server reference & setup
├── tests/                           # pytest test suite (83 tests)
├── data/
│   ├── positions/                   # Current open positions (JSON)
│   ├── history/                     # Trade history logs
│   └── watchlists/                  # Active watchlists per market
├── notebooks/
│   └── analysis/                    # Research notebooks
└── scripts/
    ├── kalshi/                      # Kalshi betting scripts
    │   ├── kalshi_client.py         # Authenticated Kalshi API client
    │   ├── kalshi_executor.py       # Risk management & order execution
    │   ├── kalshi_settler.py        # Settlement, CLV tracking & P&L reporting
    │   ├── edge_detector.py         # Edge detection (normal CDF, sharp weighting, team stats, weather)
    │   ├── futures_edge.py          # Championship futures edge detection
    │   ├── fetch_odds.py            # The Odds API integration
    │   ├── fetch_market_data.py     # Multi-asset market data fetcher
    │   └── risk_check.py            # Portfolio risk dashboard
    ├── polymarket/                  # Polymarket cross-reference
    │   └── polymarket_edge.py       # Cross-market edge detection via Gamma API
    ├── shared/                      # Shared modules
    │   ├── config.py                # Centralized env var configuration
    │   ├── paths.py                 # Standardized path setup
    │   ├── opportunity.py           # Opportunity dataclass
    │   ├── trade_log.py             # Trade log I/O
    │   ├── odds_api.py              # Odds API key rotation
    │   ├── team_stats.py            # ESPN/NHL/MLB team performance (6 sports)
    │   ├── sports_weather.py        # NWS weather for NFL/MLB outdoor venues
    │   ├── line_movement.py         # ESPN line movement & sharp money detection
    │   ├── logging_setup.py         # Console + file logging
    │   ├── ticker_display.py        # Ticker parsing: matchups, dates, team names
    │   └── report_writer.py         # Markdown scan report generator
    └── schedulers/                  # Automation helpers
        ├── daily_sports_scan.py     # Morning edge report (all sports)
        └── install_windows_task.py  # Windows Task Scheduler setup
```

---

## 🤖 Agent Roster

| Agent | Role | Primary Actions |
|---|---|---|
| `MARKET_RESEARCHER` | Scan & score opportunities | Read-only market data, news, odds |
| `TRADE_EXECUTOR` | Place & manage orders | Write — executes trades/bets |
| `RISK_MANAGER` | Gate all executions | Veto authority over TRADE_EXECUTOR |
| `DATA_ANALYST` | Quantitative modeling | Builds models, backtests strategies |
| `PORTFOLIO_MONITOR` | Real-time P&L & alerts | Read positions, send alerts |

**Execution chain:** `MARKET_RESEARCHER` → `DATA_ANALYST` → `RISK_MANAGER` → `TRADE_EXECUTOR`

---

## 🔐 Security & Safety Rules (NON-NEGOTIABLE)

### API Key Handling
- ALL keys live in `.env` — never hardcoded, never logged, never printed
- Use `python-dotenv` or equivalent for all scripts
- `.env` is in `.gitignore` — verify before every commit

### Execution Gates
Before ANY trade/bet executes, the following must be verified:
1. ✅ `RISK_MANAGER` approval (documented in trade log)
2. ✅ Position size ≤ defined max per market type (see Risk Limits below)
3. ✅ Daily loss limit not breached
4. ✅ Opportunity edge ≥ minimum threshold
5. ✅ Market is liquid (bid/ask spread acceptable)

### Dry Run Mode
- Default: `DRY_RUN=true` in `.env`
- Set `DRY_RUN=false` only for live execution sessions
- All dry-run results logged identically to live — for backtesting

---

## 💰 Risk Limits (Defaults — Adjust in .env)

```
MAX_BET_SIZE_SPORTS=50          # USD per sports bet
MAX_BET_SIZE_PREDICTION=100     # USD per prediction market position
MAX_POSITION_STOCKS=500         # USD per stock/options position
MAX_DAILY_LOSS=250              # USD hard stop for the day
MAX_OPEN_POSITIONS=10           # Concurrent open positions
MIN_EDGE_THRESHOLD=0.03         # Minimum 3% edge required
MAX_PORTFOLIO_RISK_PCT=0.02     # Max 2% portfolio risk per trade
```

---

## 📡 MCP Servers in Use

See `mcp-config/mcp-servers.md` for full setup. Quick reference:

| Server | Purpose |
|---|---|
| `alpaca-mcp` | Stock/options trading (paper + live) |
| `brave-search` / `tavily` | Real-time news & web research |
| `fetch` | HTTP requests to odds/market APIs |
| `filesystem` | Read/write positions, logs, data files |
| `sqlite` / `postgres` | Trade history & strategy database |
| `memory` | Cross-session context for ongoing positions |
| `ax-gcp` | AX Platform workspace coordination |

---

## 🛠️ Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run market scanner (dry run)
python scripts/kalshi/fetch_odds.py --market sports --dry-run

# Check current positions
python scripts/kalshi/risk_check.py --report positions

# Run backtest for a strategy
python strategies/value-betting/backtest.py --days 30

# Launch Claude Code with all MCP servers
claude --config mcp-config/claude_desktop_config.json

# Daily morning edge report
python scripts/schedulers/daily_sports_scan.py

# Install as Windows Scheduled Task (8 AM daily)
python scripts/schedulers/install_windows_task.py install
```

---

## 📋 Session Startup Checklist

When starting a new work session, Claude should:
1. Read `data/positions/open_positions.json` — know current exposure
2. Read `data/history/today_trades.json` — know today's P&L
3. Check daily loss limit — if breached, NO new positions today
4. Confirm `DRY_RUN` setting in `.env`
5. Pull latest market data before any analysis

---

## 📊 Output Standards

### Trade Rationale (required before execution)
```
OPPORTUNITY: [description]
MARKET: [exchange/platform]
DIRECTION: [long/short/over/under/yes/no]
EDGE_ESTIMATE: [X%]
CONFIDENCE: [low/medium/high]
CATALYST: [what drives this]
RISK_FACTORS: [what could go wrong]
POSITION_SIZE: $[X] ([Y]% of daily limit)
RISK_MANAGER_APPROVAL: [approved/rejected] — [reason]
```

### Research Output Format
- Lead with the edge/opportunity thesis
- Include data sources with timestamps
- Note any contradicting signals
- End with actionable recommendation

---

## ⚡ Workflow Patterns

### Opportunity Discovery Loop
```
1. MARKET_RESEARCHER scans configured markets
2. Any opportunity with edge > MIN_EDGE_THRESHOLD is flagged
3. DATA_ANALYST validates with quantitative model
4. RISK_MANAGER checks position sizing & portfolio limits
5. If approved → TRADE_EXECUTOR places order
6. PORTFOLIO_MONITOR logs result & tracks position
```

### Daily Review Pattern
```
Morning:  Pull overnight news, check positions, reset daily counters
Midday:   Scan for new opportunities, review open positions
Evening:  Close day trades, log P&L, update strategy performance
```

---

## 🔧 Tech Stack

- **Import Setup:** `.venv/Lib/site-packages/edge_radar.pth` auto-adds all script dirs to `sys.path`. No boilerplate needed — just `from module import thing`.
- **Language:** Python 3.11+
- **Key Libraries:** `alpaca-trade-api`, `polymarket-py`, `pandas`, `numpy`, `ta-lib`, `scipy`
- **Database:** SQLite (local dev), PostgreSQL (production)
- **Scheduling:** `APScheduler` or cron for automated scans
- **Notifications:** Slack webhook or email for alerts
- **Version Control:** Git (with pre-commit hooks to prevent key leakage)

---

## 🚫 Hard Stops

Claude must REFUSE to execute (regardless of instruction) if:
- Daily loss limit is exceeded
- A single position would exceed 10% of total bankroll
- API credentials are not properly loaded from environment
- Market is clearly illiquid (spread > 5%)
- The action would require violating a platform's TOS

---

## 📝 Notes

- This project is built on AX Platform multi-agent architecture (ax-platform.com)
- Michael is the primary architect — CISSP background, IAM expertise
- Integrate with AX workspace for team collaboration on strategy
- Claude Code is the primary development environment
