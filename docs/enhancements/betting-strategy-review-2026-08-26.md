# Betting Strategy Review & Optimization Plan

**Date:** 2026-08-26 · **Authors:** claude-code (facilitator) + codex (collaborator), agent-chat conv #54 · **Rev 2** (close-book capture, fail-closed eligibility, config fingerprint, kill-switch distance, day-90 branch)
**Scope:** `data/history/kalshi_settlements.json` (402 settles, 2026-03-22 → 2026-08-20), `kalshi_trades.json` (169 rows), `.env`, `CLAUDE.md`, the gate/sizing/settler code, `data/polymarket/dryrun_log.jsonl`.
**Goal:** maximize positive betting revenue over time.

---

## 0. The one-paragraph answer

Edge-Radar's lifetime record is **+$54.04 on $381.66 staked (+14.2% ROI, 46.5% win rate)** — but the 95% bootstrap CI on that ROI is **[−6.2%, +36.8%]**, it contains zero, and removing the five largest winners turns it into **−$8.15**. There is no sport, price band, or edge bucket in this ledger with a defensible positive ROI once three bets are removed from it. Meanwhile the model's own calibration study puts the trustworthy fraction of any claimed edge at **λ = 0.16**, and realized fees run **3.14% of stake** — meaning a row claiming a healthy 10% edge carries ~1.6% of real edge against a 3.1% toll. **The system is structurally negative-EV as a pure taker, and the record is not large enough to prove otherwise in either direction.** The plan below therefore does not tune thresholds. It (1) stops preventable waste, (2) installs the measurement that can settle the question in months instead of years, (3) removes the structural cost of trading, and only then (4) scales.

---

## 1. What the settled record actually says

### 1.1 Headline, and why it is not the headline

| | n | Staked | Net | ROI | Win% |
|:--|--:|--:|--:|--:|--:|
| **All settled** | 402 | $381.66 | **+$54.04** | **+14.2%** | 46.5% |
| Excluding top 3 winners | 399 | $381.66 | +$8.27 | +2.2% | — |
| **Excluding top 5 winners** | 397 | $381.66 | **−$8.15** | **−2.1%** | — |

Bootstrap 95% CI on lifetime ROI (10k resamples): **[−6.2%, +36.8%]**.

The four largest winners:

| Ticker | Entry | Net |
|:--|:--|--:|
| KXMLSSPREAD-26MAY16SEALAG-LAG1 | 6c | +$20.59 |
| KXMLSSPREAD-26APR19LAFCSJ-SJ1 | 7c | +$14.80 |
| KXUFCFIGHT-26MAY09CHISTR | — | +$10.38 |
| KXMLSSPREAD-26MAY10LAFCHOU-HOU1 | 6c | +$8.42 |

Three of four are sub-10c MLS spread longshots. The entire sub-10c band is **25 bets, $20.35 staked, +$25.83** — and every dollar of that comes from those three tickets. 22 of 25 lost.

**Conclusion:** the current record cannot distinguish "we have a +14% edge" from "we are break-even and got lucky three times in eight weeks."

### 1.2 The regime broke in June

| Period | n | Staked | Net | ROI |
|:--|--:|--:|--:|--:|
| Mar–May | 274 | $229.31 | +$74.16 | **+32.3%** |
| Jun–Aug | 128 | $152.35 | −$20.12 | **−13.2%** |

Permutation test on the ROI gap: **p = 0.018** one-sided (20k shuffles). Real enough to act on; flagged for multiple comparisons.

The bleed is **broad, not localised** — every slice a lifetime-ROI pruning strategy would have kept is losing recently:

| Slice | Lifetime ROI | Jun–Aug ROI |
|:--|--:|--:|
| YES side | +30.8% | **−16.2%** |
| NO side | −9.6% | −11.5% |
| SPREAD | +36.6% | **−28.2%** |
| TOTAL | +2.2% | **−13.3%** |
| Claimed edge 5–15% | +16.7% | **−20.1%** (n=88, $112.61) |

A static gate tuned on Mar–May is tuned on a distribution that no longer exists.

### 1.3 Every "good" sport is a concentration artifact

