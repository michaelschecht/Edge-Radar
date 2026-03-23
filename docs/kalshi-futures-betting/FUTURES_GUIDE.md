# Kalshi Futures & Championship Betting Guide

Bet on season-long outcomes: championship winners, conference winners, MVP awards, and more. Futures markets stay open for weeks or months and settle when the season ends or the award is announced.

---

## Table of Contents

- [Quick Reference](#quick-reference)
- [How Futures Edge Detection Works](#how-futures-edge-detection-works)
- [NFL](#nfl)
- [NBA](#nba)
- [NHL](#nhl)
- [MLB](#mlb)
- [NCAA](#ncaa)
- [Soccer](#soccer)
- [Motorsports](#motorsports)
- [Golf](#golf)
- [Cricket](#cricket)
- [All Futures Filters](#all-futures-filters)
- [Available Markets Summary](#available-markets-summary)
- [Strategy Tips](#strategy-tips)

---

## Quick Reference

See [Scripts Reference](../SCRIPTS_REFERENCE.md) for complete CLI flags. Key command: `python scripts/kalshi/futures_edge.py scan --filter <filter>`

---

## How Futures Edge Detection Works

Futures use **N-way de-vigging** instead of the 2-way de-vig used for game outcomes:

1. **Fetch** outright odds from 5-12 US sportsbooks via The Odds API
2. **Each book** has odds for every team/player (e.g., 30 NBA teams to win the title)
3. **Implied probabilities** are calculated: `1 / decimal_odds` for each outcome
4. **De-vig** by normalizing: divide each implied probability by the sum of all implied probabilities for that book. This removes the house edge.
5. **Consensus** = median de-vigged probability across all books for each team
6. **Compare** to Kalshi's price for that team/player
7. **Edge** = consensus fair value - Kalshi ask price

**Example:** Sportsbooks consensus says Thunder have a 38.7% chance to win the NBA title. Kalshi prices "Oklahoma City to win Western Conference" at $0.49 (which implies they need to win the conference AND the finals). If our model says their conference probability is higher than $0.49, that's edge.

---

## NFL

### Super Bowl Winner

**Kalshi prefix:** `KXSB` (~32 markets)

**Edge detection:** Yes -- compares against The Odds API's `americanfootball_nfl_super_bowl_winner` outrights from DraftKings, FanDuel, BetMGM, and others.

**Example market:** "Will Washington win the 2027 Pro Football Championship?"

**Settlement:** After the Super Bowl game.

**Seasonality:** NFL Super Bowl futures are available year-round. NFL MVP markets (~45) are also available under `KXNFLMVP`.

### AFC / NFC Conference & Division Winners

**Not currently available on Kalshi.** Unlike NBA/NHL/MLB, Kalshi does not offer NFL conference champion or division winner markets. Only Super Bowl and MVP. If Kalshi adds these, they would likely use prefixes like `KXNFLAFC`, `KXNFLNFC`, or similar -- we'll map them when they appear.

### NFL MVP

**Kalshi prefix:** `KXNFLMVP` (~45 markets)

**Edge detection:** Not yet (Odds API doesn't have NFL MVP outrights). Browse and research manually.

**Example market:** "Will Patrick Mahomes win the NFL MVP?"

**Settlement:** When the NFL announces the MVP (typically in February).

---

## NBA

### NBA Finals Champion

**Kalshi prefix:** `KXNBA` (~30 markets)

**Edge detection:** Yes -- compares against NBA Championship outright odds from DraftKings, FanDuel, BetMGM, and others.

**Example market:** "Will Oklahoma City win the 2026 Pro Basketball Finals?"

**Settlement:** After the NBA Finals.

### Conference Winners

**Kalshi prefixes:** `KXNBAEAST` (15 teams), `KXNBAWEST` (15 teams)

**Edge detection:** Yes -- compares against NBA Championship outright odds. If sportsbooks give a team a high championship probability, their conference win probability should be at least that high.

**Example markets:**
- "Will Boston win the 2026 Eastern Conference Finals?"
- "Will Oklahoma City win the 2026 Western Conference Finals?"

**Settlement:** When the conference finals conclude.

**Note:** `--filter nba-futures` scans all three: Finals champion + both conferences.

### NBA Awards (Browse Only)

| Prefix | Award | Markets |
|--------|-------|---------|
| `KXNBAMVP` | Most Valuable Player | ~72 |
| `KXNBAROY` | Rookie of the Year | ~28 |
| `KXNBADPOY` | Defensive Player of the Year | ~43 |

**Edge detection:** Not yet (Odds API doesn't have NBA award outrights on the free tier). Research using media voting trends, stats leaders, and Vegas award odds from sportsbook websites.

**Settlement:** When the NBA announces each award (typically June).

---

## NHL

### Stanley Cup Champion

**Kalshi prefix:** `KXNHL` (~32 markets)

**Edge detection:** Yes -- compares against NHL Championship (Stanley Cup) outright odds from DraftKings, FanDuel, BetMGM, and others.

**Example market:** "Will Winnipeg Jets win the 2025-26 Stanley Cup Finals?"

**Settlement:** After the Stanley Cup Finals.

### Conference Winners

**Kalshi prefixes:** `KXNHLEAST` (16 teams), `KXNHLWEST` (16 teams)

**Edge detection:** Yes -- compares against NHL Championship outright odds.

**Example markets:**
- "Will the Florida Panthers win the Eastern Conference Finals?"
- "Will the Edmonton Oilers win the Western Conference Finals?"

**Settlement:** When the conference finals conclude.

**Note:** `--filter nhl-futures` scans all three: Stanley Cup champion + both conferences.

### NHL Awards (Browse Only)

| Prefix | Award | Markets |
|--------|-------|---------|
| `KXNHLHART` | Hart Memorial Trophy (MVP) | ~30 |
| `KXNHLNORRIS` | James Norris Trophy (best defenseman) | ~30 |
| `KXNHLCALDER` | Calder Memorial Trophy (best rookie) | ~30 |

**Settlement:** After the NHL Awards ceremony (typically June).

---

## MLB

### World Series Champion

**Kalshi prefix:** `KXMLB` (~30 markets)

**Edge detection:** Yes -- compares against World Series outright odds from DraftKings, FanDuel, BetMGM, and others.

**Example market:** "Will Toronto win the 2026 Pro Baseball Championship?"

**Settlement:** After the World Series.

### Playoff Qualifiers

**Kalshi prefix:** `KXMLBPLAYOFFS` (~30 markets)

**Edge detection:** Yes -- compares against World Series outright odds.

**Example market:** "Will the Yankees make the playoffs?"

**Settlement:** When the MLB playoff field is set (late September/October).

**Note:** `--filter mlb-futures` scans both: World Series champion + playoff qualifiers.

---

## NCAA

### Men's Basketball -- Most Outstanding Player

**Kalshi prefix:** `KXNCAAMBMOP` (~35 markets)

**Edge detection:** Yes -- compares against NCAAB Championship outright odds as a proxy.

**Example market:** "Who will win Men's College Basketball Most Outstanding Player?"

**Settlement:** After the NCAA tournament championship game.

### Heisman Trophy (Browse Only)

**Kalshi prefix:** `KXHEISMAN` (~21 markets)

**Edge detection:** Not yet. Research using preseason polls, Vegas Heisman odds, and player stats.

**Settlement:** When the Heisman is announced (December).

---

## Soccer

### European League Winners (Browse Only)

| Prefix | League | Markets |
|--------|--------|---------|
| `KXUCL` | UEFA Champions League | ~8 |
| `KXEPL` | English Premier League | -- |
| `KXLALIGA` | La Liga (Spain) | ~20 |
| `KXSERIEA` | Serie A (Italy) | ~20 |
| `KXBUNDESLIGA` | Bundesliga (Germany) | ~18 |
| `KXLIGUE1` | Ligue 1 (France) | ~18 |

**Edge detection:** Not yet -- The Odds API free tier doesn't include soccer league outrights. Browse and research manually using league standings and bookmaker websites.

**Settlement:** When the league season ends or the tournament concludes.

---

## Motorsports

### Formula 1

| Prefix | Market | Markets |
|--------|--------|---------|
| `KXF1` | Drivers Championship | ~22 |
| `KXF1CONSTRUCTORS` | Constructors Championship | ~11 |

**Edge detection:** Not yet for championship outrights. Browse and use current standings + points gap analysis.

### NASCAR

**Kalshi prefix:** `KXNASCARRACE` (~37 markets)

**Edge detection:** Not yet. Individual race winner markets.

---

## Golf

### PGA Tour Events

**Kalshi prefix:** `KXPGATOUR` (~160 markets per tournament)

**Edge detection:** Yes -- compares against PGA Championship outright odds when available.

**Example market:** "Will Scottie Scheffler win the Valspar Championship?"

**Settlement:** After the tournament concludes.

---

## Cricket

### IPL

**Kalshi prefix:** `KXIPL` (~10 markets)

**Edge detection:** Not yet. Browse only.

**Settlement:** After the IPL final.

---

## All Futures Filters

### With Edge Detection

| Filter | Sport | What It Scans | Odds API Source |
|--------|-------|---------------|-----------------|
| `futures` | All | All supported futures | Multiple |
| `nfl-futures` | NFL | Super Bowl champion | `americanfootball_nfl_super_bowl_winner` |
| `nba-futures` | NBA | Finals champion + East/West conference winners | `basketball_nba_championship_winner` |
| `nhl-futures` | NHL | Stanley Cup champion + East/West conference winners | `icehockey_nhl_championship_winner` |
| `mlb-futures` | MLB | World Series champion + playoff qualifiers | `baseball_mlb_world_series_winner` |
| `ncaab-futures` | NCAAB | Most Outstanding Player | `basketball_ncaab_championship_winner` |
| `golf-futures` | Golf | PGA tournament winners | `golf_pga_championship_winner` |

### Browse Only (No Automated Edge)

Use the raw ticker prefix with the edge detector or client:

| Prefix | Market | How to Browse |
|--------|--------|---------------|
| `KXNFLMVP` | NFL MVP | `--filter KXNFLMVP` |
| `KXNBAMVP` | NBA MVP | `--filter KXNBAMVP` |
| `KXNBAROY` | NBA Rookie of the Year | `--filter KXNBAROY` |
| `KXNBADPOY` | NBA DPOY | `--filter KXNBADPOY` |
| `KXNHLHART` | NHL Hart Trophy | `--filter KXNHLHART` |
| `KXNHLNORRIS` | NHL Norris Trophy | `--filter KXNHLNORRIS` |
| `KXNHLCALDER` | NHL Calder Trophy | `--filter KXNHLCALDER` |
| `KXHEISMAN` | Heisman Trophy | `--filter KXHEISMAN` |
| `KXUCL` | Champions League | `--filter KXUCL` |
| `KXLALIGA` | La Liga | `--filter KXLALIGA` |
| `KXSERIEA` | Serie A | `--filter KXSERIEA` |
| `KXBUNDESLIGA` | Bundesliga | `--filter KXBUNDESLIGA` |
| `KXLIGUE1` | Ligue 1 | `--filter KXLIGUE1` |
| `KXF1` | F1 Drivers Championship | `--filter KXF1` |
| `KXF1CONSTRUCTORS` | F1 Constructors | `--filter KXF1CONSTRUCTORS` |
| `KXNASCARRACE` | NASCAR race winners | `--filter KXNASCARRACE` |
| `KXIPL` | IPL winner | `--filter KXIPL` |

---

## Available Markets Summary

| Sport | Futures Type | Markets | Edge Detection |
|-------|-------------|---------|----------------|
| **NFL** | Super Bowl Champion (KXSB) | ~32 | Yes |
| **NFL** | MVP (KXNFLMVP) | ~45 | Browse only |
| **NBA** | Finals Champion (KXNBA) | ~30 | Yes |
| **NBA** | Conference winners (KXNBAEAST/WEST) | ~30 | Yes |
| **NBA** | MVP, ROY, DPOY | ~143 | Browse only |
| **NHL** | Stanley Cup Champion (KXNHL) | ~32 | Yes |
| **NHL** | Conference winners (KXNHLEAST/WEST) | ~32 | Yes |
| **NHL** | Hart, Norris, Calder | ~90 | Browse only |
| **MLB** | World Series Champion (KXMLB) | ~30 | Yes |
| **MLB** | Playoff qualifiers (KXMLBPLAYOFFS) | ~30 | Yes |
| **NCAAB** | Most Outstanding Player | ~35 | Yes |
| **NCAAB** | Heisman Trophy | ~21 | Browse only |
| **Soccer** | UCL, EPL, La Liga, Serie A, Bundesliga, Ligue 1 | ~84 | Browse only |
| **F1** | Drivers + Constructors | ~33 | Browse only |
| **NASCAR** | Race winners | ~37 | Browse only |
| **Golf** | PGA tournament winners | ~160 | Yes |
| **Cricket** | IPL winner | ~10 | Browse only |

**Total:** ~750+ futures markets across all sports.

---

## Strategy Tips

### When Futures Have Edge

1. **Early season** -- sportsbook lines are softest before the season starts. Kalshi prices may lag behind sharp book adjustments.
2. **After major trades/injuries** -- Kalshi reprices slowly after blockbuster trades, star injuries, or coaching changes. Sportsbooks update within hours.
3. **Playoff seeding locked** -- once matchups are known, conference winner probabilities shift. Compare Kalshi's stale prices against fresh outright odds.
4. **Contrarian value** -- futures markets often overweight recent performance (recency bias). A team on a losing streak may be underpriced relative to their season-long true talent level.

### Key Differences from Game Betting

| Aspect | Game Betting | Futures |
|--------|-------------|---------|
| **Time horizon** | Hours (one game) | Weeks to months |
| **Liquidity** | High | Lower (fewer participants) |
| **Price movement** | Fast (game lines move quickly) | Slow (season-long adjustment) |
| **Capital lock-up** | Minutes to hours | Weeks to months (money is tied up) |
| **Edge source** | De-vigged game odds | De-vigged outright odds |
| **Information edge** | Hard (markets are efficient) | Easier (slower to reprice) |

### Position Sizing for Futures

Since your capital is locked up longer with futures, consider:
- **Smaller unit sizes** than game bets (e.g., $0.50-$1.00 vs $1.00-$3.00)
- **Diversify across sports** rather than concentrating in one league
- **Track opportunity cost** -- $5 locked in a futures bet for 3 months can't be used for daily game bets
