# Changelog

---

## 2026-03-31 -- Unified Scanner, Scheduler Reorganization, Env & Report Cleanup

### P9. Unified Scan Entry Point (`scripts/scan.py`)
- Single entry point routing to all 4 scanners: `sports`, `futures`, `prediction`, `polymarket`
- Auto-inserts `scan` subcommand when omitted
- Aliases: `sport`, `pred`, `poly`, `xref`
- All flags forwarded directly via subprocess — no duplicate argument parsing
- Updated Quick Start, More Examples, Daily Workflow, and Scripts Reference to use `scan.py`

### P10. Documentation Cleanup
- Updated SPORTS_GUIDE: replaced all `kalshi_executor.py run` with `scan.py sports`, removed duplicated daily workflow (defers to SCRIPTS_REFERENCE), fixed composite score dimensions (3 → 4 with weights), added roadmap cross-link
- Updated FUTURES_GUIDE and PREDICTION_MARKETS_GUIDE: `scan.py` commands, roadmap cross-links
- Updated ARCHITECTURE: replaced duplicated Phase 2-4 task lists with pointer to ROADMAP.md
- Added back-links from SCRIPTS_REFERENCE to all domain guides

### P11. Pre-Commit Hooks (`.pre-commit-config.yaml`)
- `detect-secrets` — credential leak prevention (requires `.secrets.baseline`)
- `black` — code formatting (line-length 100)
- `flake8` — linting (max-line-length 100, ignore E203/W503)
- `check-json`, `check-yaml` — config file validation
- `end-of-file-fixer`, `trailing-whitespace` — whitespace hygiene
- `no-commit-to-branch` — prevents direct commits to master
- Install: `make hooks` or `pip install pre-commit && pre-commit install`

### P12. Makefile
- 18 targets: `scan-mlb`, `scan-nba`, `scan-nhl`, `scan-nfl`, `scan-sports`, `scan-futures`, `scan-predictions`, `scan-polymarket`, `scan-all`, `status`, `risk`, `settle`, `report`, `reconcile`, `test`, `test-quick`, `install`, `hooks`
- `make help` for full reference
- Note: requires `make` installed (`choco install make` on Windows)

### Scheduler Directory Reorganization
- Moved 4 `.bat` morning scan jobs to `scripts/schedulers/morning_scans/`
- Moved 2 Python automation scripts to `scripts/schedulers/automation/`
- Fixed `PROJECT_ROOT` depth in `install_windows_task.py` for new path
- Updated all path references in CLAUDE.md, README.md, SCRIPTS_REFERENCE.md

### P7. `MAX_BET_SIZE_SPORTS` Added to `.env.example`
- Added `MAX_BET_SIZE_SPORTS=50` — was referenced in CLAUDE.md and used by `risk_check.py` but missing from the env template

### P8. Report Output Format Unified
- Confirmed all scanners support `--save` for markdown reports
- `kalshi_executor.py run` delegates scanning to dedicated scanners (which have `--save`), so no gap remains
- Marked complete in roadmap

---

## 2026-03-30 -- Unified CLI, Readable Displays, Date Filtering, Project Cleanup

### Unified CLI Flags Across All Scanners
- All 4 scanners (`edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`) now share the same execution flags: `--execute`, `--unit-size`, `--max-bets`, `--pick`, `--ticker`, `--save`
- Previously `--execute`/`--unit-size`/`--max-bets` only worked on `edge_detector.py` and `futures_edge.py`; prediction and polymarket scanners required routing through `kalshi_executor.py`

### Date & Open Position Filters
- Added `--date` flag to all scanners and executor: filter opportunities by game date
  - Accepts: `today`, `tomorrow`, `YYYY-MM-DD`, `MM-DD`, `mar31`
- Added `--exclude-open` flag: automatically skips markets where you already have an open position (both sides of the same game)
- Both filters work on all 5 entry points

### Shared Ticker Display Module (`scripts/shared/ticker_display.py`)
- New shared module for parsing Kalshi tickers into human-readable labels
- `parse_game_datetime()` -- extracts "Mar 30 6:40pm" from any ticker
- `parse_matchup()` -- extracts "White Sox @ Miami" from game tickers
- `parse_pick_team()` -- extracts picked team name from ticker suffix
- `format_bet_label()` -- best-effort readable label for any market type
- Team name lookups for MLB (30), NBA (30), NHL (32 teams)
- All 8 display tables across 7 scripts now show game date/time and readable matchup names

