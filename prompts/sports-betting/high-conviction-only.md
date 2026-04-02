# High Conviction Only

I only want bets where we have very strong edge. Scan all sports with a high bar -- 5%+ edge, high confidence, good liquidity.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --min-edge 0.05 --top 10 --date today --exclude-open --save
```

To focus on one market type, add `--category game`, `--category total`, etc.

Filter out anything with:
- Confidence below "high"
- Composite score below 8.0
- Spread wider than $0.10

For each remaining pick, show the Bet, Type, Pick, Edge, Conf, and Score columns. Give me a conviction rating (1-10) and explain what would have to go wrong for this bet to lose. Include team stats and sharp money context.
