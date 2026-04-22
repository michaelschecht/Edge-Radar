# Edge-Radar Enhancement Roadmap

*Last updated: 2026-04-21 (R1 + R2 + R3 + R4 shipped)*

All pending improvements for Edge-Radar in a single prioritized action list, plus findings/context behind them and an index of completed work.

Priority framing (from 2026-04-02 assessment):

> Edge-Radar does not primarily need more features right now. It needs tighter execution truth, stronger measurement, and a simpler operating surface.

Priority order: **execution correctness → calibration → risk controls → data quality → UX → features.**

Source context: 3rd-party assessments (`edge_radar_assessment_2026-04-02.md`, `edge_radar_assessment_2026-04-04.md`, `edge-radar-web-app-recommendations_2026-04-04.md`), 2026-04-18 calibration report, 2026-04-21 14-day review.

---

## Current Performance

| Metric | At Launch (03-22) | Interim (04-02) | Post-Baseline (04-18) | 14-Day (04-21) |
|--------|-------------------|-----------------|------------------------|-----------------|
| Sample | 12 bets | 54 bets | 70 bets (since 04-03 baseline) | 76 settled (last 14d) |
| Win rate | 8% (1/12) | 46% (25-29) | 51% (36-34) | **48.7% (37-39)** |
| ROI | -88% | +29.3% | +20.3% | **+31.2% ($19.55 P&L)** |
| Brier score | n/a | n/a | 0.2561 | **0.2646** (still > 0.2500) |
| CLV | not tracked | tracking | tracking | tracking |

Aggregate ROI looks healthy but is driven heavily by NHL (+87%) and a single 7¢ MLS fill (+$14.80). Predictive accuracy (Brier) has not improved — the 2026-04-18 C1 fix dampens sizing, not probability estimates. See Findings for detail.

---

## Action Items (Consolidated)

One unified list. Items from retired sections (C1a, R-series, S/H/M/U/D/A/T tiers) have been merged, deduplicated against each other, and re-sorted by priority. Old IDs preserved so existing commits / comments still resolve.

### Priority 1 — Ship Now (P&L or Correctness)

*Empty — R1, R2, R3, R4 all shipped 2026-04-21. Next measurement gate is R12 (re-run `model_calibration.py` at 100 post-baseline trades, currently at 66).*

### Priority 2 — Near Term (Weeks)

Items that improve measurement, close known gaps, or remove operator friction.

| ID | Item | Impact | Effort | Notes |
|----|------|--------|--------|-------|
| R5 | **Reconcile settlements ↔ trade log** | Medium | Medium | Only 10/76 14-day settlements match a trade log entry. Document why 158 historical settlements have no trade record; decide whether to backfill a minimal stub. Should land before A3 (DB migration) so we don't compound data debt. |
| R7 | **Minimum market-price floor** | Medium | Small | Suppress lottery-ticket longshots. Env var `MIN_MARKET_PRICE=0.15` (configurable). Addresses F10. |
| R8 | **Cross-category same-event dedup** | Medium | Small | Extend `dedup_correlated_brackets()` to optionally collapse ML + Total + Spread on the same game to one bet, configurable per sport. Addresses F11. |
| R9 | **Sport-specific `SERIES_DEDUP_HOURS`** | Medium | Small | MLB 72h, NHL 72h, NBA 48h. Today's single 48h bound lets adjacent-day MLB repeats slip (Apr 14 + Apr 16 = 49h). Addresses F12. |
| R10 | **Category-weighted composite score** | Medium | Medium | Pull back on ML and Spread (ML: 23% claimed edge → -8% realized; Spread sample is a one-fill mirage). Favor Total (+23% ROI across both windows). |
| R11 | **Explicit direction fields in settlement schema** | Low | Small | Add `fair_value_yes` and `fair_value_side` so NO-side post-hoc analysis is unambiguous (current `fair_value` field flipped meaning between bets during review). |
| R12 | **Re-run `model_calibration.py` at 100 post-baseline trades** (supersedes C7) | Low | Trivial | Currently at 66. Run once at 100; cron monthly after R2 lands so we can attribute impact. |
| C6 | **Totals bias audit** | Medium | Small | 2026-04-18 report showed Totals -14% ROI on largest volume; 14-day shows +33%. Investigate stability before any sport-level adjustment. |
| U1 | **Automated settlement cron** | Medium | Small | Run `kalshi_settler.py` hourly on market-close times. Standalone; also a building block for A6. |
| U2 | **Daily P&L email / Slack** | Medium | Small | Morning report: prior day P&L, current exposure, upcoming positions. AgentMail integration already exists for scan reports. |

