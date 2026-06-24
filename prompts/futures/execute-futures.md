# Execute Futures Bets

Scan championship/futures markets and execute the best picks. Futures edges are small (0.5–2% is normal) and capital locks up until the season resolves, so be disciplined and size small.

> Futures execution mirrors the automated **Weekly-Futures-Execution** task (Saturdays): `scan.py futures --execute` with a small budget, capped at a few bets. Most weeks it places **zero** bets by design — that's expected, not a failure.

```
python scripts/kalshi/kalshi_executor.py status

# Preview first
python scripts/scan.py futures --filter <sport> --min-edge 0.01 --top 20 --exclude-open --save

# Execute with a tight budget cap
python scripts/scan.py futures --filter <sport> --min-edge 0.01 --max-bets 3 --unit-size 1 --budget 5% --exclude-open --execute
```

Replace `<sport>` with: `nfl-futures`, `nba-futures`, `nhl-futures`, `mlb-futures`, `ncaab-futures`, `golf-futures`. Omit `--filter` to scan all futures at once.

Output columns: Bet Type, Candidate, Date, Side, Mkt, Fair, Edge, Conf.

## Discipline

1. Show the preview first — Candidate, Side (YES/NO), Mkt price, Fair value, Edge, Conf
2. Wait for confirmation before executing
3. Prefer YES bets where edge supports it (lower cost, cleaner ROI)
4. Flag any pick where the displayed Kalshi price looks **stale or unfillable** — futures liquidity is thin
5. After execution: orders placed, fill status, total cost, updated balance, and the settlement horizon (these positions lock up for weeks/months)

If the best edge is under ~0.5%, say so honestly and recommend skipping — daily game betting usually offers better value.
