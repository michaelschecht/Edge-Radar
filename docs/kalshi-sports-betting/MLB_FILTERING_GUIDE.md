# MLB Filtering & Pick Selection Guide

Comprehensive reference for filtering MLB bets on Kalshi using Edge-Radar's data pipeline.

---

## Quick Reference — CLI Filters

```bash
# Game markets (moneyline)
python scripts/kalshi/edge_detector.py scan --filter mlb

# Futures (World Series + Playoff Qualifier)
python scripts/kalshi/edge_detector.py scan --filter mlb-futures

# Top 10 MLB picks with 5% minimum edge
python scripts/kalshi/edge_detector.py scan --filter mlb --min-edge 0.05 --top 10

# Save results to watchlist
python scripts/kalshi/edge_detector.py scan --filter mlb --save
```

**Kalshi Tickers:**
| Ticker | Market Type |
|---|---|
| `KXMLBGAME` | Game outcomes (moneyline) |
| `KXMLBPLAYOFFS` | Playoff qualifier futures |
| `KXMLB` | World Series champion futures |

---

## 1. Edge-Based Filters (Core Pipeline)

These use the existing edge detection engine (`edge_detector.py`).

### Minimum Edge Threshold
Only surface picks where the Kalshi-implied probability diverges from the consensus line by a meaningful margin.

- **Default:** 3% (`MIN_EDGE_THRESHOLD=0.03`). MLB uses the global floor. Per-sport overrides exist via `MIN_EDGE_THRESHOLD_<SPORT>` — NCAAB set to 10% after 2026-04-18 calibration; NBA bumped to 12% in R14 on 2026-04-24 (NBA Brier 0.3306 was the worst-calibrated sport in the 30-day review). MLB's floor remains 3%.
- **Conservative MLB play:** 5%+ edge — baseball variance is lower than basketball/football, so smaller edges are more meaningful but also noisier
- **Aggressive:** 3–5% edge with supporting filters below

### Sharp Book Weighting
The pipeline already weights sharp books higher when calculating consensus probability:

| Bookmaker | Weight | Why |
|---|---|---|
| Pinnacle | 3.0x | Sharpest MLB lines, lowest vig |
| Bookmaker.eu | 3.0x | Sharp market |
| BetOnline | 2.0x | Accepts sharp action |
| LowVig | 1.5x | Low-margin book |
| DraftKings / FanDuel | 0.7x | Recreational-skewed lines |

**Filter idea:** Only take picks where Pinnacle and at least 2 other sharp books agree on direction.

### Consensus Book Count
More bookmakers pricing a line = more reliable consensus. Filter by minimum number of books offering the market.

- **Strong signal:** 6+ books with odds available
- **Weak signal:** <4 books (thin market, less reliable edge)

---

## 2. Team Performance Filters

Available via `team_stats.py` → MLB Stats API (`statsapi.mlb.com`).

### Win Percentage
- **Hot team:** Win% > .580 (playoff pace)
- **Cold team:** Win% < .420
- **Fade strat:** Bet against teams with win% < .400 when facing teams > .550

### Run Differential
The single best predictor of future MLB team performance.

- **Elite:** +100 or better run differential
- **Pretender:** Positive win% but negative run diff (regression candidate — fade)
- **Undervalued:** Negative win% but positive run diff (buy low)

### Last 10 Games Record
Captures recent form and momentum.

- **Hot streak:** 7-3 or better in L10
- **Cold streak:** 3-7 or worse in L10
- **Combine with:** run diff to separate real momentum from lucky streaks

### Streak
Current consecutive win/loss streak.

- **Long win streak (6+):** Market overvalues — look for fade opportunities
- **Long loss streak (6+):** Market undervalues — look for bounce-back spots

### Runs Scored vs. Runs Allowed
- **Offense-first team** (high RS, high RA): Overs, high-variance outcomes
- **Pitching-first team** (low RS, low RA): Unders, grind-it-out favorites
- **Imbalanced** (low RS, high RA): Strong fade candidates