### Priority 3 — Background (Data Quality, UX, Hygiene)

Items that compound over months but don't block anything today.

**Sports data (Tier 2 origin)**

| ID | Item | Impact | Effort | Notes |
|----|------|--------|--------|-------|
| S3 | Bullpen availability tracker | Medium | Medium | IPs over last 2-3 days per reliever; tired bullpen → overs in late innings. Depends on S1 (done). |
| S4 | Injury impact scoring | Medium | Medium | Star-player status from ESPN injury report; adjust fair-value confidence -10-20% when key player questionable. |
| S6 | Wind direction classification | Low | Small | NWS wind bearing vs stadium orientation — blowing out (overs) vs blowing in (unders). |
| S7 | Umpire tendencies | Low | Medium | Strike-zone size by umpire, small edge on MLB totals. |
| S8 | Platoon splits | Low | Medium | Batter vs LHP/RHP via MLB Stats API. |

**Prediction market models (Tier 4 origin)**

| ID | Item | Impact | Effort | Notes |
|----|------|--------|--------|-------|
| M1 | Ensemble crypto fair value | Medium | Large | Current is CoinGecko price + trend only. Add implied vol, funding rates, on-chain, momentum. |
| M2 | SPX volatility model | Medium | Small | Use VIX to build a price-target distribution; current model uses moving average. |
| M3 | Weather-model calibration | Low | Medium | Calibrate hand-coded impact % against historical NWS forecast vs actual. |
| M4 | Mentions seasonality | Low | Small | Election / event seasonality in TV-mention predictions. |

**UX & automation (Tier 5 origin)**

| ID | Item | Impact | Effort | Notes |
|----|------|--------|--------|-------|
| U3 | Interactive pick mode | Low | Medium | Pick rows directly from preview instead of rerunning with `--pick`. |
| U4 | Single-command session | Low | Medium | `scan.py session` = status + settle + scan + preview. |
| U5 | Persistent odds cache | Low | Small | TTL 5-10 min across runs. |

**Dashboard (Tier 5a origin — completed items in Completed index)**

| ID | Item | Impact | Effort | Notes |
|----|------|--------|--------|-------|
| D3 | Site icon / favicon | Low | Small | |
| D6 | Scan-result caching | Low | Small | TTL cache to avoid refetch on re-render. |
| D10 | Mobile-responsive tweaks | Low | Medium | Fewer columns on small screens. |
| D12 | Scan-comparison view | Low | Medium | Side-by-side results from different times/filters. |
| D13 | Risk dashboard page | Medium | Medium | Concentration heatmap, daily-loss trend, per-sport exposure. |
| D15 | Watchlist page | Low | Medium | View and manage saved watchlist opportunities. |
| D18 | Tailscale / Cloudflare setup guide | Low | Small | Remote-access guide in `docs/web-app/`. |
| D19 | `/healthz` endpoint | Low | Small | For monitoring. |

**Simplification & hygiene (Tier 3 origin)**

| ID | Item | Impact | Effort | Notes |
|----|------|--------|--------|-------|
| H2 | Split `requirements.txt` into core / dev / research | Low | Small | Alpaca, Playwright, SQLAlchemy etc. aren't in the live path. |
| H3 | Separate runtime state from source tree | Low | Small | Consistent gitignore for `data/`, `logs/`, `reports/`, `__pycache__`; consider dedicated `runtime/`. |

**Testing (Tier 7 origin)**

