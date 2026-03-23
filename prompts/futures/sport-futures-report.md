# Sport-Specific Futures Report

Generate a detailed futures analysis report for `<sport>`. Replace with: `nfl-futures`, `nba-futures`, `nhl-futures`, `mlb-futures`, `golf-futures`, `ncaab-futures`.

```
python scripts/kalshi/futures_edge.py scan --filter <sport> --min-edge 0.005 --top 30
```

Build a report (save to `reports/<SPORT>/` folder) that includes:
- Top 5 edge opportunities with full analysis of each
- Complete market landscape table (all teams/candidates with prices)
- Sportsbook championship consensus odds
- Methodology explanation
- Caveats and risk factors
- Clear recommendation: buy, hold, or wait for better entry

Use the MLB and NBA reports in the `reports/` folder as formatting templates.
