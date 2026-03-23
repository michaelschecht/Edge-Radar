# Weekly Futures Tracker

Run a weekly scan of all futures markets and compare to last week's report. Track how edges are moving.

```
python scripts/kalshi/futures_edge.py scan --filter nfl-futures --min-edge 0.005 --top 15
python scripts/kalshi/futures_edge.py scan --filter nba-futures --min-edge 0.005 --top 15
python scripts/kalshi/futures_edge.py scan --filter nhl-futures --min-edge 0.005 --top 15
python scripts/kalshi/futures_edge.py scan --filter mlb-futures --min-edge 0.005 --top 15
```

For each sport, summarize:
- Number of opportunities and average edge (vs last week if available)
- Any new opportunities that appeared
- Any edges that closed (were available last week, gone now)
- Top pick per sport with confidence rating

Save the combined report to `reports/weekly/YYYY-MM-DD_futures_weekly.md`.
