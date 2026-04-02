# S&P 500 Daily Scan

Check S&P 500 binary options for edge using current SPX price and VIX.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py prediction --filter spx --min-edge 0.03 --top 15 --exclude-open
```

Output columns: Title | Date | Cat. | Side | Mkt | Fair | Edge | Conf | Score

Tell me:
- Current SPX price and VIX level
- Which strike prices have the most edge
- Whether the edge is on YES (SPX stays above) or NO (SPX drops below)
- How VIX level affects the opportunities -- high VIX = more uncertainty = more potential mispricing
- Settlement time (today's close? this week?)

Is VIX elevated right now? If so, which strikes are most likely mispriced?