### Live Risk Dashboard (`scripts/kalshi/risk_check.py`)
- Rewritten to pull live data from Kalshi API (was reading empty local JSON files)
- Shows: account balance, risk limits, open positions with readable names + dates, resting orders, today's P&L, watchlist
- Positions table shows "Bet | When | Pick | Qty | Cost | P&L" instead of raw tickers

### Executor Status Improvements (`scripts/kalshi/kalshi_executor.py`)
- `status` command now shows readable matchups + game dates instead of raw tickers

### Markdown Report Format (`scripts/kalshi/kalshi_settler.py`)
- `report --detail --save` now generates proper markdown (tables, headers, bold values, code-formatted tickers)
- Changed file extension from `.txt` to `.md`

### MLB Filtering Guide (`docs/kalshi-sports-betting/MLB_FILTERING_GUIDE.md`)
- New comprehensive guide covering 10 filtering categories for MLB picks
- Includes composite strategies: "Strong MLB Play", "Weather Fade", "Sharp Follow", "Regression Fade", "Early Season Value"

### Markdown Scan Reports (`scripts/shared/report_writer.py`)
- New shared module: all scanners now save a markdown report alongside the JSON watchlist when `--save` is passed
- Reports include: readable matchups, game dates, edge/fair/market prices, confidence, composite score
- Saved to `reports/Sports/`, `reports/Futures/`, `reports/Predictions/` with date-stamped filenames
- Example: `reports/Sports/2026-03-30_mlb_sports_scan.md`

### Test Suite (83 tests)
- Created `tests/` with 4 test files covering the highest-value targets
- `test_risk_gates.py` (19 tests): position sizing (`unit_size_contracts`), all 5 risk gate rejections, bankroll capping, price clamping
- `test_ticker_display.py` (30 tests): team code splitting, date/time parsing, matchup rendering, date filtering, position exclusion
- `test_edge_detection.py` (14 tests): N-way de-vigging, normal CDF spread/total probability math
- `test_weather.py` (11 tests): MLB and NFL weather threshold adjustments, severity classification
- Shared fixtures in `conftest.py` for sample Opportunity objects

### Standardized Logging
- All 8 entry-point scripts migrated from `logging.basicConfig` + `logging.getLogger` to `setup_logging()` from `scripts/shared/logging_setup.py`
- Every script now gets console output (INFO+) plus a dedicated log file in `logs/` (DEBUG+)
- Zero `logging.basicConfig` calls remain in the codebase
- Library modules (`team_stats.py`, `line_movement.py`, etc.) correctly use `logging.getLogger()` to inherit config from entry points

### Consolidated Import Boilerplate
- Created `.venv/Lib/site-packages/edge_radar.pth` — auto-adds all script directories to `sys.path` when the venv is active
- Removed 16 `sys.path.insert(0, ...)` lines across 15 files
- Scripts now directly import shared modules without path setup boilerplate
- Created `scripts/bootstrap.py` as fallback for non-venv usage

### Removed Scheduler Framework
- Deleted `base_scheduler.py`, `sports_scheduler.py`, `prediction_scheduler.py`, `run_schedulers.py`, `scheduler_config.py`
- The framework was overengineered — every scheduler just called `scan_all_markets()` → `execute_pipeline()`, which the CLI scripts already do
- Replaced with direct Windows Task Scheduler / cron scheduling using the existing scanner scripts
- Kept `daily_sports_scan.py` (morning edge report) and `install_windows_task.py` (Task Scheduler helper)
- Removed `docs/schedulers/SCHEDULER_GUIDE.md`
- Added "Scheduling Your Own Scans" section to SCRIPTS_REFERENCE with `schtasks` examples

### Save Flag for Status & Risk Commands
- `kalshi_executor.py status --save` saves portfolio status as markdown to `reports/Accounts/Kalshi/kalshi_status_YYYY-MM-DD.md`
- `risk_check.py --save` saves full risk dashboard as markdown to `reports/Accounts/Kalshi/kalshi_dashboard_YYYY-MM-DD.md`
- Reports include: account balance, open positions (readable matchups + dates), today's P&L, resting orders, watchlist

