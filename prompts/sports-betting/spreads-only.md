# Spreads-Only Scan

Scan for point spread edges only -- no moneylines or totals. The normal CDF model with sport-specific standard deviations handles alternate spreads well.

## Steps

1. Check current portfolio:
```bash
python scripts/kalshi/kalshi_executor.py status
```

2. Scan spreads across all sports today:
```bash
python scripts/scan.py sports --category spread --min-edge 0.03 --top 20 --date today --exclude-open --save
```

Or filter to a single sport:
```bash
python scripts/scan.py sports --filter nba --category spread --min-edge 0.05 --top 15 --date today --exclude-open
```

3. To execute top picks:
```bash
python scripts/scan.py sports --filter nba --category spread --min-edge 0.05 --max-bets 5 --unit-size 1 --date today --exclude-open --execute
```

## What to look for

The output table shows: Bet (matchup), Type (Spread), Pick (e.g., "Spurs -4.5" or "Warriors +7.5"), When, Mkt, Fair, Edge, Conf, Score.

Focus on:
- **Confidence**: Spread edges with LOW confidence are often from book disagreement (injury news) -- be cautious
- **Alternate spreads**: Large edges on big alternate spreads (e.g., -15.5) can look tempting but have high variance
- **Sharp money alignment**: If the Pick direction matches sharp money signal, confidence is higher
- **Team stats**: Check if the team's recent record (L10, home/away) supports the spread direction