| ID | Item | Impact | Effort | Notes |
|----|------|--------|--------|-------|
| T1 | Integration tests (mocked workflows) | Medium | Medium | scan→risk→preview, scan→save→execute, settle→report→CLV, API-failure paths. |
| T2 | API mocking | Medium | Small | Deterministic Kalshi / Odds API / ESPN fixtures. Prereq for T1. |
| T3 | CI/CD pipeline | Low | Small | GitHub Actions: tests on PR, lint, detect-secrets. |

### Priority 4 — Web App Evolution (Tier 6 origin)

Multi-quarter track. Build order: A2 → A3 → A4+A5 → A6+A7+A8 → A9. Assumes R5 completes first so DB migration doesn't inherit the trade-log/settlement gap.

| ID | Item | Impact | Effort | Notes |
|----|------|--------|--------|-------|
| A2 | Extract service layer | Critical | Large | Isolate edge calc, risk sizing/gating, fill accounting, Kalshi client from CLI concerns. New `app/services/`. |
| A3 | Replace JSON state with database | High | Medium | Postgres (prod) / SQLite (dev). Tables: `scan_runs`, `opportunities`, `risk_decisions`, `orders`, `fills`, `positions`, `settlements`, `bankroll_snapshots`, `audit_events`. **Supersedes T4.** |
| A4 | FastAPI backend | High | Large | REST layer: `POST /api/scans`, `GET /api/opportunities`, `POST /api/opportunities/{id}/execute`, `GET /api/positions`, `GET /api/settlements`, `GET /api/portfolio/summary`, etc. |
| A5 | Idempotent execution | High | Small | Client-generated idempotency key + server-side pre-submission record + market/order locks. |
| A6 | Background job runner | Medium | Medium | Scheduled scans, order-status refresh, fill sync, settlement ingestion, daily rollups. APScheduler (MVP) → Celery/Redis if needed. U1 is a smaller standalone version of this. |
| A7 | Concurrency controls | Medium | Medium | Locks around scan-triggered execution, order submission, position refresh. |
| A8 | Web secrets handling | Medium | Small | Encrypted secret storage; no raw key-path assumptions in request handlers. |
| A9 | React / Next.js dashboard | High | Large | Overview, Scan Runner, Opportunity Review, Trade Ticket, Orders & Fills, Positions, Settlements & Performance, Settings. Depends on A4. |

### Deferred / Blocked / Superseded

| ID | Item | Reason |
|----|------|--------|
| R6 | Audit Gate 2 batch-counter | **Dropped 2026-04-21.** Original evidence ("16 open vs MAX_OPEN_POSITIONS=10") read the code default, not the live `.env` (which is 50). At 16/50 there is no over-limit bleed. The latent batch-counter question is real but low-value without an actual exposure issue — revisit only if a future run shows approvals compounding past the cap. |
| C4 | Review "high confidence" bump | Deferred. High-confidence bucket is flat (+$13.50 / 21 trades). Revisit at 50+ high-confidence trades. |
| C2 | Bump per-sport stdev 10-20% | **Merged into R2** (more specific sport-by-sport prescription). |
| C7 | Re-run calibration monthly | **Merged into R12** (same action, concrete trigger at 100 trades). |
| D17 | Fix sidebar toggle | Blocked — Material icon font renders broken in dark theme. |
| T4 | SQLite trade DB | **Superseded by A3.** |
| H1 | Centralize config into typed settings | **Resolved by H5** (2026-04-06). |

---

## Findings & Context

### 2026-04-21 — 14-day post-C1/C3/C5 review

Sample: 76 settled trades (2026-04-07 → 2026-04-21). 37W-39L (48.7%), +31% ROI ($19.55 P&L), Brier 0.2646. Aggregate looks good but is carried by NHL and one outlier.