### Project Cleanup
- Removed empty `strategies/` directory (edge detection is centralized in scanners, not strategy-pattern architecture)
- Updated CLAUDE.md project structure to reflect current state (`tests/`, `ticker_display.py`, `report_writer.py`)

---

## 2026-03-28 -- Polymarket Cross-Reference Integration

### Polymarket Edge Module (`scripts/polymarket/polymarket_edge.py`)
- New module: cross-references Kalshi market prices against Polymarket via the Gamma API (free, no key required)
- Fetches active Polymarket markets by category (crypto, weather, S&P, politics, companies)
- Fuzzy market matching engine using 4 signals: title similarity, strike price, expiry date, asset keyword overlap
- Standalone edge detection: surfaces price discrepancies between Kalshi and Polymarket as arbitrage-style signals
- Enrichment mode: boosts composite score when Polymarket confirms an existing edge, penalizes when it disagrees
- Standalone CLI: `polymarket_edge.py scan`, `polymarket_edge.py match TICKER`

### Prediction Scanner Integration (`scripts/prediction/prediction_scanner.py`)
- Added `--cross-ref` flag to enable Polymarket cross-referencing during scans
- Added `--filter polymarket` / `poly` / `xref` shortcuts (auto-enables cross-ref mode)
- When active, the scanner: (1) finds standalone cross-market edge opportunities, and (2) enriches all existing opportunities with Polymarket confirmation/disagreement signals
- New `cross_ref` parameter on `scan_prediction_markets()` for programmatic use

---

## 2026-03-23 -- Edge Model Overhaul, Scheduler Framework, Doc Consolidation

### Spread & Total Model Recalibration (`scripts/kalshi/edge_detector.py`)
- Replaced linear probability adjustment (`+3% per point`) with normal CDF model using `scipy.stats.norm`
- Infers expected score margin from book spread + implied probability, then calculates P(margin > strike) on the bell curve
- Added sport-specific standard deviations: NBA (12), NCAAB (11), NFL (13.5), MLB (3.5), NHL (2.5), soccer (1.8)
- Same fix applied to total (over/under) markets with separate total stdev values
- Old model systematically overestimated edge on alternate spreads (caused 1W-11L on NCAAB)

### Daily Morning Scan (`scripts/schedulers/daily_sports_scan.py`)
- New script: scans MLB, NBA, NHL, NFL each morning for top 25 opportunities
- Saves timestamped report to `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md`
- Report includes edge, fair value, market price, confidence, team stats, sharp signals, weather
- `--daemon` flag runs via APScheduler at 8:00 AM PST daily with automatic DST handling
- `--top N` to customize number of opportunities (default 25)

### Line Movement & Sharp Money Detection (`scripts/shared/line_movement.py`)
- New module: ESPN scoreboard API provides opening vs closing odds (DraftKings) for free
- Detects reverse line movement (spread moves away from favorite = sharp on underdog)
- Detects sharp total movement (total drops/rises >2 pts)
- Pre-fetched once per scan, integrated into game/spread/total confidence signals
- Sharp agreement boosts confidence; contradiction reduces it
- Covers NBA, NFL, NHL, MLB, NCAAB, NCAAF

### Weather Impact for Outdoor Sports (`scripts/shared/sports_weather.py`)
- New module: NWS hourly forecast for 31 NFL + 30 MLB venues (dome/outdoor classified)
- Scoring adjustment model: wind >15mph, rain >40%, cold <32F (NFL) / <45F (MLB)
- Integrated into `detect_edge_total()`: bad weather reduces over fair value, boosts under
- Dome stadiums automatically skipped (zero adjustment)
- Free NWS API, no key required

### Team Stats Integrated into Edge Detection (`scripts/kalshi/edge_detector.py`)
- Game and spread edge detectors now look up team win% via `team_stats.py`
- Stats signal: "supports" (win% >= 60% for YES, <= 40% for NO), "contradicts" (opposite), or "neutral"
- Confidence is bumped up one level when stats support the bet, dropped when stats contradict
- Team record and signal stored in opportunity details for transparency

### Sharp Book Weighting (`scripts/kalshi/edge_detector.py`, `scripts/kalshi/futures_edge.py`)
- Added `BOOK_WEIGHTS` map: Pinnacle/Circa at 3x, mid-tier at 1-1.5x, DraftKings/FanDuel/BetMGM at 0.7x
- Replaced simple median with `weighted_median()` across all consensus functions (game, spread, total, futures)
- Sharp books pull the consensus fair value toward their more accurate lines
- 21 books mapped with weights; unknown books default to 1.0x

