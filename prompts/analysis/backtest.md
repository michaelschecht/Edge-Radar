# Backtest & Strategy Simulation

Analyze settled trades to see what's actually working: win rate, signal quality, edge realization, and risk-adjusted returns. Run what-if simulations to compare alternative strategies.

```
# Full backtest report
python scripts/backtest/backtester.py --save

# Slice the analysis
python scripts/backtest/backtester.py --sport mlb           # one sport
python scripts/backtest/backtester.py --min-edge 0.05       # only edges >= 5%
python scripts/backtest/backtester.py --confidence high     # only high-confidence bets

# Compare strategies (what-if simulation)
python scripts/backtest/backtester.py --simulate --save
```

## What to surface

- **Win rate and ROI** overall, then sliced by sport, market type (ML/Spread/Total/Prop), and confidence tier
- **Edge realization**: average claimed edge vs realized ROI — are we over- or under-estimating edge?
- **CLV (closing line value)**: are we beating the close? Positive CLV means the edge model is sound even when short-term results swing
- **Profit factor** (revenue ÷ losses): >1.0 profitable, >1.5 strong
- **Strategy simulation**: which min-edge / confidence / sport filters would have improved results?
- **Concrete recommendation**: thresholds to adjust, sports/categories to drop or lean into

Reports save under `reports/` when `--save` is included. Pair this with `prompts/portfolio/weekly-review.md` for the settlement-side view.