| ID | Finding | Evidence | → Action |
|----|---------|----------|----------|
| F1 | NO-side systematically loses on high edge | YES +93% ROI (n=48). NO -20% ROI (n=28). NO at ≥20% edge: 31% WR, -33% ROI (n=16). **All 13 high-edge losers are NO-side.** | R1 |
| F2 | Brier 0.2646 — probability estimates still adding noise | C1 dampens sizing on fake-high edges but doesn't touch the probabilities. | R2 |
| F3 | Edge-bucket inversion intact post-C1 | 5-10%: +140% · 10-15%: +111% · 15-20%: +1% · 20-25%: +3% · **25%+: -24%** (n=11). | R2, R10 |
| F4 | Overconfident in favorite band | 50-60%: +14% gap · 60-70%: +18% gap (n=40, largest bucket) · 70-80%: +14% gap. | R2 |
| F5 | NBA -26% / MLB -10% persist | C3 floor applied to new bets only; history keeps settling. | R2 |
| F6 | "Low" confidence 0W-3L, -105% ROI | Consistent across 2026-04-18 and 2026-04-21 windows. | R3 |
| F7 | 16% of recent orders orphaned resting | 4/25 resting 25-66h, 1 partial (2/5). No follow-up. | R4 |
| F8 | Trade log ↔ settlement disconnect | Only 10/76 14-day settlements match a trade log entry; 158 historical settlements unmatched. | R5, R11 |
| F10 | Extreme-price bets (<10¢) are lottery tickets | 4 bets: 1W-3L. One win masks systemic pattern of model claiming "+50% edge" on 8-10¢ longshots. | R7 |
| F11 | Within-day same-matchup dedup gap | 12 matchups bet ≥2× in 14d; several same-day on different categories. | R8 |
| F12 | 48h series-dedup window too tight | MLB_NYMLAD bet Apr 14 + Apr 16 (~49h), both landed, both lost. | R9 |
| F13 | Spread +200% ROI is an outlier | n=7 driven by one 7¢ MLS fill. Remove it: -$1.71 over 6 bets. Don't re-weight on this window. | — (watch) |

**Watch list (do not act on yet):**
- MLS +169% ROI (n=6) — single-fill artifact.
- NHL +87% ROI (n=40) — consistent; **do not stdev-bump NHL**.

### 2026-04-18 — First post-baseline calibration (66 trades since 04-03 baseline)

Full report: `reports/Calibration/2026-04-18_calibration_report.md`.

- **Brier 0.2561** — worse than coin-flip. Probability estimates add noise.
- **Calibration curve:** 60-70% predicted → 50% realized (n=34, +15% gap); 70-80% → 58% (n=12, +14% gap). Favorites band systematically overstated.
- **Edge bucket inverted:** 10-15% edges → +127% ROI; ≥25% → -35% ROI (n=10).
- **Confidence:** High n=21 (-$0.81, avg claimed edge 22.4%), Low n=3 (0W, -$4.91), Medium n=46 (+$18.39, avg claimed edge 14.3%). Medium is carrying the model.
- **Category:** Totals +33%, ML -8%, Spread -25% ROI.
- **Sport (edge-metadata only):** NHL +100% (n=35), NBA -15%, MLB -20%, MLS -54%.
- **Series-correlation leak** observed: same matchup bet across consecutive nights — motivated C5.

### C1 details — what shipped 2026-04-18

`trusted_edge()` in `scripts/kalshi/kalshi_executor.py` soft-caps edge inside the Kelly sizing expression only. Raw edge still flows through the edge-threshold gate, composite score, trade rationale, reports, and trade journal.

```
trusted_edge(edge) = edge                            if edge ≤ cap
                   = cap + (edge - cap) × decay      if edge > cap
```

Defaults `KELLY_EDGE_CAP=0.15`, `KELLY_EDGE_DECAY=0.5`:

| Raw edge | Trusted edge | Kelly reduction |
|---|---|---|
| ≤15% | unchanged | 0% |
| 20% | 17.5% | 12.5% |
| 25% | 20.0% | 20.0% |
| 30% | 22.5% | 25.0% |
| 35% | 25.0% | 28.6% |
| 50% | 32.5% | 35.0% |

Re-measure at 4 weeks. If ≥25% bucket is still negative, tighten to a harder cap (decay=0) or add a composite-score penalty.

---

## Completed

Index only — detailed notes are in the collapsed section below.

### 2026-04-21 — 14-Day Review Response (R1, R2, R3, R4)