### Team Stats Module (`scripts/shared/team_stats.py`)
- New module providing team performance data from free APIs (no keys required)
- ESPN API: NBA, NCAAB, NFL, NCAAF standings, win%, points for/against
- NHL Stats API: standings, goal differential, L10 record, streak
- MLB Stats API: standings, run differential, winning percentage
- 6 sports covered, unified `get_team_stats(team, sport)` lookup with fuzzy name matching
- Data cached per session to minimize API calls

### Closing Line Value Tracking (`scripts/kalshi/kalshi_settler.py`)
- Settler now captures closing price from Kalshi API when settling trades
- Calculates CLV = closing_price - entry_price per trade
- Performance report includes CLV section: average CLV and beat-the-close rate
- CLV is the gold standard for validating whether the model has real predictive value

### Rebranded to Edge-Radar
- Renamed from FinAgent / Finance-Agent-Pro / edge-hunter to Edge-Radar
- Updated all references across CLAUDE.md, README, ARCHITECTURE, agents, Python docstrings, User-Agent headers, reports, and memory

### Documentation Consolidation
- Merged `USER_GUIDE.md` + `BETTING_GUIDE.md` into single `SPORTS_GUIDE.md` (1117 → 405 lines)
- Replaced `KALSHI_STRATEGY_PLAN.md` with lean `ARCHITECTURE.md` (pipeline, risk gates, data flow)
- Trimmed `FUTURES_GUIDE.md` (456 → 359 lines) and `PREDICTION_MARKETS_GUIDE.md` (414 → 252 lines)
- Slimmed `README.md` (206 → 79 lines) with doc index linking to all guides
- Eliminated ~600 lines of duplicated risk gates, command examples, and filter tables across docs

---

## 2026-03-23 -- Scheduler Framework, Trade Log Cleanup, Report Export

### Scheduler Framework (`scripts/schedulers/`)
- New per-market scheduler architecture — each sport/market gets its own independent scheduler
- `BaseScheduler` class with DRY_RUN enforcement, consecutive failure auto-pause (5 strikes), structured logging
- `SportsScheduler` and `PredictionScheduler` subclasses calling existing pipelines directly (no subprocess wrapping)
- `scheduler_config.py` — profiles loaded from `SCHED_{NAME}_*` env vars (9 registered: NBA, NHL, MLB, NFL, NCAA, soccer, crypto, weather, SPX)
- `run_schedulers.py` — CLI entry point: `--list` (show all profiles), `--only nba` (single), or launch all enabled in parallel
- All schedulers disabled by default — enable via `SCHED_{NAME}_ENABLED=true` in `.env`
- Docs: `docs/schedulers/SCHEDULER_GUIDE.md`

### Trade Log Cleanup
- Cross-validated local trade log against Kalshi API fills — identified 32 demo trades mixed with 12 live trades
- Purged all demo trades from `kalshi_trades.json` and `kalshi_settlements.json`
- Backups saved: `kalshi_trades_pre_cleanup_2026-03-23.json`, `kalshi_settlements_pre_cleanup_2026-03-23.json`
- Report now shows accurate live-only data: 12 trades, $10.67 wagered

### Report File Export
- Added `--save` flag to `kalshi_settler.py report` — writes plain-text report to `reports/Accounts/Kalshi/kalshi_report_YYYY-MM-DD.txt`
- Report includes timestamp, strips Rich markup for clean text output

### Kalshi Client Hardening
- Changed default `KALSHI_BASE_URL` fallback from demo API to production API
- Prevents accidental demo connection if env var is unset

### Odds API Key Expansion
- Added 2 additional Odds API keys (3 total) for increased rate limit capacity
- Existing key rotation in `odds_api.py` handles this automatically

### Memory System
- Added `.claude/memory/` for cross-session project context
- CLAUDE.md updated to instruct Claude Code to check memory on startup

