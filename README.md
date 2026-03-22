# Strategies — FinAgent

This directory contains strategy configurations, parameters, and backtest results for each approach deployed by the platform.

---

## Strategy Index

| Strategy | Market | Status | Edge Type |
|---|---|---|---|
| [Line Shopping Arbitrage](#arbitrage) | Sports | 🟡 In Development | Cross-book price discrepancy |
| [Closing Line Value (CLV)](#clv) | Sports | 🟡 In Development | Beat the closing line |
| [Sharp Money Fade/Follow](#sharp) | Sports | 🟡 In Development | Steam move detection |
| [Value Betting (Model Edge)](#value) | Sports/Prediction | 🟢 Active | Model vs. market probability |
| [Prediction Market Arbitrage](#pm-arb) | Prediction | 🟡 In Development | Cross-platform pricing |
| [Earnings IV Crush](#iv-crush) | Options | 🟡 In Development | Volatility overpricing |
| [Momentum + Mean Reversion](#momentum) | Stocks | 🔴 Research | Technical signals |
| [DFS Ownership Leverage](#dfs-gpp) | DFS | 🟢 Active | Contrarian + stack value |

---

## Strategy Detail

### Line Shopping Arbitrage {#arbitrage}
**Concept:** When the same outcome is priced differently across books, guaranteed profit exists if you can get both sides down simultaneously.

**Requirements:**
- Accounts at 3+ books simultaneously
- Fast execution (lines move quickly)
- Transaction fees accounted for in edge calculation

**Key parameters:**
```python
MIN_ARB_EDGE = 0.01  # 1% minimum guaranteed edge
MAX_EXECUTION_WINDOW_SECONDS = 120  # Lines may move; act fast
BOOKS_TO_MONITOR = ["pinnacle", "betonline", "bookmaker", "fanduel", "draftkings"]
```

---

### Closing Line Value (CLV) {#clv}
**Concept:** If you consistently beat the closing line, you are a long-run winner regardless of short-term results. The closing line is the most accurate probability estimate.

**Key insight:** Books sharpen lines over time as sharp money comes in. If you bet early at a number that is later moved against you, that's evidence of edge.

**Tracking:** Compare `bet_odds` vs. `closing_line_odds` for every sports bet. Target CLV of +1.5% or better.

---

### Sharp Money Detection {#sharp}
**Concept:** Track line movement relative to public betting percentages. When the line moves against the public, sharp money is likely responsible.

**Signals:**
- Reverse line movement: Public on Team A, line moves toward Team B
- Steam move: Rapid, simultaneous line movement across multiple books
- Respected handicapper consensus

---

### Value Betting (Model Edge) {#value}
**Concept:** Build probability models that outperform market-implied probabilities. Bet when model probability > market probability by at least MIN_EDGE.

**Active models:**
- `models/nba_model.pkl` — NBA point spreads & totals
- `models/nfl_model.pkl` — NFL spreads, totals, team props
- `models/prediction_base_rate.pkl` — Prediction market event base rates

---

### DFS Ownership Leverage {#dfs-gpp}
**Concept:** In GPP (tournament) DFS, winning requires differentiated lineups. Target players with high projected scores but low ownership — the "leverage" play.

**Cash game approach:** Maximize floor (consistency), prefer chalk.
**GPP approach:** Maximize ceiling, target ownership gaps, use correlated stacks.

**Key metrics:**
- `pts_per_dollar` — Value metric (projection / salary * 1000)
- `ownership_gap` — Projected ownership vs. my target ownership
- `correlation_score` — How well lineup pieces correlate (game stacks)

---

## Backtesting Standard

All strategies must pass the following before live deployment:

1. **Minimum history:** 500+ events in backtest sample
2. **Out-of-sample validation:** Hold out 20% of data; backtest only on 80%
3. **Walk-forward test:** Re-run in rolling windows to avoid curve-fitting
4. **Sharpe ratio:** > 0.5 annualized
5. **Max drawdown:** < 30% of peak bankroll in simulation
6. **Edge realization:** Realized edge ≥ 75% of estimated edge
7. **Paper trading:** 30 days paper trading before live capital

---

## Adding a New Strategy

1. Create a directory: `strategies/[strategy-name]/`
2. Add `config.json` with all tunable parameters
3. Add `model.py` with edge estimation logic
4. Add `backtest.py` using the standard backtesting framework
5. Run backtest and save results to `backtest_results.json`
6. Update this README with strategy status
7. Get DATA_ANALYST sign-off before live deployment
