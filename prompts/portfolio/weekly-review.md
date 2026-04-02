# Weekly Performance Review

End-of-week analysis: settle all bets, review performance, identify what's working, and plan next week.

## Steps

1. Settle all outstanding bets:
```bash
python scripts/kalshi/kalshi_settler.py settle
```

2. Reconcile trade log against Kalshi API:
```bash
python scripts/kalshi/kalshi_settler.py reconcile
```

3. Generate detailed performance report:
```bash
python scripts/kalshi/kalshi_settler.py report --detail --save
```

4. Check current portfolio state:
```bash
python scripts/kalshi/risk_check.py --save
```

5. Preview next week's futures for early lines:
```bash
python scripts/scan.py futures --min-edge 0.005 --top 15 --exclude-open --save
```

## Analysis to provide

Using the settlement report, break down:

- **Win rate by category**: ML vs Spread vs Total vs Prop -- which categories are profitable?
- **Win rate by sport**: MLB vs NBA vs NHL -- where is the edge model strongest?
- **Win rate by confidence**: High vs Medium -- is the confidence scoring well-calibrated?
- **Edge realization**: Average estimated edge vs realized ROI -- are we over/under-estimating?
- **CLV (Closing Line Value)**: Did we beat the close? If CLV is positive, the edge detection is sound even if short-term results vary.
- **Profit factor**: Revenue / losses -- above 1.0 means profitable. Above 1.5 is strong.
- **Best/worst trades**: What drove the biggest wins and losses?

## Key questions

1. Should we adjust min-edge threshold based on what's actually profitable?
2. Are there any sports or categories we should stop betting on?
3. Is the unit size appropriate given the bankroll and win rate?
4. Any concerning concentration patterns (too many bets on same sport/game)?
