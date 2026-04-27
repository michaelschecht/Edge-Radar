# Execute Prediction Market Bets

Scan a prediction category and execute the best picks through the pipeline.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py prediction --filter <category> --min-edge 0.05 --max-bets 5 --unit-size 1 --exclude-open --execute
```

Replace `<category>` with: `crypto`, `btc`, `eth`, `xrp`, `doge`, `sol`, `weather`, `spx`, `mentions`, `companies`, `politics`.

Output columns: Title | Date | Cat. | Side | Mkt | Fair | Edge | Conf | Score

1. Show me the preview first with plain English explanations
2. Wait for my go-ahead
3. Execute and report results
4. Tell me when each bet settles so I know when to run `python scripts/kalshi/kalshi_settler.py settle`