| ID | Item |
|----|------|
| R3 | Gate 4.5 — `MIN_CONFIDENCE` (default `medium`) rejects low-confidence opportunities. Addresses 0W-3L / -105% ROI in two review windows. |
| R1 | Gate 4.6 — NO-side favorite guard: reject NO bets priced below `NO_SIDE_FAVORITE_THRESHOLD` (0.25) unless edge ≥ `NO_SIDE_MIN_EDGE` (0.25) AND `confidence=high`. Plus sizing dampener: NO bets priced below `NO_SIDE_KELLY_PRICE_FLOOR` (0.35) sized at `NO_SIDE_KELLY_MULTIPLIER` (0.5 = half-Kelly). Addresses F1 — all 13 high-edge losers in 14d window were NO-side. +14 regression tests (195 total). |
| R4 | Resting-order janitor — `cancel_stale_resting_orders()` runs at the top of `execute_pipeline()` when `execute=True` AND `DRY_RUN=false`. Cancels resting orders older than `RESTING_ORDER_MAX_HOURS` (default 24) with zero fills. Partial/full fills left to the settler. Addresses F7 — 16% of new orders resting 25-66h with no follow-up. +12 tests (207 total). |
| R2 | Per-sport stdev bump in `SPORT_MARGIN_STDEV` / `SPORT_TOTAL_STDEV` (edge_detector.py). NBA +15% (12.0→13.8 margin, 18.0→20.7 total), NCAAB +10% (11.0→12.1, 16.0→17.6), MLB +15% (3.5→4.025, 3.0→3.45). NHL untouched (+87% ROI, well-calibrated). Direct fix for Brier 0.2646 and the 60-70% favorite-band overconfidence (F2, F3, F4, F5). Supersedes C2. +6 tests (213 total). R12 (re-run calibration at 100 trades) is the attribution check. |

### 2026-04-18 — Calibration-Driven Tuning

| ID | Item |
|----|------|
| C1 | Soft-cap edge used in Kelly sizing (`trusted_edge()`, `KELLY_EDGE_CAP=0.15`, `KELLY_EDGE_DECAY=0.5`, +6 tests) |
| C3 | Per-sport `MIN_EDGE_THRESHOLD` (NBA=8%, NCAAB=10%, `min_edge_for()` helper, +5 tests) |
| C5 | Series-level dedup — Gate 7, `matchup_key()`, `SERIES_DEDUP_HOURS=48`, +16 tests (177 total passing) |

### 2026-04-07 — Backtesting, Dashboard Batch 2, Package Structure

| ID | Item |
|----|------|
| W1 | Backtesting framework — equity curve, Sharpe, drawdown, calibration curve, strategy simulation, +32 tests |
| H4 | Package structure — `pyproject.toml` with `pythonpath`, `__init__.py` files, simplified `conftest.py` |
| A1 | Domain package extracted — `app/domain/` with `Opportunity`, `RiskDecision`, `ExecutionPreview`, `ExecutionResult`, +7 tests |
| D5 | Auto-refresh portfolio (`st.fragment(run_every=30s)` + toggle) |
| D7 | Position P&L color coding (W/L/F count + unrealized P&L) |
| D8 | Execution confirmation dialog (`@st.dialog`) |
| D9 | Toast notifications after execution and settlement |
| D11 | Settlement history tab (sortable + CSV export) |
| D14 | CSV export buttons on scan/positions/settlements/report |
| D16 | `streamlit>=1.33.0` added to `requirements.txt` |

### 2026-04-06 — Dashboard v1.0, Dynamic Stdev, Simplification

| ID | Item |
|----|------|
| U6 | Streamlit dashboard v1.0 — 3 pages (Scan & Execute, Portfolio, Settle & Report), dark theme, favorites, quick-scan |
| D1 | Quick-scan sidebar buttons |
| D2 | Favorite scans |
| D4 | Default unit size $0.50 |
| S5 | Dynamic stdev adjustment — weather severity, rest/B2B applies to spreads, per-home-team weather cache |
| H5 | Simplified scripts & config — removed `DEFAULT_BET_SIZE`, `MIN_CONFIDENCE`, `MAX_POSITION_CONCENTRATION`, merged `MAX_BET_SIZE_*`; -4 env vars, -2 CLI flags, -2 gates. See `archive/SIMPLIFICATION.md`. |
| H1 | Centralize config (resolved by H5 — `config.py` deleted; `kalshi_executor.py` is canonical) |

