# Performance & Calibration Report

Generate a post-hoc performance report on closed positions — win rate, ROI, edge calibration, and Brier score — to judge whether the edge model is well-calibrated.

Prefer the dedicated skill, which wraps the settlement + calibration analysis:

```
/edge-radar-analysis
```

Or assemble it from the settlement tooling directly:

```
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail --save
python scripts/kalshi/kalshi_settler.py reconcile
```

## What to surface

- **Brier score** and edge calibration — do claimed edges match realized outcomes? (Baseline reference: ~0.26 Brier at 76 trades; recalibrate around 100+ settled trades.)
- **Win rate by confidence tier** — is "high" actually outperforming "medium"? (Calibration has previously shown the opposite, which is why confidence bumps are one-way — R13.)
- **Win rate by sport and market type** — where is the model strongest/weakest?
- **CLV** — are we beating the closing line?
- **Reconciliation** — any drift between the trade log and Kalshi's record
- Concrete threshold or sizing adjustments to feed back into `.env`

See also `prompts/analysis/backtest.md` (what-if simulations) and `prompts/portfolio/weekly-review.md` (weekly cadence).
