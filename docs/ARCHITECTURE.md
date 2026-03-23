# Edge-Radar Architecture

---

## System Overview

Edge-Radar is an automated edge-detection and execution pipeline for Kalshi prediction markets and sports betting. It scans thousands of open markets, cross-references prices against sportsbook consensus odds and external data models, identifies mispriced contracts, applies risk gates and position sizing, and executes limit orders -- logging every decision for post-hoc calibration.

---

## Pipeline Steps

### 1. FETCH

Pull all open Kalshi markets (5,000+) via the Kalshi API. Simultaneously fetch sportsbook odds from The Odds API and external data feeds (CoinGecko, NWS, Yahoo Finance) for prediction markets.

### 2. CATEGORIZE

Classify each market by type: game outcome, spread, total, player prop, futures, esports, prediction (crypto, weather, S&P 500), or other. Category determines which edge model is applied.

### 3. COMPARE

For each market, compare the Kalshi ask price against the consensus fair value derived from the appropriate edge model. Calculate raw edge (fair\_value - market\_price) and score on four dimensions: edge strength, confidence, liquidity, and time to expiry.

### 4. CAP

Limit selection to the top 3 opportunities per game or event to enforce diversification across matchups and prevent concentration in a single contest.

### 5. RISK-CHECK

Filter opportunities through six risk gates (see Risk Management below). Reject any bet that fails a gate. Surviving opportunities are sized via quarter-Kelly criterion, capped at the fixed unit size.

### 6. EXECUTE

Place limit orders on Kalshi for approved opportunities. Log every order to the trade journal with edge estimate, sizing rationale, fill price, fees, and status.

### 7. MONITOR

Track open positions and resting orders via the portfolio dashboard. On market settlement, record outcome, realized P&L, and edge calibration data.

---

## Edge Detection Models

### Game Outcomes (Moneyline / 2-Way De-Vig)

Fetch head-to-head odds from 8-12 US sportsbooks. De-vig each book's line using the multiplicative method to extract true implied probability. Take the **weighted median** across all books — sharp books (Pinnacle, Circa) weighted 3x, recreational books (DraftKings, FanDuel) weighted 0.7x. Confidence factors in book count, estimate spread, and team stats signal.

### Spreads (Normal CDF Model)

Fetch spread lines from sportsbooks and compute weighted median spread and implied probability. Infer expected score margin using the book's line, then model the final margin as **Normal(mean, stdev)** with sport-specific standard deviations (NBA: 12, NCAAB: 11, NFL: 13.5, MLB: 3.5, NHL: 2.5). Calculate `P(margin > strike)` via normal CDF. Confidence factors in book count, book agreement (spread range), and team stats signal.

### Totals (Normal CDF Model + Weather)

Same approach as spreads: infer expected total from book line, model as Normal distribution with sport-specific stdev, calculate `P(total > strike)` via CDF. For NFL and MLB outdoor games, a **weather adjustment** is applied: NWS hourly forecasts for the game venue provide wind speed, precipitation, and temperature. High wind (>15mph), rain (>40%), and extreme cold reduce expected scoring — the fair value for "over" is adjusted downward accordingly. Dome stadiums are automatically excluded.

### Futures (N-Way De-Vig)

For championship and season-long markets with N outcomes, de-vig the full N-way market from sportsbook futures odds. Distribute the overround proportionally. Take weighted median across books.

### Confidence Signals

Confidence (low/medium/high) is determined by three factors:
1. **Book count and agreement** — more books with tighter consensus = higher confidence
2. **Book spread range** — high disagreement (>4 points) signals injury news or stale lines, drops confidence
3. **Team stats** — win% from ESPN/NHL/MLB APIs. Stats that support the bet direction bump confidence up; stats that contradict drop it down

### Predictions (Model-Specific)

| Market Type | Data Source | Method |
|---|---|---|
| Crypto (BTC, ETH, XRP, DOGE, SOL) | CoinGecko | Current price + 24h volatility vs. Kalshi strike; probability derived from log-normal distribution |
| Weather (13 US cities) | NWS / NOAA | Ensemble forecast temperature distributions vs. Kalshi strike thresholds |
| S&P 500 | Yahoo Finance + VIX | Current level + implied volatility to derive probability of reaching Kalshi strike by expiry |

---

## Risk Management

### Risk Gates

