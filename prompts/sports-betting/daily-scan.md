# Daily Sports Scan

Run a full scan across all active sports, show me the top opportunities with the highest edge. Don't execute -- just show me what's out there.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --min-edge 0.03 --top 20 --date today --exclude-open --save
```

To narrow by market type, add `--category game`, `--category spread`, `--category total`, or `--category player_prop`.

For each opportunity, explain:
- The Bet (matchup), Type (ML/Spread/Total/Prop), and Pick (e.g. "Spurs win", "Over 220.5")
- Why there's edge (sportsbook consensus vs Kalshi price)
- Confidence level and how many books agree
- Sharp money signals or line movement, if any
- Recommended position size at $1 unit

Reports auto-save to `reports/Sports/` when `--save` is included.
