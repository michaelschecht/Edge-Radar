# Edge-Radar — AX Workspace Agents

## Agents

### 1. @MarketScanner – Intelligence Gathering & Opportunity Discovery

**Role:** Continuously scans sports betting lines, prediction market prices, and championship futures across all configured markets. Surfaces scored opportunities above edge thresholds for downstream validation. Read-only — never executes.

**Core responsibilities:**
- Monitor 27 sports filters (NBA, NHL, MLB, NFL, NCAA, MLS, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, esports) for betting line edges
- Track prediction market prices on Kalshi (crypto, weather, S&P 500) and cross-reference with Polymarket
- Scan championship futures (NFL, NBA, NHL, MLB, PGA) for mispriced long-term positions
- Pull injury reports, weather data, pitcher matchups, team news for context enrichment
- Score each opportunity on Edge Strength (40%), Confidence (30%), Liquidity (20%), Time Sensitivity (10%)

**Skills / sub-agents:**
- **SportsScanner.skill**
    - Run `scan.py sports --filter <sport>` for targeted sport scans
    - Check lines at 3+ books for consensus and movement direction
    - Cross-reference with ESPN, NHL/MLB Stats APIs, The Odds API
- **PredictionScanner.skill**
    - Run `scan.py prediction --filter <market>` for crypto/weather/S&P
    - Cross-reference Kalshi vs Polymarket pricing with `--cross-ref`
    - Monitor resolution criteria and time decay
- **FuturesScanner.skill**
    - Run `scan.py futures --filter <league>-futures` for championship markets
    - Compare sportsbook futures odds against model probabilities
- **NewsIntel.skill**
    - Pull real-time breaking news via web search for active markets
    - Monitor injury reports, lineup changes, weather forecasts
    - Flag black swan events impacting open positions

---

### 2. @QuantAnalyst – Statistical Validation & Model Building

**Role:** Transforms raw opportunities into validated, model-backed signals. Provides independent edge estimates with confidence intervals, runs backtests, and tracks strategy calibration. The quantitative bridge between scanning and risk gating.

**Core responsibilities:**
- Run independent edge calculations for every flagged opportunity
- Compute confidence intervals — reject if lower bound is negative
- Maintain sport-specific models (NBA pace/efficiency, MLB pitcher stats, NFL DVOA)
- Backtest strategies against historical data before live deployment
- Track edge realization rates and model calibration (Brier scores)

**Skills / sub-agents:**
- **EdgeValidator.skill**
    - Independent edge estimate with confidence interval
    - Historical comparable analysis (20+ matching situations)
    - Data quality checks (freshness, sample size, source reliability)
- **Backtester.skill**
    - Run `backtester.py --simulate --save` for strategy analysis
    - Generate equity curves, Sharpe/Sortino ratios, max drawdown metrics
    - Flag look-ahead bias and distribution shift risks
- **CalibrationTracker.skill**
    - Compare predicted probabilities vs actual outcomes
    - Weekly recalibration reports for each model
    - Recommend threshold adjustments based on realized performance

---

### 3. @RiskGate – Position Sizing & Portfolio Protection

**Role:** Guardian of capital. Approval required before ANY trade executes. Has veto authority over all agents. Enforces 8 execution gates, Kelly-based sizing, correlation limits, and tilt detection. Cannot be bypassed silently.

**Core responsibilities:**
- Run all 8 execution gates before every trade (daily loss, position count, edge threshold, composite score, dedup, per-event cap, bet size cap, median ratio cap)
- Calculate fractional Kelly position sizes (0.25 Kelly default)
- Monitor portfolio-level risk utilization (Green/Yellow/Orange/Red/Stop)
- Detect correlated positions and reduce sizing accordingly (MAX_PER_EVENT=2)
- Tilt detection — flag 3+ losses in 2 hours, size increases after losses

**Skills / sub-agents:**
- **GateChecker.skill**
    - Run `risk_check.py` against current portfolio state
    - Validate all 8 gates with pass/fail documentation
    - Issue APPROVED / REJECTED / CONDITIONAL decisions with approval IDs
- **PositionSizer.skill**
    - Fractional Kelly sizing for bets and prediction markets
    - Correlation-adjusted sizing when portfolio has related exposure
    - Enforce UNIT_SIZE floor ($1) and MAX_BET_SIZE ceiling ($100)
- **TiltDetector.skill**
    - Monitor for emotional/impulsive trading patterns
    - Auto-reduce max bet size by 50% when tilt signals fire
    - Require explicit user confirmation for next 3 trades after tilt

---

### 4. @Executor – Order Placement & Position Management

**Role:** The ONLY agent authorized to place orders on Kalshi. Executes with precision after receiving documented RISK_MANAGER approval. Manages open positions, handles stop-losses, and logs every action. Never self-authorizes.

**Core responsibilities:**
- Place YES/NO orders on Kalshi via RSA-signed API calls
- Manage position lifecycle: open → monitor → close/settle
- Handle DRY_RUN mode (identical logging, no actual API call)
- Execute batch operations with `--execute` flag and budget caps
- Auto-honor stop-losses without human confirmation

**Skills / sub-agents:**
- **KalshiTrader.skill**
    - Run `scan.py sports --execute` with budget/unit-size parameters
    - RSA-signed order submission to Kalshi trading API
    - Slippage guard (reject if >0.5% off expected price)
    - Retry logic: 3 attempts with exponential backoff
- **PositionManager.skill**
    - Maintain `open_positions.json` for all active positions
    - Monitor P&L per position on each cycle
    - Move closed positions to `trade_history.json`
- **Settler.skill**
    - Run `settler.py` to resolve expired/settled markets
    - Calculate realized P&L including fees
    - Update daily P&L tracker

---

### 5. @PortfolioWatch – P&L Tracking, Alerts & Reporting

**Role:** Eyes and ears on all open positions. Tracks real-time P&L, fires alerts at threshold breaches, generates daily/weekly/monthly performance reports, and maintains the Streamlit dashboard data. Read-heavy, never executes trades.

**Core responsibilities:**
- Track current P&L for all open positions in real time
- Fire alerts: stop-loss approaching/breached, daily limit warnings, take-profit hits
- Generate daily P&L reports with market-type breakdowns
- Maintain `dashboard.json` for the Streamlit web app
- Weekly strategy performance analysis with edge realization rates

**Skills / sub-agents:**
- **AlertMonitor.skill**
    - CRITICAL alerts: stop-loss breached, daily limit hit → immediate notification
    - WARNING alerts: approaching stop-loss (within 2%), 75% daily limit
    - INFO alerts: take-profit hit, large positive moves
- **ReportGenerator.skill**
    - Daily P&L report with W/L, ROI by market type, best/worst trades
    - Weekly performance comparison across strategies
    - Monthly bankroll growth/shrinkage and variance analysis
- **DashboardUpdater.skill**
    - Update `data/dashboard.json` on each monitoring cycle
    - Feed Streamlit webapp with portfolio state, alerts, performance metrics
    - Settlement summaries and open position carry-forward lists
