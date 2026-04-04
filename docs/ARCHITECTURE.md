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

Filter opportunities through nine risk gates (see Risk Management below). Reject any bet that fails a gate. Surviving opportunities are sized via quarter-Kelly criterion, with the flat unit size as a floor. Kelly scales up high-edge bets, capped by max bet size and max concentration limits.

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

Confidence (low/medium/high) is determined by four factors:
1. **Book count and agreement** — more books with tighter consensus = higher confidence
2. **Book spread range** — high disagreement (>4 points) signals injury news or stale lines, drops confidence
3. **Team stats** — win% from ESPN/NHL/MLB APIs. Stats that support the bet direction bump confidence up; stats that contradict drop it down
4. **Sharp money / line movement** — ESPN open vs close odds detect reverse line movement. When the line moves opposite to public money, sharp bettors are on the other side. Signals that agree with our bet boost confidence.

### Predictions (Model-Specific)

| Market Type | Data Source | Method |
|---|---|---|
| Crypto (BTC, ETH, XRP, DOGE, SOL) | CoinGecko | Current price + 24h volatility vs. Kalshi strike; probability derived from log-normal distribution |
| Weather (13 US cities) | NWS / NOAA | Ensemble forecast temperature distributions vs. Kalshi strike thresholds |
| S&P 500 | Yahoo Finance + VIX | Current level + implied volatility to derive probability of reaching Kalshi strike by expiry |
| Cross-market (all matchable) | Polymarket Gamma API | Fuzzy-match Kalshi markets to Polymarket equivalents; price discrepancy = edge signal. Also enriches existing edges with confirmation/disagreement |

---

## How Scoring Works

Four independent attributes are calculated for every opportunity. They build on each other but are derived from different data sources.

```
Sportsbook odds ──→ FAIR VALUE ──→ EDGE (vs Kalshi price)──┐
                         │                                   │
Book count + agreement ──→ CONFIDENCE ──────────────────────┤
                                                             ├──→ SCORE
Bid/ask spread ──────────→ Liquidity ───────────────────────┤
                                                             │
Time to expiry ──────────→ Time factor ─────────────────────┘
```

### Fair Value

The model's estimate of the true probability. Derived purely from sportsbook odds:

1. Fetch odds from 8-12 US sportsbooks
2. De-vig each book's line (multiplicative method) to extract true implied probability
3. Take the **weighted median** — sharp books (Pinnacle, Circa) weighted 3x, recreational books (DraftKings, FanDuel) weighted 0.7x
4. For spreads/totals: infer expected margin/total from book lines, then apply **normal CDF** with sport-specific standard deviations

Result: a probability (e.g., 0.74 = "74% chance this team wins").

### Edge

How mispriced the Kalshi contract is. Pure math, no judgment:

```
edge = fair_value - kalshi_ask_price
```

Example: fair value = $0.74, Kalshi asks $0.61 → edge = **+13.3%**

A positive edge means Kalshi is underpricing the outcome relative to sportsbook consensus.

### Confidence

How much to trust the fair value estimate. Derived from **data quality**, not edge size. A 30% edge with low confidence may be stale data; a 3% edge with high confidence is a real, durable signal.

**Base confidence** (from book consensus):

| Market Type | Low | Medium | High |
|---|---|---|---|
| Game (ML) | < 5 books | 5+ books | 8+ books AND fair range < 5% |
| Spread | < 3 books OR range > 4pts | 3+ books AND range ≤ 4pts | 6+ books AND range ≤ 2pts |
| Total | < 3 books | 3+ books | (via adjustments only) |

**Adjustments** (each can bump confidence up or down one level):
- **Team stats** — win%, L10, home/away from ESPN/NHL/MLB APIs. Stats that support the bet direction bump up; contradicting stats bump down.
- **Sharp money / line movement** — ESPN open-vs-close odds. Reverse line movement (line moves opposite to public money) that agrees with our bet bumps up; disagreement bumps down.

### Score (Composite)

The final ranking that combines all signals into a single 0-10 number:

| Component | Weight | Source |
|---|---|---|
| Edge strength | 40% | `min(edge / 0.01, 10)` — scales linearly, caps at 10% edge |
| Confidence | 30% | low = 3, medium = 6, high = 9 |
| Liquidity | 20% | `10 - (bid_ask_spread * 20)` — tighter spread = higher score |
| Time | 10% | Fixed at 5 (placeholder for time-to-expiry weighting) |

