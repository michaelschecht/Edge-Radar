# Edge-Radar — Workspace Information

- **Workspace Name** — Edge-Radar Trading Desk
- **Workspace Type** — Team Workspace
- **AX MCP Tools** — Messages and Tasks
- **Existing Space ID** — `f6e56126-c293-45e4-b33e-147cb3481cdc`
- **Primary Agent** — `Edge-Radar-Scriptor` (ID: `0d20bd22-9822-4176-8f61-ce06d96e5489`)

## Description

Edge-Radar Trading Desk is a multi-agent workspace that orchestrates sports and prediction market edge detection, risk management, and execution on Kalshi. The workspace connects five specialized agents — @MarketScanner, @QuantAnalyst, @RiskGate, @Executor, and @PortfolioWatch — in a structured pipeline where every opportunity is scanned, validated, risk-gated, and executed with full auditability. No capital is deployed without documented rationale and risk approval.

The workspace leverages MCP-native architecture to unify data from 9+ live APIs (The Odds API, Kalshi, ESPN, MLB/NHL Stats, CoinGecko, Yahoo Finance, NWS, Polymarket) into a single collaboration surface. Agents communicate through topic-based channels — `#sports-scan`, `#prediction-scan`, `#risk-review`, `#execution-log`, `#portfolio-alerts`, and `#daily-report` — ensuring every decision and its reasoning is transparent and searchable. The AX MCP Server handles inter-agent messaging and task delegation, while the AX Channel MCP provides real-time relay to Claude Code sessions for human oversight.

The core value proposition is systematic edge extraction with institutional-grade risk management. The 8 execution gates (daily loss limit, position count, edge threshold, composite score, dedup check, per-event cap, bet size cap, median ratio cap) enforce discipline that prevents emotional or oversized betting. Fractional Kelly sizing, correlation-adjusted position limits, and tilt detection provide multiple layers of capital protection. The Streamlit dashboard at `edge-radar.streamlit.app` provides a password-gated web interface for scanning, execution, portfolio monitoring, and settlement — making the entire pipeline accessible without CLI access.

## Setup Steps

### 1. Workspace Configuration
- Use existing AX Space **Edge Radar** (`f6e56126-c293-45e4-b33e-147cb3481cdc`)
- Set shared context key `github-repo` → `https://github.com/michaelschecht/Edge-Radar` (refresh every 24h due to TTL)
- Configure topic channels: `#sports-scan`, `#prediction-scan`, `#futures-scan`, `#risk-review`, `#execution-log`, `#portfolio-alerts`, `#daily-report`, `#model-calibration`, `#cross-market`

### 2. Agent Registration
Register each agent with AX Platform via `mcp__ax-platform__agents`:

| Agent | Handle | Capabilities |
|:------|:-------|:-------------|
| @MarketScanner | `edge-radar-scanner` | Sports/prediction/futures scanning, news intelligence, opportunity scoring |
| @QuantAnalyst | `edge-radar-quant` | Edge validation, backtesting, model calibration, confidence intervals |
| @RiskGate | `edge-radar-risk` | 8-gate execution check, Kelly sizing, correlation management, tilt detection |
| @Executor | `edge-radar-executor` | Kalshi API trading (RSA-signed), position management, settlement |
| @PortfolioWatch | `edge-radar-portfolio` | P&L tracking, alert monitoring, daily/weekly reporting, dashboard updates |

### 3. Environment Configuration
Ensure `.env` contains all required keys:
```env
# Kalshi (required for execution)
KALSHI_API_KEY=...
KALSHI_PRIVATE_KEY_PATH=...

# Market Data
ODDS_API_KEY=...
COINGECKO_API_KEY=...

# Risk Limits
DRY_RUN=true
UNIT_SIZE=1.00
KELLY_FRACTION=0.25
MAX_BET_SIZE=100
MAX_DAILY_LOSS=250
MAX_OPEN_POSITIONS=10
MAX_PER_EVENT=2
MIN_EDGE_THRESHOLD=0.03
MIN_COMPOSITE_SCORE=6.0
```

### 4. MCP Server Connections
- `ax-platform` — Agent identity, messaging, tasks, space context
- `ax-channel` — Real-time message relay to/from Claude Code
- `github` — Repo access for `michaelschecht/Edge-Radar`
- `serper` — Google search for breaking news and research
- `context7` — Library documentation for Python dependencies

### 5. Automation
- Windows Task Scheduler: daily 8 AM ET sports scan via `daily_sports_scan.py`
- Settlement runs: evening batch via `settler.py`
- Dashboard: Streamlit Cloud deployment with secrets bridge to `.env`

## Quick Start

```bash
# Clone and setup
git clone https://github.com/michaelschecht/Edge-Radar.git
cd Edge-Radar
pip install -r requirements.txt
cp .env.example .env  # Fill in API keys

# Verify environment
python scripts/doctor.py

# Run first scan (dry-run by default)
python scripts/scan.py sports --filter mlb --date today --save

# Launch dashboard
streamlit run webapp/app.py
```
