# Tomorrow's Preview

Look ahead to tomorrow's slate. Get early lines before they move.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --min-edge 0.02 --top 20 --date tomorrow --exclude-open --save
```

To focus on one market type, add `--category game`, `--category spread`, `--category total`, or `--category player_prop`.

Tell me:
- How many games are available and across which sports
- Top 10 early edges -- show the Bet, Type, Pick, Edge, Conf, and Score for each
- Any lines that look soft and likely to move (bet now vs wait)
- Which games have the most books disagreeing (signal for mispricing)
- Any games where we already have an open position on a related market

Reports auto-save to `reports/Sports/` when `--save` is included.