---

## 3. Weather Filters

Available via `sports_weather.py` → NWS forecast API. All 30 MLB stadiums mapped with grid points.

### Wind Impact
| Condition | Adjustment | Play |
|---|---|---|
| Wind > 20 mph | -0.06 | Unders, pitching-dominant sides |
| Wind 12–20 mph | -0.03 | Mild under lean |
| Wind blowing out to CF/RF | (not yet tracked) | Overs — fly balls carry |
| Wind blowing in from OF | (not yet tracked) | Unders — suppresses HR |

### Precipitation
| Condition | Adjustment | Play |
|---|---|---|
| Precip > 50% | -0.05 | Unders, avoid game bets (delay risk) |
| Precip 30–50% | -0.02 | Mild under lean |

### Temperature
| Condition | Adjustment | Play |
|---|---|---|
| Temp < 45°F | -0.03 | Unders — cold affects ball flight and grip |
| Temp > 85°F | Neutral | Slight fatigue factor, minimal edge |

### Dome Filter
- **Skip weather for domed/retractable stadiums:** ARI, HOU, MIA, MIL, SEA, TEX, TOR, TB
- **Focus weather analysis on:** Wrigley (CHC), Fenway (BOS), Coors (COL), Kauffman (KC)

### Coors Field Special Case
Coors Field (COL) inflates scoring by 20–30%. When the Rockies play at home:
- Totals are already adjusted by books but still present edge on player props
- Road Rockies are historically undervalued (hitters adjust poorly leaving altitude)

---

## 4. Line Movement & Sharp Money Filters

Available via `line_movement.py` → ESPN scoreboard API.

### Reverse Line Movement (RLM)
The line moves **opposite** to where public money flows. This signals sharp/syndicate action.

- **Spread RLM:** Line moves ≥1.5 points against public side
- **Example:** Public on Yankees -1.5, line moves to Yankees -1.0 → sharp money on the opponent
- **Filter:** Only take RLM signals where the move is ≥1.5 points

### Total Movement
- **Sharp under signal:** Total drops ≥2.0 runs from open
- **Sharp over signal:** Total rises ≥2.0 runs from open
- **Best combined with:** Weather data and pitching matchup

### Moneyline Movement
- **Significant shift:** ≥5% implied probability move from open to current
- **Example:** Team opens -130 (56.5%), moves to -155 (60.8%) → 4.3% probability shift toward that side

---

## 5. Pitching Matchup Filters (Enhancement — Not Yet Implemented)

These are the highest-value MLB-specific filters to add. MLB is the most pitcher-dependent major sport.

### Starting Pitcher ERA/FIP
- **Ace vs. Ace (both ERA < 3.00):** Lean unders, tighter games
- **Ace vs. Journeyman (ERA gap > 2.00):** Back the ace side if market underprices
- **Bullpen day / Opener:** High variance — avoid or lean overs

### Pitcher Handedness vs. Lineup
- **LHP vs. LH-heavy lineup:** Pitcher advantage, lean unders
- **RHP vs. RH-heavy lineup:** Pitcher advantage
- Platoon splits are one of baseball's most exploitable edges

### Pitcher Home/Away Splits
- Some pitchers have massive home/away performance gaps
- **Coors adjustment:** Any pitcher at Coors gets a significant ERA bump

### Recent Pitcher Workload
- **Short rest (< 4 days):** Performance decline, lean overs
- **Long rest (6+ days):** Rust factor, first-inning vulnerability

### Bullpen Availability
- **Depleted bullpen (3+ innings previous 2 days):** Lean overs in close games
- **Fresh bullpen + strong closer:** Lean unders / favorites

---

## 6. Situational / Spot Filters

### Travel & Schedule
- **Cross-country travel (West → East, day game after night):** Fade the traveling team
- **4+ game series finale:** Fatigue for bullpens, lean overs
- **Getaway day (afternoon game before travel):** Teams rest starters, bullpen games

