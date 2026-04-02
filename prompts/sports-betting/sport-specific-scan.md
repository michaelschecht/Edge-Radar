# Sport-Specific Scan

Scan a single sport for today's/tonight's betting opportunities. Replace `<sport>` with: `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, `ncaawb`, `mls`, `ufc`, `boxing`, `esports`.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --filter <sport> --min-edge 0.03 --top 15 --date today --exclude-open --save
```

To scan only one market type, add `--category game`, `--category spread`, `--category total`, or `--category player_prop`.

Give me a breakdown of:
- Total markets scanned and how many have edge
- The top 5 picks ranked by composite score
- For each pick: the Bet (matchup), Type (ML/Spread/Total/Prop), Pick (our side), When, Edge, Conf, and Score
- Team stats context (win%, L10, streak) for each pick
- Sharp money or line movement signals
- Total cost if we bet all 5 at $1 unit size
- Any games I should watch for live movement

Reports auto-save to `reports/Sports/` when `--save` is included.
