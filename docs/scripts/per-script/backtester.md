# backtester.py — Strategy Backtesting & Analysis

**Location:** `scripts/backtest/backtester.py`

**When to use:** Analyze settled trade history to evaluate strategy performance, identify which signals are profitable, compare filter strategies, and calibrate the edge model. Run after accumulating settled trades to guide strategy adjustments.

**Features:** Equity curve with max drawdown, Sharpe ratio, profit factor, win/lose streaks. Breakdowns by sport, category, confidence level, and edge bucket. Calibration curve (predicted probability vs actual win rate). Strategy simulation comparing different filter combinations. Markdown report export.

---

## Quick Start

```bash
# Full analysis of all settled trades
python scripts/backtest/backtester.py

# Strategy simulation (compares 13+ strategies)
python scripts/backtest/backtester.py --simulate

# Save markdown report
python scripts/backtest/backtester.py --simulate --save

# Makefile shortcuts
make backtest          # Full report
make backtest-sim      # Simulation + save
```

---

## Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--sport SPORT` | *(all)* | Filter by sport (`mlb`, `nba`, `nhl`, `ncaab`, etc.) |
| `--category CAT` | *(all)* | Filter by category (`game`, `spread`, `total`) |
| `--confidence CONF` | *(all)* | Filter by confidence level (`low`, `medium`, `high`) |
| `--min-edge N` | *(none)* | Minimum edge threshold (e.g., `0.10` for 10%+) |
| `--after DATE` | *(none)* | Only trades settled on or after this date (`YYYY-MM-DD`) |
| `--simulate` | `false` | Run strategy comparison across filter combinations |
| `--save` | `false` | Save markdown report to `reports/backtest/` |
| `--quiet` | `false` | Skip terminal output (useful with `--save`) |

---

## Examples

```bash
# MLB only
python scripts/backtest/backtester.py --sport mlb

# Totals only
python scripts/backtest/backtester.py --category total

# Medium confidence only
python scripts/backtest/backtester.py --confidence medium

# Edge >= 10%
python scripts/backtest/backtester.py --min-edge 0.10

# Trades from April onwards
python scripts/backtest/backtester.py --after 2026-04-01

# Combined: high confidence spreads with 15%+ edge
python scripts/backtest/backtester.py --confidence high --category spread --min-edge 0.15

# Full simulation with save (no terminal output)
python scripts/backtest/backtester.py --simulate --save --quiet
```

---

## Output Sections

### Summary

Overall performance: trades, record (W-L), win rate, net P&L, total wagered, ROI, profit factor, avg win/loss, best/worst trade, longest streaks, max drawdown, Sharpe ratio.

### Breakdowns

Four dimensional breakdowns, each showing trades, record, win rate, P&L, ROI, and avg edge:

| Breakdown | Groups |
|-----------|--------|
| **By Sport** | NBA, MLB, NHL, NCAAB, NFL, etc. |
| **By Category** | game (moneyline), spread, total (over/under) |
| **By Confidence** | low, medium, high |
| **By Edge Bucket** | 3-5%, 5-10%, 10-15%, 15-25%, 25%+ |

### Calibration Curve

Compares predicted probability (fair_value) against actual win rate in 7 buckets (0-30%, 30-40%, ..., 80-100%). The "gap" column shows whether the model is overconfident (negative gap) or underconfident (positive gap) in each range.

### Equity Curve

Day-by-day cumulative P&L with daily change. Shows the shape of the portfolio's growth/decline over time.

### Strategy Simulation (`--simulate`)

Compares 13+ strategies side by side:

| Strategy Type | Variants |
|---------------|----------|
| Baseline | All trades |
| Edge threshold | >= 5%, >= 8%, >= 10%, >= 15% |
| Confidence | Medium only, High only |
| Combined | High confidence + edge >= 10% |
| Category | Game only, Spread only, Total only |
| Sport | One per sport with 5+ trades |

Each strategy shows: trades, win rate, P&L, ROI, Sharpe ratio, max drawdown, profit factor.

---

## Data Source

Reads from `data/history/kalshi_settlements.json` (populated by `kalshi_settler.py settle`). Each settlement record contains:

- `ticker`, `side`, `won`, `result`
- `contracts`, `cost`, `revenue`, `fees`, `net_pnl`, `roi`
- `edge_estimated`, `fair_value`, `market_price_at_entry`
- `confidence`, `settled_at`

Sport and category are derived from the ticker pattern at runtime.

---

## Saved Reports

When `--save` is used, a timestamped markdown report is written to:

```
reports/backtest/backtest_YYYY-MM-DD_HHMM.md
```

The report includes all sections (summary, breakdowns, calibration, equity curve) plus the strategy simulation table if `--simulate` was used.

---

## Interpreting Results

**Key metrics to watch:**

| Metric | Good Sign | Red Flag |
|--------|-----------|----------|
| ROI | Positive and stable | Negative or wildly varying |
| Profit Factor | > 1.0 (wins > losses) | < 1.0 |
| Sharpe Ratio | > 1.0 (risk-adjusted) | < 0.5 |
| Max Drawdown | < 30% of peak | > 50% of peak |
| Calibration Gap | Within +/- 5% per bucket | > 15% systematic overconfidence |
| Win Rate vs Edge | Higher edge buckets win more | Inverted (high edge, low win rate) |

**Actionable patterns:**

- If a confidence level is losing money, consider downweighting or removing it from the model
- If spreads consistently underperform, consider excluding them or raising the edge threshold
- If high-edge trades don't convert at higher rates, the edge model may be miscalibrated
- If the calibration curve shows systematic overconfidence at high probabilities, the de-vig or CDF model may need adjustment
