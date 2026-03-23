# Edge Optimization Roadmap

Prioritized improvements to edge detection accuracy, ranked by expected impact on realized P&L.

**Context:** Live trading results (2026-03-22 to 2026-03-23) showed 1W-11L on NCAAB spreads with estimated 33% edge but realized -88% ROI. The edge calibration is systematically off — the model overestimates edge, particularly on spread markets. The improvements below are ordered by what will most directly fix this.

---

## Priority 1: High Impact (Fix What's Broken) -- DONE

### 1. Recalibrate the Spread Adjustment Formula -- DONE (2026-03-23)

**Problem:** The spread probability adjustment function in `edge_detector.py` used a linear model (`+3% per point`) that systematically overestimated edge on alternate spreads.

**Fix implemented:**
- Replaced linear adjustment with **normal CDF model** using `scipy.stats.norm`
- Infers expected score margin from book spread + implied probability
- Calculates `P(margin > strike)` on the bell curve instead of a flat linear slope
- Added sport-specific standard deviations: NBA (12), NCAAB (11), NFL (13.5), MLB (3.5), NHL (2.5), soccer (1.8)
- Same fix applied to total (over/under) markets with separate stdev values

### 2. Closing Line Value (CLV) Tracking -- DONE (2026-03-23)

**Problem:** Without CLV, we can't distinguish bad luck from bad edge estimation.

**Fix implemented:**
- Settler captures `last_price` from Kalshi API when settling trades
- Calculates `CLV = closing_price - entry_price` per trade (positive = got a better price than close)
- Stores `closing_price` and `clv` fields on each trade record
- Performance report includes CLV section: average CLV and beat-the-close rate

---

## Priority 2: Medium Impact (Better Data Sources) -- DONE

### 3. Sharp Book Weighting -- DONE (2026-03-23)

**Problem:** All sportsbooks were weighted equally. Sharp books (Pinnacle, Circa) have tighter lines than recreational books (DraftKings, FanDuel).

**Fix implemented:**
- Added `BOOK_WEIGHTS` map with 21 books: Pinnacle/Circa at 3x, mid-tier at 1-1.5x, DraftKings/FanDuel/BetMGM at 0.7x
- Built `weighted_median()` function for cumulative-weight percentile calculation
- Applied to all 4 consensus functions: game outcomes, spreads, totals, and futures outrights

### 4. Team Performance Stats APIs -- DONE (2026-03-23)

**Problem:** Edge detection relied entirely on sportsbook consensus with no team performance data.

**Fix implemented:**
- New `scripts/shared/team_stats.py` module covering 6 sports from free APIs (no keys):
  - ESPN API: NBA, NCAAB, NFL, NCAAF (wins, losses, win%, points for/against)
  - NHL Stats API: standings, goal differential, L10 record, streak
  - MLB Stats API: standings, run differential, winning percentage
- Unified `get_team_stats(team, sport)` lookup with fuzzy name matching
- Data cached per session to minimize API calls
- Integrated into `detect_edge_game` and `detect_edge_spread`: team win% is looked up and used as a confidence modifier
- Stats signal: "supports" (win% >= 60% for YES bets), "contradicts" (opposite), "neutral"
- Confidence bumped up when stats support, dropped when stats contradict
- Team record and signal stored in opportunity details for post-hoc analysis

### 5. Injury & Line Disagreement Signal -- DONE (2026-03-23)

**Problem:** A star player being out shifts game lines 3-7 points. Kalshi prices may lag behind injury news.

**Fix implemented:**
- ESPN injury endpoints were tested but return empty data unreliably
- Instead, implemented **book disagreement detection** as a proxy: when sportsbooks disagree significantly on spreads (range > 4 points), it signals recent news (usually injuries) that some books haven't adjusted for
- Added `book_spread_range` metric to spread consensus output
- Confidence now factors in both book count AND book agreement:
  - High: 6+ books AND spread range <= 2 points (consensus is tight)
  - Medium: 3+ books AND spread range <= 4 points
  - Low: few books or wide disagreement (something is moving)
- This naturally downgrades confidence on games with injury-driven line movement

### 6. Line Movement & Sharp Money Detection -- DONE (2026-03-23)

**Problem:** Public betting percentages require paid APIs ($30/mo). But line movement is a free proxy — when the line moves opposite to where public money would push it, sharp bettors are on the other side.