### Divisional vs. Interleague
- **Divisional rivalry games:** Tighter, more unpredictable — reduce position sizes
- **Interleague (AL vs. NL):** DH rule equalized now, but NL teams visiting AL parks historically have less bench depth

### Day vs. Night
- **Day games after night games:** Offensive production drops ~5%
- **West Coast teams playing early East Coast starts:** Circadian disadvantage

### Monthly Splits
- **April:** High variance, small samples, cold weather — reduce bet sizes
- **May–June:** Sample starts to stabilize, best time for stat-based models
- **July (pre-deadline):** Sellers mail it in — fade sub-.500 teams harder
- **Aug–Sept:** Roster expansion, bullpen depth matters more, playoff-contending teams press

---

## 7. Market-Specific Filters (Kalshi)

### Liquidity Check
- **Spread > 5%:** Skip — illiquid market, bad fills
- **Spread 3–5%:** Proceed with caution, reduce size
- **Spread < 3%:** Liquid, full position sizing

### Market Timing
- **Lines sharpen 2–4 hours before first pitch** — best edge is found early in the day
- **Avoid last-minute bets** unless a material lineup change (injury, scratch) creates a new edge

### Kalshi-Specific Pricing Quirks
- Kalshi moneylines can lag sportsbook moves by 15–60 minutes
- **Stale line detection:** If Kalshi odds diverge >5% from current consensus and the line recently moved at sportsbooks, the Kalshi price is stale — this is a high-confidence edge

---

## 8. Composite Filter Strategies

### The "Strong MLB Play" Stack
Require ALL of the following:
1. Edge ≥ 5% vs. sharp-weighted consensus
2. Run differential supports the pick direction
3. No adverse weather (severity = "none" or "mild")
4. No reverse line movement against the pick
5. ≥6 bookmakers pricing the market

### The "Weather Fade"
1. Outdoor stadium with wind > 15 mph or precip > 40%
2. Market total has NOT already moved down significantly
3. Take the under or the pitching-dominant side

### The "Sharp Follow"
1. Reverse line movement detected (≥1.5 point spread move or ≥2.0 total move)
2. Sharp signal direction aligns with team stats (run diff, L10)
3. Edge ≥ 3% on Kalshi vs. current sportsbook consensus

### The "Regression Fade"
1. Team with positive win% but **negative** run differential (lucky, due to regress)
2. Facing a team with positive run differential
3. Market prices the overperforming team as a moderate favorite
4. Bet the underdog

### The "Early Season Value"
*(April–May specific)*
1. Team with strong prior-year peripherals (run diff, pitching staff ERA)
2. Currently underperforming (cold streak, bad luck)
3. Market has overcorrected based on small 2026 sample
4. Buy low before market adjusts

---

## 9. Data Sources Summary

| Data | Source | Script |
|---|---|---|
| Game odds (ML, spread, total) | The Odds API | `fetch_odds.py` |
| Kalshi market prices | Kalshi API | `edge_detector.py` |
| Team standings & stats | MLB Stats API | `team_stats.py` |
| Weather forecasts | NWS API | `sports_weather.py` |
| Line movement & sharp signals | ESPN API | `line_movement.py` |
| Futures (WS, playoffs) | Kalshi + Odds API | `futures_edge.py` |

---

## 10. Recommended Enhancements (Not Yet Built)

Priority order for maximum MLB edge improvement:

1. **Starting pitcher data** — ERA, FIP, WHIP, K/9 from MLB Stats API (free). This is the single biggest edge unlock for MLB.
2. **Bullpen availability tracker** — Innings pitched over last 2–3 days per reliever
3. **Wind direction** — NWS provides wind bearing; classify as "blowing out" vs "blowing in" relative to stadium orientation
4. **Umpire tendencies** — Strike zone size affects totals (data available from Baseball Savant)
5. **Platoon splits** — Batter vs. LHP/RHP performance from MLB Stats API
6. **Pace/tempo stats** — Time per pitch, pace of play affects total duration and late-inning scoring
