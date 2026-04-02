# edge_detector.py — Sports Edge Scanner

**Location:** `scripts/kalshi/edge_detector.py`

**Via scan.py:** `python scripts/scan.py sports [flags]`

**When to use:** Primary script for sports betting. Scan for edge, filter by sport/date/category, preview opportunities, and execute -- all from one command. Use this for NBA, MLB, NHL, NFL, NCAA, soccer, UFC, and all other sports markets.

**Features:** Normal CDF spread/total model with sport-specific stdev, sharp book weighting (Pinnacle 3x), team stats confidence signal (ESPN/NHL/MLB), weather adjustment for NFL/MLB outdoor totals, per-game cap (top 3 per matchup).

---

## `scan` -- Batch Scan

```bash
python scripts/kalshi/edge_detector.py scan [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--filter FILTER` | (none) | Sport/prefix filter: `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, `ncaafb`, `soccer`, `mma`, `esports`, or raw ticker prefix (`KXNBA`) |
| `--category CAT` | (none) | Filter by market type: `game`, `spread`, `total`, `player_prop`, `esports`, `other` |
| `--min-edge N` | `0.03` | Minimum edge threshold |
| `--top N` | `20` | Number of top opportunities |
| `--date DATE` | (none) | Only show games on this date (`today`, `tomorrow`, `YYYY-MM-DD`, `mar31`) |
| `--save` | off | Save results to `data/watchlists/kalshi_opportunities.json` and a markdown report to `reports/Sports/` |
| `--report-dir DIR` | (auto) | Override report output directory for `--save` |
| `--exclude-open` | off | Skip markets where you already have an open position |
| `--execute` | off | Place orders through executor pipeline |
| `--unit-size N` | (from .env) | Dollar amount per bet -- routes through executor pipeline |
| `--max-bets N` | `5` | Max bets to place |
| `--pick '1,3'` | (none) | Execute specific rows from the preview table |
| `--ticker TICKER` | (none) | Execute specific ticker(s) |

### Examples

```bash
# Scan only NBA game outcomes (no spreads/totals)
python scripts/scan.py sports --filter nba --category game

# Tomorrow's MLB games only, skip open positions
python scripts/scan.py sports --filter mlb --date tomorrow --exclude-open

# Execute top 10 MLB picks at $1 each
python scripts/scan.py sports --filter mlb --execute --unit-size 1 --max-bets 10

# Scan all sports with 10% min edge, save report
python scripts/scan.py sports --min-edge 0.10 --save

# NCAA basketball totals only
python scripts/scan.py sports --filter ncaamb --category total --date today
```

---

## `detail` -- Single Market Deep Dive

```bash
python scripts/kalshi/edge_detector.py detail TICKER
```

Shows the full breakdown for one market: matched sportsbook odds, de-vigged probabilities, fair value, and edge.

```bash
python scripts/kalshi/edge_detector.py detail KXNBAGAME-26MAR25LALBOS-LAL
```

---

## Edge Detection Methodology

1. **Fetch Kalshi markets** -- pulls all open markets for the filtered sport(s)
2. **Fetch sportsbook odds** -- The Odds API with key rotation (up to 4 keys)
3. **Match markets to odds events** -- team name fuzzy matching
4. **Calculate fair value** -- de-vig each book, then take the weighted median:
   - Sharp books (Pinnacle, LowVig) weighted 3x
   - Standard books weighted 1x
5. **Team stats adjustment** -- ESPN/NHL/MLB APIs for win%, recent form. Supports NBA, NHL, MLB, NFL, NCAA, MLS
6. **Weather adjustment** -- NWS forecasts for NFL/MLB outdoor venues affect totals
7. **Sharp money signal** -- ESPN line movement detection
8. **Confidence scoring** -- based on book count, book agreement, stats signal, sharp money
9. **Composite score** -- edge (40%) + confidence (30%) + liquidity (20%) + time (10%)
10. **Per-game cap** -- max 3 opportunities per matchup to avoid over-concentration

### Sport Filters

| Filter | Ticker Prefixes | Odds API Key |
|--------|----------------|--------------|
| `nba` | KXNBAGAME, KXNBASPREAD, KXNBATOTAL, KXNBA3PT, KXNBABLK, ... | `basketball_nba` |
| `mlb` | KXMLBGAME, KXMLBSPREAD, KXMLBTOTAL, KXMLBHR, ... | `baseball_mlb` |
| `nhl` | KXNHLGAME, KXNHLSPREAD, KXNHLTOTAL, KXNHLGOAL, ... | `icehockey_nhl` |
| `nfl` | KXNFLGAME, KXNFLSPREAD, KXNFLTOTAL, ... | `americanfootball_nfl` |
| `ncaamb` | KXNCAAMBGAME, KXNCAAMBSPREAD, KXNCAAMBTOTAL | `basketball_ncaab` |
| `soccer` | KXSOCCER, KXEPL, KXUCL, ... | `soccer_epl`, `soccer_uefa_champs_league` |
| `mma` | KXUFC | `mma_mixed_martial_arts` |
| `esports` | KXCSGO, KXLOL | -- |

---

## Output

### Console Table

```
| Sport | Bet              | Type   | Pick        | When  | Mkt   | Fair  | Edge   | Conf. | Score |
|-------|------------------|--------|-------------|-------|-------|-------|--------|-------|-------|
| NBA   | Phoenix @ Hornets| Total  | Over 220.5  | Apr 2 | $0.53 | $0.66 | +13.3% | MED   |   8.3 |
| NBA   | Spurs @ Clippers | ML     | Spurs win   | Apr 2 | $0.62 | $0.74 | +12.0% | MED   |   8.3 |
| NBA   | Spurs @ Clippers | Spread | Spurs -4.5  | Apr 2 | $0.53 | $0.86 | +32.5% | LOW   |   7.2 |
```

### Saved Report

Markdown report saved to `reports/Sports/YYYY-MM-DD_{filter}_sports_scan.md` with the same table plus summary stats.
