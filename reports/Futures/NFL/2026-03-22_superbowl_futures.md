# NFL Super Bowl Futures Analysis
**Date:** 2026-03-22
**Market:** KXSB (2027 Pro Football Championship)
**Source:** The Odds API outrights (3 books: DraftKings, FanDuel, BetMGM)

---

## Top 5 Edge Opportunities

| Rank | Team | Side | Kalshi Price | Fair Value | Edge | Confidence |
|------|------|------|-------------|-----------|------|------------|
| 1 | Kansas City Chiefs | NO | $0.93 | 94.6% | **+1.6%** | Medium (3 books) |
| 2 | Seattle Seahawks | NO | $0.91 | 91.9% | **+0.9%** | Medium (3 books) |
| 3 | Philadelphia Eagles | NO | $0.95 | 95.6% | **+0.6%** | Medium (3 books) |
| 4 | Detroit Lions | NO | $0.95 | 95.6% | **+0.6%** | Medium (3 books) |
| 5 | Green Bay Packers | NO | $0.95 | 95.5% | **+0.5%** | Medium (3 books) |

---

## Analysis

All opportunities are **NO bets** (betting the team will NOT win the Super Bowl). This means Kalshi is slightly overpricing these teams' championship odds relative to sportsbook consensus.

### #1 Kansas City Chiefs -- NO at $0.93 (+1.6% edge)

- **Kalshi implies:** 7% chance to win (YES at $0.08, after spread)
- **Sportsbook consensus:** ~5.4% chance
- **Thesis:** KC is a popular public bet that inflates their Kalshi price above true value. Three sportsbooks agree they're closer to a 5-6% probability.
- **Risk:** If KC makes a deep playoff run, this NO position loses. $0.93 cost means max loss is $0.07/contract.

### #2 Seattle Seahawks -- NO at $0.91 (+0.9% edge)

- **Kalshi implies:** 9% chance (YES at $0.10, after spread)
- **Sportsbook consensus:** ~8.1% chance
- **Thesis:** Slight overpricing on Kalshi. Seattle is competitive but books price them a tick lower.
- **Risk:** Thinner edge, less conviction.

### #3 Philadelphia Eagles -- NO at $0.95 (+0.6% edge)

- **Kalshi implies:** 5% chance
- **Sportsbook consensus:** ~4.4% chance
- **Thesis:** Marginal mispricing. Philly was a recent Super Bowl contender, public still pricing in past performance.

### #4 Detroit Lions -- NO at $0.95 (+0.6% edge)

- **Kalshi implies:** 5% chance
- **Sportsbook consensus:** ~4.4% chance
- **Thesis:** Similar to Philly -- recent playoff success inflating public perception.

### #5 Green Bay Packers -- NO at $0.95 (+0.5% edge)

- **Kalshi implies:** 5% chance
- **Sportsbook consensus:** ~4.5% chance
- **Thesis:** Smallest edge. Only worth considering as part of a diversified futures portfolio.

---

## Full Super Bowl Market Landscape

| Team | Kalshi YES | Kalshi NO | Fair Value | Edge (NO) | Volume |
|------|-----------|----------|-----------|----------|--------|
| Seattle | $0.10 | $0.91 | 8.1% | +0.9% | 986,498 |
| Los Angeles Rams | $0.10 | $0.91 | -- | -- | 1,022,669 |
| Kansas City | $0.08 | $0.93 | 5.4% | +1.6% | 1,257,138 |
| Buffalo | $0.08 | $0.93 | -- | -- | 768,388 |
| San Francisco | $0.07 | $0.95 | 4.8% | +0.2% | 824,352 |
| Baltimore | $0.07 | $0.94 | -- | -- | 704,442 |
| Philadelphia | $0.06 | $0.95 | 4.4% | +0.6% | 171,516 |
| Los Angeles Chargers | $0.06 | $0.95 | -- | -- | 239,151 |
| Green Bay | $0.06 | $0.95 | 4.5% | +0.5% | 183,506 |
| Detroit | $0.06 | $0.95 | 4.4% | +0.6% | 98,873 |
| New England | $0.05 | $0.96 | -- | -- | 340,299 |
| Denver | $0.05 | $0.96 | -- | -- | 1,044,489 |
| Chicago | $0.05 | $0.96 | 3.5% | +0.5% | 1,005,444 |
| Jacksonville | $0.04 | $0.97 | -- | -- | 136,128 |
| Houston | $0.04 | $0.97 | -- | -- | 186,556 |
| Dallas | $0.04 | $0.97 | -- | -- | 1,040,525 |
| Cincinnati | $0.04 | $0.97 | 2.6% | +0.4% | 746,750 |
| Tampa Bay | $0.03 | $0.98 | 1.8% | +0.2% | 903,370 |

*"--" = no match found in Odds API data (name mismatch or not listed)*

---

## Methodology

1. Fetched outright Super Bowl winner odds from 3 US sportsbooks via The Odds API
2. Calculated implied probability for each team per book: `1 / decimal_odds`
3. De-vigged by normalizing: `fair_prob = implied / sum(all_implied)` per book
4. Took median across books for consensus fair value
5. Compared consensus to Kalshi YES/NO ask prices
6. Edge = consensus fair value - Kalshi price (for the chosen side)

---

## Caveats

- **Only 3 books** had NFL Super Bowl outrights available. More books = higher confidence.
- **All edges are under 2%** -- this is expected for heavily traded championship markets.
- **NO bets on futures** tie up capital at high cost ($0.91-$0.95) for a small potential profit ($0.05-$0.09).
- **Capital efficiency:** $0.93 locked up to profit $0.07 on KC NO = 7.5% ROI if correct, but that capital is locked until the Super Bowl.
- **Better entry points** may appear after the NFL draft, free agency moves, or early-season results when lines are softer.

---

## Recommendation

**Hold for now.** The edges are real but thin. Consider:
- Waiting for NFL draft (late April) when Kalshi reprices slowly
- Monitoring for injuries/trades that create larger mispricings
- Re-running this scan weekly during the offseason to track edge movement

**If betting:** KC NO at +1.6% is the strongest signal. A $1 unit bet costs $0.93 and profits $0.07 if KC doesn't win the Super Bowl (~94.6% likely per sportsbooks).

---

*Generated by KALSHI_BETTOR agent | Finance Agent Pro*
*Scan command: `python scripts/kalshi/futures_edge.py scan --filter nfl-futures`*
