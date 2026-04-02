# futures_edge.py — Futures & Championship Scanner

**Location:** `scripts/kalshi/futures_edge.py`

**Via scan.py:** `python scripts/scan.py futures [flags]`

**When to use:** Championship and season-long markets -- World Series, Super Bowl, Stanley Cup, NBA Finals, conference winners, PGA Tour. Uses N-way de-vigging across all candidates (not just 2-way). Use this instead of `edge_detector.py` for any futures/outright market.

---

## `scan` -- Scan Futures

```bash
python scripts/kalshi/futures_edge.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter FILTER` | (all futures) | `nfl-futures`, `nba-futures`, `nhl-futures`, `mlb-futures`, `ncaab-futures`, `golf-futures`, `futures` (all) |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--top N` | `20` | Number of top opportunities |
| `--date DATE` | (none) | Only show markets on this date (`today`, `tomorrow`, `YYYY-MM-DD`, `mar31`) |
| `--save` | off | Save results to `data/watchlists/futures_opportunities.json` |
| `--exclude-open` | off | Skip markets where you already have an open position |
| `--execute` | off | Place orders through executor pipeline |
| `--unit-size N` | (from .env) | Dollar amount per bet |
| `--max-bets N` | `5` | Max bets to place |
| `--pick '1,3'` | (none) | Execute specific rows |
| `--ticker TICKER` | (none) | Execute specific ticker(s) |

### Examples

```bash
# Preview all futures
python scripts/scan.py futures

# NHL futures with $3 sizing
python scripts/scan.py futures --filter nhl-futures --unit-size 3

# Execute top NBA futures picks
python scripts/scan.py futures --filter nba-futures --unit-size 2 --execute --max-bets 3

# Save futures scan to watchlist
python scripts/scan.py futures --filter mlb-futures --save
```

---

## Edge Detection Methodology

Futures markets have many candidates (e.g., 30 NBA teams for championship winner). The edge detection:

1. **Fetch sportsbook odds** for the outright/futures market
2. **N-way de-vig** -- removes the overround across all candidates simultaneously (not pairwise)
3. **Compare to Kalshi prices** -- each candidate's de-vigged probability vs Kalshi ask price
4. **Score** by edge, confidence (book count + agreement), and liquidity

---

## Output

**Scan-only mode** (no `--unit-size` or `--execute`): compact table with Bet Type, Candidate, Date, Side, Market Price, Fair Value, Edge, Confidence.

**Executor mode** (with `--unit-size` or `--execute`): routes through the full executor pipeline with risk checks, sizing, and the standard preview/execute table.
