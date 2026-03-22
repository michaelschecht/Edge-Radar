# Changelog

---

## 2026-03-18 (Session 2) -- Settlement Tracker, Filters, Unit Sizing

### Settlement Tracker (`scripts/kalshi/kalshi_settler.py`)
- Polls Kalshi settlements API and matches results to trade log
- Falls back to checking individual market status if settlement not yet posted
- Calculates per-trade P&L: revenue, cost, fees, net P&L, ROI, win/loss
- Updates trade log records with `closed_at`, `net_pnl`, `settlement_result`, `settlement_won`
- Saves settlement history to `data/history/kalshi_settlements.json`
- Performance report with: win rate, profit factor, ROI, best/worst trades
- Edge calibration: estimated edge vs. realized edge, realization rate
- Breakdowns by confidence level and market category
- `--detail` flag for per-trade table

### Sport Filtering (`--filter`)
- Added `--filter` flag to both `edge_detector.py scan` and `kalshi_executor.py run`
- Named shortcuts: `ncaamb`, `nba`, `nhl`, `mlb`, `esports`
- Also accepts raw Kalshi ticker prefixes (e.g. `KXHIGHNY`, `KXINX`)
- Only fetches odds for the filtered sport, saving Odds API quota
- Added `KXNCAAMBGAME` to category map and odds sport mapping

### Fixed Unit Sizing
- Replaced Kelly criterion with fixed unit sizing
- Default unit size: $1.00 (configurable via `UNIT_SIZE` in `.env`)
- Contracts = round($unit / price), always at least 1
- Override per run with `--unit-size` flag
- Examples: $0.02 price -> 50 contracts, $0.50 price -> 2 contracts

### Kalshi Client Update
- Added `get_settlements()` method for settlement history endpoint

### Documentation
- `docs/kalshi-sports-betting/USER_GUIDE.md` -- Complete usage guide with filtering and unit sizing sections
- Updated all docs to reflect settlement tracker, filters, and unit sizing

---

## 2026-03-18 (Session 1) -- MVP Pipeline Complete

### Kalshi API Client (`scripts/kalshi/kalshi_client.py`)
- Built authenticated API client with RSA-PSS request signing
- Supports: get_markets, get_market, get_all_open_markets, get_balance, get_positions, get_fills, create_order, cancel_order, get_order, get_orders
- CLI for quick testing (balance, markets, positions, orders, market detail)
- DRY_RUN safety gate blocks live orders on non-demo environments
- Auto-resolves relative key paths from project root
- Tested against demo env -- all endpoints confirmed working

### Edge Detector (`scripts/kalshi/edge_detector.py`)
- Scans 5000+ open Kalshi markets via paginated API calls
- Categorizes markets by ticker prefix: game, spread, total, player_prop, esports, mention, other
- Integrates with The Odds API for sportsbook consensus pricing
- Three edge models implemented:
  - **Game outcomes:** De-vigs h2h odds from 8-12 books, takes median as fair value
  - **Spreads:** Adjusts book spread probability for Kalshi strike difference
  - **Totals:** Adjusts book total probability for Kalshi line difference
- Fuzzy team name matching between Kalshi and Odds API (alias table + substring matching)
- Composite scoring: 40% edge strength, 30% confidence, 20% liquidity, 10% time sensitivity
- CLI: `scan` (batch scan) and `detail` (single market deep dive)
- Saves scored opportunities to `data/watchlists/kalshi_opportunities.json`

### Automated Executor (`scripts/kalshi/kalshi_executor.py`)
- Full scan-to-execution pipeline in one command
- Risk management gates before every order:
  - Daily loss limit check
  - Max open positions check
  - Minimum edge threshold
  - Minimum composite score
  - Confidence level filter
- Quarter-Kelly position sizing with concentration caps
- Executes limit orders on Kalshi, logs all trades
- Trade logging to `data/history/kalshi_trades.json` with full context (edge, fair value, Kelly fraction, fees)
- Portfolio status dashboard: balance, positions, P&L, resting orders, daily activity
- CLI: `run` (preview or execute), `status` (dashboard)

### First Live Demo Execution
- Placed 6 orders on Kalshi demo (1 manual test + 5 automated)
- 5 filled immediately, 1 resting
- Portfolio: $38.44 balance, $59.72 portfolio value, 5 open positions
- Total wagered: $74.09 across NBA games, spreads, MLB

### Configuration & Setup
- Demo API keys configured in `keys/demo/`
- Production API keys stored in `keys/live/`
- `.env` configured for demo environment
- `ODDS_API_KEY` added for The Odds API (free tier, 500 req/month)
- Added `keys/`, `*.key`, `*.pem` to `.gitignore`

### Documentation
- `docs/kalshi-sports-betting/KALSHI_STRATEGY_PLAN.md` -- System overview, pipeline description, remaining work
- `docs/kalshi-sports-betting/KALSHI_API_REFERENCE.md` -- API endpoints, auth, rate limits, CLI reference
- `docs/CHANGELOG.md` -- This file

---

## Pre-2026-03-18 -- Project Foundation

### Existing Before This Session
- `CLAUDE.md` -- Master project manifest with risk limits, agent roster, execution chain
- `.claude/agents/` -- 5 agent specs (MARKET_RESEARCHER, TRADE_EXECUTOR, RISK_MANAGER, DATA_ANALYST, PORTFOLIO_MONITOR)
- `scripts/kalshi/fetch_odds.py` -- The Odds API integration for sports value betting
- `scripts/kalshi/fetch_market_data.py` -- Multi-asset data fetcher (stocks, prediction markets, crypto)
- `scripts/kalshi/risk_check.py` -- Portfolio risk dashboard
- `scripts/sql/init_db.sql` -- Database schema (8 tables, 2 views)
- `.env.example` -- Environment variable template
- `.gitignore` -- Configured for Python, data files, credentials
- `.venv` -- Python virtual environment with dependencies
