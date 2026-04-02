# Compare Two Sports

Scan two different sports and tell me which has better opportunities right now.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --filter <sport1> --min-edge 0.03 --top 10 --date today --exclude-open --save
python scripts/scan.py sports --filter <sport2> --min-edge 0.03 --top 10 --date today --exclude-open --save
```

Replace `<sport1>` and `<sport2>` with: `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, etc.

Compare:
- Number of opportunities above threshold
- Average edge per opportunity
- Distribution of Type (ML/Spread/Total/Prop) and Conf levels
- Liquidity (bid/ask spreads)
- Sharp money signals -- which sport has more books agreeing?
- Settlement timing (how soon do we get paid?)
- Overall recommendation: where should I focus tonight's betting?
