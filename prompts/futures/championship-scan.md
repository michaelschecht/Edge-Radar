# Championship Futures Scan

Scan all available championship/futures markets and find the best edges. Compare Kalshi prices against sportsbook outright odds using N-way de-vigging.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py futures --min-edge 0.005 --top 20 --exclude-open
```

Output columns: Bet Type, Candidate, Date, Side, Mkt, Fair, Edge, Conf.

For each opportunity:
- Team/candidate name and what they're competing for
- Kalshi price vs de-vigged sportsbook fair value
- Edge percentage and number of books confirming
- Whether this is a YES bet (team wins) or NO bet (team doesn't win)
- Capital lockup period (when does this settle?)

Rank by edge and tell me which 3-5 are worth betting on. Be honest about liquidity concerns -- futures edges of 0.5-2% are typical.
