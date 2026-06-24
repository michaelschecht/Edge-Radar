# Player Props Scan

Scan player-prop markets only — points, rebounds, assists, goals, strikeouts, etc. — for the sports that carry them on Kalshi (primarily NBA and NHL).

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --filter nba --category player_prop --min-edge 0.05 --top 20 --date today --exclude-open --save
```

Swap `--filter nba` for `nhl` to scan hockey props (goals, points, assists, first goal). NBA carries the widest prop coverage (PTS, REB, AST, BLK, STL, 3PT).

To execute the top picks:

```
python scripts/scan.py sports --filter nba --category player_prop --min-edge 0.06 --max-bets 5 --unit-size 1 --date today --exclude-open --execute
```

## What to look for

- **Pick clarity**: each row's Pick names the player and line (e.g. "LeBron Over 26.5 PTS")
- **Book agreement**: props move on lineup/usage news — LOW confidence often means a late scratch or role change; be cautious
- **Edge 5%+**: prop lines are softer than game lines but also noisier; demand a higher edge bar
- **Avoid stacking correlated props** on the same player/game — the per-event cap (Gate 6) helps, but check manually
- **Liquidity**: prop markets are thinner; flag any pick where the bid/ask spread is wide
