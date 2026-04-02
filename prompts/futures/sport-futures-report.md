# Sport-Specific Futures Report

Generate a detailed futures analysis report for `<sport>`. Replace with: `nfl-futures`, `nba-futures`, `nhl-futures`, `mlb-futures`, `golf-futures`, `ncaab-futures`.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py futures --filter <sport> --min-edge 0.005 --top 30 --save --exclude-open
```

Output columns: Bet Type, Candidate, Date, Side, Mkt, Fair, Edge, Conf.

Build a report that includes:
- Top 5 edge opportunities with full analysis of each
- Complete market landscape table (all teams/candidates with prices)
- Sportsbook championship consensus odds
- Methodology explanation (N-way de-vigging across all candidates, sharp book weighting)
- Liquidity assessment for each pick
- Caveats and risk factors
- Clear recommendation: buy, hold, or wait for better entry

The `--save` flag writes the report to `reports/Futures/`.
