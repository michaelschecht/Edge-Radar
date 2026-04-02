# Weekly Futures Tracker

Run a weekly scan of all futures markets and compare to last week's report. Track how edges are moving.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py futures --filter nfl-futures --min-edge 0.005 --top 15 --save --exclude-open
python scripts/scan.py futures --filter nba-futures --min-edge 0.005 --top 15 --save --exclude-open
python scripts/scan.py futures --filter nhl-futures --min-edge 0.005 --top 15 --save --exclude-open
python scripts/scan.py futures --filter mlb-futures --min-edge 0.005 --top 15 --save --exclude-open
```

Output columns per scan: Bet Type, Candidate, Date, Side, Mkt, Fair, Edge, Conf.

For each sport, summarize:
- Number of opportunities and average edge (vs last week if available)
- Any new opportunities that appeared
- Any edges that closed (were available last week, gone now)
- Top pick per sport with confidence rating

Check previous reports in `reports/Futures/` for week-over-week comparison.
Save the combined report to `reports/Futures/weekly/YYYY-MM-DD_futures_weekly.md`.
