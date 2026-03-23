# Championship Futures Scan

Scan all available championship/futures markets and find the best edges. Compare Kalshi prices against sportsbook outright odds.

```
python scripts/kalshi/futures_edge.py scan --min-edge 0.01 --top 20
```

For each opportunity:
- Team/candidate name and what they're competing for
- Kalshi price vs sportsbook consensus fair value
- Edge percentage and number of books confirming
- Whether this is a YES bet (team wins) or NO bet (team doesn't win)
- Capital lockup period (when does this settle?)

Rank by edge and tell me which 3-5 are worth betting on.
