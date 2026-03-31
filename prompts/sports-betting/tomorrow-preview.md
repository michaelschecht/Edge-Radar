# Tomorrow's Preview

Look ahead to tomorrow's slate. Get early lines before they move.

```
python scripts/scan.py sports --min-edge 0.02 --top 20 --date tomorrow --exclude-open
```

Tell me:
- How many games are available and across which sports
- Top 10 early edges -- these may widen or narrow by game time
- Any lines that look soft and likely to move (bet now vs wait)
- Which games have the most books disagreeing (signal for mispricing)
- Any games where we already have an open position on a related market

Save for morning comparison: add `--save` to the command above.
