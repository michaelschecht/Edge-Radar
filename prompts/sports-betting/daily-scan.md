# Daily Sports Scan

Run a full scan across all active sports, show me the top opportunities with the highest edge. Don't execute -- just show me what's out there.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --min-edge 0.03 --top 20 --date today --exclude-open
```

For each opportunity, explain:
- What the bet is in plain English (matchup, side, market type)
- Why there's edge (what do sportsbooks say vs Kalshi?)
- Confidence level and how many books agree
- Sharp money signals or line movement, if any
- Recommended position size at $1 unit

Save the scan: add `--save` to the scan command above.
