# Execute Prediction Market Bets

Scan a prediction category and execute the best picks through the pipeline.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/kalshi_executor.py run --prediction --filter <category> --min-edge 0.05 --max-bets 5 --unit-size 1
```

Replace `<category>` with: `crypto`, `weather`, `spx`, `mentions`, `companies`, `politics`, `techscience`.

1. Show me the preview first with plain English explanations
2. Wait for my go-ahead
3. Execute and report results
4. Tell me when each bet settles so I know when to run `/kalshi-bet settle`
