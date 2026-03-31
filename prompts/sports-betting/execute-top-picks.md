# Execute Top Picks

Scan for the best opportunities on `<sport>` and execute the top picks. Be disciplined -- only bet where edge is real.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --filter <sport> --min-edge 0.05 --max-bets 5 --unit-size 1 --date today --exclude-open --execute
```

Replace `<sport>` with: `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, etc.

1. First show me the preview -- what you plan to bet and why
2. Wait for my confirmation before executing
3. After execution, show me: orders placed, fill status, total cost, updated balance
4. Remind me when to run `python scripts/kalshi/kalshi_settler.py settle`

To cherry-pick specific rows instead of top N: replace `--max-bets 5` with `--pick '1,3,5'`.
