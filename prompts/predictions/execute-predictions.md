# Execute Prediction Market Bets

Scan a prediction category and execute the best picks through the pipeline.

> **⚠️ Prediction execution is gated off by default (Gate 4.7 / R25).** Crypto, weather, SPX, mentions, companies, and politics bets are **rejected at the risk gate** unless `ALLOW_PREDICTION_BETS=true` is set in `.env`. Scans (preview) always work; only `--execute` is blocked. If you set this in `.env`, restart any running Streamlit app (gates snapshot at import). For a one-off CLI run you can prepend it:
> ```
> ALLOW_PREDICTION_BETS=true python scripts/scan.py prediction --filter <category> --min-edge 0.05 --max-bets 5 --unit-size 1 --exclude-open --execute
> ```

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
