# Edge-Radar — Workflow

## Agent Workflow

The Edge-Radar workspace orchestrates a five-agent pipeline that mirrors a professional trading desk: research, validate, gate, execute, and monitor. Every opportunity flows through the full pipeline before capital is deployed, ensuring no trade executes without documented rationale, statistical validation, and risk approval.

The workspace operates on a daily cadence anchored to market schedules. Morning scans pull overnight news and check existing positions. Midday sweeps scan for new edges across 27 sports filters, crypto/weather/S&P prediction markets, and championship futures. Evening operations settle resolved markets, log P&L, and update strategy performance. The Kalshi API is the primary execution venue, with Polymarket used for cross-reference pricing.

The workspace is powered by 5 primary agents:

- **@MarketScanner** — intelligence gathering and edge discovery:
  - Scans sports, prediction, and futures markets via `scan.py`
  - Scores opportunities on a 4-dimension rubric (edge, confidence, liquidity, time)
  - Surfaces opportunities with composite score ≥ 6.0 and edge ≥ 3%

- **@QuantAnalyst** — statistical validation and model maintenance:
  - Runs independent edge estimates with confidence intervals
  - Backtests strategies against historical data
  - Tracks model calibration and edge realization rates

- **@RiskGate** — capital protection and position sizing:
  - Enforces 8 execution gates (daily loss, position count, edge, score, dedup, per-event, size cap, median ratio)
  - Calculates fractional Kelly position sizes
  - Detects tilt patterns and correlated exposure

- **@Executor** — order placement and position lifecycle:
  - Places RSA-signed orders on Kalshi
  - Manages open positions, stop-losses, settlements
  - Logs every action (dry-run identical to live)

- **@PortfolioWatch** — P&L tracking and alerting:
  - Real-time position monitoring with threshold alerts
  - Daily/weekly/monthly performance reports
  - Feeds the Streamlit dashboard

**Primary topics** include:

- `#sports-scan` — Daily sports opportunity scan results (MLB, NBA, NHL, NFL, etc.)
- `#prediction-scan` — Crypto, weather, S&P prediction market opportunities
- `#futures-scan` — Championship futures market analysis
- `#risk-review` — Risk gate decisions, approvals, rejections, and sizing
- `#execution-log` — Trade execution confirmations, fill reports, errors
- `#portfolio-alerts` — Stop-loss triggers, daily limit warnings, large moves
- `#daily-report` — End-of-day P&L summaries, strategy performance
- `#model-calibration` — Weekly model accuracy reviews, threshold adjustments
- `#cross-market` — Kalshi vs Polymarket arbitrage and cross-reference signals

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      AX WORKSPACE: Edge-Radar                          │
│                                                                         │
│  Topics: #sports-scan  #prediction-scan  #futures-scan  #risk-review   │
│          #execution-log  #portfolio-alerts  #daily-report              │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐
│ @MarketScanner  │  │ @QuantAnalyst   │  │ @PortfolioWatch     │
│                 │  │                 │  │                     │
│ • SportsScanner │  │ • EdgeValidator │  │ • AlertMonitor      │
│ • PredScanner   │──▶ • Backtester   │  │ • ReportGenerator   │
│ • FuturesScaner │  │ • Calibration   │  │ • DashboardUpdater  │
│ • NewsIntel     │  │   Tracker       │  │                     │
└─────────────────┘  └────────┬────────┘  └──────────▲──────────┘
                              │                      │
                              ▼                      │
                    ┌─────────────────┐               │
                    │ @RiskGate       │               │
                    │                 │               │
                    │ • GateChecker   │               │
                    │ • PositionSizer │               │
                    │ • TiltDetector  │               │
                    └────────┬────────┘               │
                             │                        │
                    APPROVED │ REJECTED                │
                             ▼                        │
                    ┌─────────────────┐               │
                    │ @Executor       │───────────────┘
                    │                 │  (position updates)
                    │ • KalshiTrader  │
                    │ • PositionMgr   │
                    │ • Settler       │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────────┐
         │                   │                       │
         ▼                   ▼                       ▼
┌─────────────────┐ ┌────────────────┐ ┌─────────────────────┐
│ The Odds API    │ │ Kalshi API     │ │ CoinGecko / Yahoo   │
│ ESPN / MLB Stats│ │ (RSA-signed)   │ │ Finance / NWS       │
│ NHL Stats API   │ │                │ │ Polymarket CLOB     │
└─────────────────┘ └────────────────┘ └─────────────────────┘
```

## Pipeline Flow: Opportunity → Execution

```
1. @MarketScanner posts scored opportunity to #sports-scan or #prediction-scan
       │
       ▼
2. @QuantAnalyst picks up opportunity, runs independent edge estimate
   ├── Edge CI lower bound < 0% → PASS (posted to #risk-review)
   └── Edge CI lower bound > 0% → validated signal sent to @RiskGate
       │
       ▼
3. @RiskGate runs 8 execution gates
   ├── Any gate FAILS → REJECTED (posted to #risk-review with reason)
   └── All gates PASS → APPROVED with approval ID + sized position
       │
       ▼
4. @Executor receives approval, executes on Kalshi
   ├── DRY_RUN=true → simulated fill, logged identically
   └── DRY_RUN=false → live RSA-signed order submission
       │
       ▼
5. @PortfolioWatch picks up new position
   ├── Monitors P&L, fires alerts at thresholds
   ├── Updates Streamlit dashboard
   └── Generates daily/weekly reports to #daily-report
```

## Daily Cadence

| Time (ET) | Action | Agent(s) |
|:----------|:-------|:---------|
| 8:00 AM | Automated same-day sports scan | @MarketScanner |
| 8:15 AM | Validate flagged opportunities | @QuantAnalyst |
| 8:30 AM | Risk gate + sizing for approved batch | @RiskGate |
| 8:45 AM | Execute approved batch (if DRY_RUN=false) | @Executor |
| Midday | Ad-hoc prediction/futures scans | @MarketScanner |
| Ongoing | Position monitoring + alerts | @PortfolioWatch |
| Evening | Settle resolved markets, daily P&L report | @Executor, @PortfolioWatch |
| Sunday | Weekly performance + calibration review | @QuantAnalyst, @PortfolioWatch |