Every order must pass all six gates before execution.

| Gate | Check | Reject Condition |
|---|---|---|
| 1. Daily loss limit | Sum of realized losses today | Losses >= `MAX_DAILY_LOSS` |
| 2. Position count | Number of open positions | Count >= `MAX_OPEN_POSITIONS` |
| 3. Edge threshold | Calculated edge for this opportunity | Edge < `MIN_EDGE_THRESHOLD` |
| 4. Composite score | Weighted score across edge, confidence, liquidity, time | Score < `MIN_COMPOSITE_SCORE` |
| 5. Confidence level | Model confidence rating (low / medium / high) | Confidence < `MIN_CONFIDENCE` |
| 6. Size limits | Proposed bet size vs. Kelly and concentration caps | Size exceeds Kelly fraction or max bet |

### Risk Parameters

| Env Variable | Default | Description |
|---|---|---|
| `UNIT_SIZE` | $1.00 | Fixed dollar amount targeted per bet |
| `MAX_BET_SIZE_SPORTS` | $50 | Maximum USD per sports bet |
| `MAX_BET_SIZE_PREDICTION` | $100 | Maximum USD per prediction market position |
| `MAX_DAILY_LOSS` | $250 | Hard stop -- no new positions after this daily loss |
| `MAX_OPEN_POSITIONS` | 10 | Maximum concurrent open positions |
| `MIN_EDGE_THRESHOLD` | 3% | Minimum edge required to consider a bet |
| `MIN_COMPOSITE_SCORE` | 6.0 | Minimum composite opportunity score |
| `MIN_CONFIDENCE` | medium | Minimum model confidence level |
| `MAX_PORTFOLIO_RISK_PCT` | 2% | Maximum portfolio risk per trade |

---

## Position Sizing

All bets use fixed unit sizing. The target dollar amount per bet is set by `UNIT_SIZE` (default $1.00). The number of contracts purchased is `round(UNIT_SIZE / ask_price)`, ensuring each bet risks approximately the same dollar amount regardless of contract price.

Examples at UNIT_SIZE = $1.00:

| Ask Price | Contracts | Actual Cost |
|---|---|---|
| $0.02 | 50 | $1.00 |
| $0.13 | 8 | $1.04 |
| $0.50 | 2 | $1.00 |
| $0.76 | 1 | $0.76 |

Quarter-Kelly criterion determines the maximum recommended size. If Kelly suggests a larger bet than `UNIT_SIZE`, the fixed unit still applies. If Kelly suggests a smaller bet, the bet is skipped or reduced.

---

## Data Flow

| File Path | Contents |
|---|---|
| `data/history/kalshi_trades.json` | Complete trade log: edge estimate, sizing, fill price, fees, status |
| `data/history/kalshi_settlements.json` | Settlement history with outcome, realized P&L, edge calibration |
| `data/watchlists/kalshi_opportunities.json` | Latest scored opportunities from the edge detector |
| `data/positions/open_positions.json` | Snapshot of current open positions |
| `data/finagent.db` | SQLite database (schema defined in `scripts/sql/init_db.sql`) |
| Executor logs (stdout) | Per-run pipeline output: markets scanned, opportunities found, orders placed |

---

## Remaining Work

### Phase 2: Expand Edge Sources

| Task | Priority | Notes |
|---|---|---|
| Spread model recalibration | P1 | Re-derive adjustment rate from historical data; current 3%/point is heuristic |
| Weather model (NOAA) | P1 | High-frequency daily markets, free data |
| Economic data model (FRED) | P1 | CPI, jobs, GDP -- recurring events |
| Player prop models | P2 | Requires additional stat data sources |
| CLV tracking | P2 | Validates whether models actually find edge |

### Phase 3: Operational Improvements

| Task | Priority | Notes |
|---|---|---|
| Initialize SQLite database | P2 | Run `init_db.sql`, migrate trade log to DB |
| Create `requirements.txt` | P2 | Document all Python dependencies |
| Calibration dashboard | P2 | Estimated edge vs. realized edge over time |

### Phase 4: Go Live

| Task | Criteria |
|---|---|
| Switch to production | 500+ demo bets, Sharpe > 0.5, drawdown < 30%, edge realization > 75% |
| Start small | $1-5 per contract on production |
| Scale up | Increase sizing as edge is confirmed over 30+ days |