### 2026-04-04 — Fill-based Logging, MLB Pitcher Data, Calibration Tooling

| ID | Item |
|----|------|
| X5 | Fill-based trade logging — `filled_contracts`/`filled_cost` vs `requested_*`, `fill_status`, +16 regression tests |
| X6 | Gates 8-9 documented as sizing caps; approval subtypes `APPROVED`, `APPROVED_CAPPED_CONCENTRATION`, `APPROVED_CAPPED_MAX_BET` |
| S1 | Starting pitcher data — ERA / FIP / WHIP / K9 / days-rest, matchup classification, stdev adjustment |
| S2 | Back-to-back / rest days — NBA / NHL detection via ESPN scoreboard, stdev + confidence adjustment |
| W2 | `model_calibration.py` — Brier, calibration curve, dimension breakdowns, cross-tabs, prioritized recommendations |
| W4 | Win-rate analytics by dimension (confidence × category × sport × edge bucket) |

### 2026-04-02 — Execution Correctness

| ID | Item |
|----|------|
| X1 | Hardcoded Python path fixed (`sys.executable`) |
| X2 | All 9 risk gates enforced in executor; Kelly sizing with unit-size floor |
| X3 | Per-event caps + correlated-bracket dedup (`dedup_correlated_brackets()`) |
| X4 | Startup doctor command (`scripts/doctor.py`) |
| W3 | Kelly Criterion sizing (part of X2) |

### 2026-04-01 — Display Improvements

| ID | Item |
|----|------|
| D1 | Bet-type column (ML/Spread/Total/Prop) in all output tables |
| D2 | Descriptive Pick column replacing raw YES/NO |

### 2026-03-23 — Edge Model Improvements

| ID | Item |
|----|------|
| E1 | Normal CDF spread/total model |
| E2 | Closing Line Value tracking |
| E3 | Sharp book weighting (Pinnacle 3×) |
| E4 | Team performance stats (ESPN/NHL/MLB APIs) |
| E5 | Injury / line-disagreement signal |
| E6 | Line movement & sharp-money detection |
| E7 | Weather for outdoor sports (NWS API) |

### 2026-03-30 to 31 — Project Quality

| ID | Item |
|----|------|
| P1 | Standardize CLI flags |
| P2 | Standardize logging (`setup_logging`) |
| P3 | Consolidate import boilerplate (`.pth`) |
| P4 | Markdown scan reports |
| P5 | Initial test suite (83 tests) |
| P6 | Remove empty `strategies/` |
| P7 | `MAX_BET_SIZE_SPORTS` in `.env.example` |
| P8 | Unify report output format |
| P9 | Unified `scan.py` entry point |
| P10 | Docs cleanup + `docs/scripts/` sub-docs |
| P11 | Pre-commit hooks |
| P12 | Makefile (18 targets) |

---

## Completed Item Details

<details>
<summary>X1-X4. Execution Correctness (2026-04-02 to 2026-04-04)</summary>

**X1.** Replaced hardcoded `.venv/Scripts/python.exe` in `scan.py` with `sys.executable`. Now works across any environment (CI, WSL, Docker, other machines).

**X2.** Enforced all risk gates that were previously loaded but never checked in `kalshi_executor.py`. The executor now runs 9 gates before every order: daily loss, max open positions, edge threshold, composite score, confidence floor, duplicate ticker, per-event cap, max concentration, max bet size. Position sizing upgraded from flat unit to quarter-Kelly with flat unit as floor. Pipeline tracks approved orders within the batch so gates apply correctly across the run.