**Example:** A bet with 8% edge, high confidence, and tight spread:
- Edge: min(8, 10) × 0.40 = **3.2**
- Confidence: 9 × 0.30 = **2.7**
- Liquidity: 9.0 × 0.20 = **1.8**
- Time: 5 × 0.10 = **0.5**
- **Score = 8.2**

The minimum score to pass risk checks is 6.0 (configurable via `MIN_COMPOSITE_SCORE`).

---

## Risk Management

### Risk Gates

Every order must pass all nine gates before execution.

| Gate | Check | Reject Condition |
|---|---|---|
| 1. Daily loss limit | Sum of realized losses today | Losses >= `MAX_DAILY_LOSS` |
| 2. Position count | Number of open positions | Count >= `MAX_OPEN_POSITIONS` |
| 3. Edge threshold | Calculated edge for this opportunity | Edge < `MIN_EDGE_THRESHOLD` |
| 4. Composite score | Weighted score across edge, confidence, liquidity, time | Score < `MIN_COMPOSITE_SCORE` |
| 5. Confidence level | Model confidence rating (low / medium / high) | Confidence < `MIN_CONFIDENCE` |
| 6. Duplicate ticker | Already holding this exact market | Ticker in open positions |
| 7. Per-event cap | Too many positions on the same game/event | Event count >= `MAX_PER_EVENT` |
| 8. Max concentration | Single position would exceed % of bankroll | Cost > `MAX_CONCENTRATION` * bankroll |
| 9. Max bet size | Category-aware bet size cap | Cost > `MAX_BET_SIZE_SPORTS` or `MAX_BET_SIZE_PREDICTION` |

### Risk Parameters

| Env Variable | Default | Description |
|---|---|---|
| `UNIT_SIZE` | $1.00 | Minimum dollar amount per bet (Kelly floor) |
| `KELLY_FRACTION` | 0.25 | Quarter-Kelly sizing multiplier |
| `MAX_BET_SIZE_SPORTS` | $50 | Maximum USD per sports bet |
| `MAX_BET_SIZE_PREDICTION` | $100 | Maximum USD per prediction market position |
| `MAX_DAILY_LOSS` | $250 | Hard stop -- no new positions after this daily loss |
| `MAX_OPEN_POSITIONS` | 10 | Maximum concurrent open positions |
| `MAX_PER_EVENT` | 3 | Maximum positions on the same game/event |
| `MAX_POSITION_CONCENTRATION` | 20% | Maximum single position as % of bankroll |
| `MIN_EDGE_THRESHOLD` | 3% | Minimum edge required to consider a bet |
| `MIN_COMPOSITE_SCORE` | 6.0 | Minimum composite opportunity score |
| `MIN_CONFIDENCE` | medium | Minimum model confidence level |

---

## Position Sizing

Bets are sized using **quarter-Kelly with a flat unit floor**. The system calculates both a flat unit size and a Kelly-optimal size, then uses whichever is larger -- so Kelly only scales up for high-edge opportunities, never below the minimum unit.

**Quarter-Kelly formula:** `bet = 0.25 * edge * bankroll / market_price`

The result is then capped by (in order): max concentration (20% of bankroll), max bet size ($50 sports / $100 prediction), and available bankroll.

Examples at UNIT_SIZE = $1.00, bankroll = $50:

| Ask Price | Edge | Flat Contracts | Kelly Contracts | Used | Actual Cost |
|---|---|---|---|---|---|
| $0.50 | 3% | 2 | 1 | 2 (flat) | $1.00 |
| $0.50 | 15% | 2 | 4 | 4 (Kelly) | $2.00 |
| $0.10 | 10% | 10 | 13 | 13 (Kelly) | $1.30 |
| $0.02 | 5% | 50 | 31 | 50 (flat) | $1.00 |

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

For the full enhancement roadmap (completed and pending items), see [ROADMAP.md](enhancements/ROADMAP.md).

Key remaining priorities:
- **Backtesting framework** -- replay settled markets, calibration curve, win rate by dimension
- **Bullpen availability tracker** -- high-value for MLB totals (pitcher data now live)
- **Injury impact scoring** -- ESPN injury reports, star player adjustments
- **Wind direction classification** -- NWS bearing relative to stadium orientation
