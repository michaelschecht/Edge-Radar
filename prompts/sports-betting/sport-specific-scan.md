# Sport-Specific Scan

Scan a single sport for today's/tonight's betting opportunities. Replace `<sport>` with any active filter:

- **US majors:** `nba`, `nhl`, `mlb`, `nfl`
- **College:** `ncaamb`, `ncaawb`, `ncaafb`, `ncaabb`
- **Soccer:** `soccer` (all leagues), `mls`, `epl`, `ucl`, `laliga`, `seriea`, `bundesliga`, `ligue1`, `worldcup`
- **Combat:** `ufc`, `boxing`
- **Motorsports:** `f1`, `nascar`
- **Other:** `ipl` (cricket), `esports` (`cs2`, `lol`)
- **Golf:** `pga` routes to the futures scanner (outright winner markets) — see `prompts/futures/`

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py sports --filter <sport> --min-edge 0.03 --top 15 --date today --exclude-open --save
```

To scan only one market type, add `--category game`, `--category spread`, `--category total`, or `--category player_prop`.

> In-progress games are **excluded by default** (Gate 4.8). The scan flags started games with a **Started/LIVE** column; to act on them you must set `ALLOW_LIVE_BETS=true` — see `prompts/sports-betting/live-betting.md`.

Give me a breakdown of:
- Total markets scanned and how many have edge
- The top 5 picks ranked by composite score
- For each pick: the Bet (matchup), Type (ML/Spread/Total/Prop), Pick (our side), When, Edge, Conf, and Score
- Team stats context (win%, L10, streak) for each pick
- Sharp money or line movement signals
- Total cost if we bet all 5 at $1 unit size
- Any games I should watch for live movement

Reports auto-save to `reports/Sports/` when `--save` is included.
