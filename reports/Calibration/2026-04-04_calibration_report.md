# Model Calibration Report (all time)

*Generated: 2026-04-04 16:29 UTC | 88 settled trades*

## Overall

| Metric | Value |
|--------|-------|
| Win rate | 39/88 (44%) |
| ROI | +17.5% |
| Avg estimated edge | 24.0% |
| Brier score | 0.2759 (worse than 0.2500 baseline) |

## Calibration Curve

| Predicted Range | Count | Predicted | Realized | Gap |
|-----------------|-------|-----------|----------|-----|
| 0%-30% | 1 | 25% | 0% | +25% |
| 30%-40% | 7 | 36% | 29% | +8% |
| 40%-50% | 14 | 46% | 57% | -11% |
| 50%-60% | 31 | 56% | 39% | +17% |
| 60%-70% | 19 | 63% | 47% | +15% |
| 70%-80% | 9 | 74% | 44% | +30% |
| 80%-101% | 7 | 91% | 57% | +34% |

## By Category

| By Category | Trades | WR | P&L | ROI | Avg Edge | Brier |
|-------------|--------|----|----|-----|----------|-------|
| ML | 33 | 46% | $+1.90 | +12% | 15% | 0.2494 |
| Spread | 29 | 31% | $-1.54 | -8% | 33% | 0.2793 * |
| Total | 26 | 58% | $+8.81 | +53% | 25% | 0.3058 * |

## By Confidence

| By Confidence | Trades | WR | P&L | ROI | Avg Edge | Brier |
|---------------|--------|----|----|-----|----------|-------|
| high | 46 | 33% | $-3.27 | -12% | 24% | 0.2741 * |
| medium | 42 | 57% | $+12.44 | +51% | 24% | 0.2780 * |

## By Sport

| By Sport | Trades | WR | P&L | ROI | Avg Edge | Brier |
|----------|--------|----|----|-----|----------|-------|
| NCAAB | 56 | 45% | $+7.87 | +22% | 29% | 0.2882 * |
| MLB | 32 | 44% | $+1.30 | +8% | 14% | 0.2546 * |

## By Edge Bucket

| Bucket | Trades | WR | P&L | ROI | Avg Edge |
|--------|--------|----|-----|-----|----------|
| 5-10% | 27 | 48% | $+0.00 | +0% | 7% |
| 10-15% | 8 | 75% | $+4.79 | +119% | 11% |
| 15-25% | 14 | 43% | $-0.64 | -7% | 21% |
| 25%+ | 39 | 36% | $+5.02 | +21% | 39% |

## Confidence x Category

| Confidence | Category | Trades | WR | P&L | ROI |
|------------|----------|--------|----|-----|-----|
| medium | ML | 15 | 53% | $+3.48 | +48% |
| medium | Total | 26 | 58% | $+8.81 | +53% |
| high | ML | 18 | 39% | $-1.58 | -17% |
| high | Spread | 28 | 29% | $-1.69 | -9% |

## Recommendations

### 1. [HIGH] Confidence Signals

**Finding:** High confidence (33% WR, $-3.27) underperforms medium (57% WR, $+12.44). Team stats and sharp money bumps are hurting, not helping.

**Action:** Weaken or remove confidence bumps from _adjust_confidence_with_stats(). Option A: Remove team stats bump entirely (set signal to 'neutral' always). Option B: Only allow bumps DOWN (contradicts), never UP (supports). Option C: Reduce bump to half-level (medium stays medium, low->medium only if strong signal).

### 2. [HIGH] Spread Model

**Finding:** Spread claims 33% avg edge but realizes -8% ROI (31% WR over 29 trades). Model is severely overestimating edge.

**Action:** Increase SPORT_MARGIN_STDEV values by 20-30% for the spread model. This compresses probability estimates toward 50%, reducing phantom edge. Current values are in edge_detector.py.

### 3. [HIGH] Overall Calibration

**Finding:** Overall Brier score 0.2759 is worse than coin-flip baseline (0.2500). The model's probability estimates are adding noise, not signal.

**Action:** This suggests stdevs are too low (probabilities too extreme). Increase all stdev parameters by 10-20% as a starting point.

### 4. [MEDIUM] Calibration

**Finding:** Predicted 40%-50% bucket: model says 46%, realized 57% (14 trades). Model is underconfident by 11%.

**Action:** Decrease stdev parameters for markets in this probability range to pull predictions toward 50%.

### 5. [MEDIUM] Calibration

**Finding:** Predicted 50%-60% bucket: model says 56%, realized 39% (31 trades). Model is overconfident by 17%.

**Action:** Increase stdev parameters for markets in this probability range to pull predictions toward 50%.

### 6. [MEDIUM] Calibration

**Finding:** Predicted 60%-70% bucket: model says 63%, realized 47% (19 trades). Model is overconfident by 15%.

**Action:** Increase stdev parameters for markets in this probability range to pull predictions toward 50%.

### 7. [MEDIUM] Calibration

**Finding:** Predicted 70%-80% bucket: model says 74%, realized 44% (9 trades). Model is overconfident by 30%.

**Action:** Increase stdev parameters for markets in this probability range to pull predictions toward 50%.

### 8. [MEDIUM] Calibration

**Finding:** Predicted 80%-101% bucket: model says 91%, realized 57% (7 trades). Model is overconfident by 34%.

**Action:** Increase stdev parameters for markets in this probability range to pull predictions toward 50%.

### 9. [MEDIUM] Edge Estimation

**Finding:** Highest-edge bucket (15-25%, avg 21%) has worst ROI (-7%), while 10-15% (avg 11%) has best ROI (+119%). Large edges are systematically overestimated.

**Action:** Consider capping maximum trusted edge at 15-20% (soft cap via composite score penalty for extreme edges), or increase stdevs to compress edge estimates.


## Current Model Parameters

### Spread Stdev (SPORT_MARGIN_STDEV)

| Sport | Current |
|-------|---------|
| americanfootball_ncaaf | 15.0 |
| americanfootball_nfl | 13.5 |
| baseball_mlb | 3.5 |
| basketball_nba | 12.0 |
| basketball_ncaab | 11.0 |
| icehockey_nhl | 2.5 |
| mma | 5.0 |
| soccer | 1.8 |

### Total Stdev (SPORT_TOTAL_STDEV)

| Sport | Current |
|-------|---------|
| americanfootball_ncaaf | 14.0 |
| americanfootball_nfl | 13.0 |
| baseball_mlb | 3.0 |
| basketball_nba | 18.0 |
| basketball_ncaab | 16.0 |
| icehockey_nhl | 2.2 |
| soccer | 1.5 |

---
*Generated by Edge-Radar model_calibration.py*