**X3.** Per-event caps + correlated-bracket dedup (updated 2026-04-04). `dedup_correlated_brackets()` groups by `(event_key, category)` and keeps only the highest composite score. `MAX_PER_EVENT` default lowered from 3 to 2. New `--max-per-game` CLI flag for session override.

**X4.** Startup doctor command (`scripts/doctor.py`). Validates Python version, venv, credentials (Kalshi key + private key path, Odds API keys), data directories, config values, API connectivity, and pre-commit hooks.

**Breaking change:** `MAX_BET_SIZE` split into `MAX_BET_SIZE_SPORTS` / `MAX_BET_SIZE_PREDICTION` (later re-merged in H5).
</details>

<details>
<summary>X5. Fill-based Trade Logging (2026-04-04)</summary>

Executor previously logged `requested_contracts` / `requested_cost` regardless of fill. Resting/partial orders overstated exposure. Added `filled_contracts` / `filled_cost` fields and `fill_status` enum (`filled`, `partial`, `resting`, `failed`). Settler / risk_check now read fill-based values. 16 regression tests for resting, partial, and zero-fill responses.
</details>

<details>
<summary>X6. Sizing Caps vs Reject Gates (2026-04-04)</summary>

`ARCHITECTURE.md` previously described concentration and max-bet as reject gates, but executor silently downsized. Docs updated to describe gates 8-9 as sizing caps. New approval subtypes `APPROVED`, `APPROVED_CAPPED_CONCENTRATION`, `APPROVED_CAPPED_MAX_BET` in trade log distinguish clean from force-capped.
</details>

<details>
<summary>E1. Normal CDF Spread/Total Model (2026-03-23)</summary>

Replaced linear `+3% per point` with `scipy.stats.norm` bell curve. Infers expected margin from book spread + implied probability, then `P(margin > strike)` on the bell curve. Sport-specific stdevs: NBA (12), NCAAB (11), NFL (13.5), MLB (3.5), NHL (2.5), soccer (1.8). Separate stdevs for totals.

**Context:** live trading 2026-03-22 had 1W-11L on NCAAB spreads at estimated 33% edge → realized -88% ROI. Linear model systematically overestimated edge on alternate spreads.
</details>

<details>
<summary>E2-E7. Edge Model Signals (2026-03-23)</summary>

- **E2:** CLV — settler captures `last_price` from Kalshi at settlement; average CLV + beat-the-close rate in performance report.
- **E3:** Sharp book weighting — 21-book `BOOK_WEIGHTS` map (Pinnacle/Circa 3×, DraftKings/FanDuel/BetMGM 0.7×), weighted-median consensus.
- **E4:** Team stats — `team_stats.py`, 6 sports from free APIs (ESPN NBA/NCAAB/NFL/NCAAF, NHL Stats, MLB Stats). Win%, run/goal diff, L10, streak.
- **E5:** Injury proxy — spread disagreement >4pts across books triggers confidence downgrade (ESPN injury endpoints were unreliable).
- **E6:** Line movement — `line_movement.py` uses ESPN scoreboard open-vs-close; detects reverse line movement + sharp total movement.
- **E7:** Weather — `sports_weather.py` NWS hourly forecast for 31 NFL + 30 MLB venues. Wind >15mph, rain >40%, cold <32F (NFL) / <45F (MLB).
</details>

<details>
<summary>D1-D2. Display Improvements (2026-04-01)</summary>

Type column (ML/Spread/Total/Prop) across all 7 output tables. Descriptive Pick column replacing raw YES/NO ("Over 220.5", "Spurs -4.5", "Heat win"). `bet_type_from_ticker()` + `format_pick_label()` in `ticker_display.py`. Kalshi team abbreviation aliases (SAS, GSW, NOP, etc.).
</details>

<details>
<summary>P1-P12. Project Quality (2026-03-30 to 31)</summary>

Standardized CLI flags (P1), logging (P2), imports via .pth (P3), markdown reports (P4), 83-test suite (P5), removed empty `strategies/` (P6), `.env.example` (P7), unified report format (P8), `scan.py` entry point (P9), docs cleanup + `docs/scripts/` (P10), pre-commit hooks (P11), Makefile 18 targets (P12).
</details>
