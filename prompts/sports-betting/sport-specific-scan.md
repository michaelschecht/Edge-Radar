# Sport-Specific Scan

Scan a single sport for tonight's betting opportunities. Replace `<sport>` with: `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, `ncaawb`, `mls`, `ufc`, `boxing`, `esports`.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/kalshi_executor.py run --filter <sport> --min-edge 0.03 --top 15
```

Give me a breakdown of:
- Total markets scanned and how many have edge
- The top 5 picks ranked by composite score
- For each pick: the matchup, our side, the edge, and a one-sentence rationale
- Total cost if we bet all 5 at $1 unit size
- Any games I should watch for live movement
