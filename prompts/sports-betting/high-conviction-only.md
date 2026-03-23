# High Conviction Only

I only want bets where we have very strong edge. Scan all sports with a high bar -- 5%+ edge, high confidence, good liquidity.

```
python scripts/kalshi/kalshi_executor.py run --min-edge 0.05 --top 10
```

Filter out anything with:
- Confidence below "high"
- Composite score below 8.0
- Spread wider than $0.10

For each remaining pick, give me a conviction rating (1-10) and explain what would have to go wrong for this bet to lose.