### Futures Betting Improvements (`scripts/kalshi/futures_edge.py`)
- Added `KXNBA` (NBA Finals Champion), `KXNHL` (Stanley Cup Champion), `KXMLB` (World Series Champion) to futures map — only conference/playoff markets were previously mapped
- Added human-readable labels to all futures: output now shows "NBA Finals Champion: Oklahoma City Thunder" instead of just the ticker
- `--filter nba-futures` now scans Finals champion + both conference winners
- `--filter nfl-futures` cleaned up (removed KXNFLMVP which has no Odds API data)
- Bet type label stored in `details["bet_type"]` and used as the display title
- CLI table shows "Bet Type" column instead of raw ticker
- Updated FUTURES_GUIDE.md with NBA Finals section and corrected filter descriptions

### Per-Game Opportunity Cap (`scripts/kalshi/edge_detector.py`)
- Limits scan results to top 3 opportunities per game (sorted by edge)
- Groups markets by date+matchup extracted from ticker (e.g., all spreads/totals/game for Michigan vs Alabama share one key)
- Prevents a single game from dominating the opportunity list

### PR #14 Review
- Reviewed and rejected Jules-generated PR "Automate Kalshi Betting Pipeline & Optimize Execution"
- Issues: missing `KELLY_FRACTION` constant (runtime crash), no `DRY_RUN` gate on scheduler, missing `apscheduler` dependency, unexplained `cryptography` addition
- Built proper scheduler framework as replacement (see above)

---

## 2026-03-22 -- Live Trading, Prediction Markets, Project Reorganization

### Switched to Live Trading
- Moved from Kalshi demo to live production API
- Set `DRY_RUN=false`, `MAX_BET_SIZE_PREDICTION=5`
- Demo credentials archived in `.env` comments

### Git Repository
- Published to GitHub as private repo: `michaelschecht/Edge-Radar`
- Working branch: `mike_desktop`

### Kalshi Bettor Agent & Skill
- New `.claude/agents/KALSHI_BETTOR.md` -- dedicated Kalshi betting agent
- New `.claude/skills/kalshi-bet/SKILL.md` -- `/kalshi-bet` slash command for scan/execute/settle
- Agent auto-runs status on startup, previews before executing, respects all risk gates

### Financial Analysis Skill
- New `.claude/skills/financial-analysis/` -- research and analysis skill
- Templates: stock analysis, earnings/corporate, global markets, market sentiment, investment strategy

### Futures / Championship Edge Detector (`scripts/kalshi/futures_edge.py`)
- N-way de-vigging of outright odds from 5-12 sportsbooks
- Fuzzy name matching between Kalshi candidates and Odds API outcomes with alias table
- Supported: NFL Super Bowl, NBA conference winners, NHL conference winners, MLB playoffs, NCAAB MOP, PGA golf
- Filter shortcuts: `futures`, `nba-futures`, `nhl-futures`, `mlb-futures`, `ncaab-futures`, `golf-futures`, `nfl-futures`
- Integrated routing from `edge_detector.py` -- `--filter nba-futures` auto-routes to futures scanner
- Browse-only: NBA/NHL awards, Heisman, soccer leagues, F1, NASCAR, IPL

### Unfiltered Scan Fix
- Running the scanner without `--filter` now scans all known sport prefixes instead of pulling 5000 generic multi-event markets
- Results: 959+ sport markets across NBA, NCAAB, MLB, NHL instead of 0

### Sport Filter Expansion
- Expanded `FILTER_SHORTCUTS` from 5 to 27 sports based on live Kalshi market discovery
- Added: NFL, NCAA women's basketball, NCAA football, MLS, Champions League, EPL, La Liga, Serie A, Bundesliga, Ligue 1, UFC, boxing, F1, NASCAR, PGA golf, IPL cricket, individual esports (CS2, LoL)
- Added NBA player props (3PT, rebounds, assists, steals, points) and awards (MVP, ROY, DPOY)
- Added NHL awards (Hart, Norris, Calder)

