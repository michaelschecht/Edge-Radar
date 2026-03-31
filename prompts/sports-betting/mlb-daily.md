# MLB Daily Scan

Focused MLB scan with full context. MLB is our highest-volume sport -- scan thoroughly.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --filter mlb --min-edge 0.03 --top 25 --date today --exclude-open --save
```

For each opportunity, I want the full picture:
- Matchup, game time, home/away
- Our side and edge (game, spread, or total)
- Team stats: win%, L10 record, streak
- Sharp money: which direction are the sharps on?
- Line movement: has the line moved since open?
- Weather impact (outdoor stadiums only): wind, rain, temperature
- Confidence level and composite score

Group by game so I can see all angles on the same matchup. Flag any games where we have edge on multiple markets (e.g., game + total on the same matchup).

Rank the top 5 and tell me which ones to bet on first.
