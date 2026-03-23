# Compare Two Sports

Scan two different sports and tell me which has better opportunities right now.

```
python scripts/kalshi/kalshi_executor.py run --filter <sport1> --min-edge 0.03 --top 10
python scripts/kalshi/kalshi_executor.py run --filter <sport2> --min-edge 0.03 --top 10
```

Compare:
- Average edge per opportunity
- Number of opportunities above threshold
- Liquidity (bid/ask spreads)
- Settlement timing (how soon do we get paid?)
- Overall recommendation: where should I focus tonight's betting?