| Sport | n | Staked | Lifetime ROI | ROI excl. its own top 3 |
|:--|--:|--:|--:|--:|
| MLS | 64 | $64.02 | +76.5% | **+8.4%** |
| NHL | 60 | $34.91 | +62.1% | **+22.0%** |
| NCAAMB | 56 | $36.24 | +21.7% | **−2.4%** |
| MLB | 143 | $161.03 | −6.4% | — |
| NBA | 32 | $50.43 | −23.3% | — |
| WC | 43 | $28.19 | −43.2% | — (already OFF via F3) |

**There is no winner to keep.** "Prune to the profitable sports" is not an available move.

### 1.4 Claimed edge is non-monotone against outcomes

| Claimed edge | n | ROI | Win% |
|:--|--:|--:|--:|
| <5% | 34 | +11.6% | 41.2% |
| 5–8% | 80 | +13.0% | 45.0% |
| 8–12% | 112 | +30.0% | 54.5% |
| 12–20% | 75 | +3.8% | 50.7% |
| **≥20%** | **89** | **+2.9%** | **34.8%** |

The largest claimed edges have the worst win rate in the book. *(CI on the 8–12% pocket is [−12.4%, +84.7%] — the direction agrees with F3's independent λ, but this bucketing is not standalone evidence.)*

**Operational consequence:** the gates have an edge *floor* and no *ceiling*. A row claiming 40% edge clears Gate 3 and is Kelly-sized off a number the record says is mostly fantasy. `KELLY_EDGE_CAP=0.15` damps the size; it does not stop the bet.

**A λ-multiplier alone cannot fix this.** Replaying all 390 settles with `edge_estimated`, applying `λ·edge ≥ floor + fee(price)`:

| λ | floor | kept | Staked | Net | ROI |
|--:|--:|--:|--:|--:|--:|
| 1.00 (today) | 0.03 | 368 | $351.71 | +$41.74 | +11.9% |
| 0.40 | 0.03 | 162 | $167.25 | +$32.23 | +19.3% |
| 0.25 | 0.03 | 90 | $87.98 | +$1.47 | +1.7% |
| **0.16** | **0.03** | **44** | **$39.13** | **+$4.78** | +12.2% |
| **0.16** | **0.04** | **27** | **$24.35** | **−$2.73** | **−11.2%** |

At λ=0.16 with unchanged floors, the effective bar at a 50c contract becomes `edge ≥ 0.29` — you keep 11% of the book, composed **entirely of the ≥20% claimed-edge population that performs worst.** λ-scaling with a fixed floor *selects for* overstatement. And because λ is a monotone transform, dropping the floor proportionally just re-cuts the same ranking at a different point. **A multiplier cannot repair a non-monotone defect; a ceiling can.** They are orthogonal tools, not alternatives.

---

## 2. Defects found (not statistics — bugs and holes)

### D1 — CLV has never once been computed. It is broken, not missing.

```
trades with closing_price:      76 / 169     distinct values: {0.0: 76}
settlements with closing_price: 150          clv populated: 0
```

`kalshi_settler.py:326` reads `closing_price = float(market_data.get("last_price", 0)) / 100` **from the market snapshot taken at settlement time.** A settled Kalshi market returns no meaningful `last_price`, so `closing_price` is `0.0`; `0.0` is falsy, so line 334's `if closing_price and entry_price` short-circuits and `clv` is `None`. Silently, on every settle, for five months.

**There is nothing to backfill** — the column is 150 zeros. CLV requires a *new capture*, and CLV data starts accruing the day it ships.

### D2 — 24 open NFL positions, 31% of bankroll, in a sport with zero settled history

Reconciling `kalshi_trades.json` against `kalshi_settlements.json` by `trade_id`:

```
open positions: 24    at-risk: $28.50    oldest entry: 2026-05-23
  KXNFLTOTAL   n=11   $14.96
  KXNFLSPREAD  n=10   $8.68
  KXNFLGAME    n= 3   $4.86
NFL rows in settlements: 0        (plus 6 status='error', 2 resting)
```

Every one is live money (`dry_run=false`). Three problems:

- **$28.50 on a ~$92 bankroll is 31% of the account**, one sport, held up to 95 days before kickoff. `MAX_OPEN_POSITIONS=50` and `MAX_PER_EVENT=2` both pass — **no gate measures total capital deployed.** You can satisfy all nine gates and still park a third of the account in September football since May.
- **NFL has no calibration evidence.** Its `margin_stdev: 13.5` in `data/cache/calibration_stdevs.json` is a hardcoded prior, not a fit — contrast `baseball_mlb: 4.025`, `icehockey_nhl: 2.5`, which carry the decimals of something computed.
- **This book was admitted by a pre-L2 filter.** The `.env` L2 comment records that the 2026-08-18 NFL Week 1 audit found *13 of 27 open positions past the 5c spread line (to 20c) and 18 of 27 with zero 24h volume.* Gate 3.6 now stops that class of row — **but Gate 3.6 only runs at entry. Nothing re-checks a position already held.**

### D3 — Every order is a taker, and the toll exceeds the trusted edge

```
maker_fees nonzero:   0 / 169 trades     ← never once the passive side
taker_fees nonzero:  17 / 169
fees: $11.97 on $381.66 = 3.14% of stake
ROI with fees: +14.2%   |   ROI at zero fees: +17.3%
```

At λ=0.16, a row claiming a 10% edge — comfortably above every floor in `.env` — carries a **trusted edge of ~1.6%** against a **3.14%** realized fee drag. No gate tuning changes that sign.

`kalshi_client.create_order()` already takes `yes_price_cents`/`no_price_cents` with `time_in_force="good_till_canceled"` — these *are* restable limit orders. They never rest because the executor prices them to cross.

### D4 — Config changes may never reach the live automation

Scheduler `.bat` files pass `--unit-size` and `--budget` explicitly, and `kalshi_executor.py` snapshots every gate threshold into module globals **at import time**. **Every recommendation in this document can be shipped to `.env` and change nothing.**

### D5 — Deterministic venue rejections are being retried

The 2026-08-26 daily summary shows 3 orders rejected by the venue: Nevada residents cannot open positions in Sports, Elections, and Entertainment. This is not noise — it is the automation spending cycles on rows that structurally cannot fill.

### D6 — Historical numbers were screened on gross edge

F1 (2026-08-25) folds `ceil(0.07·C·P·(1−P))` into the Gate 3 floor and Kelly. Correct — and it means **every figure in §1, including +14.2%, was generated by a looser filter than the one now running.** The live and historical systems are not the same system.

### D7 — Polymarket has produced no tradable evidence

45 dry-run passes, 1,250 rows, 54 executable, **all 54 failed on edge, 0 settlements.** Useful as a pricing lab; not a revenue candidate.

---

## 3. Design decisions the room agreed on

1. **Rolling policy may only ever tighten.** A trailing window that can *loosen* a gate will overfit whichever slice just got lucky. Static hard stops stay in `.env`; rolling state may demote to dry-run, raise an effective floor, or cap a stake — nothing else — until a pre-declared promotion rule is met.
2. **Segment policy expires.** NBA, NHL and NCAAMB are out of season as of 2026-08-26 (last settles 2026-06-14, 2026-06-15, 2026-04-02). A demotion written today would still be enforcing a 32-bet April sample in October. Every segment carries `last_settled_at` and an expiry.
3. **`dry_run: insufficient_evidence` is not `dry_run: negative_clv`.** Negative CLV says the model is bad; insufficient evidence says it is unproven. Different reasons, different exits.
4. **Cold start means pilot mode, not prohibition** — live entries off until CLV capture exists, then a tiny bounded discovery allocation the operator explicitly enables.
5. **Legacy positions are quarantined from performance claims.** Anything opened under a superseded gate set cannot be used to validate *or* condemn the current one.
6. **Shadow before live.** New gate logic logs what it *would* have done for at least one full cycle before it rejects anything.
7. **Every action item names its verification step**, because of D4.

---

## 4. Action items

Ordered. Each names the file, the key, the check, and the measurement that says it worked.

### Phase 1 — Stop preventable waste (this week, no evidence required)

| # | Action | Where | Verify | Success measure |
|:--|:--|:--|:--|:--|
| **1.1** | **Freeze new NFL live entries — temporarily.** Set `MIN_EDGE_THRESHOLD_NFL=1.0` (the F3 World-Cup idiom — a floor at or above 1.0 can never be cleared). **This is a freeze mechanism, not NFL policy.** It comes back out the moment 2.3 exists; the durable rule is strategy-state `cold_start` → pilot, not an impossible threshold left in `.env` forever (that is D4 waiting to happen again). | `.env` | `python scripts/doctor.py`; next scan preview shows NFL `off` | 0 new NFL entries; the key is removed when 2.3 ships |
| **1.2** | **Quarantine the 24-position pre-L2 NFL book.** Hold, do not flatten — market-exiting 5–20c-wide books pays the illiquidity penalty Gate 3.6 exists to avoid. Do not add to any existing NFL event or ticker. Review exit **only** if the current spread is 5c or tighter and the exit price implies less expected loss than holding to settlement. | position policy + daily report | Daily summary gains a "legacy positions (pre-current-gates)" section | Legacy book excluded from every ROI/CLV claim |
| **1.3** | **Jurisdiction/product eligibility preflight — and fail closed.** This is a correctness bug, not just waste. Cache venue/account eligibility at startup, print it in `doctor.py` and in the daily summary, and treat **unknown eligibility as `dry_run`** — a transient API or config failure must never fall back to attempting real orders in a barred product. If the account truly cannot trade Sports on this venue, that is a day-one fact about the reachable book, not a trickle of rejects to discover over weeks. | executor preflight, `doctor.py` | `doctor.py` prints eligibility; daily summary shows 0 venue rejections | Venue-rejection count reaches 0; unknown ⇒ no live order ever placed |
| **1.4** | **Cumulative exposure gates (new).** `MAX_OPEN_EXPOSURE_PCT=0.20` (total open at-risk over bankroll, hard reject) and `MAX_SEGMENT_EXPOSURE_PCT=0.10` (per sport/category/venue). Neither `MAX_BET_RATIO` nor `--budget 10%` covers this — both bound a *single batch*; the NFL book accumulated across roughly a dozen scans over three months. | `.env`, `app/config.py`, risk gate 2b | Force a synthetic over-limit scan; confirm the reject reason | NFL-style 31% concentration becomes unreachable |
| **1.5** | **Time-to-event cap.** `MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS=14`. Futures get a separate, longer config. | `.env`, risk gate | Scan preview rejects far-dated game rows | No game-market position held more than 14 days pre-event |
| **1.6** | **Propagate config to automation.** Audit every scheduler `.bat` for `--unit-size`/`--budget`; restart long-running hosts; make `doctor.py` echo the *effective* gate values it would execute with. | `scripts/schedulers/`, `doctor.py` | `doctor.py` output matches `.env` | No silent divergence |
| **1.7** | **Hold all sizing.** `KELLY_FRACTION` at 0.5 or below, `UNIT_SIZE=1.00`, `ALLOW_PREDICTION_BETS=false`, `ALLOW_LIVE_BETS=false`, World Cup off. Lifetime ROI CI contains zero — nothing here justifies more size. | `.env` | `doctor.py` | — |
| **1.8** | **Index this document.** Add its row to the nearest `docs/` README index. Docs in this repo are navigated through README indexes — an unlinked doc is an unreachable doc. | `docs/enhancements/README.md` (or nearest parent index) | The index lists it | Document is saved **and indexed** |

### Phase 2 — Install the instrument (2–4 weeks)

| # | Action | Where | Detail |
|:--|:--|:--|:--|
| **2.1** | **Fix the CLV bug and build real capture.** Never use settlement-time `last_price`. | `kalshi_settler.py:320-334`, new scheduled job | At execution store `entry_price_bet_side` and `event_start_time`. A new job at **T−5min** writes `close_price_bet_side` from the live snapshot (T−0 fallback, never post-settlement). At settlement, `clv = close_price_bet_side − entry_price_bet_side`. **All prices in bet-side probability space** so CLV means the same thing for YES and NO. **Persist the whole closing book, not one scalar:** `close_yes_bid`, `close_yes_ask`, `close_no_bid`, `close_no_ask`, `close_mid_bet_side`, `close_capture_at`, `close_capture_reason` ∈ {`t_minus_5`, `t_zero_fallback`, `missed`}. A single close value cannot tell you whether maker CLV improved through better execution or because the close was sampled on the other side of the book — which would make the Phase 3 A/B unreadable. Publish the mean on one agreed convention; keep the raw book so it can be re-scored on mid, same-side and cross-side later. **`missed` writes NULL, never 0.0.** A falsy sentinel absorbed by a truthiness guard is precisely how D1 happened; a zero close would drag every mean toward a fictitious −entry_price. |
| **2.2** | **CLV reporting slice.** Mean CLV in percentage points **with bootstrap CI**, by sport / category / side / price band / fee role. | `scripts/kalshi/betting_analysis.py` | This replaces realized ROI as the primary decision signal. **Every CLV figure prints `n_captured / n_settled` beside it.** Mean CLV over 60% of the book is not the same claim as over 97%, and misses will not be random — they concentrate in thin markets, which is where the bad bets live, so low coverage biases the mean optimistic. |
| **2.3** | **`strategy_state.json`, protective mode only.** Written by analysis, read at the risk boundary. | `scripts/backtest/strategy_state.py` writes · `app/config.py` exposes path and flag · executor preflight reads · `doctor.py` prints its timestamp | Per segment: `last_settled_at`, `evidence_status` in {`active`, `stale`, `cold_start`, `insufficient`}, `expires_after_days` (about 45 for daily sports, 120 for seasonal/futures), `default_when_stale: dry_run`, `execution`, `reason`. **Never inherits stale positive ROI.** |
| **2.4** | **Shadow diagnostics — log only, change no decision.** `calibrated_edge = lambda × claimed_edge` (0.16, and log 0.25/0.40); `gate3_ceiling_would_reject` at `EDGE_CEILING_WARN=0.20` and `EDGE_CEILING_REJECT=0.30`; a `legacy_gateset` label on every trade row. | edge detector + executor logging | After one full cycle, review firing rates before anything goes live. |
| **2.5** | **Re-run `calibration_study.py` and `correlation_check.py`** once CLV exists, and re-measure lambda against CLV rather than outcomes. | `scripts/backtest/` | Lambda's CI is currently [−0.04, +0.42] — far too wide to size against. |
| **2.6** | **The daily scoreboard.** Every mechanism above is invisible unless it surfaces daily. Six lines, no more: (1) `eligibility: OK | UNKNOWN→dry_run`; (2) `risk_config_fingerprint()` — see below; (3) `open exposure: $X (Y% of bankroll) — legacy $Z excluded`; (4) `CLV last 30d: +A.A pts [CI], n=B/C captured (D%)`; (5) segments in dry_run, with reason; (6) **kill-switch distance** — which trigger is nearest and how far. | daily summary job | Line 6 is the important one. A kill switch you first learn about when it fires is a switch you will argue with; one you watch approach for three weeks is one you have already accepted by the time it trips. That is the whole reason §5 is written now. |
| **2.7** | **`risk_config_fingerprint()` — make D4 an invariant, not an audit.** One function, defined at the risk boundary (the executor) and called by **both** `doctor.py` and the daily summary. It hashes the *actual runtime decision inputs*: `.env` values, command-line overrides from scheduler `.bat` files, module-level constants **as they stand after process start**, the strategy-state file path + mtime/hash, and the eligibility-cache version. | `kalshi_executor.py`, `doctor.py`, daily summary | Hashing `.env` alone would miss every one of D4's failure modes. With one shared function, **the thing printed is the thing executing** — which turns "audit the `.bat` files" from a recurring chore into a check that cannot silently lapse. |

### Phase 3 — Remove the structural cost of trading (after 2.1–2.3 land)

**Maker-fill A/B.** Kalshi maker fees are zero. On the settled book that is **$11.97 on $381.66 — a +3.14 percentage-point ROI swing that requires no improvement in the model.** It is the only lever in this document whose payoff does not depend on Edge-Radar having skill.

- **Not a new default — a bounded experiment.** "Post at the bid" is at least three strategies: best-bid passive (lowest fee, lowest fill rate, highest adverse selection), one-tick-inside-spread (better fill, gives up spread capture), and today's aggressive baseline.
- **Require a post-only flag if the venue offers one.** If not, place a maker-test order only when the limit price sits strictly inside the opposite side so it cannot accidentally cross. **On a 1c-wide market there may be no safe maker test at all.**
- **Eligibility:** passes Gate 3.6; spread 3c or tighter preferred, never wider than 5c; nonzero 24h volume once that floor is on; event inside the game-market window; no legacy positions.
- **Allocation:** deterministic by ticker hash, never chosen after seeing the market. **Start 25% maker / 75% taker** — fill loss can starve the sample and the bankroll is small.
- **Sizing unchanged.** Fee savings must not increase stake during the experiment.
- **Recompute edge at the intended order price**, never inherit the scan row's displayed market price. Log `scan_price`, `limit_price`, `fill_price`, `would_cross_at_submit`, `liquidity_regime`, `fee_role`. Without these you cannot separate "maker improved EV" from "maker selected a different price distribution."
- **Metrics:** fill rate, partial-fill rate, mean CLV, realized spread captured, cancellation rate via `RESTING_ORDER_MAX_HOURS`, post-fee ROI, and missed-opportunity cost on unfilled orders that later moved favorably.
- **Stop rule:** maker-fill CLV underperforms taker-fill CLV by more than 1 point after 100 filled maker orders, **or** fill rate falls below 25% on otherwise-qualifying rows. Disable maker mode for that segment.
- **Promotion:** becomes the default only if it nets at least 1 percentage point after adverse selection, with the lower bootstrap bound above 0, over 100 or more filled maker orders.

**Note the symmetry:** Gate 3.6 and a maker strategy are the same policy approached from two directions — *only trade where a real two-sided market exists.*

### Phase 4 — Scale, if and only if the evidence arrives

Turnover is the other multiplicand: **$382 across five months on a ~$92 bankroll, median stake $0.80.** Even a genuine, durable +10% edge returns about $38 in five months. Scaling comes last, and only on a pre-declared trigger.

**Day-90 checkpoint, with a pre-declared losing branch.** At 90 days from CLV ship:

- **Coverage under 60%** → the capture job is the problem. Nothing else in the numbers is readable yet. Fix capture; do not interpret CLV.
- **Coverage fine, global CLV CI still straddles zero** → the answer is *not* "run longer at this size." A median stake of $0.80 will not resolve it in a second 90 days either. The honest branch is: shrink to the segments with the tightest CLV CIs, or stop. Writing that down now means the review has a losing option as well as a winning one.
- **Coverage fine, CLV lower bound above 0** → the promotion rule below applies.

**Promotion rule (deliberately harder than the kill rule, because scaling is where the damage happens):** at least 150 CLV-captured bets **and** at least 60 calendar days, global mean CLV **above +1.0 point with the lower 95% bound above 0**, and no segment sitting in a qualifying negative-CLV kill. Then raise **exactly one knob**: `UNIT_SIZE` from $1.00 to $1.50 (the longshot lane). Wait a further 60 days before touching `KELLY_FRACTION` (the favorites lane). Never both at once.

---

## 5. Kill switches

Written now, while nothing is at stake, so the decision is not made emotionally after a bad month.

| Trigger | Threshold | Effect |
|:--|:--|:--|
| **Global negative CLV** | Rolling 90 days, at least 150 captured bets, mean CLV at or below −1.0 point with the 95% bootstrap **upper** bound below 0 | **All automated execution to dry-run only.** Stop betting real money. |
| **Segment negative CLV** | At least 40 captured bets in a sport/category/side, mean CLV at or below −1.5 points with upper bound below 0 | That segment to dry-run, reason `negative_clv` |
| **Insufficient evidence** | 120 days elapsed with fewer than 150 captures for a segment | That segment to dry-run, reason `insufficient_evidence` — off-season quiet is not the same as a bad model, but silence defaults to off, not to running |
| **Venue/product rejection** | Any repeated structural rejection (e.g. the Nevada restriction) | Immediate disable of that venue/product until `doctor.py` reports it eligible. No sample threshold — this is deterministic, not noisy |
| **Daily loss** | `MAX_DAILY_LOSS` breach | Unchanged, stays as-is |

**Kill-switch distance is defined mechanically**, so the daily summary's line 6 has no author discretion. Per active trigger, compute a normalized distance in [0, 1] and report the minimum:

| Trigger | Distance |
|:--|:--|
| Global negative CLV | `upper_ci − 0`, alongside `n_captured / 150` |
| Segment negative CLV | same, against that segment's threshold and `n / 40` |
| Exposure | `cap_pct − current_pct` |
| Insufficient evidence | `120 − days_since_first_capture_or_policy_start` |
| Venue/product | binary — eligible, or distance 0 |

Line 6 prints the nearest trigger and its distance. This is the operator's early-warning surface; it must be generated, not written.

---

## 6. Disagreements that survived, and what would settle them

| Question | Where we landed | What would settle it |
|:--|:--|:--|
| **Lambda multiplier vs. edge ceiling** | Both, and both in shadow first. Lambda sets *how much* to trust a claimed edge; the ceiling handles *where* trust inverts. The replay showed lambda-with-fixed-floors selects for the worst population, so lambda cannot go live as a Gate 3 transform. | Re-measure lambda against CLV rather than outcomes, then check whether the ceiling still fires on rows lambda has already killed. If it never fires independently, drop it. |
| **The sub-10c longshot lane** (`MIN_MARKET_PRICE=0.10`, flagged in CLAUDE.md as an open experiment) | **Keep, tiny fixed stake, and stop counting it as evidence.** F3 says the model's only clean signal is on cheap contracts (32c or below: high-edge half wins +10.8 points more than low-edge), so killing it may kill the one real edge. But three MLS tickets are the entire lane's P&L, so it proves nothing about strategy. | Mean CLV on sub-10c fills, with CI, over 40+ captures. Realized ROI on this population will never converge. |
| **Adverse selection on maker fills** | Unsized. Neither of us can quantify it from this data. It is written above as a **risk resolved by the A/B**, not as a settled recommendation. | The Phase 3 A/B: maker-fill CLV vs. taker-fill CLV over 100 filled maker orders. |
| **Whether the Jun–Aug break is signal** | Treat it as real (p = 0.018) but do not tune against it. It is one comparison among several we ran. | CLV over the next 90 days. If CLV was positive through a losing quarter, the break was variance; if CLV went negative alongside ROI, the model decayed. |
| **Whether to flatten the NFL book** | **Hold**, with the exit condition in 1.2. We do not have current bid/ask, and exiting into a 20c-wide book could cost more than the position is worth. | Pull live bid/ask on all 24 tickers. If the spread is 5c or tighter and the exit price beats hold-to-settlement EV, exit that ticker. |

---

## 7. What this plan does and does not claim

**It does not claim Edge-Radar is profitable.** The lifetime CI contains zero, the last three months are negative, the model's Brier score lost to the market in 6 of 6 months, and the entire positive P&L is five bets.

**It does not claim Edge-Radar is unprofitable either.** 402 settles at a median stake of $0.80 cannot resolve a question this fine. That is precisely the problem the CLV work exists to fix.

**Phases 1 and 2 reduce loss and buy information. Phase 3 is the first item that increases revenue** — and it does so without requiring the model to improve, which is why it is separated from Phase 4. Scaling turnover on a taker-only system whose trusted edge is smaller than its toll is not revenue optimization; it is a faster way to pay fees.

The honest summary for the operator: **the next 90 days are a measurement project, not a betting strategy.** At the end of them there will be a number — mean CLV with a confidence interval — that says whether there is anything here worth scaling. Today there is no such number, and every decision made without one is a guess.

---

*Produced by agent-chat conversation #54, 2026-08-26. All figures recomputed directly from `data/history/` at the time of writing; nothing quoted from prior reports without independent verification, except where explicitly attributed to CHANGELOG entries F1/F3/F4, C4, C10, C11, R1, R28, and L2.*
