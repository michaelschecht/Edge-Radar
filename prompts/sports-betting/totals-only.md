# Totals-Only Scan

Scan for over/under edges only -- no moneylines or spreads. Useful when you want to focus on game totals where the model is strongest.

## Steps

1. Check current portfolio:
```bash
python scripts/kalshi/kalshi_executor.py status
```

2. Scan totals across all sports today:
```bash
python scripts/scan.py sports --category total --min-edge 0.03 --top 20 --date today --exclude-open --save
```

Or filter to a single sport:
```bash
python scripts/scan.py sports --filter nba --category total --min-edge 0.03 --top 15 --date today --exclude-open
```

3. To execute top picks:
```bash
python scripts/scan.py sports --filter nba --category total --min-edge 0.05 --max-bets 5 --unit-size 1 --date today --exclude-open --execute
```

## What to look for

The output table shows: Bet (matchup), Type (Total), Pick (e.g., "Over 220.5" or "Under 235.5"), When, Mkt, Fair, Edge, Conf, Score.

Focus on:
- **High confidence**: At least 5+ books agree on the total
- **Weather flags**: Outdoor games with wind/rain lean toward unders
- **Edge 5%+**: Totals with big edges tend to have the best CLV
- **Same-game stacking**: If you see both an over and under on the same game at different strikes, the model sees the market total as significantly off