**Fix implemented:**
- New `scripts/shared/line_movement.py` module
- ESPN scoreboard API provides opening and closing odds (DraftKings) for every game — free, no key
- Calculates spread movement (open vs close) and total movement per game
- Detects **reverse line movement**: spread moves away from the favorite = sharp on underdog
- Detects **sharp total movement**: total drops >2 pts = sharp under, rises >2 pts = sharp over
- Pre-fetched once per scan in `scan_all_markets()`, indexed by team abbreviation
- Integrated into all three edge detectors (game, spread, total) as a confidence signal
- Sharp signal that agrees with our bet → confidence bumped up; contradicts → dropped down
- Signal data stored in `details["sharp_money"]` for transparency
- Tested: 7 sharp signals detected from 10 NBA games on 2026-03-23

---

## Priority 3: Lower Impact (Nice to Have)

### 7. Weather for Outdoor Sports -- DONE (2026-03-23)

**Problem:** Wind, rain, and extreme temperatures affect scoring in outdoor sports.

**Fix implemented:**
- New `scripts/shared/sports_weather.py` module
- NWS hourly forecast API (free, no key): fetches temperature, wind speed, precipitation probability
- 31 NFL venues and 30 MLB venues mapped with NWS grid points and dome/outdoor classification
- Dome stadiums automatically return zero adjustment
- Scoring adjustment model for NFL/MLB based on wind (>15mph), rain (>40%), cold (<32F NFL, <45F MLB)
- Integrated into `detect_edge_total()`: weather adjusts fair value for over/under markets
  - Bad weather → reduces over probability, increases under probability
  - Adjustment capped at -15% (severe: high wind + rain + cold combined)
- Weather data stored in opportunity details for transparency

### 8. Historical Kalshi Pricing Analysis

**Problem:** Kalshi may systematically misprice certain market types (e.g., wide spreads, high totals). Without historical analysis, we don't know where the persistent inefficiencies are.

**Action:**
- Build a backtest dataset: for each settled market, record Kalshi price at various times before settlement and the final result
- Analyze: do Kalshi spread markets at specific distances (+1.5, +3.5, +7.5, etc.) have predictable biases?
- If yes, incorporate the bias correction into the spread model

**Cost:** Requires accumulating data over time. Can start logging now and analyze after 500+ settled markets.

**Expected impact:** Could reveal systematic inefficiencies unique to Kalshi's market microstructure. Long-term value.

### 9. Line Movement Tracking (Odds API Paid Tier)

**Problem:** Tracking *where* lines move and *when* they move signals sharp action. A line moving 2 points toward the underdog in the last hour before game time usually means sharp bettors are hammering that side.

**Action:**
- Upgrade to Odds API paid tier (historical odds snapshots)
- Track opening line vs. current line for each game
- Flag "reverse line movement" — line moves opposite to public betting side

**Cost:** Odds API paid tier ($20-80/month depending on plan). More API calls.

**Expected impact:** Moderate. Useful signal but redundant with sharp book weighting (#3) if Pinnacle data is available.

---

## Implementation Order

| Phase | Items | Status | Dependencies |
|-------|-------|--------|--------------|
| **Phase 1** | #1 Spread recalibration, #2 CLV tracking | DONE (2026-03-23) | None |
| **Phase 2** | #3 Sharp book weighting, #4 Team stats APIs | DONE (2026-03-23) | Phase 1 validates the approach |
| **Phase 3** | #5 Injury/line disagreement signal | DONE (2026-03-23) | None |
| | #6 Line movement / sharp money detection | DONE (2026-03-23) | ESPN free API |
| **Phase 4** | #7 Weather for outdoor sports | DONE (2026-03-23) | None |
| | #8 Historical analysis, #9 Line movement | Ongoing | Data accumulation over time |

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Win rate (spreads) | 8% (1/12) | 52%+ |
| Edge realization | -263% | 50%+ (realized edge / estimated edge) |
| CLV | Not tracked | Positive average |
| Profit factor | 0.14 | 1.2+ |
| ROI | -88% | Break-even to positive |

**Note:** A 52% win rate on -110 lines is profitable. The current model doesn't need to be brilliant — it needs to stop being systematically wrong on spreads.