### Prediction Market Edge Detectors (`scripts/prediction/`)
- **`probability.py`** -- shared math: strike probability (log-normal model), weather probability (normal model), realized volatility
- **`crypto_edge.py`** -- BTC, ETH, XRP, DOGE, SOL edge detection via CoinGecko (free API, with rate limit retry)
- **`weather_edge.py`** -- NYC, Chicago, Miami, Denver temperature markets via NWS API (free, no key). Uncertainty scales with forecast horizon.
- **`spx_edge.py`** -- S&P 500 binary options using Yahoo Finance for price + VIX for implied volatility
- **`mentions_edge.py`** -- TV mention markets: Poisson model for KXLASTWORDCOUNT (word counts), historical YES rate for binary mention markets (KXPOLITICSMENTION, KXFOXNEWSMENTION, KXNBAMENTION)
- **`companies_edge.py`** -- KXBANKRUPTCY (normal distribution vs historical ~750/yr baseline), KXIPO (browse only)
- **`politics_edge.py`** -- KXIMPEACH, KXQUANTUM, KXFUSION: time-decay hazard model with calibrated annual probabilities
- **`prediction_scanner.py`** -- unified CLI scanner with filters: crypto, weather, spx, mentions, companies, politics, techscience, and individual asset/series shortcuts
- All detectors produce the same `Opportunity` dataclass compatible with the existing executor pipeline

### Project Reorganization
- **Scripts:** Moved all Kalshi scripts to `scripts/kalshi/`, new prediction scripts in `scripts/prediction/`
- **Docs:** Reorganized into `docs/kalshi-sports-betting/` and `docs/kalshi-prediction-betting/`
- Fixed all `parent.parent` path resolution for new script depth
- Updated all cross-references across CLAUDE.md, agents, skills, and docs
- Removed local filesystem paths from all committed files

### Architecture Optimization
- **`scripts/shared/opportunity.py`** -- single Opportunity dataclass (was duplicated in edge_detector + prediction_scanner)
- **`scripts/shared/trade_log.py`** -- centralized trade log I/O (was duplicated in executor, settler, edge_detector)
- **`scripts/shared/paths.py`** -- standardized path setup replacing ad-hoc sys.path hacks
- **`scripts/shared/config.py`** -- centralized config: risk limits, scoring weights, model params, all loaded from .env
- **`scripts/shared/logging_setup.py`** -- dual logging to console (INFO+) and daily log file (DEBUG+) in `logs/`
- **`--prediction` flag on executor** -- prediction scanner now feeds directly into the execution pipeline
- **`reconcile` command on settler** -- compares local trade log vs Kalshi API positions, flags discrepancies
- **CLAUDE.md** updated to reflect actual implementation status vs planned features
- **`.env.example`** updated with all actually-used variables

### Odds API Key Rotation (`scripts/shared/odds_api.py`)
- Supports multiple API keys via `ODDS_API_KEYS=key1,key2,key3` in `.env`
- Auto-rotates to next key on 401/429 (exhausted/rate limited)
- Tracks remaining requests per key from response headers
- Warns when a key drops below 10 remaining
- Backwards compatible with single key

### Prompt Library (`prompts/`)
- 18 ready-to-use prompts for agents across 3 categories:
  - `prompts/sports-betting/` (6): daily scan, sport-specific, execute, settle, high conviction, compare
  - `prompts/futures/` (5): championship scan, sport report, weekly tracker, best value, portfolio builder
  - `prompts/predictions/` (7): all predictions, crypto, weather, SPX, mentions, execute, morning brief

### Reports
- `reports/NFL/2026-03-22_superbowl_futures.md` -- Super Bowl analysis (KC NO +1.6% best edge)
- `reports/mlb/2026-03-22_mlb_playoff_futures.md` -- MLB playoffs (Cleveland YES +25.5%, Cincinnati YES +21.0%)
- `reports/NBA/2026-03-22_nba_championship_futures.md` -- NBA championship (OKC YES +26.3% biggest edge across all sports)

### README
- Complete rewrite focused on sports betting, futures, and prediction markets
- Project structure, quick start, all market categories, API reference
- Removed financial-analysis skill (project dedicated to betting)

### Repo Renamed
- `Finance-Agent-Pro` -> `edge-hunter` -> `Edge-Radar`

### New Skills
- `market-mechanics-betting` -- betting theory, Kelly criterion, scoring rules
- `polymarket` -- API reference, trading guides, getting started docs

### Documentation
- `docs/kalshi-sports-betting/BETTING_GUIDE.md` -- comprehensive sport-by-sport guide with all 27 filters
- `docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md` -- crypto, weather, S&P 500, mentions, companies, politics, tech/science
- `docs/kalshi-futures-betting/FUTURES_GUIDE.md` -- NFL, NBA, NHL, MLB, golf futures with N-way de-vig
- Updated KALSHI_BETTOR agent and kalshi-bet skill with futures + prediction commands
- Updated all docs to reflect live trading, new script paths, and new commands

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
