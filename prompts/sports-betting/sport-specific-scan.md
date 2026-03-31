# Sport-Specific Scan

Scan a single sport for today's/tonight's betting opportunities. Replace `<sport>` with: `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, `ncaawb`, `mls`, `ufc`, `boxing`, `esports`.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --filter <sport> --min-edge 0.03 --top 15 --date today --exclude-open
```

Give me a breakdown of:
- Total markets scanned and how many have edge
- The top 5 picks ranked by composite score
- For each pick: the matchup, game date/time, our side, the edge, and a one-sentence rationale
- Team stats context (win%, L10, streak) for each pick
- Sharp money or line movement signals
- Total cost if we bet all 5 at $1 unit size
- Any games I should watch for live movement

To save the report: add `--save` to the scan command.
