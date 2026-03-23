# Daily Sports Scan

Run a full scan across all active sports, show me the top opportunities with the highest edge. Don't execute -- just show me what's out there.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/kalshi_executor.py run --min-edge 0.03 --top 20
```

For each opportunity, explain:
- What the bet is in plain English
- Why there's edge (what do sportsbooks say vs Kalshi?)
- Confidence level and how many books agree
- Recommended position size at $1 unit
