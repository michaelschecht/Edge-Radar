# Changelog

---

## 2026-07-31 -- the C8 stdev loop had never calibrated anything: `--days 7` starved it

Asked to add a weekly calibration cadence. Checked the machine first. **The cadence
already existed**, and the real defect was elsewhere and worse.

### Cadence was never the problem

Three calibration tasks are registered under `\Edge-Radar-MikesAILab\`:

| Task | Schedule | Last run | Reality |
|:--|:--|:--|:--|
| `Calibration` | **Weekly**, Sun 7 PM | 7/26/2026, result 0 | the one actually doing the work |
| `MonthlyCalibration` | Monthly, day 1 | **11/30/1999 — never run** | dead duplicate the installer described |
| `Calibration Loader` | — | — | unrelated |

The cache timestamp (`2026-07-27T02:00:01Z` = 7/26 7:00 PM PDT) matches the weekly task's
last run exactly. So T3's premise -- "monthly cadence means ~30 blind days" -- was wrong,
and the ROADMAP entry has been corrected rather than quietly dropped.

### The real bug: a 7-day window cannot clear a 20-sample gate

The weekly task ran `model_calibration.py --days 7 --save`.

`save_calibration_stdevs()` is handed the **day-filtered** settled list, and
`_calibrate_one_stdev()` needs `_MIN_CALIB_SAMPLES = 20` rows **per (sport, category)**
before it will move a value. Only **~22 bets settle in any 7-day window across all sports
and categories combined**. No pair could ever reach 20.

So every weekly run skipped every sport and wrote the hardcoded defaults straight back.
That is why `data/cache/calibration_stdevs.json` was byte-identical to
`edge_detector.SPORT_*_STDEV`: **the closed calibration loop has been a silent no-op for
its entire existence.** It never once did the job C8 was built for.

| lookback | settled (all) | MLB totals visible | vs the 20-sample bar |
|:--|--:|--:|:--|
| `--days 7` | 22 | **17** | **SKIPS — writes the default back** |
| `--days 14` | 37 | 28 | calibrates |
| `--days 30` | 53 | 28 | calibrates |

### Fixes

- `scripts/schedulers/maintenance/calibration.bat`: `--days 7` → `--days 30`. **Gitignored
  — this, the actual fix, appears in no diff.** First real run moves
  `total_stdev.baseball_mlb` 3.45 → 4.005 (gap +16.1%, n=28, se=0.085), which drops the
  phantom edge on MLB high-strike unders below the R28 8% NO floor and blocks 21 of 25
  such bets (see the T1 entry below).
- `tests/test_calibration_config.py` (new, 6 tests): fails the build if the `--save`
  window is ever narrowed below 14 days, if `CURRENT_*_STDEV` drifts from
  `edge_detector.SPORT_*_STDEV` (a hand-copied duplicate that is the baseline every
  calibration multiplies against), or if the loop stops being stateless. Verified the
  window guard actually fires by reverting the `.bat` and watching it fail.
- `install_windows_task.py`: its `calibration` profile described a MONTHLY task that had
  never run and did not match the live weekly one. Reconciled to WEEKLY/Sun 19:00 pointing
  at the `.bat`, so there is one definition of the arguments.
- `model_calibration.py` docstring: corrected a claim that the loop "relies on the monthly
  loop compounding small corrections over time" -- wrong twice over. The loop is weekly,
  and it does **not** compound: `base_stdev` is the hardcoded baseline, never the prior
  cache value. Documented, because that statelessness is exactly what makes running it
  more often safe.

### Not fixed -- T4

Even with the window corrected, C8 cannot move a value until 20 of a market type's bets
have **settled**, which by construction happens after the flood. MLB totals reached 69% of
the book before any calibration could legitimately have data. No cadence or window change
addresses that; it needs a rule treating never-calibrated market types as suspect (higher
edge floor until first calibration, or a per-shape batch cap). Logged as T4, nothing
shipped. Relevant now: the Polymarket US seasonal games repoint is the next coverage
addition queued.

### `MonthlyCalibration` removed

The duplicate task was unregistered the same day (`schtasks /Delete`). It had **never once
executed** in its entire registered life -- `Last Run Time` was still the Task Scheduler
sentinel `11/30/1999` with `Last Result 267011` ("task has not yet run"). Every calibration
this repo has ever performed came from the weekly `Calibration` task instead, which makes
the monthly one pure cruft now that both would run `--days 30` against a stateless loop.

Its definition was archived before deletion and the recreate command is recorded in
`docs/task-schedules/README.md` section 15, which is now a removal record rather than a
task description. The surviving weekly task was re-verified afterwards: `Calibration`,
Sun 7 PM, `Last Result 0`, next run 8/2/2026, pointing at the fixed `.bat`.

`install_windows_task.py` also carries a note that it installs into the `Edge-Radar\` task
folder while the owner's live tasks live in `Edge-Radar-MikesAILab\` -- intentional, since
that file is a reference template rather than a turnkey installer for that machine, but it
means running it creates a parallel task rather than editing the live one.

683 tests.

---

## 2026-07-31 -- T1 resolved: the distance cap was measured and rejected; stale stdev calibration was the cause

The proposed T1 fix was a **cap on extrapolation distance** -- reject a totals bet whose
Kalshi strike sits more than ~1 sigma from the model's inferred mean. Backtested before
building. It does not survive.

### The cap would have made things worse

New tool `scripts/backtest/totals_distance_check.py` (re-runnable, mirrors
`correlation_check.py`). Extrapolation distance is recovered by inverting the normal CDF
from the stored `fair_value`, since `z = (strike - inferred_mean) / stdev` is exactly what
the model applied. Over **136 settled totals bets** -- read from the settlement log, not
the 41-row trade-log slice the first pass used:

| \|z\| bucket | n | W-L | WR | claimed | ROI |
|:--|--:|:--|--:|--:|--:|
| < 0.5 | 67 | 34W-33L | 51% | 60% | -1.1% |
| 0.5 - 1.0 | 32 | 18W-14L | 56% | 73% | **-29.5%** |
| **1.0 - 1.5** | **29** | **23W-6L** | **79%** | 89% | **+5.8%** |
| 1.5 - 2.0 | 5 | 4W-1L | 80% | 95% | -49.1% |
| > 2.0 | 3 | 2W-1L | 67% | 99% | -3.9% |

The 1.0-1.5 sigma band -- exactly where the MLB strike-12.5 bets sit -- is the **only
profitable bucket**. A cap at 1 sigma would have deleted the best band and kept the
-29.5% one. No cap was built.

### What the data actually says

The over-claim is **uniform across every bucket** (+9, +17, +10, +15, +32 points; +12%
overall, +16% MLB-only). A bias that does not vary with distance is not a distance
problem -- it is stdev calibration, which is already C8's job.

### Root cause: C8 was correct but stale

Running `model_calibration.py` today prints
`Calibrate baseball_mlb/total: base=3.45 gap=+16.1% (n=28, se=0.085) -> 4.00 (x1.161)` --
independently deriving the same +16% the backtest found. But the live cache, written
2026-07-27, still held **3.45, byte-identical to the hardcoded default**.

The reason is timing. MLB totals coverage landed **2026-07-20**, so at the 07-27 run fewer
than `_MIN_CALIB_SAMPLES = 20` had settled and the sport was skipped; the next scheduled
`MonthlyCalibration` was not until 08-01. **The flood ran for the entire blind window.**

### Action taken

Ran the calibration. `total_stdev.baseball_mlb` **3.45 -> 4.005**, verified live through
`_get_total_stdev()`. Note `data/cache/calibration_stdevs.json` is gitignored, so this
change appears in no diff.

Replayed over the 25 settled MLB NO-totals:

| | count | actual result |
|:--|--:|:--|
| Now blocked at Gate 4.6b (edge drops under the R28 8% NO floor) | **21 of 25** | 15W-6L, -$1.09, -3.1% ROI |
| Still placed | 4 | 3W-1L, -$5.19, **-63.4% ROI** |

**Honest read: the concentration is fixed, the selection quality is not.** Widening the
stdev removes 84% of the shape -- the volume problem originally spotted -- but the four
bets that still clear the floor are the *worst* performers in the group. Same "large
claimed edge = model error" pattern C4 found for confidence and C11 for sub-40c prices,
and the reason `KELLY_EDGE_CAP` exists. At n=4 that -63% is noise-level: a signal to
watch, not a result.

### T3 opened -- the structural lesson

`_MIN_CALIB_SAMPLES = 20` plus a **monthly** cadence means any newly-covered market type
can bet uncalibrated for up to ~30 days. This will recur on every coverage addition, and
one is already scheduled (the Polymarket US seasonal games repoint). Options logged, none
shipped: weekly calibration, event-triggering on first crossing 20 settled bets, or a
higher edge floor for market types that have never been calibrated.

Code added: `scripts/backtest/totals_distance_check.py`. No gate or model logic changed.

---

## 2026-07-31 -- MLB high-strike totals dominate the book (T1/T2 opened)

Operator observation: "under 13.5 or so runs in baseball" bets seemed to be placed far
more often than anything else. Investigated. Confirmed, and understated.

**Concentration.** Of 115 live trades, **31 are MLB totals (27%)**, **28 NO-side**, and
**14 sit on strike 13** -- one repeated wager shape is 12% of the whole book, against just
7 MLB moneylines in the same window. No gate prevents it: each bet is a *different game*,
so `MAX_PER_EVENT` and series dedup never engage, and `CROSS_CATEGORY_DEDUP` only collapses
categories within a single game.

**Calibration.** Those 28 settled NO bets went **18W-10L (64.3%)** against an **80.1%**
market-implied break-even -- **-12.6% ROI (-$6.28)**. Versus the market that is p=0.038
(marginal at n=28). Versus **the model's own claimed 89.7% fair value it is p=0.0003**.
Whether the bets are exactly -EV is not settled by 28 samples; that the model is wrong
about them is.

**Mechanism.** `consensus_total_prob` infers a mean total from the sportsbook line (~8.7
runs) and extrapolates to the Kalshi strike with a normal CDF at
`SPORT_TOTAL_STDEV["baseball_mlb"] = 3.45`. Strike 13 is **1.25 sigma** out, where the
answer comes from the stdev assumption rather than any book quote. There is a
**disagreement sweet spot**: near the line model and market agree, far out both approach
100% NO, and around 1.25 sigma the model says 89% NO against the market's 80%. Every MLB
game lists a strike in that window, so every game emits one near-identical NO bet. **R28's
global NO floor is 8% while the phantom edge averages 9.6%** -- the gate built to stop bad
NO bets sits just under the bias.

**Ruled out:** skew. The intuitive story (normal CDF understates a right-skewed tail) is
wrong here -- a negative binomial with the same mean and variance gives a *lower* P(>13)
(9.0% vs 10.6%), which would raise the model's NO fair value, not lower it.

**Most likely driver: adverse selection.** The model bets the games where its own noisy
inferred mean sits lowest relative to the strike, selecting the cases where that estimate
is most wrong -- the same winner's-curse pattern C4 found for high confidence and C11 found
for sub-40c prices.

**Relation to C11b.** That investigation measured *correlation* among the "four MLB unders
on one night" slate and correctly found none (totals rho -0.187, p=0.75). It never asked
why there were four. This is the answer: not a correlation problem, a generation problem.
C11b's conclusion stands; its question was the wrong one.

Opened as **T1** (concentration + calibration) and **T2** (the strike-boundary hypothesis).

### T2 verified same day -- no bug, hypothesis was wrong

T2 proposed that Kalshi's strike-13 market resolves YES on "13 or more" while the model
computes `P(> 13)` -- a 3.1-point systematic error toward NO on every totals bet in every
sport. Checked against the live Kalshi API for all 28 logged markets. It is wrong on every
count:

- **The ticker suffix is not the strike.** `KXMLBTOTAL-...MINCLE-13` carries
  `floor_strike: 12.5`; the suffix is a market index.
- `extract_strike()` reads **`floor_strike` first** (`edge_detector.py:1214`), so the model
  uses 12.5, not 13.
- Kalshi's `rules_primary` ("more than 12.5 runs ... resolves to Yes") and
  `strike_type: greater` match the model's `1 - norm.cdf(12.5)` exactly.
- `floor_strike` is a **half-integer on 28/28** markets, so no integer run total can tie the
  strike and the `>=` vs `>` distinction is mathematically moot regardless.

Recorded because the negative result is load-bearing: the cheap single-line explanation is
eliminated, so T1's cause lies in the model or in bet generation.

### The concentration is worse than first reported

The "27% of the book" figure understated it. MLB totals did not exist in the book until
**2026-07-20**, when the MLB spread/total coverage gap was closed. Before that date: 70
trades, **0** MLB totals. On and after: 45 trades, **31** MLB totals -- **69% of everything
bet since the coverage landed**. Within 11 days one bet shape took over two-thirds of all
betting.

### Caveats

All 28 bets sit in a single 11-day window, so this is not a broad sample and late-July
scoring is a real confound. Two checks against that: losses are not concentrated in one bad
day (1 of 11 days had zero wins, n=1), and treating each *day* as the unit gives a 66.5%
mean win rate against the per-bet 64.3% -- so the result is not an artifact of a few
heavily-bet days. The time trend is the useful cut: **first 5 days 11W-1L (+6.7% ROI),
after that 7W-9L (-18.3%)**. An early hot streak masked the shape for a week, which is
itself a caution against reading the opening days of any newly-covered market as
validation.

Also documented **PM2e**: the post-C10/C10b risk posture. The bugs themselves cost almost
nothing (0 Polymarket trades, 0 prediction bets, 0 trades over `MAX_BET_SIZE`, 0 NBA/NCAAB
bets in the band the stale Cloud config would have admitted), but the *fixes* made Gate 4
reachable on futures and games for the first time, on surfaces with zero settled trades,
while the venue is armed and executing unattended. T1 is the cautionary precedent for what
happens when a composite lets a new bet shape through at scale.

No code changed in this entry -- findings and roadmap only.

---

## 2026-07-31 -- C10b: the games composite had the same unreachable Gate 4

C10 (2026-07-23) diagnosed the futures composite scaling edge as `min(10, edge * 20)` --
saturating at a 50% edge instead of the sports composite's 10% -- and traced it to a
copy-paste from the `liquidity` line above it on the launch-day commit. It fixed
`scripts/kalshi/futures_edge.py` and `scripts/polymarket/polymarket_futures_edge.py`.

It missed `scripts/polymarket/polymarket_games_edge.py`. That file was written on
2026-07-20, three days before C10, and had copied `edge * 20` from the Polymarket futures
file -- which had itself copied it from its own `liquidity` line. A copy of a copy of the
same bug, so it carried no independent rationale either.

### Same disease, independently confirmed on this surface

Clearing `MIN_COMPOSITE_SCORE=6.0` required roughly **15% edge at high confidence, 26% at
medium, 38% at low**, against Polymarket game edges that run **1-7%** in practice.

The evidence log settles it: across **362 logged Gamma game rows**, not one ever reached
composite 6.0. The maximum observed was **5.30**. Gate 4 was structurally unreachable
here exactly as it was for futures -- 330 of those rows were stopped earlier at Gate 3
(edge) and 32 reached Gate 4 only to die on `score`.

### Not a floodgate

Replayed through the shipped code over those same 362 rows: only **5 (1.4%)** newly clear
Gate 4, all marginally (composite 6.02-6.26), and each still faces gates 3.5 (price), 4.5
(confidence), 4.6b (NO floor), 5, 6, and 7. The 330 edge-gated rows are unaffected --
they never reach Gate 4 at all.

**No live behavior changes.** Gamma-sourced game rows carry no US `market_slug`, so they
are auto-excluded from execution and remain dry-run evidence only. This matters for the
seasonal US games repoint on the roadmap: without it, that surface would have inherited
the same arithmetically-unreachable gate a third time.

### Two divergences kept deliberately

- **Liquidity stays `book_spread * 100`** (vs `spread * 20` on the Kalshi paths). Rows
  wider than `MAX_BOOK_SPREAD = 0.10` are already dropped upstream, so `* 20` would
  compress every surviving row into 9.8-10.0 and the term would carry no information.
  `* 100` spreads the admissible 0-0.10 band across the full 0-10 range. This does make
  games and futures composites non-comparable when they are merged and ranked together,
  but it errs strict and is the better-calibrated of the two -- not worth loosening a
  second term in the same change.
- **`high: 9` stays uncapped**, on C10's own precedent. C4 capped high->medium for
  *Kalshi sports* on 306 settled bets (F49) and explicitly scoped everything else out;
  there is still no settled Polymarket data. Worth revisiting when PM3 settlement lands
  -- this path prices against the same Odds API consensus as sports, so C4's *reasoning*
  plausibly transfers even though its evidence does not.

+4 tests (677), including a cross-surface parity check against the sports composite,
scoped to medium confidence so it does not silently encode the `high` decision above.

### C10c -- the same scale survives in all 7 prediction scanners (logged, not fixed)

The propagation sweep for this change grepped the repo for the old form and found
`edge_score = min(10, edge * 20)` still in `companies_edge.py:167`, `crypto_edge.py:227`,
`mentions_edge.py:201` and `:269`, `politics_edge.py:140`, `spx_edge.py:200`, and
`weather_edge.py:255`. Three families of this bug have now been found: futures (C10),
games (C10b), and prediction (C10c).

**No live impact today** -- Gate 4.7 (`ALLOW_PREDICTION_BETS=false`, R25) rejects every
prediction category before the composite matters, so it is latent rather than active.

Deliberately **not** fixed here: seven modules, zero settled prediction bets to replay
against, and the prediction models are already flagged as surfacing garbage fair values
(R25, F34-F39). Loosening their gate before the model rebuild would be fixing the wrong
layer first. Logged as **C10c** in ROADMAP Priority 2, to be done as part of the
prediction rebuild (R25b/R25c) and replayed against evidence the way C10 and C10b each
were. If `ALLOW_PREDICTION_BETS` is ever flipped before that, this becomes active and
must be fixed first.

### Propagation

`docs/ROADMAP.md` (C10b in the Priority 0 dry-run blockquote; new **PM2d** dashboard row;
**A10**/**A11** under Web App Evolution; **C10c** in Priority 2; a 2026-07-31 Completed
entry), `CLAUDE.md` (C10b note, dashboard row, views list, test count),
`docs/polymarket/README.md`, `docs/polymarket/polymarket-games-betting/GAMES_GUIDE.md`
(new "Composite scoring" section with the full formula),
`docs/setup/polymarket-us-setup.md`, `docs/setup/ARCHITECTURE.md`, `README.md`,
`skills/edge-radar/SKILL.md` (5 pages, not 3).

One ROADMAP nuance worth recording: **PM2d supersedes Q1** (2026-04-22), which *removed*
a Polymarket market type from the webapp. That removal was correct at the time -- it was a
UI-only stub that never reached the service layer. This one does.

---

## 2026-07-31 -- Streamlit dashboard: Polymarket venue, Config page, env-registry fix

The dashboard had drifted well behind the CLI. It exposed three market types while
`scan.py` had four, its risk-gate help text still described gate values from April, and
its Streamlit-secrets bootstrap listed ~20 fewer knobs than `app/config.py` reads. This
brings it level and adds the Polymarket venue.

### The env-var registry was the real bug

`webapp/services.py` carried a hand-maintained `_flat_keys` list naming which flat TOML
keys to lift from `st.secrets` into `os.environ`. It has to exist -- the lift must happen
*before* any script import caches config, so it cannot introspect `app.config` -- but it
was last extended in April. Everything added since was absent: the R28 NO-side globals,
both L1 live-bet gates, `MIN_CONSENSUS_BOOKS_NBA`, `CALIBRATION_STDEVS_TTL_DAYS`,
`CROSS_CATEGORY_DEDUP` (global and per-sport), both cache groups (R24b/R26), and every
Polymarket credential.

The failure mode is silent and specific to Cloud: set one of those in **Settings ->
Secrets** and nothing reads it, with no error -- the app runs on the code default while
the secret sits there looking authoritative. Local `.env` deployments were unaffected
(`python-dotenv` loads the file wholesale), which is why it went unnoticed.

Replaced with `ENV_VAR_SPEC`, one registry serving three consumers: the secrets bootstrap,
the new Config page, and anyone reading the file. `tests/test_webapp_env_registry.py`
parses `app/config.py` for every `_bool`/`_float`/`_int`/`_str`/`_list` name plus the
f-string per-sport expansions and fails if the two diverge in either direction. Writing
that test immediately surfaced nine more undocumented vars (`KALSHI_PROD_*`, `ALPACA_*`,
`TELEGRAM_*`, `PROJECT_ROOT`) -- the same gap the 2026-07-14 repo review flagged against
`.env.example`, which is now closed there too.

### Polymarket as a first-class venue

Market type `polymarket` routes the scan through `_route_filter` -- the CLI's own filter
router, imported rather than reimplemented, so the dashboard and `scan.py polymarket
--filter X` cannot disagree about which surfaces a filter covers -- and switches the
execution client to `PolymarketClient` via the `get_market_client` factory.

Three venue asymmetries needed explicit handling rather than reuse:

- **Two-flag dry run.** Orders require BOTH `DRY_RUN=false` and `POLYMARKET_DRY_RUN=false`.
  The banner and confirm dialog resolve the live state through the same logic as
  `polymarket_futures_edge._order_mode` instead of assuming `DRY_RUN` alone, so a
  Polymarket-armed account cannot show a "DRY RUN" dialog.
- **Only futures are orderable.** Gamma-sourced game rows carry no US `market_slug`. They
  now show `Exec = -` in the results table, are excluded before `execute_pipeline`
  (matching the CLI), and the confirm dialog counts only orderable rows -- selecting five
  game rows previously would have said "up to 5" and sent zero.
- **Different position shape.** Polymarket money fields are Amount objects
  (`{"value": "4.98", "currency": "USD"}`) and `market_exposure_dollars` is cost basis,
  not market value. Run through the Kalshi formatter this printed `$0.00` unrealized on
  every row; a separate formatter reads `cashValue` for mark-to-market and reconciles to
  the Portfolio Value tile. Portfolio is now Kalshi/Polymarket tabs -- but the daily-loss
  bar is deliberately shared and labelled as such, because Gate 1 reads the common trade
  log.

### Config page

New read-only page: execution mode per venue, then every variable with its live value,
its source (`set` / `default` / `unset`), group, and rationale. Credentials render as a
character count only. Exports a `.env` template with live values and secrets blanked.

This is the direct answer to "is the app actually running my config?" -- previously
unanswerable from the UI, and genuinely ambiguous because `kalshi_executor` snapshots
gates at import time.

### Smaller corrections

- **Gate column added** to scan results. The Min Edge help text had promised "Each scan
  row's Gate column previews which gate will reject it" since April; there was no such
  column. It now runs the same `preflight_gate_status` the CLI preview uses.
- **Help text resynced** -- it still cited a `$0.06` price floor (live value `0.10`) and
  omitted gates 4.6b, 4.8, and the C10/C11b changes.
- **Budget % is no longer sports-only.** The cap is venue- and type-neutral and the
  schedulers pass `--budget` on futures and Polymarket runs, so hiding the control made
  a dashboard futures run the one path with no batch cap at all.
- Settle page states Kalshi-only scope (PM3 pending) and shows a Venue column.
- `DEFAULT_UNIT_SIZE`, Max Bets, and Exclude Open defaults matched to the live `.env`.

Docs: `docs/web-app/LOCAL.md` (Polymarket mode, Config page, per-venue Portfolio, new
columns), `docs/web-app/CLOUD.md` (secrets template rebuilt -- it was missing every knob
added since April, plus the `[polymarket]` block), `.env.example` (the nine undocumented
vars). 673 tests pass.

---

## 2026-07-27 -- Working branch moved from `mike_win-desktop` to `mike_desktop`

Every other repo under `Repos/Live_Apps` (Agent-Chat, edge-spectrum, my-prompt-library,
taskhub) uses `mike_desktop` as the working branch. Edge-Radar was the lone exception on
`mike_win-desktop`. It is now aligned.

The switch was clean, not a migration: `mike_win-desktop` had **0 commits** not already in
`origin/master` (PR #243 merged the last of them), and the operator deleted and re-created
`origin/mike_desktop` from `master`, so `origin/mike_desktop == origin/master == c23b3c7`.
The only working-tree change -- the weekly account-graph HTML refresh -- was already
byte-identical to the copy on `master`, so nothing had to be carried across.

Local state after the move: `mike_desktop` checked out and tracking `origin/mike_desktop`;
local `master` fast-forwarded to `origin/master`. The `git sync-master` alias
(`git fetch origin && git branch -f master origin/master`) is unaffected -- it only ever
touched `master`.

Docs updated: the `CLAUDE.md` session-startup checklist (now carries an explicit **working
branch: `mike_desktop`, deploy branch: `master`** callout, matching the sibling repos),
`docs/task-schedules/README.md` (account-graph `gh`-push rationale), and
`docs/my-documents/account-graph/README.md`. Historical references in this changelog, in
`docs/my-documents/repo-reviews/2026-07-14-repo-review.md`, and in
`docs/my-documents/temp/archive/streamlit_deployment.md` were **left as-is** -- they record
what the branch was at the time and rewriting them would falsify the record.

Nothing in code, tests, schedulers, `Makefile`, or `.github/workflows/` referenced the branch
name (`deploy.yml` watches `master` only), so no automation changed. `origin/mike_win-desktop`
still exists as a safety net and can be deleted once the new setup has been exercised.

---

## 2026-07-27 -- C11b: correlation guard measured and dropped; budget cap made floor-aware

### The correlation guard does not survive measurement

C11 left "add a correlation guard for same-night/same-league/same-direction slates" as the
open follow-up. Measuring it first killed the premise.

The naive read is convincing: pairwise concordance within clusters is 0.591 against 0.501
expected, **rho +0.181, permutation p = 0.0018**. That is Simpson's paradox. Clusters live
inside strata with very different base rates -- totals win 82% of the time, spreads 24% --
and pooling unequal-mean groups manufactures apparent within-group concordance.

Judging each cluster against its own (series, type, side) base rate, with a permutation test
that shuffles *within* stratum:

| slice   | clusters | bets | pooled rho | stratified rho | perm p |
|:--------|:---------|:-----|:-----------|:---------------|:-------|
| ALL     | 80       | 243  | +0.181     | **+0.048**     | 0.036  |
| totals  | 11       | 28   | -0.010     | **-0.187**     | 0.75   |
| spreads | 18       | 42   | -0.067     | -0.111         | 0.69   |
| game    | 12       | 35   | +0.054     | +0.027         | 0.26   |

Totals -- the four-MLB-unders case that motivated the idea -- show nothing. Even at the
aggregate +0.048, four bets behave like ~3.8 independent ones, which no sizing mechanism
needs to model. **No guard was built.** Added `scripts/backtest/correlation_check.py`, which
reports both figures side by side so the artifact stays visible; re-run as settlements
accumulate, since 28 clustered totals bets cannot detect a small rho.

### Correction to C11

The "32% of bankroll" figure used to justify `KELLY_FRACTION=0.5` was computed from
`size_order` in isolation and ignored `--budget`, which every scheduler passes (12% sports,
10% futures/Polymarket) and which proportionally scales the entire batch. Real blast radius
was already bounded at ~$11.03. The 0.5 value stands on its own merits -- full portfolio
Kelly is too aggressive -- but not for the reason originally given.

### Regression found and fixed

Because the budget is a **fixed pool**, C11's correctly-sized favorites crowd everything
else out. On the 07-27 slate the 18c MLS leg fell from 6 contracts ($1.08) to 2 ($0.36) --
about a third of its intended size -- which would have quietly starved the
`MIN_MARKET_PRICE=0.10` longshot experiment rather than testing it.

`_apply_budget_cap` now:

- **never shaves an order below its flat unit floor** `round(unit_size / price)`. That floor
  encodes "if we are betting this at all, bet at least `unit_size`"; the proportional pass
  was silently overriding it.
- **bisects for the largest feasible scale** instead of taking a single proportional pass,
  so it packs the budget properly ($10.89 of $11.03 on the 07-27 slate, vs $9.36 before).
- **drops whole orders -- lowest composite first -- only when the floors alone cannot fit.**
  An earlier draft clamped first and dropped on any overage, which deleted a whole position
  to reclaim $0.23. Shaving legs that still sit above their floor always comes first.
- never scales an order *up*: the floor is clamped to the order's own count, which the
  `MAX_BET_SIZE` / bankroll caps may already have pushed below `unit_size_contracts`.

`unit_size=None` restores the pre-C11b pure-proportional behaviour.

### Scheduler override

The `.bat` files passed `--unit-size .5` explicitly, which **overrode the `.env`
`UNIT_SIZE=1.00`** set in C11 for every automated run -- so the longshot protection never
reached automation at all. All 16 now pass `--unit-size 1`. (These live under
`scripts/schedulers/`, which is gitignored by design.)

Net effect on the 07-27 slate: longshot leg back to **6 contracts**, batch $10.89 of the
$11.03 budget, nothing dropped.

### Tests

New `TestBudgetCapUnitFloor` (8 cases): under-budget passthrough, floor honored under
pressure, the pre-C11b behaviour still reproducible via `unit_size=None`, drop-lowest-
composite when floors do not fit, never-scale-up, single-order honors budget over floor,
always-within-budget across five budget levels, empty input. Full suite **667 passed**.

### Docs propagated

Swept the repo for both the old and new forms of every touched value/flag, then updated:

- **`.env.example`** -- `KELLY_FRACTION` and `UNIT_SIZE` rationale blocks: which knob moves
  which lane, the portfolio-fraction caveat, the `f* = edge / (1 - price)` formula, and a
  warning that scheduler `.bat` files pass `--unit-size` explicitly so CLI beats `.env`.
- **`CLAUDE.md`** -- C11 + C11b notes, live-`.env` block, `--unit-size` example, test count.
- **`docs/ROADMAP.md`** -- C11 + C11b as shipped rows in Priority 2, new Completed index
  entry, `Last updated` bumped to 2026-07-27.
- **`docs/setup/ARCHITECTURE.md`** -- budget-cap section rewritten for the floor-aware /
  bisecting / drop-only-when-floors-do-not-fit behaviour.
- **`docs/scripts/SCRIPTS_REFERENCE.md`** -- registered `backtest/correlation_check.py` with
  usage, flags, and a callout to read the stratified rho rather than the pooled one.
- **`docs/scripts/per-script/kalshi_executor.md`** -- sizing formula corrected to include
  `/ (1 - market_price)`, plus the which-knob-moves-what and portfolio-fraction notes.
- **`docs/task-schedules/README.md`** -- documented scheduler flags now `--unit-size 1`.
- **`skills/edge-radar/SKILL.md`** -- sizing formula, budget-cap description (both the flag
  table and the risk-limits section), live `KELLY_FRACTION`/`UNIT_SIZE`/`MAX_BET_SIZE`
  values, `--unit-size` examples, test count.
- **`skills/edge-radar-analysis/SKILL.md`** -- `correlation_check.py` added to Related with
  the Simpson's-paradox caveat and a re-run trigger.
- **`webapp/views/scan_page.py`** -- `DEFAULT_UNIT_SIZE` 0.50 -> 1.00 to match live config.
- **`.claude/html/index.html`** -- "1/4-Kelly" -> "fractional Kelly" (live value is 0.5).
- **Memory** -- new `project-scheduler-flags-override-env` (CLI flags beat `.env`; simulate
  the full `size_order` -> ratio cap -> budget cap chain), and
  `project-longshot-kelly-experiment` rewritten now that `KELLY_FRACTION` is no longer part
  of that experiment.

Historical references to the old values in `docs/CHANGELOG.md` and the ROADMAP's Findings /
Completed sections were left intact as record.

---

## 2026-07-27 -- C11: Kelly was missing the (1 - price) divisor

### The bug

`size_order()` in `scripts/kalshi/kalshi_executor.py` sized off `kelly_fraction * edge *
bankroll`. Kelly for a binary contract is `f* = (q - p) / (1 - p)` = `edge / (1 - price)`;
the `/ (1 - price)` term was absent. That is the even-money (`b=1`) approximation -- exact
only at 50c, and increasingly wrong toward either extreme.

Favorites were under-sized by `1/(1-p)`: **2.5x at 60c, 5.0x at 80c, 5.9x at 83c**. Because
the flat `UNIT_SIZE` floor then won at high prices, nearly every bet above ~60c collapsed to
a single contract. Mean contracts by entry price: sub-40c **5.56**, 40-60c **1.83**, 60c+
**1.17**.

### Why it mattered

The starved segment is the best-calibrated one in the book. Over 367 settled trades,
realized win rate *over break-even*:

| band   | n   | avg px | model fair | real WR | break-even | WR - BE | overclaim |
|:-------|:----|:-------|:-----------|:--------|:-----------|:--------|:----------|
| <40c   | 149 | 0.211  | 0.410      | 0.255   | 0.221      | +0.034  | **+0.155** |
| 40-60c | 166 | 0.494  | 0.628      | 0.542   | 0.504      | +0.039  | +0.086    |
| >=60c  | 52  | 0.726  | 0.817      | 0.846   | 0.736      | **+0.111** | -0.029 |

60c+ is 44/52 against a 73.6% break-even -- one-sided binomial **p=0.044**, the only price
band distinguishable from noise. Model calibration inverts with price: a 15.5-point
overclaim below 40c versus *conservative* by 2.9 points at 60c+. Last 30 days: 60c+
**+4.7% ROI** vs sub-60c **-48.3%**. Re-sized over the settled history, the 60c+ segment
goes **+$10.02 -> +$47.52 at the same ROI**.

### Shipped

- `kalshi_executor.py` -- divide the Kelly bet by `max(0.01, 1 - market_price)`. Single
  sizing site; Polymarket shares it via `size_order`.
- `.env` `KELLY_FRACTION` **1 -> 0.5**. The executor divides this by `batch_size`, which
  doubles as a crude correlation guard -- so it is a *portfolio* Kelly fraction. At 1.0 a
  fully correlated slate reaches full Kelly: the 07-27 slate of four MLB unders would have
  been $29.43, **32% of bankroll and ~98% of `MAX_DAILY_LOSS` in one evening**. At 0.5 the
  same slate is $16.35 (17.8%), verified live.
- `.env` `UNIT_SIZE` **.50 -> 1.00**. Longshots bind on the flat floor, not Kelly, so
  lowering `KELLY_FRACTION` alone would have cut sub-30c sizing **39%** ($6.15 -> $3.76).
  This holds the lane at its prior size ($6.15 -> $7.10). **`UNIT_SIZE` is the longshot
  knob; `KELLY_FRACTION` is the favorites knob** -- they bind at different prices and are
  independently tunable. `KELLY_FRACTION=1` was set on 07-22 to size longshots up, which
  was the wrong knob.
- `.env` `MAX_BET_SIZE` **15 -> 8**, backstop only. Nothing recent reaches it (largest
  projected position 5.6% of bankroll), but at ~$92 bankroll $15 is 16.3% on one position,
  breaching the CLAUDE.md 10% hard stop -- a cap that was unreachable while Kelly was broken.
- `MIN_MARKET_PRICE` (Gate 3.5) untouched -- a reject threshold, independent of sizing. The
  07-22 longshot experiment continues unaffected.

### Tests

New `TestKellyPriceComplement` (7 cases): dollars-at-risk scale as `1/(1-p)`, 50c reference
point, favorites no longer collapse to the flat unit, longshots barely move, no divide-by-
zero at 99c, and R1/R28 NO-side damping still composes. Full suite **659 passed**.

Also added a shared `sizing_defaults` fixture and applied it to the five gate-test classes
that assert a bare `"APPROVED"`. Those read `MAX_BET_SIZE`/`KELLY_FRACTION` from the live
`.env` at import time, so lowering `MAX_BET_SIZE` flipped twelve unrelated gate tests to
`APPROVED_CAPPED_MAX_BET`. Same class of breakage hit the venue-min-shares tests on 07-22.

### Still open

A real correlation guard for same-night / same-league / same-threshold slates. Dividing by
`batch_size` is only a proxy -- it assumes every leg in a batch is perfectly correlated,
which over-damps independent slates and under-damps ones like tonight's four MLB unders.

---

## 2026-07-25 -- Polymarket task audit: portfolio value was always $0.00

### Audit result

Reviewed the 07-24 and 07-25 `Daily-Polymarket-Execution` runs and their paired emails.
**Both tasks ran clean, exit 0, zero orders placed.** Every executable row died at Gate 3
(edge < 3%): 07-24 rejected `PM-tec-nhl-champ-...-was` (1.3%) and `...-nj` (1.1%); 07-25
rejected the same Capitals row. The paired emails sent successfully both days.

Two structural observations from the run logs:

- **The C10 composite fix is still unexercised.** Making Gate 4 reachable changed nothing,
  because nothing survives Gate 3 to reach it. Consistent with what C10 predicted, but it
  means the fix has no live validation yet.
- **The executable funnel is collapsing: 4 -> 2 -> 1** across 07-23/24/25. Today the whole
  venue produced one orderable candidate -- a $0.04 NHL futures longshot that would also
  fail Gate 3.5 (`MIN_MARKET_PRICE=0.10`) even if its edge tripled. Until the seasonal US
  games repoint lands, this task realistically cannot fill an order; 39 of today's 40 rows
  were Gamma-sourced games, auto-excluded from execution.

### Bug: Polymarket portfolio value always reported $0.00

`polymarket_exec_client.py:167` summed `p["currentValue"]`, but the US Portfolio API names
the mark-to-market field **`cashValue`**. The key is simply absent, so the best-effort
`except` never fired and the sum silently returned zero against real open exposure. Live
account: **$0.00 -> $11.03**. Fixed, `currentValue` kept as a fallback, regression tests
added for both paths.

### Polymarket zero-fill claim corrected

`CLAUDE.md` claimed "No Polymarket order has filled yet." The account holds **two open
positions** in `tec-mlb-champ-2026-09-27` (MIL 59 sh, NYY 36 sh, ~$9.88 cost, $10.99
value). They are **not system trades** -- `kalshi_trades.json` has 0 Polymarket-tagged rows
out of 90, and both carry `updateTime: 2026-07-06` -- they were hand-placed in the iOS app.
But they *are* visible to the risk gates: they are the `Positions: 2/50` line in the scan
banner and they occupy Gate 5 / Gate 6 slots for those two markets. Claim rescoped to
Edge-Radar-placed orders, with the hand-placed pair documented.

### `Email-Polymarket-DryRun` renamed to `Email-Polymarket-Execution`

The scan stopped being a dry run on 2026-07-23, but the email still announced itself as a
"Daily Polymarket Dry-Run Report" while the paired task placed live orders. The 07-23
rename deferred this as cosmetic; it wasn't -- **the prompt never asked whether an order
had been placed**, so the one fact that matters most on an execute-enabled venue was the
one the email was never required to report. The prompt now mandates an **Execution
Outcome** section led by whether an order filled (ticker/side/qty/cost when it did).

Two further prompt guards: the agent is told not to call the run a dry run, and told that
the Summary table's `total` row is a **bet-type count** (over/under), not a sum -- it had
reported that as an "internal inconsistency" in the 07-24 and 07-25 emails, which was a
misread of `report_writer.py:78` (categories sorted by count, so `total` lands first).

Task re-registered preserving the daily 10:00 AM trigger, principal and settings; old task
unregistered and `Polymarket-DryRun-Report.sh` deleted, so exactly one task and one script
remain. Log paths keep their `dryrun` filenames on purpose -- append-only history from the
dry-run window, and the scan `.bat` still writes to them.

### Test suite: `TestVenueMinShares` un-coupled from live `.env`

Two cases had been failing since 2026-07-22 (`assert 4 == 2` on `contracts`). They pass
`unit_size=1.00` but never pinned `KELLY_FRACTION`, which is a `kalshi_executor` module
global sourced from the operator's `.env` -- when it went `0.25 -> 1`, Kelly started
clearing the flat unit floor those cases assume. Pinned to the code default via an autouse
fixture; the class tests venue min-share bumps, not Kelly sizing. **Full suite: 653 passed.**

> **Wider risk:** `kalshi_executor` snapshots every gate threshold into module globals at
> import, so any test calling `size_order` without pinning them inherits operator config.
> Nothing else fails today, but the longshot experiment is open -- if `MIN_MARKET_PRICE` or
> the Kelly fraction moves again and tests break in a way that looks unrelated, start here.

### Note: live automation is intentionally untracked

`scripts/custom/` and `scripts/schedulers/*` are gitignored **by design** -- they are the
operator's personal files and stay out of the repo (operator-confirmed 2026-07-25). So the
header-comment corrections made today to `daily_polymarket_scan.bat` and the new
`Polymarket-Execution-Report.sh` are local-only and by design absent from these commits.
**Do not propose tracking them.** When editing task wiring, expect the change to live on
this machine only, and record the *behaviour* here in docs rather than the script itself.

---

## 2026-07-23 -- Wager-quality audit: config intent recorded, skills resynced

### Audit result

Reviewed every wager placed since 2026-07-20 (15 trades) and the last four days of
scheduled runs. **No misconfigured or erroneous wagers.** All 12 daily tasks exited 0;
`doctor.py` clean. Every trade carried `risk_approval: APPROVED`, `fill_status: filled`,
and a correct venue tag, and each mapped to the right scheduled task by timestamp. All
8 NO-side bets cleared the R28 8% global floor (0.081-0.149); all composites >= 6.0; no
prediction-category or in-progress-game leakage. Settled P&L since 07-15: 10W-4L,
$10.96 staked, **+$3.71 / +33.9% ROI**.

### Config intent recorded

Two `.env` changes made 2026-07-22 read as drift because the surrounding comments still
described the prior values. Both are deliberate; documented as such in `.env`, `CLAUDE.md`,
and the `/edge-radar` skill:

- **`KELLY_FRACTION` 0.25 -> 1**, to size longshots up. Worth stating precisely, because
  the name misleads: `kalshi_executor.py:785` divides it by
  `batch_size = min(len(opportunities), --max-bets)`, and every scheduler passes
  `--max-bets 5`, so the effective multiplier is **0.20 Kelly**, not 1.0 (previously 0.05).
  The practical effect is that low-priced legs now size off Kelly instead of falling back
  to the `UNIT_SIZE` flat floor -- 11c spread legs at 6-11 contracts where they were 4.
- **`MIN_MARKET_PRICE` 0.12 -> 0.10**, deliberately re-opening the longshot lane that R7
  closed on 2026-07-14.

**The longshot evidence is weaker than the headline suggests.** Sub-15c is 6W-47L over 53
settled bets at +47.5% ROI -- but **99% of that P&L is one trade**
(`KXMLSSPREAD-26MAY16SEALAG-LAG1`, +$20.59). Ex that bet the lane is roughly breakeven,
and it is -100% in June / -33% in July. Separately, the 15-25c bucket is the *worst* on the
board at -19.2%, so R7's original "lottery-ticket floor" premise is itself weakly supported.
Flagged as an open experiment in both `.env` and `CLAUDE.md`; recheck after ~30 more
sub-15c settles.

- **`--budget 12%` on all three intraday executes is intentional** (operator-confirmed).
  Stale `.bat` headers described a de-escalating 12% -> 8% -> 5% ladder that was never
  implemented and is not wanted. Headers corrected to match the flags, with an explicit
  "do not restore the ladder" note in `same_day_execute_late.bat`,
  `no_date_filter_execution_midday.bat`, and the skill.

### Polymarket status corrected

`CLAUDE.md` still claimed orders stay `dry_run_blocked` while the venue accumulated
dry-run evidence. Both `DRY_RUN` and `POLYMARKET_DRY_RUN` have been false since
2026-07-23 and `Daily-Polymarket-Execution` passes `--execute`, so **the venue is live**.
Nothing has filled -- every candidate is still stopped at Gate 3 (observed edges 1.1-2.6%
vs the 3% floor) -- and `--max-bets 2 --budget 10%` bounds exposure, but the doc read as
though a safety flag was engaged that isn't.

### Skills resynced (91 commits of drift)

`/edge-radar` and `/edge-radar-analysis` were last touched at `9b2cff1` (L1 Phase 1).
Everything since was invisible to them, most importantly **the entire Polymarket venue**:
no `polymarket` market type, no `poly`/`pm` aliases, none of the 11 filter values. Also
added or corrected:

- Five undocumented risk-gate changes -- R28 (4.6b), L1 (4.8) and its staleness knobs,
  R29, C4, C10, C8. Gate count 13 -> 15, plus the R18 Gate-column legend.
- `MIN_MARKET_PRICE` was documented as **$0.06**, its April value, two moves stale.
- A warning that the live `.env` overrides many shipped defaults (`MAX_DAILY_LOSS` is $30,
  not $250), pointing at `make doctor` for ground truth.
- Live registered task schedule replacing the stale installer-profile table; MLB
  spread/total; tennis/Wimbledon/World Cup filters; v1->v2 order-endpoint migration; M2
  trade-log lock; `scripts/schedulers/*` being gitignored.
- Test count 347 -> 651; Makefile 18 -> 22 targets.
- `/edge-radar-analysis`: settler is **hourly at :35** (U1) plus the 11 PM backstop, not
  nightly-only -- worst-case staleness ~1h, not ~24h. Pre-R5 legacy-schema orphans
  178 -> 190 of 354. Scope note that settlements carry no `venue` field and Polymarket has
  never filled, so the report is Kalshi-only. New rule: report any slice under ~50 bets
  with *and without* its top winner.

### Open items (not fixed -- no code changed this session)

- **Trade-log orphans.** Six `status: "error"` World Cup records from the 2026-06-20 v1->v2
  410 outage (four were successfully re-placed 06-22) and two zero-fill `resting` orders
  whose markets have since closed sit in `kalshi_trades.json` as permanently "open."
  Harmless to gating -- Gate 5 reads live Kalshi positions, which correctly showed 2/50 --
  but they inflate any log-derived exposure count and pollute backtests.
- **The pytest suite writes into production `logs/`.** All 64 lines of
  `kalshi_executor_2026-07-23.log` are test fixtures (`KXMLB-TEST`, "Kalshi API 500: API
  down"); the day's real runs logged nothing there. A genuine executor failure would be
  indistinguishable from this noise.
- **`R8-Review` and `U2-Review` have never run and never will** -- one-shot triggers with
  start boundaries in the past (2026-05-29, 2026-05-14), no repetition, blank NextRun.
  That is the cross-category and 2-week calibration feedback loop, dead since install.

Docs only; no behavior change.

---

## 2026-07-23 -- Futures composite unblocked (C10) + Polymarket evidence-log split

### What shipped

The Polymarket dry-run window was not converging: four days of scheduled evidence
(8 runs, 79 rows) produced **zero** gate-passing opportunities -- 73 rejected on
`edge`, 6 on `score`. The cause turned out not to be market conditions but **gate
arithmetic**.

The futures composite scaled edge as `min(10, edge * 20)` -- saturating at a **50%**
edge -- while the sports composite uses `min(edge / 0.01, 10)`, saturating at **10%**.
Identical weights and structure otherwise; one term **5x stricter**, with no recorded
rationale (launch-day commit `1d92f0f`, where the `* 20` appears copied from the
`liquidity` line directly above it).

Clearing `MIN_COMPOSITE_SCORE=6.0` therefore required roughly **11% edge at high
confidence / 23% medium / 34% low**, against championship-futures edges that run
**1-4%** in practice. Two consequences, both long-standing and previously unexplained:

- **0 futures bets across 85 settled Kalshi trades.**
- **Polymarket US was permanently unexecutable** -- futures are its only executable
  market type, so the PM2 "prove edge in dry-run, then flip `POLYMARKET_DRY_RUN`"
  gate could never terminate no matter how long it ran.

**Fix:** aligned both futures paths (`scripts/kalshi/futures_edge.py`,
`scripts/polymarket/polymarket_futures_edge.py`) to `min(edge / 0.01, 10)`. The bar
becomes ~2.1% / 4.4% / 6.6% at typical liquidity, so the composite gate binds in the
same region as the 3-4% `MIN_EDGE_THRESHOLD` floors instead of dominating them.

**Deliberately not a floodgate.** Replayed against the four days of live Polymarket
evidence, the new scale approves **none** of the 9 observed US candidates on its own --
each remains independently blocked by Gate 3 (edge floor), Gate 3.5 (price floor) or
Gate 4.5 (confidence). Live-verified on a real scan: NHL 4.36 -> 4.8, Spurs 3.57 -> 4.4,
all still correctly gated on `edge`.

The futures `high: 9` confidence weight was **left alone** -- C4 capped high->medium for
*sports* on the F49 evidence and explicitly scoped futures out; there is still no futures
settlement data to justify either choice.

### Also

- **Evidence-log split.** 66 of the 79 logged Polymarket rows were Gamma-sourced *games*
  carrying no US `market_slug` -- auto-excluded from execution, so the log read far busier
  than the 13-row tradable universe actually was. Runs now record `executable_count`, each
  row carries an `executable` flag, and the preview gained a `US` column (ASCII-only: the
  scan runs headless under Task Scheduler, where a cp1252 console raises
  `UnicodeEncodeError` on non-ASCII).

+6 tests (645), including cross-venue scoring parity between the Kalshi and Polymarket
futures composites.

### Polymarket documentation folder

Added `docs/polymarket/`, mirroring the `docs/kalshi/` layout, as the authoritative
record of the integration:

| File | Covers |
|:-----|:-------|
| `polymarket/README.md` | Hub -- coverage matrix (executable vs evidence-only), integration status PM0->PM3, dry-run evidence artifacts, common commands |
| `polymarket-futures-betting/FUTURES_GUIDE.md` | The only executable surface: question-grouping, whole-word matching, price reading, edge model, C10 composite |
| `polymarket-games-betting/GAMES_GUIDE.md` | Gamma per-game ML/spread/total, why it can't trade on US, the three guard rails |
| `polymarket-execution/EXECUTION_GUIDE.md` | Two-flag dry-run, pipeline flow, venue min shares, slug registry, position normalization, order mapping |
| `polymarket-api/POLYMARKET_API_REFERENCE.md` | Ed25519 scheme, endpoints, response shapes, and the three signing details that cost debugging time |

Navigation is wired both ways: `docs/README.md` gained a Polymarket section, the Kalshi
README links across to it as a sibling venue, `docs/setup/polymarket-us-setup.md` points up
into the domain folder (and is now scoped to key generation + `.env` wiring), and every new
page carries a footer nav back to its index. `CLAUDE.md`'s project tree lists the new folder.

### Scheduler changes (live money)

- **`Daily-Polymarket-DryRun` -> `Daily-Polymarket-Execution`.** The task now passes
  `--execute` with batch caps (`--max-bets 2 --budget 10%`), so the daily 9:40 AM run can
  place real unattended Polymarket wagers. Renamed because the old name asserted the
  opposite of what it does; re-registered from exported XML preserving trigger and
  principal, old task unregistered, re-validated (`LastTaskResult=0`, 4 opportunities
  risk-checked, **0 orders placed**). The evidence log still writes either way -- `--save`
  runs outside the execute branch. Only futures are orderable; Gamma games are
  auto-excluded. The paired `Email-Polymarket-DryRun` job keeps its name (it only emails
  the report).
- **`Weekly-Futures-Execution` disabled.** C10 made Kalshi futures clear Gate 4 for the
  first time, so Saturday's run would have been the first-ever live futures order through
  an unexercised path. Disabled pending a manual futures cycle in preview.

Note: the scheduler `.bat` files are gitignored (`.gitignore:87` -- they hardcode local
paths), so `docs/task-schedules/README.md` is the only tracked record of what the
automation actually runs.

### Known issue (pre-existing, unrelated)

`tests/test_risk_gates.py::TestVenueMinShares` has 2 failures that reproduce on a clean
checkout: the tests read the operator's live `.env` at import time and assume the
documented `KELLY_FRACTION=0.25` while `.env` carries `1`. Test-isolation defect, not a
sizing bug.

---

## 2026-07-20 -- MLB spreads + totals wired (KXMLBSPREAD/KXMLBTOTAL coverage gap)

### What shipped

A "not much coming through" health check found `KXMLBSPREAD` and `KXMLBTOTAL` live on
Kalshi with open markets but never scanned — MLB ran **moneyline-only all season**. The
series launched after MLB was first wired (March 2026); every other major sport already
scanned all three market types, and the R2-calibrated baseball stdevs were in place.

- Fix: three map entries in `edge_detector.py` (`FILTER_SHORTCUTS["mlb"]`, `CATEGORY_MAP`,
  `KALSHI_TO_ODDS_SPORT`). Everything downstream (spread/total detectors, stdev lookup via
  the `KXMLB` prefix, bracket dedup, series dedup, ticker display) is prefix-generic.
- Live market shapes verified: bracket-style, line in `floor_strike` (e.g.
  `KXMLBSPREAD-...-SEA9` = "Seattle wins by over 8.5 runs", `KXMLBTOTAL-...-9` =
  "Over 8.5 runs").
- First scan: MLB 106 → **407 markets** (103 spreads + 176 totals); 7 gate-`ok` rows at
  +8–12% claimed edge on the next slate — all deep-bracket **Unders** (high-line NO-side
  favorites). ⚠️ This is an **uncalibrated sub-population**: the normal-CDF total model may
  overstate Under probability against MLB's right-skewed run distribution (fat blowout
  tail; a Coors Field Under 17.5 is in the first batch). Existing guards apply (R28 NO-side
  8% floor, correlated-bracket dedup, per-event cap, $1 units). Posture: bet small via the
  normal automation and review the first settlements — the 06-29 soccer-spread precedent
  (always-YES lean proved real) cuts either way.

**+5 tests (640 total).** Health check otherwise clean: all 22 scheduled tasks exit 0,
Odds API quota 3,919 remaining, MLS/MLB data pulls verified, hourly settle running.

---

## 2026-07-20 -- PM2c: Polymarket execution pipeline wired (orders gated behind POLYMARKET_DRY_RUN)

### What shipped

Resolved **PM2c** (execution-pipeline wiring — the last code step of ROADMAP Priority 0
Phase 2). `python scripts/scan.py polymarket --execute` now routes US-slug futures
opportunities through the shared `execute_pipeline` with `venue="polymarket"` — the same
risk gates, Kelly sizing, and ratio/budget caps as Kalshi — then `create_order` on the US
API. `--unit-size / --budget / --max-bets / --min-bets / --pick / --ticker` supported.

- **Two-flag dry-run safety (new `POLYMARKET_DRY_RUN`, default true)** — Polymarket orders
  return `dry_run_blocked` unless BOTH `DRY_RUN=false` and `POLYMARKET_DRY_RUN=false`.
  Required because `.env` runs Kalshi live: without a venue-scoped flag, flipping the
  scanner's `--execute` refusal would have placed live Polymarket orders immediately,
  contradicting the "prove edge in dry-run first" phase gate.
- **Venue minimum order size** — `minimumTradeQty` captured at scan time into
  `opp.details["min_order_shares"]` + the registry; `size_order` bumps sub-minimum counts
  up (post-caps) or rejects (`below_venue_min_shares`) when the bump would breach
  `MAX_BET_SIZE`/bankroll; the pipeline drops rows the ratio/budget caps push back under.
- **Positions normalized** — `PolymarketClient.get_positions` also emits Kalshi-shaped
  `market_positions` with `PM-{marketSlug}` tickers (the scanner's own convention), so
  Gate 5, per-event counts, and `status --venue polymarket` work unchanged.
- **Venue-tagged trade log** — records carry `venue`; `orderId` (US camelCase) accepted.
  Gate 1 (daily loss) spans venues by design. Batch placement now survives non-Kalshi
  exceptions (one failed order can't abort the batch); the Kalshi resting-order janitor is
  skipped for non-Kalshi venues; Gamma games opps (no US slug) are excluded from execution.

Live-verified end-to-end in preview mode: $60.12 balance, 2 US positions counted through
the normalized shape, four championships priced, the one live edge (Spurs) correctly
gate-rejected on composite score, client initialized `dry_run=True` despite global
`DRY_RUN=false`. **+15 tests (635 total).** Remaining: prove edge in the daily dry-run
window → deliberately flip `POLYMARKET_DRY_RUN`; seasonal games repoint; PM3 settlement/ops.

---

## 2026-07-20 -- Polymarket US repoint: execution rebuilt (Ed25519) + futures scanner on US data

### What shipped

Resolved **PM2c-0**. The operator's funded account is the **CFTC-regulated Polymarket US**
product (iOS-app only), which uses an **Ed25519 retail API** (`api.polymarket.us`) — not the
international EIP-712 / `py-clob-client` scheme the earlier PM2b client assumed. (The prior
"$0 empty twin wallet" diagnosis was wrong — it was the wrong product/API entirely, not a
per-sign-in-method Magic account.)

- **Auth + execution client rebuilt** — `PolymarketClient` on signed requests (shared
  `polymarket_us_auth` Ed25519 signer, raw `cryptography` + `requests`, no SDK); `app.config`
  creds → `POLYMARKET_KEY_ID` / `POLYMARKET_SECRET_KEY`; `market_registry` → US `market_slug`.
  Verified live ($60.12 buying power, real positions).
- **Futures scanner repointed to US market data** — new `polymarket_us_data` read client
  (paginates `GET /v1/markets`, groups championships by `question`, extracts each team's YES
  ask + US slug); prices US quotes vs the Odds-API consensus and records the real
  `marketSlug`. Verified live (Spurs NBA-champ +3.6%). World Cup dropped (over + not on US).
- **Config cleanup** — retired `POLYMARKET_PRIVATE_KEY` / `_FUNDER_ADDRESS` / `_SIGNATURE_TYPE`
  and the `py-clob-client` dependency; added `POLYMARKET_KEY_ID` / `POLYMARKET_SECRET_KEY`.
- **Inventory finding** — Polymarket US is **not** a Gamma mirror: game markets are
  moneyline-only + seasonal (no spreads/totals, no MLB per-game); futures are the deep,
  always-on surface. The games scanner still reads Gamma (dry-run only, not executable on
  US); its repoint is a deferred seasonal follow-on.

**620 tests pass.** Remaining before live orders: execution-pipeline wiring (size →
`create_order`, ~5-share minimum, flip the scanner `--execute` refusal). Full detail:
`docs/setup/polymarket-us-setup.md`.

---

## 2026-07-20 -- Session note: PM2b live verification — auth works, wallet identity mismatch found

### What happened

First live test of the PM2b `PolymarketClient` against the operator's real
account. The signing chain **works end-to-end**: exported key valid, EIP-712
signing + CLOB L2 credential derivation succeeded (`signature_type=1`;
signer EOA distinct from funder, as expected for a Magic proxy account).

But the configured account is **empty** — confirmed three independent ways
(CLOB collateral read, raw on-chain USDC/USDC.e balances via Polygon RPC,
Data-API portfolio value = 0). The operator sees the funds in the phone app
while the desktop session (same email) shows $0: Polymarket/Magic creates a
**separate wallet per sign-in method** (Google vs Apple vs typed-email magic
link), so the desktop-exported key + address belong to an empty twin
account. The public username lookup (`toastyllama6297`) dead-ends (no web
profile), so the funded address must come from the phone side.

### Status

**Blocked on operator action — logged as PM2c-0, the most urgent roadmap
item** (full fix steps in the ROADMAP Priority 0 table): re-login on desktop
with the phone's exact sign-in method, re-export key + address from that
session, update `.env`, re-run the read-only verification.

---

## 2026-07-20 -- Session: PM2b — PolymarketClient write half (py-clob-client)

### Why

The wallet question resolved: the operator's funded Polymarket account is an
email/Magic proxy wallet whose balance ≈ the intended bankroll, so it IS the
dedicated trading wallet (decision revised from "create a separate wallet").
That unblocked building the execution client — mock-tested now, live smoke
test once the exported key lands in `.env`.

### What landed

- **`polymarket_exec_client.PolymarketClient`** — implements the
  `MarketClient` contract via `py-clob-client` (new dep): EIP-712
  wallet-signed CLOB orders (`signature_type=1` proxy accounts), balance via
  CLOB collateral (+ Data-API position value), positions via the public Data
  API, orders/cancel/fills via CLOB. `get_settlements` returns empty until
  PM3. Lazy CLOB construction — init is network-free, and DRY_RUN order
  paths (blocked with `status="dry_run_blocked"`, exactly like KalshiClient)
  never touch the network.
- **`market_registry`** — the `MarketClient` contract speaks Kalshi-shaped
  tickers but the CLOB needs token ids; scanners now record
  ticker → {condition_id, clob_token_ids} at scan time (7-day expiry,
  atomic write), and `create_order` resolves through it (side→token is
  structural: yes=0/no=1; NO price is used directly — no 1-minus, unlike
  Kalshi's single-book API). A registry miss refuses the order.
- **Factory flip:** `get_market_client("polymarket")` now returns the real
  client; without credentials it raises the same style of setup-guidance
  error as KalshiClient (no more blanket Phase-2 refusal).
- **Config:** `PolymarketCredentials` in `app.config`
  (`POLYMARKET_PRIVATE_KEY` / `POLYMARKET_FUNDER_ADDRESS` /
  `POLYMARKET_SIGNATURE_TYPE`, default 1) + documented `.env.example` block
  with the full-account-access warning.
- **Known venue constraint:** ~5-share minimum order on most markets — at
  $1 units a 50¢ contract sizes below it. Logged as a warning; PM2c wiring
  must bump to the minimum or skip.
- **Test hygiene fix:** the scan orchestration tests were writing fixture
  entries into the real `market_registry.json`; registry path now
  monkeypatched in every scan-invoking test, polluted file purged and
  repopulated clean from a live scan (13 real entries).
- **Tests:** +18 (605 total) — registry roundtrip/prune, conformance
  signature coverage, creds guidance, network-free construction, dry-run
  block, yes/no token+price resolution, registry-miss refusal, factory.

### Remaining (PM2c)

- Live auth smoke test (blocked on the operator exporting the key to
  `.env`), execution-pipeline wiring (gates → sized orders →
  `create_order`, min-share handling, flip the scanner `--execute`
  refusal), then first live orders after the edge window proves out.

---

## 2026-07-20 -- Session: PM1d — Polymarket per-game edge detection (ML/spread/total)

### Why

The operator asked whether Polymarket carries individual game markets. The
07-14 spike said no ("0 MLB game markets") — that finding was **wrong**. Game
events exist for every MLB/NFL/NBA/NHL game (moneyline + run-line spread +
game total, tight 1–4¢ books) but are invisible to title search and default
listing order; they surface only via tag_id + open filtering — the same
discovery failure mode as the PM1b futures slugs. Game lines are the bigger
prize: ~15 MLB games/day vs 4 slow futures boards, and games **settle daily**,
so the PM2 edge-proving window can validate against real settlements in weeks
instead of waiting for October futures resolution.

### What landed

- **`polymarket_games_edge.py`** — prices every open pre-game Polymarket
  ML/spread/total against the SAME calibrated consensus model as Kalshi
  sports: `consensus_fair_value` / `consensus_spread_prob` /
  `consensus_total_prob` reused unchanged (de-vig, sharp-book weighted
  median, sport-specific stdevs incl. C8 calibrated overrides; a synthetic
  `KX<sport>` stdev-routing ticker feeds the prefix lookup). ML and totals
  priced on both sides (second outcome's effective ask = 1 − best bid);
  spreads YES-only. Category = game/spread/total, so the existing risk gates
  compose naturally (verified: ~5% Under edges correctly held by the R28
  NO-side 8% floor).
- **Client additions** — `get_tag_id(slug)` (cached), `fetch_game_events`
  (tag_id + open, paginated), `iter_game_rows` (normalizes via Gamma's
  `sportsMarketType`; skips exotic NRFI/first-five/props — dead 2¢/98¢
  books — and closed/degenerate rows).
- **Guard rails:** pre-game only (mirrors Gate 4.8's default); 10¢
  `MAX_BOOK_SPREAD` book-quality floor; and **start-time matching (±6h)**
  between the PM game and the Odds API event — team matching alone priced
  later series games against the wrong game's odds (caught live: 3 phantom
  Twins/Rangers ML edges from July 22–23 games priced with July 21 odds; the
  2026-06-03 Kalshi bug class). Doubleheaders that stay ambiguous are
  refused.
- **CLI routing:** `--filter` now takes `all` (futures+games, new default) |
  `futures` | `worldcup|nfl|mlb|nba|nhl` | `games` | `<sport>-games`.
  Games import lazily so futures-only scans skip the edge_detector stack.
- **Scheduled task widened** (`Daily-Polymarket-DryRun`): now
  `--filter all --min-edge 0.01 --top 40` so the evidence log records the
  full funnel including near-misses (17 rows on first run vs 3 at the old
  floor) — the gates still enforce real floors at execution. Re-validated
  (`LastTaskResult=0`).
- **Verified live:** 55 MLB games priced 1:1 against consensus; 2 genuine
  edges (Under 12.5 totals, +4.3%/+5.0%, gate=edge per R28); 1 NFL preseason
  game; NBA/NHL offseason gracefully empty.
- **Tests:** +9 (`test_polymarket_games.py` — row normalization, both-sides
  ML, spread strike negation, total over/under, filter routing, started-game
  skip, and a regression test for the series-date mismatch). 587 total.

---

## 2026-07-20 -- Session: U1 hourly settle + R10/C6 measurement (no tuning)

### Why

Priority 2 head items while the Polymarket dry-run window accumulates: U1
(hourly settlement) is a standalone quick win newly enabled by M2's trade-log
lock; R10 (category-weighted composite) required a measurement pass before any
weight could be chosen.

### What landed

- **U1 — `Hourly-Settle` task (every hour at :35).** Runs
  `kalshi_settler.py settle` hourly (direct python, NightlySettle pattern).
  Enabled by M2: the cross-process lock makes a settle that overlaps an
  execute task merge-safe. Fresher settlements sharpen Gate 1 (daily-loss)
  intraday, clear positions as games end, and run R4 resting-order cleanup
  timely. `:35` is the only minute slot clear of every existing task.
  `NightlySettle` kept ~1 week as belt-and-suspenders (settle is idempotent),
  then retire. Validated on install (`LastTaskResult=0`). Task #22 in
  `docs/task-schedules/README.md`.
- **R10 — RESOLVED, no re-weighting.** The April premise (Total +32% >> ML
  +11%) inverted: 90d shows ML +19.6% (n=70) vs Total -4.4% (n=42), and every
  category flips sign between adjacent ~45d slices. The spread aggregate
  (+45.3%) decomposes into WC spreads 5-31/-60% (realized ≈ the market price
  — zero alpha on the claimed +6.6% edge, post-de-vig-fix) vs MLS spreads
  +246.8% (n=14 longshot luck); combined soccer spreads land dead on model
  fair. The dominant variation is sport×regime, not category — re-weighting
  the composite on this data would fit noise (the C4 lesson). Watch-don't-
  tune; revisit only on a stable same-signed gap across two independent ~90d
  windows at n≥100. Writeup:
  `docs/my-documents/temp/r10-category-weights/README.md` (local).
- **C6 — CLOSED with the same pass.** April's Totals +32% didn't persist
  (90d -4.4%); nothing pathological either. No action.
- **Finding for the record:** the World Cup spread cohort ran at market, not
  at model — tempers the 06-29 conclusion that WC always-YES spread edge was
  "largely real." Soft follow-up: re-check soccer-spread edge realization
  early in the next major tournament.

---

## 2026-07-20 -- Session: PM2a — venue-neutral MarketClient seam (execution plumbing)

### Why

PM2 (Polymarket execution) needs a venue-agnostic client boundary before any
wallet code exists. The executor hardcoded `KalshiClient()`; extracting the
seam now is decision-free (no real money, no wallet secrets) and shortens the
risky half later, while the PM1c dry-run evidence window accumulates.

### What landed

- **`MarketClient` Protocol** (canonical `scripts/shared/market_client.py`,
  re-exported via `app/domain/market_client.py` following the `Opportunity`
  pattern): the 7-method contract the money paths actually use —
  `get_balance_dollars`, `get_positions`, `create_order`, `get_orders`,
  `cancel_order`, `get_fills`, `get_settlements` — with the KalshiClient-set
  conventions documented (dollars not cents; legacy order shape translated
  internally; DRY_RUN honored via `status="dry_run_blocked"`).
- **`get_market_client(venue)` factory** — the single place a venue name
  becomes a client (lazy imports so a venue's dependency stack only loads
  when selected). `kalshi` resolves; `polymarket` raises a clear
  NotImplementedError until the PM2 write half ships; unknown venues raise
  ValueError.
- **Executor `--venue` plumbing** (`run` + `status`): `KalshiClient()`
  hardcode replaced with the factory; `--venue polymarket` refuses with a
  clean message (exit 2), not a traceback. Verified live: `status` runs
  through the factory against the real portfolio.
- **Tests:** +21 (`test_market_client.py` — class-level KalshiClient
  conformance incl. per-method signature coverage so drift is caught,
  runtime_checkable behavior, factory routing/refusal/validation). 578 total.
- Deliberately untouched: `webapp/services.py:161` keeps its direct
  `KalshiClient()` — its Streamlit-secrets credential handling is
  Kalshi-specific and migrates when a real second venue exists.

### Next

- PM2 write half (`PolymarketClient` via `py-clob-client`), gated on the
  dry-run edge-proving window + operator answers (wallet choice, test
  stakes, sports-only scope, arb vs independent edge).

---

## 2026-07-20 -- Session: PM1c — Polymarket dry-run evidence persistence

### Why

The Phase 1→2 gate is "prove edge in dry-run," but the Polymarket scanner
accepted `--save` and silently discarded it — no evidence could ever
accumulate to satisfy the gate.

### What landed

- **`--save` is now functional** on `polymarket_futures_edge.py` (flows through
  `scan.py polymarket ... --save` unchanged): appends one run record —
  timestamp, filter, min-edge, count, and every opportunity **with its
  preflight gate verdict** — to `data/polymarket/dryrun_log.jsonl`
  (append-only time series). Zero-opportunity runs are logged too: "how often
  does edge appear at all" is part of the evidence.
- **Markdown scan report** to the new `reports/Polymarket/` directory via
  `report_writer` (new `"polymarket"` report type, reuses the futures table
  layout). `--report-dir` override supported, matching the other scanners.
- Gate preflight refactored out of the preview (`_gate_statuses`) so the
  table and the persisted record share one computation.
- **First live record captured:** NBA Spurs at 19¢ vs 23¢ fair (+4.0%), low
  confidence, gate=`score` — correctly rejected.
- **Tests:** +3 (`TestSaveDryrun` — JSONL shape + gate field + report,
  zero-opp logging, multi-run accumulation). 557 total.

### Scheduled (same day)

- New `Daily-Polymarket-DryRun` Windows task (daily 9:40 AM PST) runs the
  `--save` scan unattended, so the PM2 evidence log builds itself. Read-only,
  no paired email (output to `logs/polymarket_dryrun_scan.log`), ~4 Odds API
  requests/run. Validated on install (`LastTaskResult=0`, record appended).
  See `docs/task-schedules/README.md` task #21.

---

## 2026-07-20 -- Session: PM1b — Polymarket futures event discovery (NFL/MLB/NBA/NHL)

### Why

Phase 1 of the Polymarket integration proved the pricing path on the World Cup
only — the keyword-search fallback couldn't locate the Super Bowl / World Series /
NBA / Stanley Cup boards, blocking year-round futures coverage (ROADMAP PM1b).

### What landed

- **Root cause:** the championship boards sit beyond the first 300 active Gamma
  events, so `find_event`'s pagination fallback never reached them (and the NFL
  board is titled "NFL Champion 2027", so "super bowl" terms couldn't match it).
- **All four slugs wired into `PM_FUTURES`:** NFL `big-game-champion-2027`,
  MLB `mlb-world-series-champion-2026`, NBA `nba-2027-champion`,
  NHL `nhl-2027-champion-20260612185656162` (verified live 2026-07-20).
- **`find_event` fallback rebuilt on Gamma `/public-search`** (new
  `search_events()`): relevance-ranked search per term, open-events-only,
  all-words-of-a-term title match (excludes e.g. Conn Smythe with "nhl champion"),
  highest-volume winner (picks "World Cup Winner" over "Golden Boot Winner"),
  then a re-fetch by slug since search results may truncate the markets list.
  Slugs rot at season rollover; the fallback re-resolves all four boards from
  dead slugs (live-proven), so next season heals without a code change.
- **End-to-end verification:** `scan.py polymarket --filter futures` prices all
  four sports vs Odds API outrights — 32/30/30/32 candidates each matched 1:1 to
  sportsbook outcomes; one edge surfaced (NBA Spurs +4.0%, low confidence →
  correctly gated on composite score). World Cup board closed at the final
  (2026-07-20) and is correctly skipped — dormant until the 2030 cycle.
- **Tests:** +4 (`TestFindEvent` — slug short-circuit, closed-filter +
  volume-preference + full re-fetch, all-words matching, empty input). 554 total.

### Next

- **PM2** — Phase 2 execution (`MarketClient` Protocol, `py-clob-client`,
  wallet secrets handling), after the dry-run edge-proving window.

---

## 2026-07-20 -- Session: MLB recheck (M1), review residuals (#3/#6), trade-log lock (M2)

### Why

Post-review follow-through. The 2026-07-14 repo review left three tracked items;
this session closed the MLB executable-bets recheck (M1), two small safety residuals,
and the cross-process trade-log lock (M2).

### What landed

- **M1 — MLB executable-bets recheck (RESOLVED, no code change).** Ran on a full
  15-game slate: MLB now surfaces **15 opportunities** (vs 0 across the prior 30-day
  window), confirming the World-Cup crowding was the cause and is structurally gone.
  All rows gate on `edge` with sub-1% edges on efficient lines (Mkt≈Fair within ~1¢) —
  NOT the 2–3%-blocked-by-floor bucket, so `MIN_EDGE_THRESHOLD_MLB` / `MIN_COMPOSITE_SCORE`
  left unchanged. Odds quota confirmed healthy (3,988 across keys; one dead 401 key noted).
- **#6 — Odds API key redaction.** A `requests` exception stringifies the full URL with
  `?apiKey=<secret>`; it was logged verbatim at three sites. New `odds_api.redact_secrets()`
  masks `apiKey=<value>` before logging (edge_detector fetch + event fetch, futures_edge). +5 tests.
- **#3 — Longshot report crash guard.** `betting_analysis._render_longshot` now None-guards
  `edge`/`fair_value` (renders `—`) like the ledger, so one incomplete settlement no longer
  raises `TypeError` and kills the whole analysis report. +3 tests (new `test_betting_analysis.py`).
- **M2 — Cross-process trade-log lock.** `_atomic_write_json` (shipped 07-14) closed the
  corruption hole but not the concurrent read-modify-write lost-update race. Added
  `trade_log_lock()` (cross-process `filelock`, graceful no-op fallback) + `append_trades()`
  (re-reads under the lock before saving → merges instead of clobbering). Executor's two
  write sites now use `append_trades`. Settler split into Phase 1 (Kalshi network I/O, no
  lock) → Phase 2 (short locked critical section that re-loads fresh, preserving any executor
  append made mid-fetch, then saves) so the lock is never held across network I/O.
  `filelock>=3.12.0` added to requirements. +7 tests incl. end-to-end concurrent-append test.
- **#7 — execute batch aborted mid-placement on network errors.** The order loop only
  caught `KalshiAPIError`; a `requests` `ConnectionError`/`Timeout` from `create_order`
  propagated uncaught, aborting the batch part-placed with no failure record. `_request`
  now translates transport errors into a typed `KalshiConnectionError` (subclass of
  `KalshiAPIError`, `status_code=0`). The loop (extracted to a testable `_place_order_batch`)
  records each failure and continues instead of aborting, flagging transport failures as
  placement-UNKNOWN for reconciliation, with a circuit-breaker after 3 *consecutive* transport
  failures (a dead network stops the batch instead of hanging every remaining order to its
  timeout). Orders are **not** retried — a retried POST could double-place. +8 tests.
- **#8 — settlement P&L double-count.** Kalshi settlements are keyed per-market, so two
  trades sharing a ticker both matched the same settlement and each claimed the whole
  position's aggregate `revenue` (double-counted P&L). `calculate_pnl` now derives revenue
  **per-trade** from that trade's own filled contracts (a winning binary contract pays
  exactly $1.00) — additive across trades and, for a single trade, identical to the aggregate.
- **#9 — inconsistent revenue normalization.** The settler's `calculate_pnl`, the settler
  report builder, and `risk_check` normalized the settlement `revenue` cents field three
  different ways (two used a `> 1` guard that mis-read 1¢ as $1.00). Consolidated into one
  shared `trade_log.settlement_revenue_dollars()` (any int is cents → /100) used by both
  report builders; `calculate_pnl` no longer reads the raw field at all (#8). +7 tests.

**550 tests passing** (was 520).

---

## 2026-07-14 -- Polymarket Phase 1: read-only championship-futures edge detection (dry-run)

### Why

Kick off the Polymarket integration (Priority 0). Phase 0 spike found the Gamma API
live and healthy, but that Polymarket's sports coverage is **futures/props/politics**,
not per-game lines (0 MLB game markets; top markets are World Cup Winner $4.2B, F1
champion, retirement props). So Phase 1 targets **championship futures**, which map to
Edge-Radar's existing `futures_edge` outright fair-value model.

### What landed

- **New `scripts/polymarket/` package (read-only):**
  - `polymarket_client.py` — Gamma API client: `find_event` (slug + keyword fallback,
    paginated), `iter_future_candidates` (normalizes an event's sub-markets, skips
    closed/eliminated candidates and degenerate 0/1 prices, reads the Yes-token
    `bestAsk`). No auth, no wallet, places no orders.
  - `polymarket_futures_edge.py` — `detect_edge_futures_polymarket` mirrors
    `futures_edge.detect_edge_futures` but reads the Polymarket candidate shape and
    **reuses `fetch_outrights` + `consensus_outright_fair_values` unchanged** for the
    sportsbook fair-value side. Emits normalized `Opportunity` (category=`futures`,
    `edge_source=polymarket_vs_outrights`, `details.venue=polymarket`). YES-side only in v1.
- **Wired into `scan.py`:** `polymarket` market type (aliases `poly`/`pm`),
  `--filter worldcup|nfl|mlb|nba|nhl`. The preview shows each opp's `preflight_gate_status`
  (routes through the existing risk gates read-only). `--execute` is **refused** — execution
  is Phase 2 (wallet / `py-clob-client`).
- **Reuses the provider-agnostic seam:** Polymarket opps flow through the same
  `Opportunity` + gate logic as Kalshi — no gate code duplicated.
- **Proven live end-to-end:** ingested the World Cup Winner event, priced against
  `soccer_fifa_world_cup_winner` outrights, matched the final-4 candidates → 0 edge (a
  correct result: efficient cross-venue pricing + tournament ending ~07-19).
- **+12 tests** (`tests/test_polymarket_futures.py`); 520 passing. `scripts/polymarket`
  added to `pyproject.toml` pytest pythonpath.

### Known follow-up (PM1b)

Event **discovery** for NFL/MLB/NBA/NHL futures needs each event's exact Gamma slug or
tag_id — the keyword-search fallback didn't locate them (World Cup works via its confirmed
slug). The pricing framework is done; only discovery config is missing. See ROADMAP PM1b.

## 2026-07-14 -- Polymarket integration scoped as top priority + roadmap relocated to docs root

### Why

Polymarket account approved + funded (US-persons ToS confirmed legitimate by operator).
Goal: place wagers on Polymarket through Edge-Radar as a second execution venue. Ran a
technical spike to scope it before building.

### What changed

- **New Priority 0 on the roadmap: Polymarket integration** (PM0–PM3), marked the
  highest-priority active build. Phased Phase 1 read-only/dry-run → prove edge → Phase 2
  execution → Phase 3 settlement.
- **Spike findings:** the retired 2026-04-27 integration (commit `4361c85`) was a
  read-only Kalshi↔Polymarket arbitrage scanner (Gamma API) — never placed a bet.
  Execution is net-new (on-chain Polygon/USDC, EIP-712 wallet-signed via `py-clob-client`,
  CLOB order book, UMA settlement). Good news: `app/domain/opportunity.py` is
  provider-agnostic and `size_order()` runs on `Opportunity`, so a normalized Polymarket
  opp reuses the existing risk gates; the execution client is a clean ~7-method interface
  hardcoded as `KalshiClient()` at `kalshi_executor.py:1592` + `webapp/services.py:161`
  (introduce a `MarketClient` abstraction + factory). Recoverable git assets:
  `polymarket_edge.py` (Gamma reads) + `.claude/skills/polymarket/references/` (~9k lines
  of CLOB/trading docs). Full plan: `docs/my-documents/temp/polymarket-integration/PLAN.md`.
- **Roadmap relocated:** `docs/enhancements/ROADMAP.md` → **`docs/ROADMAP.md`** (`git mv`,
  history preserved). Fixed all 11 inbound links (README, docs/README, ARCHITECTURE,
  SCRIPTS_REFERENCE, SETUP_GUIDE, the three kalshi guides, CLAUDE.md + ARCHITECTURE trees,
  `r8_cross_category_review.py`). Historical CHANGELOG "Files:" references left as-is.
- **CLAUDE.md** — added a "🔴 NEXT UP: Polymarket" callout and marked it in-progress in the
  Planned list.

## 2026-07-14 -- Full repo review + money-path fixes, longshot floor, config reconcile, cruft purge

### Why

Session started from "not many wagers being placed." Diagnosis (30-day settled
review) flipped the premise: volume wasn't gate-starved — it was **calendar-driven**
(World Cup ending ~07-19, MLB All-Star break, NBA/NHL offseason) and the bets that
*were* placed bled **−43% ROI (12W–30L, L9 streak)**, ~98% World Cup spread-YES
longshots. The sub-15¢ price bucket went **0W–21L, −100%**. Odds API quota was
healthy (2,465 requests). A full five-agent repo review ran alongside; findings at
`docs/my-documents/repo-reviews/2026-07-14-repo-review.md`.

### What changed

**Money-path bug fixes (all 508 tests green):**
- **Calibration-on-read** (`model_calibration.py`): `save_calibration_stdevs()` was
  called unconditionally, so a read-only report run silently mutated the per-sport
  margin/total stdevs the scanner prices against. Now gated behind `--save` (all
  scheduled calibration tasks pass `--save`, so the C8 feedback loop is unaffected).
- **Trade-log corruption** (`scripts/shared/trade_log.py`): `save_trade_log` /
  `save_settlement_log` did a plain non-atomic `open("w")`. Added
  `_atomic_write_json` (temp file + fsync + `os.replace`) so a crash/interrupt can
  no longer corrupt the ledger or lose a live position. (Residual cross-process
  read-modify-write lock left as a follow-up — see repo review.)
- **R26 replay gate bypass** (`kalshi_executor.py`): the cached-preview replay path
  set `to_execute = list(cached_rows)` and skipped straight to execution, bypassing
  gates 5/6/7. It now re-checks duplicate-ticker, per-event cap, and series-dedup
  against *current* portfolio state before executing (sizing stays locked from the
  preview). Drops are reported.

**Risk-gate config reconciled to a single source of truth** (`app/config.py`) across
`.env.example` and `CLAUDE.md`:
- `MAX_OPEN_POSITIONS` → **50** everywhere (live `.env` ran 50; docs/code default
  wrongly said 10 — reconciled *up* to match live intent per operator decision).
- `MAX_PER_EVENT` → **2** in `CLAUDE.md` (was the lone outlier at 3; code/.env were 2).

**Longshot price floor (R7 tightening):** `MIN_MARKET_PRICE` **0.06 → 0.12** in live
`.env`, `.env.example`, `app/config.py` default, and `CLAUDE.md`. 30-day data: every
sub-15¢ bet lost (0W–21L / −100%) while ≥25¢ bets were profitable. This is the direct
fix for the World Cup spread-YES longshot bleed and protects future soccer/all-sport
longshots. **Requires webapp restart / Streamlit Cloud Secrets update to take effect
in long-running apps** (CLI picks it up immediately).

**Cruft purge:** `git rm` of three verified broken+orphaned scripts —
`daily_sports_scan.py` (crashed on import: `from config import …`; superseded by
`same_day_scan.bat → scan.py`), `fetch_market_data.py`, `fetch_odds.py` (orphaned,
broken auth + Polymarket response shape). Removed 16 untracked dated
`send_daily_summary_email_2026-*.py` snapshots (canonical `send_daily_summary_email.py`
retained). Updated `docs/scripts/SCRIPTS_REFERENCE.md` to drop the three blocks.
**Deliberately NOT removed:** `.claude/backup/` — its README documents it as an
intentional holding pen keeping old HTML out of the public Pages deploy (the review
agent misread it as dead cruft).

**Tests:** updated `test_config.py` (new defaults) and `test_risk_gates.py` (two tests
using $0.10 prices now neutralize the floor via monkeypatch, since they exercise the
max-bet cap / Kelly sizing, not the R7 floor). 508 passing.

### Open follow-up

- **MLB executable-bets recheck** — MLB placed 0 bets in 30 days (crowded out by
  World Cup's inflated pre-de-vig edges for the `--max-bets` slots). Should self-correct
  now that WC is ending + de-vig shipped + longshot floor raised. Recheck plan +
  commands: `docs/my-documents/temp/mlb-executable-bets/README.md`. **Run 2026-07-17/18.**
- Other repo-review follow-ups (composite-formula regression test, undocumented env
  vars `KALSHI_PROD_*`/`ALPACA_*`/`TELEGRAM_*` in `.env.example`, settlement
  double-count-by-ticker, three-way Brier definition mismatch, cross-process trade-log
  lock) are catalogued in the repo-review doc.

## 2026-06-29 -- De-vig the spread & total models (fix the always-YES bias)

### Why

A review of recent betting found World Cup spread bets were **always `YES`**
(favorite covers): 44/48 live WC spread markets priced model fair-value above
the market, including **both teams in the same match** — which is impossible for
a genuine edge. Root cause: `consensus_spread_prob` and `consensus_total_prob`
inferred the expected margin/total from the **raw, vigged** book-implied
probability (`implied_prob(book_odds)`), never de-vigging. The two-way spread/
total sums to ~1.05-1.08 implied, so each side ran ~half the vig high, inflating
the inferred mean and thus `P(cover)`/`P(over)` for both sides of every game.
The moneyline path (`consensus_fair_value`) already de-vigs — spreads/totals
were the outliers. The bias inflated claimed edges (→ Kelly oversizing, often on
the longest-shot picks) and removed the model's ability to ever take NO or pass.

### What changed

- **De-vig the two-way line before inferring the mean.** Both functions now
  divide the matched outcome's implied by the book's overround
  (`sum(implied_prob(o) for o in outcomes)`), mirroring the moneyline devig.
  Each book record now carries both `implied` (de-vigged) and `raw_implied`.
- **Validated live:** on the WC spread board the always-YES lean dropped from
  44/48 (92%) to 39/48, and mean model edge fell ~1 point — claimed edges are
  now honest. +4 tests (`TestSpreadTotalDevig`), 496 passing.

### Known residual (separate follow-up, not fixed here)

De-vig removes the vig-driven half of the bias but **not all of it**: 16/22
matches still show both sides leaning YES, traced to the **soccer margin stdev
(1.8)** making the normal-CDF tail too fat for soccer's discrete low-scoring
margins. A sensitivity sweep shows stdev ≈ 1.4 makes the model symmetric
(mean fair−mid ≈ 0, both-sides-impossible 16→1). Deferred as a calibration
decision because lowering stdev also shrinks a possibly-real underpricing edge
(placed soccer spreads hit 31% vs 19% market-implied) and should be chosen
against settled outcomes, not fit to one day's board.
## 2026-06-28 -- Wimbledon Tennis Sport Coverage Added

### Why

Wimbledon 2026 starts June 29. The scanner had no tennis mapping, so Kalshi's
Wimbledon match-winner markets were invisible. Tennis was deferred from the
2026-06-20 World Cup release because markets weren't open yet (Kalshi API
confirmed 0 open markets on June 20 for all tested prefixes).

### What landed

- **Tennis wired as a new h2h-only sport** — match-winner (`game` category) only;
  no spread or total markets on Kalshi for tennis. `KXATPMATCH` → `tennis_atp_wimbledon`
  and `KXWTAMATCH` → `tennis_wta_wimbledon` added to `CATEGORY_MAP` and
  `KALSHI_TO_ODDS_SPORT`. New `wimbledon` and `tennis` filter shortcuts.
- **Player-name extraction** — no new regex needed. Live markets read
  "... wins the *Tsitsipas* vs *Djokovic* professional tennis match in the 2026
  Wimbledon ...", which the existing "(?:vs|at) ... professional" branch in
  `extract_event_teams()` already parses, returning the two players' last names.
  Those substring-match the Odds API full names ("Stefanos Tsitsipas").
- **Display wiring** — `KXATP`/`KXWTA` prefixes → sport label "Tennis" in
  `ticker_display.py`. Player abbreviations in ticker suffixes pass through raw
  (not in the US-sport team alias table, which is correct).
- **No edge-math changes** — tennis uses the existing de-vigged h2h moneyline
  path (`detect_edge_game`). No spread/total stdev entries needed.

### 2026-06-29 — local validation + date-matching fix

The 06-28 work was authored by a cloud agent with the Kalshi API egress-blocked,
so prefixes and the rules format were guesses. Validated locally against live
markets and corrected:

- **Prefixes confirmed.** `KXATPMATCH` / `KXWTAMATCH` are correct (3+ open
  markets each on 2026-06-29). The speculative "wins this match against" regex
  the cloud agent added was dead code (real markets use the "vs ... professional
  tennis match" phrasing) and was removed.
- **Date-matching fix (the real blocker).** Tennis tickers embed the market's
  *expected expiration* date (~a day after the match), not the commence date —
  e.g. `KXATPMATCH-26JUL01TSIDJO` is the **Jun 30** 09:00 UTC match. The
  exact ET-date equality in `find_market_event()` rejected every market with
  "0 candidate events". Added a tennis branch (`_is_tennis_market()`): a player
  pair meets at most once per tournament, so the single both-players candidate
  is accepted when its commence lands within 3 days of the ticker date. After
  the fix, `--filter wimbledon` matches markets to events and `detect_edge_game`
  computes fair values (e.g. Djokovic 0.832 fair vs 0.87 ask → correctly no bet).

### Verification

`TestTennisMappings` (real-data extraction + date-tolerant matching) and
`TestTennisDisplay` → **505 passing**. Live: `python scripts/scan.py sports
--filter wimbledon` matches all 76 markets to odds events (no edges cleared the
threshold at validation time — an efficient market, not a wiring gap).

### Files

`scripts/kalshi/edge_detector.py`, `scripts/shared/ticker_display.py`,
`tests/test_edge_detection.py`, `tests/test_ticker_display.py`,
`CLAUDE.md`, `docs/kalshi/kalshi-sports-betting/SPORTS_GUIDE.md`, `docs/CHANGELOG.md`.

---

## 2026-06-24 -- C4: retire the base "high" confidence tier's composite-score premium

### Why

The 90-day review (F49) flagged that High-confidence bets keep *under*performing Medium ones (High 41.5% WR / +13.5% ROI vs Medium 53.2% / +44.4%), meeting C4's deferral condition (118 high-conf trades). The roadmap required measuring whether the tier carries any predictive signal before acting.

### What the audit found (306 settled bets)

- **No positive signal — controlled for edge.** Bucketing High vs Medium by *claimed* edge: in the 5–10% band High is 34.4% WR (n=32) vs Medium 62.7% (n=51); in the 10%+ band 45.2% vs 46.8%. At equal claimed edge, High wins less.
- **Mechanism is over-claim on efficient prices**, not "tight = low edge" as the roadmap guessed. High actually carries *higher* avg claimed edge (19.1% vs 15.9%) — a tight ≥8-sharp-book consensus is an efficient price, so a large model edge against it is most likely model error. Worst cells: NCAAMB High (33.8% edge / 28.6% WR), HIGH/NO (−29.7% ROI). High works only for NHL (70% WR).

### What landed

- **`high`→`medium` in the sports composite weight** (`{low:3, medium:6, high:6}×0.30`) across all three formulas (game/spread/total) in `edge_detector.py`. "High" no longer earns a +0.9 composite premium, so it can't float no-signal bets up the `--max-bets` queue or ease Gate 4 (`MIN_COMPOSITE_SCORE`).
- **Left intact:** the `high` *label* (still a Gate 4.6 restriction on NO-favorites), Gate 4.5, and Kelly sizing (which never read confidence). Scoped to **sports only** — futures/prediction modules mint "high" by different rules and were out of scope. No env var.
- A documented follow-up **C4b** (edge-cap the minting rule to make a meaningful High tier) is logged in the roadmap; deferred because High underperforms even at low edge.

### Verification

Full suite **493 passing**. No test asserted the internal composite formula (composite is supplied as a fixture), so the change is a pure ranking-calibration tweak; behavior validated against the 306-bet settlement history. Live automation is unaffected until the branch merges to master.

### Files

`scripts/kalshi/edge_detector.py`, `CLAUDE.md`, `docs/CHANGELOG.md`, `docs/enhancements/ROADMAP.md`.

---

## 2026-06-23 -- L1 Phase 2 live-freshness fixes (fail-closed staleness + min-books floor)

### Why

A code review of the L1 Phase 2 live-odds path found two freshness holes that both failed *open* (toward using stale/thin data) — the opposite of what the feature is for. They only bite when `ALLOW_LIVE_BETS=true` (off by default), so no live bet was affected, but they had to be fixed before live betting is enabled.

### What landed

- **Fail closed on missing `last_update` (CRITICAL #1).** `_is_bookmaker_stale` previously treated a bookmaker with a missing/unparseable `last_update` as *fresh* on an in-progress game — so a suspended feed that dropped its timestamp would silently flow into the live consensus. It now **excludes** such a book (and logs it). Real Odds API event responses always carry `last_update`, so this only fires on malformed data; pre-game markets are untouched.
- **Minimum fresh-books floor (CRITICAL #2).** After the stale filter runs on a live game, if it **thinned** the consensus below `MIN_LIVE_CONSENSUS_BOOKS` (**default 3**) surviving fresh books, the game is now skipped instead of priced off 1-2 quotes. The guard fires **only when staleness actually removed books** — a live market whose books are all fresh is no thinner than pre-game and keeps its existing behavior, as do all pre-game/futures markets.
- **Visible fallback (MEDIUM #3).** When the per-event live refresh fails (404 / quota / network), `_refresh_event_if_live` now logs a warning before falling back to the stale sport-level snapshot, instead of degrading silently.

### Verification

+4 tests (thinned-below-floor → skip, all-fresh-not-floored, missing/unparseable `last_update` exclusion, plus the config knob default + negative-value guard); existing fixtures gained a realistic per-book `last_update`. **492 passing.**

### Files

`scripts/kalshi/edge_detector.py`, `app/config.py`, `tests/test_edge_detection.py`, `tests/test_config.py`, `.env.example`, `CLAUDE.md`, `docs/CHANGELOG.md`, `docs/enhancements/ROADMAP.md`.

---

## 2026-06-23 -- 90-Day Review Fixes: NO-Side Floors (R28), NBA Consensus (R29), Auto-Stdev Calibration (C8), Live Odds Phase 2 (L1)

### Why

The 90-day review (302 settled trades) surfaced three structural P&L/calibration problems and the live-odds work had a Phase 2 remaining:
- **NO contracts net -7.0% ROI vs YES +48.1%** at near-identical (~48%) win rates (F45) — a structural pricing drag on the NO side.
- **NBA -23.3% ROI** across 32 bets (F46), partly edges built on thin/stale recreational lines.
- **Model overconfidence** — predicted probabilities run 11-25% above realized win rates across mid/high bands (F47); per-sport stdevs were still hand-tuned (F40).
- **L1 Phase 1** fixed live-edge *freshness* via caching TTLs but still re-pulled whole sports and trusted every in-play book.

### What landed

- **R28 — global NO-side floors.** Every NO bet's effective edge floor is now `max(per-sport floor, NO_SIDE_MIN_EDGE_GLOBAL)` (**default 8%**), independent of price (Gate 4.6b), plus a `NO_SIDE_KELLY_MULTIPLIER_GLOBAL` dampener on all NO sizing (**default 1.0 = off**). The edge floor does the heavy lifting; the multiplier is a tuning lever.
- **R29 — NBA consensus-book floor.** NBA games with fewer than `MIN_CONSENSUS_BOOKS_NBA` (**default 8**) agreeing books are dropped to `low` confidence, which Gate 4.5 (`MIN_CONFIDENCE=medium`) then rejects — filtering edges built on stale recreational lines.
- **C8 — auto-recalibrated per-sport stdevs.** `model_calibration.py` now writes recommended `SPORT_MARGIN_STDEV` / `SPORT_TOTAL_STDEV` to `data/cache/calibration_stdevs.json` from settled-trade outcomes; the edge detector reads them at runtime, falling back to hardcoded defaults when the cache is older than `CALIBRATION_STDEVS_TTL_DAYS` (**default 30**). Closes the F40 hand-tuning loop.
  - **Fail-safe hardening (follow-up review):** the loader now validates every cached value (numeric, finite, within `[0.5, 60]`) and rejects the whole map on any bad entry; an unsupported `version` or unreadable file falls back to defaults instead of silently retaining stale overrides; the per-lookup re-parse/re-warn loop is fixed (the file's mtime is marked processed up front); and the writer is now atomic (temp file + `Path.replace`) so a concurrent scan can't read a half-written file.
  - **Statistical fix (C8-followup):** the recommender no longer moves a sport's stdev on noise. It now requires **≥20 settled bets** in that sport+market, gates the move on **statistical significance** (the predicted-vs-realized gap must exceed 1.5 standard errors), uses a gentler `×1.0` step (was `×1.5`) clamped to **`[0.85, 1.25]`** per run (was `[0.8, 1.5]`), and **excludes settlements with no recorded `fair_value`** (previously defaulted to 0.5, contaminating the average). Run against the full 302-bet history, this writes a **single** override — NCAAB margin 12.1 → 14.7 (×1.22) from 29 spread bets at a significant +21.8pp overconfidence gap — and every other sport holds at base (below the floor or within noise). The calibration cron is now safe to run. The earlier cache (NBA totals +39%, soccer margin −20% on samples of 1–22 bets) was deleted.
- **L1 Phase 2 — targeted live fetch + stale-book suppression.** For an in-progress matched game, `fetch_event_odds_api` queries `GET /v4/sports/{sport}/events/{eventId}/odds` (bypassing the sport-level cache, with its own single-event cache via `odds_cache.load_event`/`store_event`), and `_is_bookmaker_stale` excludes any book whose line is older than `MAX_LIVE_BOOK_AGE_SECONDS` (**default 1200s / 20m**) from the live consensus.

### Verification

+15 feature tests + 6 C8 fail-safe tests (invalid-value rejection across 5 cases, unsupported-version fallback, plus a global-state reset fixture) + 5 C8 statistics tests (sample floor, significance hold, significant-widen, missing-fair_value exclusion, clamp ceiling) across `test_edge_detection.py`, `test_risk_gates.py`, `test_odds_cache.py`, `test_config.py` → **489 passing**.

### Files

`app/config.py`, `scripts/kalshi/edge_detector.py`, `scripts/kalshi/kalshi_executor.py`, `scripts/kalshi/model_calibration.py`, `scripts/shared/odds_cache.py`, `tests/test_edge_detection.py`, `tests/test_risk_gates.py`, `tests/test_odds_cache.py`, `tests/test_config.py`, `.env.example`, `CLAUDE.md`, `docs/enhancements/ROADMAP.md`, `docs/CHANGELOG.md`.

---

## 2026-06-20 -- Live In-Play Odds Freshness Fix (L1 Phase 1)

### Why

Edges on **in-progress** games were untrustworthy: the scan flagged them with a `LIVE` tag (R27) but computed the edge against **stale pre-game odds**, producing phantom edges (F44 saw `+50%` "edges" on games already underway). The Odds API already returns live in-play odds on every fetch — the staleness came entirely from caching. The in-process `_odds_cache` had **no TTL**, so in the long-running Streamlit app a pre-game snapshot stayed frozen for hours while Kalshi's price moved during the game.

### What landed

- **TTL on the in-process `_odds_cache`** (`edge_detector.fetch_odds_api`) — now stores `(stored_at_monotonic, events)` and expires entries instead of holding the first response for the whole process lifetime. Within-scan dedup is preserved (back-to-back calls in one scan are sub-second).
- **Live-aware TTL across both cache layers.** New `odds_cache.response_has_live_event()` / `effective_ttl()`: when a sport response contains an in-play event (`commence_time ≤ now`), expiry uses `ODDS_LIVE_TTL_SECONDS` (**default 45s**) instead of the 300s pre-game TTL, so in-progress games refetch current book odds. Pre-game responses keep 300s (quota-friendly). `odds_cache.load()` gained an optional `live_ttl_seconds` arg (backward compatible — `futures_edge` keeps the 3-arg call).
- **Gate 4.8 — `ALLOW_LIVE_BETS` (default off).** The freshness fix makes live edges *honest*, hence executable through scheduled scans. To keep in-play opt-in until calibrated, `size_order()` rejects bets on started games (`is_game_started(ticker)`) unless enabled; `preflight_gate_status()` surfaces it as `live-off`. Mirrors R25. Caveat: detection only fires on moneyline tickers that embed a start time (date-only spread/total tickers aren't caught).

### Verification

+15 tests (`TestLiveAwareTtl`, `TestInProcessCacheTtl`, L1 gate tests) → **463 passing**. Three `test_risk_gates.py` fixtures that used a hardcoded *past* date (`26MAR30…`, `26APR17…`) were bumped to a far-future year so they read as pre-game — fixing latent date fragility that the new gate exposed.

### Files

`scripts/shared/odds_cache.py`, `scripts/kalshi/edge_detector.py`, `app/config.py`, `scripts/kalshi/kalshi_executor.py`, `tests/test_odds_cache.py`, `tests/test_edge_detection.py`, `tests/test_risk_gates.py`, `.env.example`, `CLAUDE.md`, `docs/enhancements/live-in-play-odds-design.md`, `docs/CHANGELOG.md`.

---

## 2026-06-20 -- PGA Tour (Golf Majors) Edge Detection Fixed

### Why

PGA never surfaced edges because the wiring was pointed at the wrong tournament. `futures_edge.py` statically mapped the whole `KXPGATOUR` series to `golf_pga_championship_winner` — but that major already happened in May, so the Odds API key was inactive (no data). Meanwhile the live Kalshi markets were the **U.S. Open** (`KXPGATOUR-USO26-*`), which wasn't mapped at all. Diagnosis also revealed `KXPGATOUR` spans the *entire* PGA Tour calendar (RBC Heritage, Truist, Zurich Classic, qualifiers, ...), while The Odds API only publishes outright fields for the **4 majors**. Completes ROADMAP R19(b).

### What landed

- **`_golf_major_key(title)`** resolves the specific major from the human-readable market title (not the cryptic event code `USO`/`PGC`/...): Masters, PGA Championship, U.S. Open, The Open → the matching `golf_*_winner` Odds API key. Title-based matching cleanly rejects the **"U.S. Open Final Qualifying"** trap (contains "u.s. open" but isn't the major) and avoids "RBC Canadian Open" false-matching The Open (needs "the open"/"open championship", never bare "open").
- **Per-market routing in `scan_futures_markets`** — KXPGATOUR markets resolve their major individually; weekly tour stops + qualifiers fall through to `None` and are skipped (no odds feed → no edge, never a wrong-tournament edge).
- **`--filter pga`** now routes to the futures scanner (was a dead no-odds sports-path entry); `--filter golf-futures` unchanged.

### Verification

+7 tests (`TestGolfMajorResolution` in `tests/test_edge_detection.py`) → 449 passing. Live: `scan.py futures --filter pga` priced the U.S. Open field (71 players, 3 books) and surfaced 2 edges — both correctly caught by risk gates (sub-floor longshot → `price`, NO bet → `score`). The old wiring returned nothing.

### Files

`scripts/kalshi/futures_edge.py`, `scripts/kalshi/edge_detector.py` (pga shortcut), `tests/test_edge_detection.py`, `docs/CHANGELOG.md`, `docs/enhancements/ROADMAP.md`.

---

## 2026-06-20 -- Kalshi v2 Order Endpoint Migration (live order placement fix)

### Why

A live execute attempt failed every order with **HTTP 410 `deprecated_v1_order_endpoint`** — Kalshi retired the v1 `POST /portfolio/orders` endpoint. This blocked *all* live order placement repo-wide (a second, independent reason betting looked dead, on top of the seasonal trough). No money was at risk — 410 is a clean pre-placement rejection. Surfaced because the new World Cup coverage finally produced executable opportunities (6 orders) that drove the pipeline to the order call.

### What landed

- **Migrated `create_order` to the v2 endpoint** `POST /portfolio/events/orders` (same host — `api.elections.kalshi.com` and `external-api.kalshi.com` are interchangeable, so signing/base_url are unchanged). The v2 model is single-book / YES-perspective: `side="bid"` buys YES, `side="ask"` sells YES. The public `create_order` signature is **unchanged**; translation is internal via a new pure, unit-tested `KalshiClient._build_v2_order_body()`:
  - buy YES @ p → `bid`, `price="<p>"`; **buy NO @ p → `ask`, `price="<1−p>"`** (selling YES == buying NO at 1−price).
  - `count` → fixed-point string (`"10.00"`), `price` → YES-perspective dollar string (`"0.5600"`), `self_trade_prevention_type="taker_at_cross"` (now required), `expiration_ts` → `expiration_time`. v1 `buy_max_cost` has no v2 equivalent and was unused — dropped.
- **Response-shape fix:** the v2 create response is lean/flat (`fill_count`, `remaining_count`; no `order` wrapper, no `status`) vs the cancel/get/list schema (`fill_count_fp`, `remaining_count_fp`). New `_order_field()` helper in `kalshi_executor.py` reads both, so `log_trade` and the fill display record fills correctly instead of always reporting "resting" (which would have corrupted exposure/P&L accounting).

### Verification

Unit: +8 order-body tests (`tests/test_kalshi_client_order.py`, incl. the NO→ask inversion) + 4 v2-response tests (`tests/test_fill_accounting.py`) → **442 passing** (was 430). Live: placed two resting 1-contract orders on a World Cup market and canceled both — YES→`bid`@$0.01 (`outcome_side: yes`) and NO→`ask`@$0.99 confirmed by Kalshi as `outcome_side: no`, `no_price_dollars: 0.0100`. Both canceled; no residual exposure.

### Files

`scripts/kalshi/kalshi_client.py`, `scripts/kalshi/kalshi_executor.py`, `tests/test_kalshi_client_order.py` (new), `tests/test_fill_accounting.py`, `docs/CHANGELOG.md`.

---

## 2026-06-20 -- World Cup (FIFA) Sport Coverage Added

### Why

Wagers had dropped to ~0/day since ~June 13. Diagnosis: the pipeline is healthy — it's a **seasonal trough**. A live scan showed NBA/NHL/NCAA/European-club-soccer all out of season, leaving MLB as the only active daily sport (and books only post MLB lines ~1 day out, so future-dated Kalshi games correctly emit no edge). Meanwhile the **2026 FIFA World Cup is live** with deep Kalshi markets and an active Odds API feed — but the scanner had no mapping for it, so it was invisible. (WNBA, NCAA baseball/CWS, and Wimbledon were also considered; user chose World Cup now, Wimbledon deferred to ~June 28 when its markets/odds go live, NCAA baseball skipped as the CWS window closes within days.)

### What landed

- **World Cup wired as a soccer sport** — reuses the existing 3-way (home/draw/away) soccer edge logic with **zero changes to edge math**. `KXWCGAME`/`KXWCSPREAD`/`KXWCTOTAL` added to `CATEGORY_MAP` (game/spread/total) and `KALSHI_TO_ODDS_SPORT` (→ `soccer_fifa_world_cup`); `KXWC` → `soccer` in `_PREFIX_TO_SPORT` (margin/total stdev). New `worldcup`/`wc` filter shortcuts + folded into the combined `soccer` group. Because the no-filter scan iterates `KALSHI_TO_ODDS_SPORT`, World Cup auto-joins the daily scheduled scans with no `.bat` change.
- **Team extraction needed no change** — WC rules read "...the Congo DR vs Uzbekistan **professional** FIFA World Cup soccer game...", and `professional` is already a recognized context keyword, so `extract_event_teams` resolves country names that match the Odds API feed.
- **Display fix (country-code collision):** WC tickers use 3-letter country codes that collide with the US-sports alias map (`COL`=Colombia mis-rendered as "Colorado"). Added `_resolve_team_abbr()` in `ticker_display.py` that keeps the raw code for `KXWC*` tickers; used in both the pick-label (spread) and `parse_pick_team` (game) paths. Edge math was always correct (matches on the full name from rules); this was display-only.

### Verification

Live preview scan returned **40 World Cup opportunities** (34 spread, 6 total; edges to +14.7%, score 8.2). Moneyline produced none above 3% — expected, as 3-way match-winner prices are efficient. +6 tests (`TestWorldCupMappings` in `tests/test_edge_detection.py`; 2 country-code label tests in `tests/test_ticker_display.py`) → **430 passing** (was 424).

### Files

`scripts/kalshi/edge_detector.py`, `scripts/shared/ticker_display.py`, `tests/test_edge_detection.py`, `tests/test_ticker_display.py`, `CLAUDE.md`, `docs/kalshi/kalshi-sports-betting/SPORTS_GUIDE.md`, `docs/CHANGELOG.md`.

---

## 2026-06-15 -- R27: "Started" Column Flags In-Progress Games on Scan Views

### Why

F44 (2026-06-14): a web-UI scan CSV advertised phantom edges — +50.6% on a $0.04 "Washington lose" longshot, +34.8% on HOU@KC — while the post-start CLI priced the same games at +8–10%. Root cause: a game that has already started keeps producing edges (its market is still open) because the only "skip in-progress" filter in `edge_detector.py` keys on `expected_expiration_time`, which is the market **close** (after the game *ends*), not the start. So the scan view compares **live** Kalshi pricing against **stale** pre-game odds. Execution gates already protect real bets; the raw research/CSV surface did not.

### What landed

- **New `Started` column** on every sports scan view, showing `LIVE` for games already underway. **Tag, not exclude** — games stay visible (operator's call) so the edge is shown *with* the caveat rather than silently dropped.
- **New canonical helpers** in `scripts/shared/ticker_display.py`: `ticker_scheduled_utc(ticker)` and `is_game_started(ticker, now=None)`. They mirror the hardened `edge_detector._ticker_scheduled_utc` event-matching logic (ET wall-clock → UTC via a fixed 4h offset; a 1h EST/EDT slip is immaterial for "has it started?"). **HHMM-only** — only moneyline (GAME) tickers embed a start time (the F44 case); spread/total and NBA/NHL tickers carry date only, so `is_game_started` returns `False` rather than risk a false flag. The edge_detector matching path was left untouched to avoid regression risk.
- **Wired into four surfaces:** CLI Rich table (`edge_detector.print_opportunities`), webapp dataframe + CSV (`services.opportunities_to_rows` + `scan_page` column config), saved markdown scan report (`report_writer`), and the emailed `daily_sports_scan` table. No CLI flag and no change to `scan_all_markets` — tagging is a pure display concern, so CLI and webapp inherit it for free.
- **Tightened the misleading comment** at `edge_detector.py:1760` that called the expiration filter a "started/ended" filter — the source of the F44 confusion.

### Verification

+13 tests in `tests/test_ticker_display.py` (`TestTickerScheduledUTC` + `TestIsGameStarted`) → **424 passing** (was 411). Live smoke confirmed past/future/date-only tickers flag correctly.

### Files

`scripts/shared/ticker_display.py`, `scripts/kalshi/edge_detector.py`, `webapp/services.py`, `webapp/views/scan_page.py`, `scripts/shared/report_writer.py`, `scripts/schedulers/automation/daily_sports_scan.py`, `tests/test_ticker_display.py`, `docs/my-documents/enhancements/ROADMAP.md`, `docs/CHANGELOG.md`.

---

## 2026-06-14 -- Per-Sport Edge Floors Lowered 0.06 → 0.04 + Doc-Drift Sweep

### Why

User reported MLB wagers had dried up to ~0/day across the schedulers since the 06-03 fixes. June is almost entirely an MLB slate (NBA/NHL seasons winding down), so a throttled MLB made the whole pipeline look dead. Diagnosis confirmed MLB games are still found and matched correctly — the binding constraint is the **edge gate**, not confidence or score.

### Root cause — a double-correction

Two changes landed together on 2026-06-03/06-05 and stacked:

1. **Edge-matching correctness fixes** (opponent+date validation, strength-rank team matching) **de-inflated** MLB edges. The 06-03 report had phantom edges of +15% and +31%; honest post-fix edges now cluster at **3–6%** (live repro on 06-14 showed real MLB edges of 4.0%, 4.3%, 5.3%, ~8%).
2. **The per-sport edge floor** was set high *because* "the model over-claims ~15% edge" — but that over-claim **was** the matching bug, now fixed upstream. The floor was correcting the same error a second time, rejecting the honest 3–6% edges that remained.

### What landed

- **Lowered `MIN_EDGE_THRESHOLD_MLB`, `_NBA`, `_NCAAB` from 0.06 → 0.04** (live `.env`). Re-admits honest 4–5% edges. Running as a **2–4 week experiment** — recalibrate on fresh post-fix data (weekly `Calibration` + monthly run accumulate it) and tune from there. If 4% loses money, tighten back up on real evidence rather than the contaminated pre-fix numbers.
- **Doc-drift sweep.** Discovered the docs had been citing values that were never even the live 0.06: CLAUDE.md said NBA/NCAAB/MLB **0.08** and `MIN_MARKET_PRICE` **$0.10**; ARCHITECTURE.md / SETUP_GUIDE.md / CLOUD.md / kalshi_executor.md / the edge-radar skill variously cited NBA **0.12**, NCAAB **0.10**. Production had quietly been running 0.06. Standardized every current-state reference to the live values: **per-sport 0.04**, **`MIN_MARKET_PRICE` $0.06**. Historical CHANGELOG entries (R14, R7) left intact as record.
- **Webapp** — `scan_page.py` Min Edge help tooltip corrected (it hardcoded "NBA/NCAAB/MLB 8%" + "$0.10 floor"; the rest of the webapp reads floors dynamically from `.env` via `app.config`, so no logic change was needed).

### Files

`.env` (live floors, gitignored), `CLAUDE.md` (commit `3cf78b8`), `webapp/views/scan_page.py` (commit `1335267`), `docs/ARCHITECTURE.md`, `docs/setup/SETUP_GUIDE.md`, `docs/web-app/CLOUD.md`, `docs/scripts/kalshi_executor.md`, `.claude/skills/edge-radar/SKILL.md`, `docs/CHANGELOG.md`, plus memory (`project_edge_matching_validation.md`).

---

## 2026-06-05 -- Same-City Team-Match Inversion Fix (phantom NO-side edge)

### Why

A spot-check of why zero wagers had been placed for several days (Jun 2–5) confirmed the quiet stretch was *correct* — a thin early-June calendar (MLB plus two Finals series whose future games aren't priced yet) combined with the per-sport 0.08 edge floors and the `--min-bets 3` batch gate legitimately produces no qualifying batches. **But** the check surfaced the day's top-ranked opportunity (composite 8.3): a **+27.9% edge on "LA Dodgers lose"** in the Jun 5 Angels @ Dodgers game. That edge was entirely fabricated.

### Root cause

Kalshi truncates its market sub-titles, so the Dodgers-win market's subject reads `"Los Angeles D"` (not "Dodgers"). `_team_match` matched that against the odds event's two outcomes via a **first-match-wins** loop, and its weakest fallback rule (`kalshi_words[0]` — the city word "los") matched **both** "Los Angeles Angels" and "Los Angeles Dodgers". The loop took whichever outcome the odds feed listed first — the away Angels — so the Dodgers market was priced with the **Angels'** win probability (0.36), inverting the favorite. The "Dodgers lose" NO side (market $0.36) was then compared against `1 − 0.36 = 0.64`, manufacturing a +27.9% edge where the true edge is ~0%. Any same-city matchup where the nickname truncates was exposed; the team listed **second** in the feed was the one corrupted.

This is **not** the 2026-06-03 contamination bug — the correct game and date matched fine. It is wrong *side selection within the right event*, which that fix didn't cover.

### What landed

- **Strength-ranked, tie-refused team matching** (`scripts/kalshi/edge_detector.py`). New `_team_match_strength()` scores candidates: substring/alias (tier 3/2) > shared nickname (tier 2) > bare city word (tier 1). New `_match_team_outcome()` picks the **unique** strongest outcome and returns "ambiguous → no edge" on a genuine tie (e.g. a bare-city reference). `_team_match()` is preserved as `strength > 0`, so all other callers are byte-for-byte unchanged.
- **Applied to both team-keyed consensus functions** — `consensus_fair_value` (moneyline) and `consensus_spread_prob` (which was *worse*: it pooled **both** teams' spreads into one median when ambiguous). `consensus_total_prob` takes no team and was already safe.
- **Verified live** — the Dodgers market now prices at fair 0.639 (the actual favorite), edge collapses from +27.9% to ~0%; the phantom pick is gone from the scan.
- **Tests** — +5 regression tests (`TestSameCityDisambiguation`): strength ordering, unique-pick, city-only ambiguity refusal, correct LA-team resolution, and the end-to-end no-phantom-edge assertion. 403 → **408 passing**.

### Separate finding (not changed — flagged for decision)

The same spot-check found a **stale-offshore-line** weakness, unrelated to the matching bug: in Jun 5 Tampa Bay @ Miami, five sharp books had Miami devigged at ~0.20–0.28 while four offshore books (betonlineag, lowvig, mybookieag, betus) carried stale ~0.46 lines. The weighted median landed on the high cluster (fair 0.46, range 0.20→0.47), producing a +24.7% edge driven by book disagreement rather than value. Moneyline consensus has no disagreement penalty beyond withholding the "high" tier. Candidate future work: reject or down-weight when `max_fair − min_fair` is large.

### Files

`scripts/kalshi/edge_detector.py`, `tests/test_edge_detection.py`, `docs/scripts/edge_detector.md`, `docs/CHANGELOG.md`, plus memory (`project_edge_matching_validation.md`).

---

## 2026-06-03 -- Edge-Matching Contamination Fix, Soccer 3-Way, Test-Isolation Guard

### Why

A user spot-check after seeing implausible MLB edges (e.g. "+34.7% Minnesota lose") exposed a cross-game contamination bug in edge detection: `consensus_fair_value`/`consensus_spread_prob`/`consensus_total_prob` matched a Kalshi market against **any** odds event a single team appeared in. When a team played a series, or its game was simply absent from the feed (e.g. scanning two days out before books post lines), the detector priced the market against the **wrong game** — wrong opponent, or the wrong game of a playoff series with home/away flipped — fabricating large edges. Two NBA Finals open positions had been sized off this.

### What landed

- **Opponent + date validated matching (`find_market_event`)** — a market is priced only against the odds event that contains **both** its teams on opposite sides **and** agrees on schedule: moneyline (GAME) tickers match the embedded start time (within 6h); spread/total and NBA/NHL date-only tickers require exactly one candidate on the ticker's ET game date. Absent or ambiguous ⇒ **no edge** (never guess). Fixes both variants — wrong-opponent and the playoff-series single-event home/away flip (the old `len(candidates)==1` shortcut skipped date validation). `extract_event_teams` also strips the "Game N:" playoff prefix and the "teams in the" totals filler.
- **Belt-and-suspenders** — the three `consensus_*` functions now refuse (return None + warn) if their subject matched >1 distinct event, so a team is never pooled across games even if a caller forgets to pre-scope.
- **Soccer 3-way support** — `consensus_fair_value` skipped any market without exactly 2 outcomes, so soccer h2h (home/draw/away) silently produced **no** edges. Now uses proportional devig over 2- or 3-outcome markets; the Kalshi "team to win?" binary takes the team's devigged win share (draw → NO side). 2-way behavior unchanged.
- **MLB edge floor + threshold-drift correction** — added `MIN_EDGE_THRESHOLD_MLB=0.08` (MLB: 40% WR, -12% ROI, model over-claims ~15% edge). Corrected long-standing doc drift: R14's NBA 0.12 was **proposed but never adopted** — production runs 0.08. NBA/NCAAB/MLB now consistently documented at the 0.08 peer floor across `.env.example`, `CLAUDE.md`, and the edge-radar skill.
- **Calibration recommendation refresh** — `model_calibration.py`'s top "Confidence Signals" recommendation kept re-recommending one-way confidence bumps that already shipped as R13 (2026-04-24). Rewritten to say R13 shipped and point at the real remaining suspect: the base ">=8 sharp-books + tight-consensus" high-tier rule.
- **Test-isolation incident + guard** — `log_trade()` persists via `save_trade_log()` as a side effect, and `test_fill_accounting` calls it with an ad-hoc list, so a full `pytest` run overwrote the live `data/history/kalshi_trades.json` with a test record. Added an autouse `conftest.py` fixture redirecting the trade/settlement log paths to a per-test tmp dir (the suite now leaves both real logs byte-identical). New `scripts/kalshi/recover_trade_log.py` rebuilt the log from live Kalshi positions (15 positions, $22.03 restored; model fields like `edge_estimated` unrecoverable, set null — not needed for settlement P&L).
- **Tests** — +17 regression tests (contamination scenario, series disambiguation, wrong-date refuse, the consensus refuse-guards, 3-way soccer devig). 386 → **403 passing**.

### Caveat

The contamination likely inflated some **historical** claimed edges (MLB and consecutive-day/playoff series). Re-run calibration after ~2 weeks of clean post-fix settlements before drawing edge-bucket conclusions.

### Files

`scripts/kalshi/edge_detector.py`, `scripts/kalshi/model_calibration.py`, `scripts/kalshi/kalshi_executor.py` (docstring), `scripts/kalshi/recover_trade_log.py` (new), `tests/conftest.py`, `tests/test_edge_detection.py`, `tests/test_risk_gates.py`, `.env.example`, `CLAUDE.md`, `docs/scripts/edge_detector.md`, `docs/ARCHITECTURE.md`, `docs/SCRIPTS_REFERENCE.md`, `docs/kalshi-sports-betting/SPORTS_GUIDE.md`, `.claude/skills/edge-radar/SKILL.md`, `docs/CHANGELOG.md`, plus memory. Live `.env` (gitignored) carries the MLB override; rebuilt `data/` files are gitignored.

### Commits

`e28d157` (matching A+B), `40c3711` (test guard + recovery tool), `c066c03` (MLB floor + drift + calibration rec), `ca1d124` (series-flip date validation), `e1960ec` (soccer 3-way) on `mike_win-desktop`. This entry is the docs/memory propagation.

---

## 2026-05-31 -- Account-Growth Graph on the Pages Site (+ weekly auto-refresh)

### Why

The Kalshi account-growth graph (`/update-account-graph`) only existed locally under the gitignored `docs/my-documents/account-graph/latest/`, so it never reached the public dashboard at `edge-radar.mikesailab.com`. Wanted it one click away from the homepage, kept current automatically.

### What landed

- **Orange "Live P&L" button** in the `index.html` hero, next to the emerald *Open the app* and blue *Source* CTAs. Links to the graph with `rel="nofollow noopener"`.
- **Publish path** — the deploy workflow serves only `.claude/html/`, so the graph is copied there as `account-40c3eb1d3d3cb9c4e07fee61.html` (unguessable name). The site is public + unauthenticated, so this is *lightly hidden, not protected*: real dollar figures are visible to anyone with the link. A `<meta name="robots" content="noindex, nofollow">` tag (added to the generator's `render_html()`) keeps it out of search indexes.
- **Weekly auto-refresh** — `scripts/schedulers/automation/refresh_account_graph.py` pulls the live Kalshi snapshot, regenerates HTML + PNG, copies the HTML into `.claude/html/`, then pushes **only that one file** to `master` via the `gh` contents API (which fires the Pages deploy). Generation must run locally because it needs the `.env` Kalshi keys and the gitignored local settlements ledger. The push is best-effort and logs to `logs/account_graph_refresh.log`; it never touches the `mike_win-desktop` working branch.
- **Scheduler** — new `account-graph` profile in `install_windows_task.py` (Sundays 9 AM PT), plus `WEEKLY` schedule support added to the installer. Install with `python scripts/schedulers/automation/install_windows_task.py install account-graph`.
- **`.gitignore`** — `.claude/html/account-*.html` is ignored so the weekly out-of-band master commit is the file's sole manager and never collides with branch PRs.

### Files

`.claude/html/index.html`, `scripts/schedulers/automation/refresh_account_graph.py`, `scripts/schedulers/automation/install_windows_task.py`, `.gitignore`, `docs/CHANGELOG.md`. Local-only (gitignored): `docs/my-documents/account-graph/Script/build_account_graph.py` (noindex tag), `docs/my-documents/account-graph/README.md`, `docs/my-documents/task-schedules/README.md`.

---

## 2026-05-15 -- Pages Site Theme Alignment with mikesailab.com

### Why

The Pages site at `edge-radar.mikesailab.com` was visually disconnected from the parent `mikesailab.com` site — neon-teal accents, gradient hero, pulsing dot, three custom fonts (Outfit + Inter + JetBrains Mono), 545 lines of bespoke CSS. The parent site is the opposite: Tailwind, Inter, zinc/black, flat surfaces, no glow. Two sibling sites should look like siblings, especially because `mikesailab.com` already has an Edge-Radar "Live Sites" tile rendered with the parent palette + emerald accent. The Pages site now matches that vocabulary so a visitor jumping from one to the other doesn't get whiplash.

### What landed

- **`.claude/html/index.html`** — full rewrite. Replaced 545 lines of custom CSS with Tailwind CDN + Inter (single font; `ui-monospace` for `<pre>` blocks). Palette: `bg-[#060606]` background, `zinc-100/400/500/600` text, `zinc-900/40` surfaces with `border-zinc-800/60`. **Emerald** (low opacity) as Edge-Radar's accent — same color the parent site already uses on its Edge-Radar radar tile, and matches the favicon's `#10b981`. **Sky-400** small `● Live` pill in the eyebrow, matching the parent site's "Live Sites" convention. Hero gradient text + 900px radial glow gone; pulsing dot gone; multi-color pill palette (purple/orange/red) gone. 978 lines → 253 lines.
- **Mobile CTA fix** (`3736f67`) — the original 2-column grid clipped the `edge-radar.streamlit.app` label inside the emerald primary tile on narrow viewports. Switched to `flex-col sm:flex-row` so each CTA gets full width on mobile, with `min-w-0` + `truncate` as a safety net.
- **Quick Links refresh** — dropped `Reports tree` (the `reports/` directory is gitignored, so the GitHub link 404s for anyone who isn't me). Added two: `/edge-radar` skill link (`.claude/skills/edge-radar/SKILL.md`) and `Scripts Reference` (`docs/SCRIPTS_REFERENCE.md`). Now 6 tiles total — fits cleanly as 2×3 on desktop, 3×2 on tablet, 6 stacked on mobile.
- **`.claude/backup/index.html.backup-2026-05-15`** — snapshot of the prior teal-themed dashboard, captured per the documented backup convention (memory line 53 of `reference_mikesailab_domain.md`). `.claude/backup/README.md` updated with the new row.
- **Memory** — `reference_mikesailab_domain.md` got a new "Theme alignment with mikesailab.com (2026-05-15)" section documenting the palette + framework decision, plus the Quick Links count updated from 5 to 6 in the page-contents section.

### Where the deploy actually lives (unchanged)

Still GitHub Pages via `.github/workflows/deploy.yml`, fed from `.claude/html/` on `master`. Both commits sit on `mike_win-desktop` ahead of `master`; the deploy workflow's path filter (`.claude/html/**`) will fire automatically when the user merges to master.

### Files

`.claude/html/index.html`, `.claude/backup/index.html.backup-2026-05-15`, `.claude/backup/README.md`, `docs/CHANGELOG.md`, `memory/reference_mikesailab_domain.md`.

### Commits

`e20c739` (theme rewrite) and `3736f67` (mobile CTA fix + quick link refresh) on `mike_win-desktop`. This entry is the third commit in the trio (the docs/memory propagation).

---

## 2026-05-13 -- R11 Explicit Direction Fields in Settlement Schema

### Why

The settlement record's `fair_value` field carried bet-side perspective by convention, but pre-R5 entries written before the convention was tightened mixed YES- and NO-perspective values without a tag. Any post-hoc analysis that wanted to compare probabilities across bets had to read `side` separately and flip — easy to get wrong, impossible to audit. R11 makes the perspective explicit at write time so future analytics work isn't a guessing game.

### What landed

- **`scripts/kalshi/kalshi_settler.py`** — new `_compute_fair_value_yes(trade) -> (float | None, str | None)` helper. Returns YES-perspective probability and explicit side tag; refuses to guess when `side` is missing. Wired into `build_settlement_record()`. Two new keys on every settlement going forward: `fair_value_yes` (always YES-perspective) and `fair_value_side` (perspective tag for the legacy `fair_value` field). Legacy `fair_value` unchanged — `model_calibration.py`'s bet-side reader is untouched since it's been correct since R5; a YES-perspective cross-cut on the calibration loader is left for a future task when the post-R11 cohort has enough sample to warrant it.
- **`tests/test_reconciliation.py`** — new `TestComputeFairValueYes` class with the four boundary cases: YES bet preserves value, NO bet flips to `1-fv`, missing side yields `(None, None)`, missing fair_value with side present yields `(None, side)`. New `test_carries_r11_perspective_fields` on `build_settlement_record` and an extended assertion on the missing-optional-fields shape test (verifies the new keys are always present, not just sometimes-missing). **386 tests passing** (was 381, +5).
- **`data/history/README.md`** — documented the two new fields and the pre-R5/R11 perspective ambiguity. Reaffirmed the no-backfill stance: the underlying side resolution isn't reliably recoverable on the 178 pre-R5 orphans and synthesizing the field would be fabricating data.
- **`docs/my-documents/enhancements/ROADMAP.md`** — removed R11 row from P2 table; new Completed entry under `2026-05-13`; header note updated.

### Deliberately not in scope

- **No calibration-loader change.** `model_calibration.py:127-128` already assumes bet-side perspective and that assumption is correct for the post-R5 cohort. Switching it to consume `fair_value_yes` would be its own ship; doing it now would change Brier numbers across the rolling window without a clear before/after measurement story.
- **No backfill.** Same rationale as R5 — the missing fields don't exist anywhere on disk.

### Files

`scripts/kalshi/kalshi_settler.py`, `tests/test_reconciliation.py`, `data/history/README.md`, `docs/my-documents/enhancements/ROADMAP.md`, `docs/CHANGELOG.md`.

---

## 2026-05-08 -- Pages Site Privacy Pass + Streamlit Cross-Link

### Why

The Streamlit dashboard at `edge-radar.streamlit.app` is functionally complete and the user wants it discoverable from the personal GitHub Pages diagram site at `edge-radar.mikesailab.com` — but **not** advertised from the public GitHub repo. Three things had to land at once: scrub the README of every link that points strangers at the deployed instance, add the cross-link on the Pages site below its hero, and document the previously-unwritten fact that the Pages deploy is workflow-driven from `.claude/html/` (not from the orphan `gh-pages` branch).

### What landed

- **`README.md`** — removed five outbound advertisements: the `Dashboard` shields.io badge, the `Data Flow` shields.io badge, the centered hero banner pointing at the data-flow diagram, the inline pointer above the Mermaid graph, and the `Local Dashboard` + `Cloud Dashboard` rows from both the Next Steps and Documentation tables. The README no longer surfaces `mikesailab.com`, `michaelschecht.github.io/Edge-Radar/`, or `edge-radar.streamlit.app` to drive-by GitHub visitors. The `webapp/` and `.github/workflows/` lines in the architecture diagram stay — those describe code structure, not advertising.
- **`docs/ARCHITECTURE.md`** — same scrub: dropped the "View the interactive data-flow diagram" callout that pointed at the GitHub Pages site.
- **`.claude/html/index.html`** — added a small JetBrains Mono `↗ edge-radar.streamlit.app` link directly under the hero stats, styled with `var(--accent)` so it inherits the existing emerald accent and the underline picks up `var(--accent-dim)` for hover affordance. Sits inside `<section class="hero" id="overview">` so it visually closes the title block. Triggers the `Deploy to GitHub Pages` workflow on merge to master via the `.claude/html/**` path filter.
- **`webapp/theme.py`** — _briefly_ rendered the same link from `page_header()` as a misread of the user's intent (assumed `mikesailab.com` was a Streamlit deployment with a custom domain; it's actually GitHub Pages). Reverted in `8b8854e` once the hosting model was clarified — the Streamlit app linking to itself was a no-op self-link.

### Where the deploy actually lives (corrects a bad assumption)

`mikesailab.com` is a custom CNAME on GitHub Pages, **not** a Streamlit Cloud custom-domain deployment. The current Pages config is `build_type=workflow` with source `gh-pages /` — but the `gh-pages` branch is vestigial. The live site is built and uploaded by `.github/workflows/deploy.yml`, which runs on pushes to `master` that touch `.claude/html/**` and uploads the entire `.claude/html/` directory as the Pages artifact. Direct commits to the `gh-pages` branch (such as the dead `e388f5f` commit on that branch from earlier in this session) are ignored by the deploy. Future edits to the diagram site go through `.claude/html/index.html` on master, full stop.

### Files

`README.md`, `docs/ARCHITECTURE.md`, `docs/CHANGELOG.md`, `.claude/html/index.html`, `webapp/theme.py` (revert).

---

## 2026-05-01 -- Account Snapshot Chart (Snapshot Mode for `edge-radar-analysis`)

### Why

Visual companion to the markdown betting analysis. After each Kalshi balance pull the user wants to see cumulative account growth — deposit baseline through today's live total — in one re-runnable artifact, with the same sport / bet-type / side / confidence breakdowns the analysis report already produces. Markdown tables answer "how am I doing"; a chart answers "what does the growth curve look like, and where is the open-position value sitting today."

### What landed

- **`docs/my-documents/account-graph/Script/build_account_graph.py`** (local-only, gitignored) — self-contained Plotly HTML builder. Reads `data/history/kalshi_settlements.json`, parses sport + bet-type from the `KX<SPORT><BET_TYPE>-…` ticker prefix (works across the full 178-bet pre-R5 cohort whose `category` field is `null` on disk), aggregates daily P&L, and writes a single CDN-loaded HTML page — no install step.
- **CLI args:** `--cash`, `--portfolio`, `--positions` required; `--as-of`, `--deposit`, `--deposit-date`, `--out-dir`, `--settlements` optional. Each run also writes a `snapshot.json` next to the HTML capturing every input + summary stats so the chart is byte-reproducible from the snapshot file alone.
- **Folder convention:** `docs/my-documents/account-graph/Script/` for the builder, `docs/my-documents/account-graph/<M-D-YY>/` for each run's output. The dated subfolder is auto-derived from `--as-of` so historical snapshots are preserved automatically — no manual rename or move step.
- **Live point handling:** the historical line uses the settled-only model (deposit + cumulative settled P&L) since open-position market value isn't observable for past days. The `--as-of` day is anchored to the actual `cash + portfolio` total and rendered as a gold star on the chart; hover surfaces the cash / open-position / settled-only split. The "open-position drift" reported in the footer is the unrealized value sitting in open positions on the snapshot date.
- **`.claude/skills/edge-radar-analysis/SKILL.md`** (tracked) — extended with a new "Account Snapshot Chart" section documenting trigger phrases ("snapshot the account", "regenerate the account graph", "build the account chart"), required inputs, run command, optional flags, and execution steps. Skill description + argument-hint also expanded so dispatch routes correctly.

### Verification

- Smoke-tested with the user's 2026-05-01 portfolio status pull (cash $65.88, portfolio $27.54, 23 open positions): builder writes `account_graph.html` + `snapshot.json` to `5-1-26/`, settled-only balance reconciles to $78.04 (deposit $45.50 + settled P&L $32.54 across 178 bets), live total $93.42, open-position drift $15.38.
- Path resolution survives the `Script/` subfolder hop: `REPO_ROOT = SCRIPT_DIR.parents[3]`, `default_out_dir` writes to `ACCOUNT_GRAPH_DIR / <M-D-YY>` (one level above `Script/`) instead of nesting.

### How to use

```bash
# Pull live portfolio first
python scripts/kalshi/risk_check.py --report positions

# Then build the chart (auto-named M-D-YY folder)
python docs/my-documents/account-graph/Script/build_account_graph.py \
  --cash 65.88 --portfolio 27.54 --positions 23

# Or via the skill — natural-language triggers route to snapshot mode
# "snapshot the account" / "regenerate the account graph" / "build the account chart"
```

### Files

`.claude/skills/edge-radar-analysis/SKILL.md`, `docs/CHANGELOG.md`. Local-only (gitignored): `docs/my-documents/account-graph/Script/build_account_graph.py`, `docs/my-documents/account-graph/README.md`, `docs/my-documents/account-graph/<M-D-YY>/account_graph.html`, `docs/my-documents/account-graph/<M-D-YY>/snapshot.json`.

---

## 2026-04-30 -- U2: Daily P&L Email Digest

### Why

The R12-R26 P1 wave shipped through 2026-04-29 leaves Priority 1 empty. Between monthly R12 calibration runs (the next attribution checkpoint) the user has no daily wake-up signal — the evening Weekly-Analysis runs Sun-only, and the existing morning emails are forward-looking execution reports, not retrospective P&L. U2 fills that gap: a morning digest that lands before the 5:05 AM same-day execute so the user sees what happened yesterday + what's still on the books before today's bets get placed.

### What landed

- **`scripts/kalshi/daily_summary.py`** — pure-functions report generator. Joins yesterday's settlements (rolling 24h window, robust to DST) with currently open trade-log positions, today's pending events, and an optional live Kalshi balance. Sections:
  - **Yesterday** — N settled, W-L, P&L, ROI, per-sport breakdown table, top-win + top-loss callouts
  - **Open Exposure** — count + $ at risk + per-sport split (excludes `closed_at`, `fill_status=resting`, `status=error`, zero-fill)
  - **Pending Today** — open positions whose game datetime parses to today's PST calendar day (via `parse_game_datetime` from `ticker_display`)
  - **Context** — live Kalshi balance + 7-day rolling line (WR, P&L, ROI, Brier; flips probability for NO-side bets so it's directly comparable to the calibration report)
- **Empty-day proof-of-life** — every section still renders with `_No settlements in window._` / `_No open positions._` placeholders. Matches `feedback_sameday_empty_emails`: empty digest = "the system ran" signal, never silent.
- **Architecture** — clean split between pure functions (`load_recent_settlements`, `aggregate_yesterday`, `aggregate_exposure`, `filter_pending_today`, `rolling_7d_context`, `render_report`) and I/O wrappers (`_fetch_balance` swallows all Kalshi-API failures gracefully, `--save` filesystem write). `build_report()` is the test-friendly composition entry point.
- **Window choice — rolling 24h not "yesterday in PST".** Robust to DST transitions, captures the 11 PM PST settler's late-night settlements, and survives wall-clock weirdness. Defaultable via `--hours` for ad-hoc runs.
- **Two new scheduled tasks** under `\Edge-Radar\`:
  - `Daily-Summary` (Daily 4:50 AM PT) — runs `scripts/schedulers/maintenance/daily_summary.bat` → `daily_summary.py --save`
  - `Email-Daily-Summary` (Daily 5:00 AM PT) — runs `scripts/custom/Shell-Scripts/Run-Reports/Daily-Summary-Report.sh` (mirrors the existing email pattern: `claude --dangerously-skip-permissions -p` subprocess + `agentmail` skill, dark-themed HTML, skip-on-missing-report)
- **Timing rationale** — 4:50 AM PT is the slot before `All-Sports-SameDay-Execution` (5:05 AM) so "Open Exposure" reflects overnight carry rather than mixing in today's new fills. The 10-min email buffer matches the `Weekly-Analysis` precedent (the underlying report is fast — no API fetches except a single optional balance call).

### Verification

- 26 new tests in `tests/test_daily_summary.py` covering: window-boundary inclusion (`>=` cutoff), malformed-timestamp skip, sort order, open-position filtering (closed/resting/error/zero-fill), per-sport aggregation math (NBA + MLB), pending-today PST filtering across day boundaries, 7-day rolling minimum-sample threshold (5-bet floor), balance present + missing rendering, full empty-day report renders all four sections.
- **381 tests passing** (was 355). Lint clean.
- End-to-end smoke confirmed: `.bat` ran cleanly, fetched live Kalshi balance ($66.85), wrote `reports/Performance/daily_summary_2026-04-30.md` with all four sections (empty-day proof-of-life intact). Real-data round-trip with `--hours 720` showed the 173 historical settlements aggregating correctly: NHL +72.9% ROI on 44 bets, MLB -5.1% on 39, NBA -14.8% on 17 (matches the canonical 30-day numbers).

### Follow-up

A one-shot Windows scheduled task `\Edge-Radar\U2-Review` will fire on **2026-05-14 07:00 PT** (`scripts/schedulers/maintenance/u2_2week_review.bat` → `u2_2week_review.py`). It scans `reports/Performance/daily_summary_*.md` for the prior 14 days to surface firing-reliability and section-coverage stats (which sections were consistently empty across the window — candidates for trimming), then spawns a `claude --dangerously-skip-permissions -p` subprocess to do a fresh-eyes code review of `daily_summary.py` + tests with explicit instructions to be opinionated about what to drop. Output combines local-verifiable signals + model findings + an operational checklist for the user to fill in (which sections they actually read each morning, any rendering issues, anything missing) into `reports/Performance/u2_2week_review_<date>.md`. Pure analysis — never modifies code or opens PRs. Migrated to local Windows Task Scheduler (consistent with the rest of `\Edge-Radar\` and the R8-Review precedent) instead of a remote claude.ai routine — the firing-reliability signal lives only on the user's machine since `reports/Performance/` is gitignored, so a remote agent literally couldn't see it. Original remote routine `trig_01Q6iNTVkob15MewHYS5CKYH` disabled but kept for record. Doc: `docs/my-documents/task-schedules/README.md` § 15.

### How to use

The script is invoked automatically by the scheduled task. To run manually:

```bash
# Default — yesterday's 24h window, save to reports/Performance/
.venv/Scripts/python.exe scripts/kalshi/daily_summary.py --save

# Custom window
.venv/Scripts/python.exe scripts/kalshi/daily_summary.py --hours 48 --save

# Skip the live Kalshi balance fetch (offline-safe)
.venv/Scripts/python.exe scripts/kalshi/daily_summary.py --no-bankroll --save

# Manual scheduled-task trigger
schtasks /run /tn "\Edge-Radar\Daily-Summary"
schtasks /run /tn "\Edge-Radar\Email-Daily-Summary"
```

### Files

`scripts/kalshi/daily_summary.py` (new), `tests/test_daily_summary.py` (new), `scripts/schedulers/maintenance/daily_summary.bat` (new, gitignored), `scripts/custom/Shell-Scripts/Run-Reports/Daily-Summary-Report.sh` (new, gitignored), `scripts/schedulers/maintenance/u2_2week_review.py` (new, gitignored — fires 2026-05-14), `scripts/schedulers/maintenance/u2_2week_review.bat` (new, gitignored), `docs/my-documents/task-schedules/README.md` (new entries 0a/0b/15 + install snippets, gitignored), `docs/my-documents/enhancements/ROADMAP.md` (gitignored), `CLAUDE.md`, `README.md`, `.claude/skills/edge-radar/SKILL.md`, `.claude/skills/edge-radar-analysis/SKILL.md`, `docs/CHANGELOG.md`.

---

## 2026-04-29 -- R8: Cross-Category Same-Event Dedup (Optional, Per-Sport)

### Why

The existing `dedup_correlated_brackets()` keys by `(event_key, category)`, which catches alt-line brackets within a category (3× Over lines on the same NBA game collapse to one) but treats ML + Total + Spread on the same game as 3 distinct bets. F11 (14-day review) flagged 12 matchups bet ≥2× in 14d, several same-day on different categories — when an NBA game blows out, the ML + Spread + Total all win or lose together, so stacking three categories adds correlation, not diversification. Cross-category correlation is sport-dependent (NHL low-scoring → ML and Total weakly correlated; NBA blowouts → all three move together), so this needs to be opt-in per sport rather than a global flip.

### What landed

- **`dedup_correlated_brackets()`** in `scripts/kalshi/kalshi_executor.py` now accepts `cross_category_sports: set[str] | None`. When an opportunity's detected sport is in the set, the dedup key becomes `("_xcat", sport, game_id)` where `game_id` is the date+teams middle segment of the ticker (e.g. `26APR24SASPOR` from `KXNBATOTAL-26APR24SASPOR-208`). All categories on the same game collapse to the highest-composite row. Futures pass-through (R21) is checked first and immune.
- **Why a separate game_id**: `_event_key()` strips only the trailing hyphen segment, so `KXNBAGAME-…` and `KXNBATOTAL-…` produce different event keys (different prefixes). Splitting on `-` and taking `parts[1]` is identical across categories for the same game.
- **Config**: new `GateThresholds.cross_category_dedup: bool` (env `CROSS_CATEGORY_DEDUP=false` default) + `PerSportOverrides.cross_category_dedup: dict[str, bool]` (env `CROSS_CATEGORY_DEDUP_<SPORT>=true|false`) + `Config.cross_category_dedup_for(sport)` helper. Mirrors the R9 series-dedup pattern; per-sport `false` overrides global `true` in either direction.
- **Wiring**: module-level `CROSS_CATEGORY_DEDUP` and `_PER_SPORT_CROSS_CATEGORY_DEDUP` constants in `kalshi_executor.py` (test-patchable, mirrors `_PER_SPORT_SERIES_DEDUP`); `_cross_category_sports()` builds the active set on each call. `execute_pipeline` passes the set to `dedup_correlated_brackets` and surfaces it in the dedup banner when non-empty: `Deduped correlated brackets: 12 -> 8 opportunities (cross-category: ['nba', 'nfl'])`.
- **Why default OFF**: lets the user A/B test per sport against live calibration data once enough cross-category bets accumulate. Existing per-event cap (Gate 6, `MAX_PER_EVENT=2`) already provides a soft ceiling, so switching this off doesn't leave the system unbounded.
- **`.env.example`**: documents `CROSS_CATEGORY_DEDUP` in the gate section + 8 commented `CROSS_CATEGORY_DEDUP_<SPORT>` lines in the per-sport-overrides section. **CLAUDE.md**: added to Risk Limits block.

### Verification

- 4 new tests in `tests/test_risk_gates.py::TestDedupCorrelatedBrackets`: off-default preserves pre-R8 behavior (regression guard); on collapses 3 categories to highest-composite; per-sport scope (NBA collapses but MLB on same scan stays uncollapsed); futures pass-through preserved even when their sport is opted in.
- 4 new tests in `tests/test_config.py::TestPerSportOverrides`: default off; global on cascades to all sports; per-sport-only override; per-sport `false` overrides global `true`.
- **355 tests passing** (was 347). Lint clean (config-centralization guard).
- One initial round of tests caught a real bug: my first cut keyed cross-category by `_event_key`, which doesn't strip the category prefix from the ticker — so the three categories never collided. The game-id-segment approach fixes it; the failure was visible in test output before any user impact.

### How to use

Default behavior is unchanged — the system keeps ML+Total+Spread on the same game as 3 independent bets. To opt in:

```env
# Enable for every sport
CROSS_CATEGORY_DEDUP=true

# OR enable for specific sports only
CROSS_CATEGORY_DEDUP_NBA=true
CROSS_CATEGORY_DEDUP_NCAAB=true

# OR enable globally but exclude one sport
CROSS_CATEGORY_DEDUP=true
CROSS_CATEGORY_DEDUP_NHL=false
```

When active, the dedup banner prints which sports are in the cross-category set so it's visible at run time.

### Files

`app/config.py`, `scripts/kalshi/kalshi_executor.py`, `tests/test_risk_gates.py`, `tests/test_config.py`, `.env.example`, `CLAUDE.md`, `docs/my-documents/enhancements/ROADMAP.md`, `scripts/schedulers/maintenance/r8_cross_category_review.py` (new), `scripts/schedulers/maintenance/r8_review.bat` (new), `docs/my-documents/task-schedules/README.md`.

### Follow-up

A one-shot Windows scheduled task `\Edge-Radar\R8-Review` will fire on **2026-05-29 06:00 PT** (`scripts/schedulers/maintenance/r8_review.bat` → `r8_cross_category_review.py`). It slices `data/history/kalshi_settlements.json` into ML/Total/Spread same-game cohorts per sport, simulates the R8-on outcome (highest-edge bet kept — `composite_score` isn't on settlement records yet, blocked on R11), and writes a recommendation report to `reports/Performance/R8_cross_category_review_<date>.md` with FLIP ON / FLIP OFF / NEED MORE DATA per sport plus a copy-pasteable `.env` snippet for the FLIP ON sports. Smoke-run on 2026-04-29 against the live 178-bet settlement file produced "NEED MORE DATA: 5" — too thin per sport (NBA 2 cohorts, NCAAB 4, NHL 3) to recommend either way; the May 29 run will have ~30 more days of cohorts to evaluate. Migrated to local Windows Task Scheduler (consistent with the rest of `\Edge-Radar\`) instead of a remote claude.ai routine — deterministic, fast, and same management UX as `Calibration` / `Backtest` / `Weekly-Analysis`. Doc: `docs/my-documents/task-schedules/README.md` § 14. R10 (category-weighted composite score) is the next P2 item after this measurement.

---

## 2026-04-29 -- R26: File-Backed Scan Cache (Row-Order Lock for `--pick`)

### Why

User-reported bug, 2026-04-29: ran a sports scan with `--exclude-open` that returned 5 games, then ran the same scan with `--pick '1,3,4,5' --execute` (without `--exclude-open`). The execute call did a fresh live scan, the row order shifted on price/score drift between the two invocations, and the wrong bets were placed against rows 1/3/4/5 of a different ranking. Two compounding causes: every `scan.py` invocation runs `scan_all_markets()` against live Kalshi prices and Odds API data and re-sorts by `composite_score`; small drifts reorder rows. And dropping `--exclude-open` on the second call changes the row universe outright. Until R26, the `--pick` flag was a foot-gun any time the user's two invocations diverged — even seconds apart, even with identical args.

### What landed

- **`scripts/shared/scan_cache.py`** (new): `store(fingerprint, sized_orders, bankroll)`, `load() -> {fingerprint, saved_at, age_seconds, bankroll_at_scan, rows}`, `clear()`, `fingerprints_match(saved, current) -> (ok, diffs)`. Single file at `data/cache/last_scan.json`, latest preview only. Serializes `SizedOrder` (incl. embedded `Opportunity`) so the executor's existing order-placement loop rehydrates without conditional branches. Silent-on-error throughout — corrupt file = miss, never an exception. Mirrors `scripts/shared/odds_cache.py` precedent.
- **`ScanCacheConfig`** in `app/config.py`: `SCAN_CACHE_TTL_SECONDS=600` (10 min default — long enough to read the preview table and pick rows, short enough that a user returning hours later gets a fresh scan) and `SCAN_CACHE_ENABLED=true`. `validate()` rejects negative TTL.
- **`execute_pipeline` wiring** in `kalshi_executor.py`: added `fingerprint`, `cached_rows`, `cache_age_seconds` params. The dedup / sizing / bet-ratio-cap / budget-cap block is now wrapped in `if cached_rows is None:` so the replay path bypasses it entirely — those decisions are locked from the original preview. On the fresh-scan path, the rendered preview rows are persisted right after `console.print(table)`.
- **CLI wiring** in `edge_detector.py main()`: new `--rescan` flag for opt-out. When `args.execute` AND (`args.pick` OR `args.ticker`) AND not `args.rescan`, attempt cache load before scanning. Fingerprint = `{scanner, filter, category, date, exclude_open, min_edge, top}` — the args that determine row identity. `--unit-size`, `--max-bets`, `--budget`, `--min-bets` deliberately excluded since those reshape sizing/caps but the rows in `cached_rows` were already sized under the original args.
- **Mismatch handling**: on fingerprint mismatch, prints the differing keys (e.g. `exclude_open: cached=True, now=False`) and rescans live rather than silently executing the wrong universe. The user's exact bug pattern from the original report.
- **Banner on hit**: `Replaying cached preview (N rows, age Xs).` + `Pass --rescan to force a fresh scan instead.`
- **`.env.example`** documents both knobs in section 6.

### Verification

- 17 new tests in `tests/test_scan_cache.py`: round-trip preserves SizedOrder + Opportunity fields; age-is-recent; miss-after-TTL; disabled-via-zero-ttl; disabled-via-env-flag; corrupted-file-silently-misses; missing-file; wrong-version; missing-required-fields; store-disabled-does-not-write; creates-parent-dir; clear-removes-file; clear-when-missing; fingerprints identical-match / value-mismatch / extra-key / exclude-open-change-mismatch (the last specifically reproduces the user's bug case).
- **347 tests passing** (was 330). Lint clean (config-centralization guard).
- Live offline round-trip smoke: `store()` writes `data/cache/last_scan.json`, `load()` rehydrates with `age_seconds=0`, `fingerprints_match` returns `(True, [])`. File cleared after smoke.
- Live `get_config()` smoke: `ScanCacheConfig(ttl_seconds=600, enabled=True)` loads from environment as expected.

### How to use

The default workflow now Just Works:

```
python scripts/scan.py sports --filter mlb --exclude-open      # writes cache
python scripts/scan.py sports --filter mlb --exclude-open --pick '1,3,4,5' --execute   # replays cache
```

The second call replays the same row order the user saw, regardless of any live-data drift between the two invocations. To force a live rescan: append `--rescan`. To disable the cache globally: set `SCAN_CACHE_ENABLED=false` or `SCAN_CACHE_TTL_SECONDS=0` in `.env`.

### Files

`app/config.py`, `scripts/shared/scan_cache.py` (new), `scripts/kalshi/kalshi_executor.py`, `scripts/kalshi/edge_detector.py`, `tests/test_scan_cache.py` (new), `.env.example`, `CLAUDE.md`, `docs/my-documents/enhancements/ROADMAP.md`.

### Streamlit UX cleanup (2026-04-29)

Three dashboard polish fixes shipped the same day as R26:

1. **Preview/Execute results table now shows the matchup.** Previously columns were `Ticker, Side, Contracts, Price, Cost, Edge, Status` — the raw Kalshi ticker was the only identifier. The user couldn't tell which scan-table row a preview row corresponded to without parsing the ticker. Now mirrors the scan-results table via the same `format_bet_label / format_pick_label / sport_from_ticker / parse_game_datetime` helpers from `ticker_display`. Final columns: `Ticker | Sport | Bet | Type | Pick | When | Side | Contracts | Price | Cost | Edge | Status`. Files: `webapp/views/scan_page.py`.
2. **Hide Streamlit's "Press Enter to apply" hint on free-standing inputs.** The frontend renders the hint next to every `st.text_input` / `st.number_input`. On the scan page it cluttered the dense Execution Parameters row. Added CSS rules in `webapp/theme.py` with `html body` specificity prefix (Streamlit 1.56 ships its own `!important` rules at the same specificity, so the prefix is required) targeting `[data-testid="InputInstructions"]` + `[data-testid="stWidgetInstructions"]` plus structural sibling-of-baseweb-input fallbacks. Belt-and-suspenders `visibility:hidden / height:0 / overflow:hidden` so even if `display:none` loses, the element doesn't take up layout space. Visible state of the input itself (focus ring, ✓/✗ icons) is preserved.
3. **Auth form: explicit submit instead of auto-submit-on-blur.** The original `check_password()` used a bare `st.text_input` and ran `if pw == correct_pw: authenticate` on every rerun. Streamlit reruns on blur/tab-out, so typing the password then clicking away would auto-authenticate without an explicit submit click — and the "Press Enter to apply" hint would render next to the password field after typing (DOM screenshot 2026-04-29 confirmed the hint appears in a portal outside the `stTextInput` subtree, which is why the CSS rule from fix #2 didn't catch it). Wrapped the input in `st.form("auth_form")` with an explicit `st.form_submit_button("Sign in")`. Streamlit suppresses the per-widget hint inside forms (the form's submit button IS the apply trigger), so the hint goes away as a side effect. Submission now requires either clicking **Sign in** or pressing Enter while focused inside the form. Files: `webapp/app.py`.

Files: `webapp/views/scan_page.py`, `webapp/theme.py`, `webapp/app.py`, `docs/my-documents/web-app/USAGE.md`, `docs/my-documents/web-app/SETUP.md`, `docs/my-documents/web-app/ARCHITECTURE.md`, `docs/web-app/LOCAL.md`. **347 tests still passing.**

### R26 follow-up — UX fixes from first live run (2026-04-29)

User ran the new flow on a real session and surfaced two cosmetic-but-real issues:

1. **Misleading post-execute cost line.** The "Total cost: $9.40 of $70.99 available" line was computed against the full preview menu and printed before the `--pick` filter. Three rows actually placed (= $1.85 stakes), so the user reasonably thought $9.40 had gone out. Fix: after `--pick`/`--ticker` filtering, print `Placing N orders, total cost: $X.XX (selected from M-row menu totaling $Y.YY)`. The pre-filter `Total cost` line stays — it describes the menu — but the post-filter line is now the truthful one. Also fixes a latent crash on the cache-replay path: the old summary line referenced `len(approved)`, which doesn't exist when rows came from cache.
2. **Quiet fingerprint-mismatch warning.** The original mismatch message was a single dim-yellow line. Easy to miss when scrolling past a long Kalshi/Odds API fetch log. Fix: bold red boxed banner with a one-line explanation that `--pick` row numbers will reference a NEW ranking, each differing arg printed in bold red, and a bold yellow trailer naming the recovery options (`re-run preview with same args`, or `--rescan` to silence intentionally).

Files: `scripts/kalshi/kalshi_executor.py`, `scripts/kalshi/edge_detector.py`, `.claude/skills/edge-radar/SKILL.md`, `docs/scripts/edge_detector.md`. **347 tests still passing.**

---

## 2026-04-28 -- R24b: File-Backed Odds API Cache

### Why

F31 (2026-04-24): one Odds API key dropped from 175 → 0 remaining in five minutes during a normal session. The dominant cause is that every `scan.py` invocation starts with a fresh in-process `_odds_cache` / `_outrights_cache`. Running the same scan twice — or the dashboard re-rendering with a tweaked filter — refetches all 18 sport keys from scratch. R23 fixed the persistent quota counter; R24a fixed the dashboard's lack of `@st.cache_data`; R24b is the structural piece: persist the actual response payloads across processes so back-to-back invocations within a 5-minute window don't burn quota.

### What landed

- **`scripts/shared/odds_cache.py`** (new): `load(sport_key, markets, ttl_seconds)`, `store(sport_key, markets, events)`, `clear()`. Files live at `data/cache/odds/<sport_key>__<markets>.json`. Comma-sanitized filenames (`h2h,spreads,totals` → `h2h_spreads_totals`); the original markets string is preserved inside the JSON body. Silent-on-error throughout — corrupt file = miss, never an exception. Mirrors the existing `data/cache/odds_api_quota.json` precedent in `scripts/shared/odds_api.py`.
- **`OddsCacheConfig`** in `app/config.py` with `ODDS_CACHE_TTL_SECONDS` (default 300) and `ODDS_CACHE_ENABLED` (default true). `validate()` rejects negative TTL.
- **Two-tier cache wiring** in `edge_detector.fetch_odds_api()` and `futures_edge.fetch_outrights()`: in-process dict in front of the file layer. The in-process dict stays so existing tests calling `_odds_cache.clear()` still work; the file layer survives across processes. Hits log `Odds API file cache hit for X (age Ns, M events)` so cache age is visible in scan output.
- **`.env.example`** documents both knobs in section 6 (System).

### Verification

- 10 new tests in `tests/test_odds_cache.py`: hit-within-TTL, miss-after-TTL, disabled-via-zero-ttl, corrupted-file-silently-misses, missing-file, missing-required-fields, store round-trip, store-creates-parent-dir, clear-removes-all, clear-when-dir-missing.
- Updated the autouse fixture in `TestFetchOddsApiKeyRotation` (`tests/test_edge_detection.py`) to redirect `odds_cache._CACHE_DIR` to a tmpdir alongside the existing quota-cache redirect — otherwise the rotation tests sharing one process would pick up each other's stored responses.
- **330 tests passing** (was 320). Lint clean.
- Offline round-trip smoke (mocked HTTP, fake key): call 1 hits HTTP and writes the cache file; clearing only the in-process dict and calling again returns identical events with 0 HTTP calls.

### Files

`app/config.py`, `scripts/shared/odds_cache.py` (new), `scripts/kalshi/edge_detector.py`, `scripts/kalshi/futures_edge.py`, `tests/test_odds_cache.py` (new), `tests/test_edge_detection.py`, `.env.example`, `docs/my-documents/enhancements/ROADMAP.md`.

---

## 2026-04-27 -- R9: Per-Sport `SERIES_DEDUP_HOURS`

### Why

F12 (14-day review): a NYM/LAD MLB matchup was bet on Apr 14 and again on Apr 16 — about 49 hours apart, just outside the single 48h global `SERIES_DEDUP_HOURS` window. Both bets landed (every other gate passed) and both lost. Series-dedup is the gate that catches "same model wrong twice on the same matchup," and the global window was tight enough to leak adjacent-day MLB and NHL repeats. NBA matchups against the same opponent within 48h are rare outside the playoffs, so the issue is sport-shaped — not a global threshold problem.

### What landed

- **`PerSportOverrides.series_dedup_hours: dict[str, int]`** in `app/config.py` — populated from `SERIES_DEDUP_HOURS_<SPORT>` env vars. Same pattern as `MIN_EDGE_THRESHOLD_<SPORT>`.
- **`recent_matchups_from_log()`** extended with a `per_sport_hours` keyword arg. Each sport uses its own cutoff; sports without an override fall back to the global `hours`. A per-sport `0` opts that sport out, even when the global is non-zero. A global `0` with a per-sport override re-enables the gate just for the listed sport — both directions tested.
- **Gate 7 in `size_order()`** now resolves the candidate's per-sport window and reports the actual sport-specific window in the rejection message: `series_dedup (matchup NYMLAD bet within 72h)` instead of the old fixed `48h`.
- **Module-level `_PER_SPORT_SERIES_DEDUP`** in `kalshi_executor.py` — tests can patch it directly the same way `_PER_SPORT_MIN_EDGE` is patched.
- **Live `.env`:** `SERIES_DEDUP_HOURS_MLB=72` and `SERIES_DEDUP_HOURS_NHL=72`. NBA leaves the global default. 72h covers any 3-game series start-to-finish regardless of game-time skew.

### Verification

- 9 new regression tests in `test_risk_gates.py` (6 set-construction edge cases including the exact F12 49h scenario, plus 3 gate-rejection-message cases).
- 4 new config-layer tests in `test_config.py` for the new loader.
- Pre-existing `test_disabled_when_hours_zero` updated to also clear `_PER_SPORT_SERIES_DEDUP` since per-sport overrides can now re-enable the gate independently of the global.
- **320 tests passing** (was 307). Lint clean.
- Live config smoke: `_PER_SPORT_SERIES_DEDUP={'mlb': 72, 'nhl': 72}` loads correctly.

### Caveat

Gate 7 reads from `kalshi_trades.json`. After R5, that file is currently the test stub R5 surfaced — empty of real history. The gate will start protecting against new repeats as bets accumulate going forward; R5 made the missing-history visible and R9 ensures the gate catches the right pattern when history exists.

### Files

`app/config.py`, `scripts/kalshi/kalshi_executor.py`, `webapp/services.py`, `tests/test_risk_gates.py`, `tests/test_config.py`, `.env`, `.env.example`, `CLAUDE.md`, `README.md`, `docs/ARCHITECTURE.md`, `docs/setup/SETUP_GUIDE.md`, `docs/web-app/CLOUD.md`, `docs/scripts/kalshi_executor.md`, `.claude/skills/edge-radar/SKILL.md`, `.claude/html/index.html`.

---

## 2026-04-27 -- R5: Settlement-Schema Fix + Reconciliation Report

### Why

F8 (14-day review) said "10/76 14-day settlements match a trade-log entry." Investigation today revealed the actual state was worse: the production trade log got wiped at some point, leaving a single test stub from this morning and **178 settlement entries with zero `trade_id` overlap** to anything in the trade log. Beyond the orphan problem, even when the two files were both healthy the settler only carried forward a hand-picked subset of trade-side fields — missing `composite_score`, `risk_approval`, `bankroll_pct`, `closing_price`, `clv`, etc. — so calibration analytics couldn't slice settlements by score bucket or risk-approval flag without re-joining to a trade log that may not exist.

### What landed

- **`build_settlement_record()` helper** in `kalshi_settler.py` — extracted from the inline `settlement_log.append({...})` so the schema is testable. Settlement record extended from 16 → 27 fields. New fields: `order_id`, `title`, `category`, `edge_source`, `closing_price`, `clv` (settler already computes these but used to discard them), `composite_score`, `risk_approval`, `bankroll_pct`, `unit_size`, `fill_status`. Pre-existing fields unchanged. After this, every future settlement is fully self-describing for calibration without joining to the trade log.
- **`--report reconciliation` mode** in `risk_check.py` — prints trade-log/settlement counts, `trade_id` overlap %, orphaned-settlement window dates, and a field-coverage matrix per R5-added field. Surfaces the join health at every session start.
- **`data/history/README.md`** — documents the two-file lifecycle and the pre-R5 historical-orphan rationale (no backfill: the missing fields don't exist anywhere on disk and synthesizing them would be fabricating data). Added a `.gitignore` exception so the README ships with the repo while runtime state stays gitignored.
- **+10 regression tests** in `tests/test_reconciliation.py`: 5 schema-coverage + 5 report-rendering edge cases (empty / all-orphan / clean-join / mixed cohort / open-trade counting).

### Verification

- **307 tests passing** (was 297). Config lint clean.
- Live `--report reconciliation` against the user's data renders cleanly: 178 orphans (oldest 2026-03-22, newest 2026-04-27), 0% R5-field coverage. Expected pre-R5 baseline.
- The R15 normalizer in `model_calibration.py` continues to work (R5 only adds fields, never removes).

### What this does NOT solve

The 178 historical orphan settlements stay orphaned. Their trade-side context isn't recoverable. R5 stops the bleed and makes the gap measurable; A3 (DB migration) can now import a clean schema without compounding the data debt.

### Files

`scripts/kalshi/kalshi_settler.py`, `scripts/kalshi/risk_check.py`, `tests/test_reconciliation.py`, `data/history/README.md`, `.gitignore`, `docs/ARCHITECTURE.md`.

---

## 2026-04-27 -- Polymarket integration removed

### Why

Zero historical use evidenced. No `data/polymarket/`, no `reports/Polymarket/`, no scheduled tasks ever ran the polymarket subcommand. Prediction-market betting is gated off by default (`ALLOW_PREDICTION_BETS=false`, R25), and the Polymarket cross-reference branch in `prediction_scanner.py` was carrying ~350 lines of decision logic for a code path nothing exercised. Decision: full delete now, recoverable via git history if the use case revives.

### Code removed

- **Deleted:** `scripts/polymarket/` (entire directory — `__init__.py` + 872-line `polymarket_edge.py`)
- **Deleted:** `.claude/skills/polymarket/` (SKILL.md + 9 reference files)
- **Deleted:** `prompts/polymarket/` (`cross-reference-scan.md`, `crypto-arbitrage.md`)
- **Deleted:** `docs/scripts/polymarket_edge.md`
- **Stripped from `scripts/scan.py`:** `polymarket` subcommand registry entry; `poly`/`xref` aliases; example/help-text mentions
- **Stripped from `scripts/prediction/prediction_scanner.py`:** `polymarket_edge` import block; `cross_ref` parameter on `scan_prediction_markets`; `polymarket`/`poly`/`xref` filter shortcuts; the standalone xref scan branch + the per-opportunity Polymarket enrichment loop (~70 lines); `--cross-ref` CLI flag; `is_poly_filter` dispatch logic in `main()`
- **Stripped from `scripts/kalshi/fetch_market_data.py`:** `POLYMARKET_URL` constant; `fetch_polymarket_markets()`; `fetch_polymarket_orderbook()`; `--source polymarket` choice; default flipped from `polymarket` to `kalshi`
- **Stripped from `scripts/shared/paths.py`:** `POLYMARKET_DIR` constant + sys.path entry
- **Stripped from `scripts/shared/report_writer.py`:** `polymarket` key in `REPORT_DIRS`
- **Stripped from `scripts/schedulers/automation/telegram_bot.py`:** `--cross-ref` flag in `/scan prediction`
- **Stripped from `webapp/services.py`:** `scripts/polymarket` from sys.path; `cross_ref` parameter on `run_scan`; `cross_ref` plumbed through to `scan_prediction_markets`
- **Stripped from `webapp/views/scan_page.py`:** `cross_ref` defaults; "Cross-Ref Polymarket" checkbox; `cross_ref` in favorite save state and the service-layer call
- **Stripped from `Makefile`:** `scan-polymarket` target; `scan-polymarket` from `scan-all`; help-text and `.PHONY` entries
- **Stripped from `requirements.txt`:** commented `py-clob-client` line
- **Stripped from `pyproject.toml`:** `scripts/polymarket` from pytest `pythonpath`

### Docs updated

- `CLAUDE.md` — removed Polymarket from "Planned" section; removed `polymarket/` from the project tree; removed `polymarket-py` from the key-libraries list
- `README.md` — dropped "Polymarket cross-ref" bullet from supported markets, "Polymarket Cross-Reference" section, polymarket dir from tree, `polymarket-py` mention in description, "Polymarket" data-sources row
- `docs/ARCHITECTURE.md` — removed Polymarket cross-market row from prediction model table
- `docs/SCRIPTS_REFERENCE.md` — removed polymarket from goal table, scanner registry, alias resolution mermaid + alias table, scanner subgraph, `--cross-ref` tip, examples; flipped `fetch_market_data --source` default from polymarket to kalshi
- `docs/setup/SETUP_GUIDE.md` — dropped Polymarket from free-API list, data-sources table, external-docs links
- `docs/web-app/LOCAL.md` — removed `scripts/polymarket/*.py` from architecture diagram, Cross-Ref filter row, Polymarket-via-CLI note
- `docs/setup/mcp-servers.md` (formerly `docs/mcp-config/mcp-servers.md`) — removed `POLYMARKET_PRIVATE_KEY` env line, polymarket-mcp future-integration row, Polymarket fetch examples
- `docs/scripts/prediction_scanner.md` — full rewrite without `--cross-ref` references
- `.claude/skills/edge-radar/SKILL.md` — multiple sections cleaned: description frontmatter, flag table, scanner table, makefile shortcuts, polymarket subsection, scan-and-bet block, routing examples
- `prompts/predictions/full-prediction-execute.md` — full rewrite (Polymarket cross-ref was central)
- `prompts/predictions/{execute-predictions,crypto-edge-scan,scan-all-predictions}.md` — removed cross-ref blocks
- `prompts/portfolio/morning-routine.md` — removed step 7 + cross-market brief item

### Known stale (not edited — flagging for future refresh)

- `.claude/images/diagrams/**/*.{mmd,svg}` — data-flow diagrams still depict the Polymarket node; will need regeneration if/when diagrams are next refreshed.
- `.claude/html/{index.html,index2.html,dataflow.html}` and `docs/my-documents/HTML-Interactive-Pages/Edge-Radar-Only/index2-*.html` — interactive visualizations include Polymarket; same status as the Mermaid diagrams.
- `docs/my-documents/temp/archive/*` and `docs/my-documents/repo-analysis/edge_radar_repository_analysis_2026-04-22.md` — point-in-time snapshots; intentionally left as-is to preserve the historical record.

### Validation

- `pytest tests/` passing (no tests referenced polymarket).
- `python scripts/scan.py --help` no longer lists polymarket.
- `python scripts/scan.py prediction --help` no longer carries `--cross-ref`.

### Recovery path

Polymarket integration can be restored from `git show <commit-before-removal>:scripts/polymarket/polymarket_edge.py` — but if/when revisited, treat as a fresh design (Polymarket Gamma/CLOB APIs evolve, a current-state implementation will likely be more useful than reverting).

---

## 2026-04-25 -- Config centralization Phase 3 (lint guard against regression)

### `scripts/lint/check_config_centralization.py`

Replaces the original "simple grep" idea from the spec with a small Python script — necessary because the rule needs nuance the raw grep can't express.

**What it does:**
- Walks `app/`, `scripts/`, `webapp/` for `os.getenv` / `os.environ`.
- Excludes `app/config.py` (the single source of truth), `scripts/custom/` (user automation), and `scripts/lint/` itself (this script names the forbidden strings to communicate the rule).
- Skips comment-only lines.
- Skips lines tagged `# config-bootstrap` — reserved for the 4 Streamlit secrets-bootstrap lines in `webapp/services.py` (lines 69, 71, 75, 77 now carry the annotation inline).
- Exits 1 on any violation, 0 otherwise. Output names file, line, content, and tells the contributor what to do.

### Wired into automation

- `make lint-config` Makefile target.
- `.pre-commit-config.yaml` local hook with `pass_filenames: false` and `always_run: true` so the lint sees the whole tree, not just staged files (a sneaky violation in an unstaged file would otherwise slip through).

### Unit tests — 5 new tests in `tests/test_lint_config_centralization.py`

1. The current production codebase passes the lint cleanly.
2. A regression — adding `os.getenv("FOO")` to a previously clean file — is detected.
3. The `# config-bootstrap` annotation correctly suppresses violations.
4. Comment-only lines mentioning `os.getenv` textually are ignored.
5. `app/config.py` is unconditionally excluded.

**Final test count: 297 passing** (292 from earlier phases + 5 lint tests). Production-code `os.getenv` reads outside `app/config.py`: 0.

---

## 2026-04-25 -- Config centralization Phase 2 — all 8 script groups migrated

### What changed

Mechanical migration of every `os.getenv` config read across the production codebase to `app.config.get_config()`. Per-step breakdown:

| Step | Files | Calls removed |
|:----:|:------|:-------------:|
| 1 | `scripts/doctor.py` | 9 |
| 2 | `scripts/kalshi/risk_check.py` | 5 |
| 3 | `scripts/kalshi/kalshi_client.py` | 8 |
| 4+6 | `scripts/kalshi/edge_detector.py`, `scripts/kalshi/fetch_odds.py` | 1 + 2 |
| 5 | `scripts/kalshi/kalshi_executor.py` | 23 |
| 7 | `prediction_scanner.py`, `backtester.py`, `logging_setup.py`, `odds_api.py`, `fetch_market_data.py`, `telegram_bot.py` | 11 |
| 8 | `webapp/services.py` (6 reads — bootstrap retained) | 6 |

**Final tally: 65 reads removed, 0 outside `app/config.py`.** The 4 `os.environ` writes in the `webapp/services.py` Streamlit secrets bootstrap are deliberately retained — they're the input side of cfg, not config consumption.

### Notable per-file details

- **`doctor.py`:** display normalization is the only user-visible change (`UNIT_SIZE=.50` previously rendered as `$.50`; now `$0.50` via explicit `:.2f` format). Numeric values reaching every gate are byte-identical.
- **`risk_check.py`:** dropped a dead `MIN_EDGE` constant that no caller imported.
- **`kalshi_client.py`:** Streamlit-secrets timing preserved — all reads happen at instantiation, not import. The `st.secrets["kalshi"]["private_key"]` fallback in `_resolve_key_content` is kept as a backup for direct Streamlit-app use that bypasses `services.py`. Phase 1 default for `KalshiCredentials.private_key_path` tweaked from `"keys/live/kalshi_private.key"` to `""` to mirror the original `os.getenv("KALSHI_PRIVATE_KEY_PATH", "")` runtime default; preserves byte-identical "credentials not configured" error path when env is unset. `.env.example` unchanged.
- **`kalshi_executor.py`:** all 21 module-level risk constants and the per-sport edge-override dict source from `_cfg = get_config()`. Constants stay as plain mutable globals because `tests/test_risk_gates.py` mutates them directly (`kalshi_executor.MAX_OPEN_POSITIONS = 10`) — only the *initial source* changed. Two in-function `DRY_RUN` reads (resting-order janitor + execute-table title) use `get_config().system.dry_run` against the memoized cache.
- **`fetch_odds.py`, `fetch_market_data.py`, `telegram_bot.py`:** API-key constants use `cfg.X or None` to preserve `None`-on-unset semantics from the original `os.getenv("X")` — matters where credentials get spliced into HTTP headers and URL f-strings (`None` and `""` render differently).
- **`logging_setup.py`:** `from app.config import get_config` placed *after* `load_dotenv()` so `.env` values are in `os.environ` before the first cfg read.
- **`webapp/services.py`:** module-level constants (imported by `views/scan_page.py` and `views/portfolio_page.py`) sourced from `_cfg = get_config()`. `reset_config()` defensive call added between the secrets bootstrap and downstream imports — explicit contract that any code mutating `os.environ` after potentially priming the cache uses this seam. Bug found and fixed: Streamlit's `webapp/app.py` puts `webapp/` on `sys.path[0]`, which made `from app.config import …` resolve to `webapp/app.py` (a file) instead of the `app/` package. Resolved by explicitly inserting `PROJECT_ROOT` at `sys.path[0]` inside `services.py` after the script-subdir loop. Documented inline.

### Infra side-fix

`scripts/shared/paths.py` and `.venv/Lib/site-packages/edge_radar.pth` both now prepend `PROJECT_ROOT` to `sys.path` so `from app.config import get_config` resolves in any script that imports `paths`. Without this, every migrated script would need its own ad-hoc `sys.path.insert(0, str(PROJECT_ROOT))`.

### Out of scope (flagged, not migrated)

- `scripts/custom/Python/send_daily_email.py` uses `os.environ["AGENTMAIL_API_KEY"]` — user-automation script, knob not documented in `.env.example` or core docs. Migrating it would add a non-core knob to `app/config.py`, violating the "no new knobs" non-goal.

All 292 tests still pass after the migration.

---

## 2026-04-25 -- Config centralization Phase 1 (refactor scaffolding)

### `app/config.py` — typed config module landed (no script migrations yet)

- **Why:** Audit found 75 `os.getenv` calls across 14 files, with `MIN_EDGE_THRESHOLD` read in 5 places using two type styles (string `"0.03"` vs float `0.03`) and `DRY_RUN` coerced inconsistently. Tracked under `docs/my-documents/enhancements/CONFIG_CENTRALIZATION.md`.
- **What landed:** `app/config.py` with 10 frozen dataclasses (Kalshi creds, Kalshi-prod creds, OddsApi creds, Alpaca creds, Telegram creds, RiskLimits, GateThresholds, KellyConfig, PerSportOverrides, System). Each has `from_env()` for one-shot coercion; aggregate `Config.from_env()` runs `validate()`. Memoized via `get_config()` / `reset_config()`. 32 unit tests in `tests/test_config.py`.
- **What did NOT change:** No existing script touched. `os.getenv` count unchanged. `.env.example` unchanged. No behavior change of any kind. Phase 2 (mechanical migration of 8 script groups) is a separate set of commits.
- **Discrepancies flagged for a future doc-reconciliation PR (not fixed here):** `MAX_OPEN_POSITIONS` is `10` in code/CLAUDE.md but `50` in `.env.example`; `MAX_PER_EVENT` is `2` in code/`.env.example` but `3` in CLAUDE.md. Phase 1 followed code as source of truth.

---

## 2026-04-24 (PM) -- Scanner Parity, Futures Bug Hunt, Prediction-Market Audit (R17, R18, R20, R21, R22, R23, R24a, R25)

### R17. Scanner flag parity (`--budget`, `--report-dir`)
- **Problem:** User tried `futures_edge.py scan --exclude-open --budget 5%` and discovered that `--budget` and `--report-dir` were sports-only. Futures / prediction / polymarket CLIs didn't accept them, and even if they had, `execute_pipeline(budget=…)` wasn't threaded through. Risk-gate logic itself was already uniform (all four call `execute_pipeline`).
- **Fix:** Extracted `parse_budget_arg()` into `kalshi_executor.py` so all four scanners share the same `"10%"` / `"15"` / `"0.15"` / `"150"` parsing contract. Added `--budget` + `--report-dir` to futures / prediction / polymarket argparse; wired each to `execute_pipeline(budget=…)` and `save_scan_report(output_dir=…)`. Sports scanner's inline 7-line budget block replaced with the shared helper.

### R21. `dedup_correlated_brackets` now passes futures through unchanged
- **Problem:** A futures scan of 20 opportunities was being collapsed to 2 before risk gates even ran. `dedup_correlated_brackets` grouped by `(event_key, category)`; for championship futures `KXNBA-26-LAL` / `KXNBA-26-BOS` / `KXNBA-26-OKC` all share event key `KXNBA-26`, so dedup saw 16+ team outcomes as one "alt-line bracket" and kept only the top composite score.
- **Fix:** When `opp.category == "futures"`, use the full ticker as the dedup key so each outcome survives. Correct for alt-line brackets ("Over 221.5" / "Over 224.5") that are genuinely correlated, wrong for futures where each team is a distinct independent bet. Concentration still bounded by Gate 6 (`MAX_PER_EVENT=2`).

### R22. `FUTURES_MAP` prefix-collision + semantic-mismatch double bug
- **Problem:** Futures scan surfacing "+30-75% edge" on basically every MLB team — too good to be true, and it was. Two compounding bugs: (1) **Prefix collision** — iteration broke on first `ticker.startswith(prefix)` match, so `KXMLBPLAYOFFS-26-LAD` matched the `KXMLB` entry first. Same silently affected `KXNBAEAST`/`KXNBAWEST`/`KXNHLEAST`/`KXNHLWEST`. (2) **Semantic mismatch** — even with prefix ordering fixed, those 5 derivative entries pointed to championship-winner odds while representing playoff-qualification or conference-winner questions. LAD's probability to **make playoffs** (~95%) is fundamentally different from LAD's probability to **win the World Series** (~28%).
- **Fix:** Switched matching from `ticker.startswith(prefix)` to exact series extraction (`ticker.split("-", 1)[0]` lookup). Removed the 5 semantically-broken entries from `FUTURES_MAP` with a comment explaining why each needs a proper data source before being re-added (tracked in R19). Updated `FUTURES_FILTER_SHORTCUTS` to match.
- **Verification:** Same scan went from 45 bogus opportunities at +30-75% edge → 2 real opportunities at +4% edge (OKC NBA Finals, LAD World Series). Modest edges are what a sharp futures market should look like.

### R23. Robust Odds API key rotation + persistent quota cache
- **Problem:** `--filter mlb-futures` returned "No outright data" despite unfiltered scan working seconds earlier. Live probe showed first 5 of 10 keys exhausted (500/500 used each). Two compounding bugs: (1) `futures_edge.fetch_outrights` used `for attempt in range(3)`, so after keys 0-2 all 401'd the retry loop exited before reaching the healthy key at index 5. (2) `_remaining` dict was process-local — every fresh invocation rediscovered exhaustion the hard way.
- **Fix:** Replaced `range(3)` in `fetch_outrights` with the `tried: set[str]` loop pattern used in `edge_detector.fetch_odds_api` (cycles through every configured key). Added `mark_exhausted()` called on 401 responses. Persistent quota cache at `data/cache/odds_api_quota.json` — `_remaining` loaded at `_load_keys()` time, saved on every `report_remaining()` / `mark_exhausted()`. `get_current_key()` now auto-advances past keys with cached `remaining == 0`. Fallback: if every key is cached exhausted, return the current slot anyway so a monthly quota reset can be re-discovered.
- Env: nothing new — uses existing `ODDS_API_KEYS`.

### R24a. Webapp scan cache (`@st.cache_data(ttl=60)`)
- **Problem:** Zero `@st.cache` decorators existed anywhere in `webapp/` before this. Every scan-button click fired a fresh Odds API fetch, and exploratory "try a filter, scan, change filter, scan again" sessions burned requests fast. Investigation under R24 surfaced this as one contributor to F31's 175-requests-in-5-min burn rate.
- **Fix:** Added 60s TTL cache on `run_scan()` keyed on all scan parameters (market_type, ticker_filter, category, date, min_edge, top_n, exclude_open, cross_ref). Client param renamed `client` → `_client` per Streamlit convention for unhashable args. CLEAR button now also calls `run_scan.clear()` so the user can force a refresh on demand.

### R18. Scan tables show "Gate" column previewing executor rejects
- **Problem:** User ran `scan --filter mlb-futures --unit-size .5` and got "No opportunities passed risk checks" (LAD rejected on composite score 4.6 < 6.0). Same command without `--unit-size` happily listed LAD as a +4.3% edge row with no indication it would fail. Scan table promised an opportunity the system would never take.
- **Fix:** Added `preflight_gate_status(opp)` helper in `kalshi_executor.py` that checks the 5 static per-opportunity gates and returns a short label: `"ok"` / `"edge"` / `"price"` / `"score"` / `"conf"` / `"no-fav"` / `"pred-off"`. Wired into the scan-table render path of all four scanners. Green "ok" for pass, red label for the failing gate. Runtime gates (daily loss, position count, duplicate ticker, per-event cap, series dedup) require live portfolio state and are NOT checked here — `"ok"` is necessary but not sufficient.

### R20. Prediction-market audit
- **Findings:** Zero prediction-market bets in 173 historical settlements. All 6 modules (crypto / weather / spx / mentions / companies / politics) cache live data with no TTL. 4 of 6 modules have zero unit tests. Live scans produce obvious garbage: crypto +80% "edges" on 4¢ tail bets, weather showing $1.00 fair values on 1°F range markets (one was ready to execute at HIG confidence, 9.7 composite, one `--unit-size` away). `DEMO_KEY` hardcoded in `companies_edge.py`.
- **Prescription:** Safety-gate the category via R25. Rebuild (R25b/R25c) before any M1-M4 upgrades.

### R25. New Gate 4.7 — prediction-market safety gate
- **Fix:** New reject gate in `size_order()` — rejects opportunities where `opp.category in {"crypto", "weather", "spx", "mentions", "companies", "politics"}` unless `ALLOW_PREDICTION_BETS=true`. Default off. `preflight_gate_status()` returns `"pred-off"` so the R18 Gate column surfaces the rejection at scan time.
- Env: `ALLOW_PREDICTION_BETS=false` added to `.env.example`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, webapp secrets passthrough.

### Gate Numbering
- **Total gates:** 13 (was 12). Reject gates 1-7 (including 3.5, 4.5, 4.6, 4.7); sizing caps 8-9.

### Tests
- 38 new tests across the session: 5 for `TestDedupCorrelatedBrackets` (R21), 7 for `TestFuturesSeriesMatch` (R22), 13 for `tests/test_odds_api.py` (R23), 9 for `TestPreflightGateStatus` (R18), 4 for the prediction safety gate (R25). 218 → 260 passing.

---

## 2026-04-24 -- 30-Day Calibration Cycle (R12, R13, R14, R15, R16)

### 30-Day Review (160 settled trades since 2026-03-25)
- **Sample:** 160 settled, 80W-80L (50%), +37.4% ROI ($43.48 P&L), Brier 0.2657. Aggregate remains healthy but concentrated: NHL +72% and NCAAB +71% carry most of the P&L; a single 7¢ MLS fill (04-20 +$14.80) is a third of the absolute P&L on its own.
- **F14 — High-confidence WR < Medium:** High 47% WR (n=57) vs Medium 53% WR (n=100). High ROI only wins via larger per-bet sizing. NBA instance is the loudest: High = 1-6 / -71% ROI.
- **F15 — NBA negative across three review windows:** 30d -14.8% (n=17), 14d -26%, post-baseline -15%. R2 stdev bump (04-21) too recent to attribute.
- **F17 — Calibration overconfidence persists 50-100%:** -14 to -22pp gap on every non-longshot probability bucket.
- **F21 — `model_calibration.py` blind to real sample:** Script read `trade_log` (16 entries, 3 closed) instead of `kalshi_settlements.json` (173 entries). R12 was impossible to run until fixed.
- **F22 — Live `.env` missing per-sport edge overrides:** For the entire post-baseline window, NBA and NCAAB were running at the 3% global floor, not the documented 8% / 10%. Silent drift — `.env.example` had them but the live env did not.

### R15. `model_calibration.py` points at settlement source
- **Fix:** New `_load_settled_trades()` normalizer reads `data/history/kalshi_settlements.json` (same source `betting_analysis.py` uses). Maps `cost` → `cost_dollars`, `won` → `settlement_won`, `settled_at` → `closed_at`; derives `category` from ticker via `bet_type_from_ticker()`. Replaces string-based ISO cutoff comparison with `datetime` parsing that tolerates trailing `Z`. All downstream helpers (`_brier_score`, `_calibration_buckets`, `_edge_bucket_stats`, `_dimension_stats`, cross-tab, recommendations) unchanged.
- Files: `scripts/kalshi/model_calibration.py`.

### R12. First full-sample calibration report
- **First run:** `reports/Calibration/2026-04-24_calibration_report.md`. 10 prioritized recommendations (2 HIGH, 8 MEDIUM). Brier 0.2657 (worse than coin-flip).
- **Per-sport Brier surfaces NBA as the worst-calibrated sport:** NBA 0.3306, NCAAB 0.2885, MLB 0.2519, NHL 0.2376 (NHL better than coin-flip — model is calibrated there), MLS 0.2364 (small sample).
- **Cross-tab insight:** medium × Total is the bread-and-butter combo (+46% ROI on n=71); high × Total is -52% on n=4 (tiny); high × ML is roughly flat at +10%.
- **Edge-bucket inversion softening:** 25%+ bucket 14d -24% ROI → 30d +16% ROI. Suggestive evidence R2 is working; needs another window + post-R13/R14 settlements to confirm.

### R14. `MIN_EDGE_THRESHOLD_NBA` bumped 0.08 → 0.12 (+ live-env override restore)
- **Fix:** NBA per-sport floor raised to 12%. Also added both `MIN_EDGE_THRESHOLD_NBA=0.12` and `MIN_EDGE_THRESHOLD_NCAAB=0.10` to the live `.env` — they were documented in `.env.example` and `CLAUDE.md` but missing from the actual env file, so both were silently falling back to the 3% global floor.
- **Scope intentionally minimal:** 17-bet NBA sample showed the bleed was concentrated in High-confidence picks (1-6, -71% ROI) and 2/3 of the NBA ML losers were sub-10¢ lottery tickets already caught by R7. Playoff-specific stdev and "NBA Totals-only" filters explicitly rejected — not enough sample. Confidence-tier fix lives in R13.
- Env: `MIN_EDGE_THRESHOLD_NBA=0.12`. Files: `.env`, `.env.example`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/setup/SETUP_GUIDE.md`, `docs/web-app/CLOUD.md`, `docs/scripts/kalshi_executor.md`, `docs/kalshi-sports-betting/MLB_FILTERING_GUIDE.md`, `.claude/html/index.html`, `scripts/kalshi/kalshi_executor.py` (docstring).

### R13. Confidence bumps are now one-way (down only)
- **Problem:** `_adjust_confidence_with_stats()` applied ±1 tier bumps from three call sites (team stats, rest/B2B, sharp money). 30-day data showed upward bumps correlated with inflated claimed edge but worse realized outcomes — High-confidence WR 47% < Medium 53% portfolio-wide, NBA High at 1-6 / -71% ROI.
- **Fix:** `contradicts` still drops a tier; `supports` is now a no-op. All three call sites share the function, so the change applies uniformly. Base "high" tier remains reachable via the book-count rule (≥8 sharp books + tight consensus <5%) — only the bolt-on bumps are neutralized. Kelly sizing unaffected (sizing doesn't use confidence directly); composite score naturally compresses; Gate 4.6's confidence=high requirement naturally tightens — correct direction.
- No env var. +4 regression tests (`TestConfidenceBumpsOneWay`) → 222 passing.
- Files: `scripts/kalshi/edge_detector.py`, `tests/test_edge_detection.py`.

### R16. Monthly calibration cron
- **Fix:** New `calibration` profile in `install_windows_task.py` runs `model_calibration.py --days 30 --save` on day 1 of each month at 02:00 (after nightly settler). Required extending the installer to support `MONTHLY` schedules with `/D` day specifier; daily profiles unchanged.
- **Also:** Narrowed `scripts/schedulers/` gitignore so the portable `automation/` folder is now tracked (three `.py` files — all paths derive from `__file__`, secrets via `.env`, no machine-specific state). Sibling scheduler folders with hardcoded-path `.bat` files stay gitignored.
- Install: `python scripts/schedulers/automation/install_windows_task.py install calibration`.
- Files: `scripts/schedulers/automation/install_windows_task.py`, `scripts/schedulers/automation/daily_sports_scan.py`, `scripts/schedulers/automation/telegram_bot.py`, `docs/setup/AUTOMATION_GUIDE.md`, `.gitignore`.

### Gate Numbering
- **Total gates:** 12 (unchanged since R7).

---

## 2026-04-22 -- Repo-Analysis Response + Lottery-Ticket Floor (Q1-Q5, R7)

### Repo Analysis Response (2026-04-22 independent review)
- **Q1. Web app `market_type` wired through service layer.** UI exposed sports/futures/prediction/polymarket but `webapp/services.py run_scan()` had no `market_type` param — everything routed into `scan_all_markets` (sports-only). `run_scan()` now dispatches to `scan_all_markets` (sports), `scan_futures_markets` (futures), or `scan_prediction_markets` (prediction) based on UI selection; `cross_ref` passed through for Polymarket reference pricing on prediction scans. Invalid types raise `ValueError` at the boundary. Standalone Polymarket removed from `MARKET_TYPES`, `CATEGORIES_BY_TYPE`, `FILTERS_BY_TYPE`, sidebar `QUICK_SCANS` — UI-only, never reached service layer. CLI `scan.py polymarket` still works. Files: `webapp/services.py`, `webapp/views/scan_page.py`, `webapp/app.py`, `docs/web-app/LOCAL.md`.
- **Q2. Test env-contamination fix.** `test_approved_clean_when_no_caps_hit` read `MAX_BET_SIZE` and `KELLY_FRACTION` from `kalshi_executor` at import time, so a developer `.env` with `MAX_BET_SIZE=15` and `KELLY_FRACTION=1.0` would trip the max-bet cap and return `APPROVED_CAPPED_MAX_BET` instead of `APPROVED`. Fix: monkey-patch both module constants to documented defaults for the test's scope, matching the existing pattern in `test_approved_capped_max_bet`. Files: `tests/test_risk_gates.py`.
- **Q3. Doc drift: count-free "risk gates" references.** `docs/SCRIPTS_REFERENCE.md`, `docs/setup/AUTOMATION_GUIDE.md`, `docs/web-app/LOCAL.md` said "8 risk gates" post-R1/R3. Updated to count-free phrasing ("all risk gates") linking to `CLAUDE.md` §"Execution Gates"; CLAUDE.md heading renamed from "11 Execution Gates" to "Execution Gates". Prevents doc churn on every gate addition.
- **Q4. Pages deploy branch fix.** `.github/workflows/deploy.yml` triggered on `main`; repo default is `master`. Flipped so pushes to master actually redeploy `.claude/html/` (the Edge-Radar data-flow visualization).
- **Q5. Declared `pandas` in `requirements.txt`.** All four `webapp/views/*.py` import pandas; it was working only via Streamlit's transitive dep. Promoted to `pandas>=2.1.4` as a first-class runtime dep.

### R7. Minimum Market-Price Floor (new Gate 3.5)
- **Problem:** F10 from the 2026-04-21 14-day review showed sub-10¢ bets at 1W-3L with the model claiming "+50% edge" on 8-10¢ longshots. One win masked a systemic lottery-ticket overfit pattern.
- **Fix:** New reject gate in `size_order()` — any bet whose market price is below `MIN_MARKET_PRICE` (default **$0.10**) is rejected. Strict less-than: $0.09 rejected, $0.10 approved. No exception for edge/confidence (unlike Gate 4.6's carve-out). Set to 0 to disable and keep all longshots.
- **Defaults:** `MIN_MARKET_PRICE=0.10` chosen in discussion ("I kind of like the long shots. But I definitely agree We shouldn't go too low. I like .10") — blocks the lottery-ticket cluster while keeping moderate longshots (≥10¢) eligible.
- Env: `MIN_MARKET_PRICE` (plumbed through `.env.example`, `CLAUDE.md`, `webapp/services.py` flat-keys for Streamlit Cloud secrets).

### Gate Numbering
- **Total gates:** 12 (was 11). Reject gates 1-7 (including 3.5, 4.5, 4.6); sizing caps 8-9.

### Tests
- 5 new tests for Gate 3.5 (reject below floor, reject just below floor, approve at floor inclusive, approve above floor, disabled when `MIN_MARKET_PRICE=0`). 213 → 218 passing. Two pre-existing tests (`test_contracts_capped_by_bankroll`, `test_price_clamped_to_valid_range`) that intentionally use sub-10¢ prices patched to disable `MIN_MARKET_PRICE` for their scope so they exercise their actual intent.

---

## 2026-04-21 -- 14-Day Review Response (R1, R2, R3, R4)

### 14-Day Review (76 settled trades since 2026-04-07)
- **Sample:** 76 settled, 37W-39L (48.7%), +31% ROI, Brier 0.2646. Aggregate was carried by NHL (+87% ROI) and a single 7¢ MLS outlier.
- **F1 — NO-side systematically loses on high edge:** YES +93% ROI (n=48); NO -20% ROI (n=28); NO at ≥20% edge: 31% WR, -33% ROI (n=16). All 13 high-edge losers in the window were NO-side.
- **F6 — Low confidence:** 0W-3L / -105% ROI, consistent with the 2026-04-18 window.

### R3. `MIN_CONFIDENCE` Reject Gate (new Gate 4.5)
- **Fix:** Reject any opportunity whose confidence label ranks below `MIN_CONFIDENCE` (default `medium`). Low-confidence bets were 0W-3L / -105% ROI across two review windows — rejecting outright instead of warning.
- Env: `MIN_CONFIDENCE` (values: `low` | `medium` | `high`).

### R1. NO-Side Favorite Guard + Half-Kelly Dampener (new Gate 4.6)
- **Problem:** Every high-edge loser in the 14-day window was a NO bet on a heavy favorite. The model over-estimates edge on the "long-price, short-distance" NO side.
- **Fix — reject gate:** Reject NO bets whose market price < `NO_SIDE_FAVORITE_THRESHOLD` (default 0.25) unless edge ≥ `NO_SIDE_MIN_EDGE` (default 0.25) AND confidence = `high`. The carve-out lets genuinely sharp NO plays through but forces the bar much higher than the default 3% floor.
- **Fix — sizing dampener:** NO bets priced below `NO_SIDE_KELLY_PRICE_FLOOR` (default 0.35) are sized at `NO_SIDE_KELLY_MULTIPLIER` (default 0.5 = half-Kelly) of normal Kelly. Complements the reject gate — bets that clear it but are still on moderate favorites get downsized rather than sized at full confidence.
- Env: `NO_SIDE_FAVORITE_THRESHOLD`, `NO_SIDE_MIN_EDGE`, `NO_SIDE_KELLY_PRICE_FLOOR`, `NO_SIDE_KELLY_MULTIPLIER`.

### Gate Numbering
- **Total gates:** 11 (was 9). Reject gates 1-7 (including 4.5 and 4.6); sizing caps 8-9.

### R4. Resting-Order Janitor
- **Problem:** The 14-day review showed 16% of new orders (4/25) resting 25-66h with zero fills. Edge-Radar is fire-and-forget after placing a limit order — nothing polled Kalshi for stale orders. Stranded resting orders tied up balance and cluttered the order book without contributing to P&L.
- **Fix:** New `cancel_stale_resting_orders()` helper in `kalshi_executor.py`. Lists resting orders via `client.get_orders(status="resting")`, filters to those older than `RESTING_ORDER_MAX_HOURS` (default 24) with `fill_count_fp == 0`, and calls `client.cancel_order()` on each. Partial/full fills are left for the settler to handle.
- **Trigger:** Runs at the top of `execute_pipeline()` only when `execute=True` AND `DRY_RUN=false`. Preview scans never touch the order book; dry-run execute calls skip the janitor entirely. With the user's existing 5AM daily `--execute` scan, the natural cadence covers the 24h threshold without needing a separate scheduler.
- Env: `RESTING_ORDER_MAX_HOURS` (0 disables).

### R2. Per-Sport Stdev Bump (supersedes C2)
- **Problem:** Brier 0.2646 (still worse than coin-flip 0.2500) and a 60-70% favorite-band overconfidence gap of +18% (largest bucket, n=40). C1's Kelly soft-cap dampens sizing on fake-high edges but does not touch the underlying probability estimates. The sport-level 14-day numbers (NBA -26%, MLB -10%) persist. Meanwhile NHL is at +87% ROI and well-calibrated.
- **Fix:** Widen the normal-CDF probability distributions for the three underperforming sports.
  - `SPORT_MARGIN_STDEV`: NBA 12.0 -> 13.8 (+15%), NCAAB 11.0 -> 12.1 (+10%), MLB 3.5 -> 4.025 (+15%).
  - `SPORT_TOTAL_STDEV`: NBA 18.0 -> 20.7 (+15%), NCAAB 16.0 -> 17.6 (+10%), MLB 3.0 -> 3.45 (+15%).
  - NHL, NFL, NCAAF, soccer, MMA unchanged.
- **Mechanism:** Wider stdev pulls probability mass toward 50%, directly reducing the favorite-band overconfidence and compressing the implausibly large edges in the >=25% bucket (which realized -24% ROI in the review).
- **Attribution plan:** R12 re-runs `model_calibration.py` at 100 post-baseline trades (currently at 66). The window between R2's ship date and that checkpoint is the cleanest place to measure whether the probability-width fix improved Brier.

### Tests
- 32 new tests (181 -> 213 passing): 6 for `MIN_CONFIDENCE` gate, 4 for NO-side reject gate, 3 for NO-side Kelly multiplier, 12 for the resting-order janitor (stale/young/partial/zero-hours/API-error/malformed-timestamp/default-env coverage), 1 multiplier-vs-full-Kelly comparison, and 6 for the R2 per-sport stdev values (margin + total + NHL-untouched + other-sports-untouched + ticker-prefix lookup).

---

## 2026-04-18 -- Calibration-Driven Risk Tuning & Odds API Rotation Fix

### First Post-Baseline Calibration Run (66 Edge-Radar trades since 2026-04-03)
- **Findings:** Brier score 0.2561 (worse than coin-flip 0.2500); claimed edges >=25% realize -35% ROI while 10-15% claimed edges realize +127%; NBA -15% ROI, NCAAB -62% ROI at the global 3% floor; NHL +100% ROI; same-matchup bets on consecutive days produced compounding losses (LA Angels @ NY Yankees Apr 13/14/15, NY Mets @ LA Dodgers Apr 13/15, Colorado @ Houston Apr 14/15).
- **Report:** `reports/Calibration/2026-04-18_calibration_report.md`.

### C1. Kelly Edge Soft-Cap
- **Problem:** Kelly sizing uses `edge` linearly. A claimed 25% edge sized 2.5x larger than a 10% edge -- and the >=25% bucket is the worst-performing (-35% ROI, 30% WR on 10 trades). The system was sizing biggest on the least-calibrated signal.
- **Fix:** New `trusted_edge()` helper in `kalshi_executor.py` softly caps the edge used inside the Kelly calculation above `KELLY_EDGE_CAP` (default 0.15), with the excess multiplied by `KELLY_EDGE_DECAY` (default 0.5). Example: a claimed 25% edge sizes like 20%, a 35% edge like 25%. Raw edge still flows through gates, reports, rationale, and the trade journal -- only Kelly sizing sees the trusted value.
- Env: `KELLY_EDGE_CAP`, `KELLY_EDGE_DECAY`.

### C3. Per-Sport `MIN_EDGE_THRESHOLD`
- **Problem:** NBA lost -15% ROI (13 post-baseline trades) and NCAAB lost -62% ROI (8 trades in 14-day window) at the 3% global floor, while NHL was +100% on the same floor.
- **Fix:** New `min_edge_for(opp)` helper with `_PER_SPORT_MIN_EDGE` dict populated at import from `MIN_EDGE_THRESHOLD_<SPORT>` env vars (supported: MLB, NBA, NHL, NFL, NCAAB, NCAAF, MLS, SOCCER). Defaults set: `NBA=0.08`, `NCAAB=0.10`. Gate 3 rejection message shows the per-sport floor in effect.

### C5. Series-Level Correlation Dedup (New Gate 7)
- **Problem:** `dedup_correlated_brackets()` deduped within a single day but couldn't see across days. Same-matchup bets on consecutive nights compounded losses (LA Angels @ NY Yankees 3 nights, net negative; NY Mets @ LA Dodgers 2 nights, both losing; COL @ HOU 2 nights, both losing).
- **Fix:** New Gate 7 rejects a new bet if the same matchup (sport + team pair, date-agnostic) was already bet within `SERIES_DEDUP_HOURS` (default 48). `matchup_key(ticker)` strips the leading YY-MMM-DD date and optional HHMM game-time prefix to produce a series-invariant key. `recent_matchups_from_log()` walks the local trade log; dry-run runs don't write to the log, so no extra filtering needed.
- **Gate numbering:** Total gates now 9 (1-7 reject, 8-9 sizing cap). Previously 8.
- Env: `SERIES_DEDUP_HOURS` (0 disables).

### Bug Fix: Odds API Key Rotation Bailed Early
- **Problem:** `scan.py sports --filter mlb` returned 0 MLB events while the all-sports `.bat` scan pulled 28 -- same API keys, same date. With 10 configured keys and the first 3-4 currently exhausted on their monthly quota, the fixed `range(3)` retry loop in `fetch_odds_api()` rotated on each 401 but exited before trying the newly-rotated key. The all-sports scan masked the issue because earlier sports (golf, soccer) rotated past the dead keys first, so by the time MLB was queried the active key was fresh. Single-sport filter runs never got that warmup.
- **Fix:** Replaced the fixed-count loop with a set-based "tried every key at most once" while-loop. Explicit log message when all keys return 401/429 instead of silent empty result. Happy path unchanged (first working key succeeds, no unnecessary rotation). 4 regression tests cover all-keys-tried, rotates-past-exhausted, first-key-success, and single-key-401.
- Files: `scripts/kalshi/edge_detector.py:fetch_odds_api`.

### Tests
- 20 new tests total (161 -> 181 passing): 6 for `trusted_edge`, 5 for per-sport edge floors, 16 for series dedup (`matchup_key`, `recent_matchups_from_log`, gate behavior), 4 for Odds API rotation.

---

## 2026-04-08 -- Full Sports Coverage & Multi-Filter Support

### Expanded Odds API Sport Mapping (4 -> 18 sports)
- **Problem:** `KALSHI_TO_ODDS_SPORT` only mapped 4 sports (NBA, NHL, MLB, NCAAB). All other sports -- NFL, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, college football/women's basketball -- were fetched from Kalshi but silently dropped because no external odds existed to calculate edge against.
- **Fix:** Added mappings for all 14 missing sports with Odds API coverage: NFL (`americanfootball_nfl`), NCAA Football (`americanfootball_ncaaf`), NCAA Women's Basketball (`basketball_wncaab`), MLS (`soccer_usa_mls`), EPL (`soccer_epl`), UCL (`soccer_uefa_champs_league`), La Liga (`soccer_spain_la_liga`), Serie A (`soccer_italy_serie_a`), Bundesliga (`soccer_germany_bundesliga`), Ligue 1 (`soccer_france_ligue_one`), UFC (`mma_mixed_martial_arts`), Boxing (`boxing_boxing`), F1 (`motorsport_formula_one`), PGA (`golf_pga_championship`), IPL (`cricket_ipl`).
- **CATEGORY_MAP expanded:** Added 18 new ticker prefix -> category mappings (NFL game/spread/total, MLS game/spread/total, all soccer leagues, UFC, boxing, IPL, F1, NASCAR, PGA, NCAA women's basketball) so these markets get properly categorized instead of falling to "other".
- **No-filter scan expanded:** Since the unfiltered scan (`scan.py sports`) uses `KALSHI_TO_ODDS_SPORT` keys to determine which prefixes to fetch, this change automatically expands coverage from 11 to 30 prefixes.

### Comma-Separated Multi-Filter (`--filter mlb,nhl`)
- **Problem:** `--filter` only accepted a single sport. Scanning two sports required two separate runs, wasting Odds API quota and time.
- **Fix:** `--filter` now accepts comma-separated values. Each value is resolved independently through `FILTER_SHORTCUTS`, and all prefixes are merged. Example: `--filter mlb,nhl` fetches all MLB and NHL prefixes in one scan.
- **Futures guard:** Single-value futures filters (e.g., `--filter nba-futures`) still route to the dedicated futures scanner as before.
- Files changed: `scripts/kalshi/edge_detector.py`

---

## 2026-04-08 -- Streamlit Community Cloud Deployment

### Web Dashboard Live at edge-radar.streamlit.app
- **Deployed** the Streamlit dashboard to Streamlit Community Cloud (free tier) with password-gated access.
- **Inline PEM support:** `KalshiClient` now accepts private key content as a string (not just a file path), enabling Cloud deployment where no filesystem is available. Priority: inline content > env var > `st.secrets` > file path. Local dev workflow unchanged.
- **Secrets bridge:** `webapp/services.py` injects Streamlit Cloud secrets into `os.environ` before script imports, so all existing `os.getenv()` calls (odds_api, edge_detector, etc.) work on Cloud without modification. Supports both nested (`[kalshi] / api_key`) and flat (`KALSHI_API_KEY`) TOML layouts.
- **Dependency pins loosened:** Changed all `==` pins to `>=` in `requirements.txt` — Streamlit Cloud runs Python 3.14 which can't build `scipy==1.11.4` from source (no Fortran compiler).
- **Repo public-readiness:** Removed tracked `reports/` and `.claude/memory/` from git (were committed before gitignore rules). Added `.claude/memory/` to `.gitignore`.
- **sys.path fix:** Added `webapp/` directory to `sys.path` in `app.py` so bare imports work when Streamlit Cloud runs from the repo root.
- Files changed: `kalshi_client.py`, `webapp/services.py`, `webapp/app.py`, `requirements.txt`, `.gitignore`

---

## 2026-04-06 -- Dynamic Stdev Adjustment (S5 Enhancement)

### S5. Dynamic Stdev Adjustment for Weather
- **Problem:** Sport-specific standard deviations in the normal CDF model were static constants. Weather, rest/B2B, and pitcher signals adjusted confidence or fair value, but only pitcher and rest affected the CDF stdev (and only for totals, not spreads). Spreads had no dynamic stdev adjustment at all.
- **Fix:** Weather now contributes a `stdev_adjustment` alongside its existing fair-value shift. The adjustment scales by severity: severe (+0.5), moderate (+0.3), mild (+0.1), none (0.0). Dome stadiums always return 0.0. Both `detect_edge_spread()` and `detect_edge_total()` now compound all applicable stdev adjustments (weather + rest for spreads; weather + rest + pitcher for totals).
- **Spread improvement:** `consensus_spread_prob()` now accepts a `stdev_adjustment` parameter, bringing spreads to parity with totals. Previously spreads used only the static sport-specific stdev.
- **Caching:** New `_weather_for_market()` cached helper in `scan_all_markets()` fetches weather once per home team, avoiding duplicate NWS API calls across spread and total markets for the same game.
- **Effect:** Bad weather increases the stdev in the normal CDF model, making the system more conservative on alternate lines where uncertainty compounds. Spreads now benefit from the same dynamic stdev pipeline that totals already had.
- Files changed: `scripts/shared/sports_weather.py` (added `stdev_adjustment` to return dict), `scripts/kalshi/edge_detector.py` (`consensus_spread_prob()` accepts stdev_adjustment, `detect_edge_spread()` and `detect_edge_total()` accept weather_data, new `_weather_for_market()` cache helper)

---

## 2026-04-06 -- Code Simplification (S5, S6)

### S5. Deleted `config.py` (Dead Module)
- **Problem:** `scripts/shared/config.py` defined env vars and constants (scoring weights, crypto/weather/SPX constants, `CONFIDENCE_RANK`) that were dead code -- no consumer imported them. The only two live imports were `LOG_DIR` and `LOG_LEVEL` used by `logging_setup.py`.
- **Fix:** Deleted `config.py` entirely. `logging_setup.py` now defines `LOG_DIR` and `LOG_LEVEL` inline (reads from env with `dotenv`). `webapp/services.py` now reads its env vars directly with `os.getenv()` instead of importing from config.
- Files changed: `config.py` (deleted), `logging_setup.py`, `webapp/services.py`

### S6. Removed `MAX_POSITION_CONCENTRATION` Env Var and Risk Gate
- **Problem:** Gate 7 (concentration cap at 20% of bankroll) was redundant with the `MAX_BET_SIZE` hard cap. The hard cap already limits any single position to $100, making a percentage-of-bankroll check unnecessary for the current bankroll range.
- **Fix:** Removed `MAX_CONCENTRATION` variable and concentration gate from `kalshi_executor.py`. Removed `MAX_POSITION_CONCENTRATION` from `.env`, `.env.example`, and `CLAUDE.md`. Removed `APPROVED_CAPPED_CONCENTRATION` approval subtype. Renumbered remaining gates: old gate 8 (max bet size) is now gate 7, old gate 9 (bet ratio cap) is now gate 8.
- **Gate count:** 9 gates reduced to 8. Gates 1-6 reject, gates 7-8 are sizing caps (max bet, bet ratio).
- **Tests:** Concentration gate test removed (101 tests down to 100).
- Files changed: `kalshi_executor.py`, `.env`, `.env.example`, `CLAUDE.md`

---

## 2026-04-06 -- Code Simplification (S3, S4)

### S3. Removed `--max-bet-ratio` and `--max-per-game` CLI Flags
- **Problem:** `--max-bet-ratio` and `--max-per-game` were available as CLI flags, duplicating env-only settings. This added unnecessary complexity to the CLI surface and every scanner's argument parser.
- **Fix:** Removed `--max-bet-ratio` from `edge_detector.py`, `kalshi_executor.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`, and `scan.py` help text. Removed `--max-per-game` from `edge_detector.py` and `kalshi_executor.py`. Removed `max_per_game` and `max_bet_ratio` parameters from `execute_pipeline()` signature.
- **Configuration:** Both settings are now `.env`-only: `MAX_BET_RATIO` (default 3.0) and `MAX_PER_EVENT` (default 2).
- Files changed: `kalshi_executor.py`, `edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`, `scan.py`

### S4. Merged `MAX_BET_SIZE_SPORTS` / `MAX_BET_SIZE_PREDICTION` into Single `MAX_BET_SIZE`
- **Problem:** Two separate env vars (`MAX_BET_SIZE_SPORTS=$50`, `MAX_BET_SIZE_PREDICTION=$100`) required a category lookup helper (`_max_bet_for()`) and a `_SPORTS_CATEGORIES` set in the executor. The distinction added complexity without meaningful risk benefit.
- **Fix:** Unified into a single `MAX_BET_SIZE` env var (default $100). Removed `MAX_BET_SIZE_SPORTS`, `MAX_BET_SIZE_PREDICTION`, `_SPORTS_CATEGORIES` set, and `_max_bet_for()` helper from executor. Risk check dashboard now shows a single "Max Bet Size" row. Gate 8 uses `MAX_BET_SIZE` directly.
- Files changed: `kalshi_executor.py`, `config.py`, `risk_check.py`, `.env.example`

---

## 2026-04-06 -- Code Simplification (S1, S2)

### S1. Removed `DEFAULT_BET_SIZE` (Dead Code)
- `DEFAULT_BET_SIZE` was defined in `kalshi_executor.py` but never referenced anywhere in the codebase. Removed the line. No behavioral change.

### S2. Removed `MIN_CONFIDENCE` Env Var and Risk Gate
- **Problem:** The confidence-floor risk gate (`MIN_CONFIDENCE`) was redundant. Composite score already incorporates confidence as 30% of its weight, so a low-confidence opportunity is already penalized in the score gate. Having a separate confidence gate added complexity without adding safety.
- **Fix:** Removed the `MIN_CONFIDENCE` env var from `kalshi_executor.py`, `config.py`, and `.env.example`. Removed `CONFIDENCE_RANK` dict from executor (kept in `config.py` with a note for scoring use). Removed risk gate 5 (confidence floor). Remaining gates renumbered: old 6-10 become 5-9.
- **Gate count:** 10 gates reduced to 9. Gates 1-4 reject, gates 5-6 reject (duplicate ticker, per-event cap), gates 7-9 are sizing caps (concentration, max bet, bet ratio).
- **Tests:** Confidence gate test removed (102 tests down to 101).
- Files changed: `kalshi_executor.py`, `config.py`, `.env.example`

---

## 2026-04-06 -- Bet Ratio Cap (Risk Gate 10) & Markdown Table Fix

### Risk Gate 10: Bet Ratio Cap (`MAX_BET_RATIO`)
- **Problem:** Kelly sizing could let one high-edge, low-price bet dominate a batch. For example, 41 contracts at $0.21 = $8.61 while two other bets cost ~$2 each. A single outlier absorbs most of the batch budget.
- **Fix:** New `MAX_BET_RATIO` parameter (default 3.0). No single bet can cost more than 3x the median batch cost. Only scales down outliers -- other bets in the batch are untouched.
- **Gate type:** Sizing cap (like gates 8-9). Downsizes the outlier rather than rejecting it. Fires after Kelly sizing and before budget cap.
- **Usage:** Set in `.env` as `MAX_BET_RATIO=3.0` or override per-run with `--max-bet-ratio 2.0`
- **CLI:** `--max-bet-ratio` flag added to all scanners (`edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`) and `scan.py`
- Files changed: `kalshi_executor.py` (new env var, `_apply_bet_ratio_cap()` function, `execute_pipeline()` kwarg, CLI flag), `edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py` (CLI flag + pass-through), `scan.py` (help text), `.env.example`, `CLAUDE.md`

### Markdown Table Pipe Fix
- **Problem:** Report markdown tables had broken column alignment on some rows. `format_bet_label()` in `ticker_display.py` was replacing `" (vs "` with `" | "`, injecting a literal pipe character into markdown table cells -- breaking the table structure.
- **Fix:** Changed replacement from `" | "` to `" vs "` in `ticker_display.py`. Added `.replace("|", "/")` sanitization on bet and pick labels in `report_writer.py` (both scan and execution report writers) as a safety net against future pipe injection.
- Files changed: `ticker_display.py`, `report_writer.py`

---

## 2026-04-06 -- Streamlit Web Dashboard (U6)

### Web Dashboard v1.0
- **Purpose:** Lightweight web UI for occasional remote access. CLI remains primary interface.
- **Stack:** Streamlit with custom dark theme (JetBrains Mono + Outfit fonts, cyan/amber/red accent palette)
- **Pages:**
  - **Scan & Execute** — all CLI flags as controls, scan to find opportunities, preview to see sizing/costs, execute to place orders
  - **Portfolio** — balance, open positions, P&L, daily loss limit progress, resting orders
  - **Settle & Report** — settle completed markets, generate P&L reports rendered as formatted markdown
- **Architecture:** Thin service layer (`webapp/services.py`) wraps existing scanner/executor/settler functions. Captures `rich` console output via stdout redirect. No business logic duplication.
- **Theme:** Custom CSS injection (`webapp/theme.py`) — dark terminal aesthetic with grid overlay, styled metric cards, gradient buttons
- **Auth:** Optional password gate via `.streamlit/secrets.toml` (gitignored)
- **Code changes:** `kalshi_settler.py` `generate_report()` now returns markdown string for web rendering
- **Skill:** Official `streamlit/agent-skills` installed at `.claude/skills/developing-with-streamlit/` (17 sub-skills)
- **Docs:** `docs/web-app/` — SETUP.md, USAGE.md, ARCHITECTURE.md
- Launch: `streamlit run webapp/app.py`

### Dashboard Enhancements (D1, D2, D4 + polish)
- **D1: Quick-scan sidebar buttons** — Sports, Futures, Prediction, Polymarket buttons in sidebar pre-select market type
- **D2: Favorite scans** — Save/load/delete named scan configs. Stored in `data/webapp/favorites.json`. Favorites appear in sidebar for one-click loading.
- **D4: Default unit size** — Changed from $1.00 to $0.50
- **Dynamic controls** — Filter, category, budget, max-per-game, and cross-ref controls adapt based on selected market type. Sports-only params hidden for futures/prediction/polymarket.
- **Clear button** — Wipes all scan results, preview, and execution data for a fresh start
- **ANSI stripping** — Console output cleaned of escape codes and rich markup before display
- **Rich table removal** — Preview shows clean pipeline summary + Streamlit dataframe instead of box-drawing character tables
- **Expander replacement** — All `st.expander` widgets replaced with toggle buttons (Material icon font renders as broken text in the custom theme)

---

## 2026-04-06 -- Min-Bets Safety Gate

### `--min-bets` Flag
- **Problem:** With `--budget 10%` and `--max-bets 6`, if only 1-2 games pass risk checks, the entire budget gets concentrated into too few positions — defeating the purpose of diversification.
- **Fix:** New `--min-bets N` flag across all scanners. If fewer than N opportunities pass the 9 risk gates, the pipeline aborts before execution with a clear message.
- **How it works:** Gate fires after risk checks but before sizing/budget scaling. Returns an empty list so no orders are placed and no reports are generated for an under-diversified batch.
- **No flag = no minimum:** When `--min-bets` is omitted (default `None`), the gate is skipped entirely — current behavior unchanged.
- Example: `scan.py sports --unit-size .5 --max-bets 6 --min-bets 3 --budget 10% --exclude-open --execute`
- Files changed: `kalshi_executor.py` (new gate in `execute_pipeline`), `edge_detector.py`, `prediction_scanner.py`, `polymarket_edge.py`, `futures_edge.py` (CLI flag + pass-through in all four)

---

## 2026-04-04 (evening) -- Budget Cap for Batch Execution

### `--budget` Flag
- **Problem:** No way to control total batch cost. Kelly + unit sizing determines per-bet amounts independently, but there was no ceiling on the sum. Users wanting to limit daily exposure to a fixed percentage of bankroll (e.g., 10%) had no mechanism to enforce it.
- **Fix:** New `--budget` flag on `scan.py`, `edge_detector.py`, and `kalshi_executor.py`. Accepts a percentage of bankroll (e.g., `10%`) or a flat dollar amount (e.g., `15`).
- **How it works:** After all bets are sized normally (Kelly/flat, per-bet caps), if total cost exceeds the budget, all approved bets are proportionally scaled down. Higher-edge bets keep proportionally more capital (Kelly weighting preserved). Each bet keeps at least 1 contract, so the actual total may slightly undershoot the budget due to contract rounding.
- **No budget = no change:** When `--budget` is omitted, the pipeline behaves exactly as before. When total is already under the budget, a green confirmation message is shown and no scaling occurs.
- Example: `scan.py sports --unit-size .5 --max-bets 5 --budget 10% --date today --exclude-open`
- Files changed: `kalshi_executor.py` (new `_apply_budget_cap()`, `budget` param on `execute_pipeline`, CLI flag), `edge_detector.py` (CLI flag + pass-through), `scan.py` (help text)

---

## 2026-04-04 (afternoon) -- Fill-Based Accounting, Sizing Gate Docs, Pitcher Parallelization

### X5. Fill-Based Trade Logging
- **Problem:** The executor logged `contracts` and `cost_dollars` from the *requested* order, not from the Kalshi API fill response. Resting or partially-filled orders overstated exposure, distorted P&L, and corrupted settlement math.
- **Fix:** `log_trade()` now records both requested and filled values:
  - `requested_contracts` / `requested_cost` — what we asked for
  - `filled_contracts` / `filled_cost` — what Kalshi actually executed (primary accounting fields)
  - `fill_status` — `resting` | `partial` | `filled`
  - Legacy `contracts` / `cost_dollars` now reflect filled values for backward compatibility
- New `get_filled_contracts()` and `get_filled_cost()` helpers in `trade_log.py` with backward-compatible fallback for pre-X5 trade records
- `kalshi_settler.py` — `calculate_pnl()` uses filled values; resting orders (zero fills) skipped during settlement; settlement log and reconciliation use filled contracts
- `risk_check.py` — "Total wagered" in P&L summary and dashboard uses filled cost
- Execution output now flags resting and partial fills visually: `(RESTING — no fills yet)`, `(PARTIAL — 3/10 filled)`
- **16 new regression tests** covering: fill helpers (old/new format), fully filled, partial fill, zero fill/resting, settlement P&L with fill-based cost

### X6. Sizing Caps vs Reject Gates (Docs + Code)
- **Problem:** `ARCHITECTURE.md` described gates 8 (concentration) and 9 (max bet) as reject gates, but the executor silently downsized and approved. Post-trade review couldn't tell if an order passed cleanly or was force-capped.
- **Fix (docs):** `ARCHITECTURE.md` now correctly documents gates 1-7 as reject gates and gates 8-9 as sizing caps with "Cap — downsize to..." behavior
- **Fix (code):** `size_order()` returns approval subtypes:
  - `APPROVED` — clean pass, no caps hit
  - `APPROVED_CAPPED_CONCENTRATION` — downsized by gate 8
  - `APPROVED_CAPPED_MAX_BET` — downsized by gate 9
- All downstream pipeline filtering updated to use `.startswith("APPROVED")`
- **3 new tests** for clean approval, concentration cap, and max bet cap scenarios

### Pitcher Stats Parallelization
- `prefetch_mlb_pitchers()` now uses `ThreadPoolExecutor(max_workers=8)` to fetch all pitcher stats concurrently
- MLB scan time reduced from ~60s to ~35s (pitcher fetch specifically: ~60s → ~11s)
- Single-game `get_game_pitchers()` also parallelized (2 pitchers fetched concurrently)

### Batch-Aware Kelly Sizing
- **Problem:** Kelly sizing was applied independently per bet, so placing 10 simultaneous bets could commit 10x what single-bet Kelly intends. Total batch exposure could exceed 50% of bankroll.
- **Fix:** `size_order()` now accepts a `batch_size` parameter. Kelly fraction is divided by the number of bets in the batch: `effective_kelly = KELLY_FRACTION / batch_size`. Each bet gets its proportional share, keeping total batch exposure consistent with what single-bet Kelly would allocate.
- `execute_pipeline()` passes `min(len(opportunities), max_bets)` as the batch size
- `KELLY_FRACTION` is now configurable in `.env` (was only in `.env.example` before)

### Bug Fix: Pitcher Data NoneType Error
- Fixed `AttributeError: 'NoneType' object has no attribute 'get'` when MLB Stats API returns `None` for a pitcher (TBD starters)
- Changed `pitcher_data.get("away_pitcher", {}).get(...)` to `(pitcher_data.get("away_pitcher") or {}).get(...)` in both game and totals detection paths

### Test Suite
- **102 tests** (up from 83): +16 fill accounting, +3 approval subtypes

---

## 2026-04-04 -- Per-Game Diversification, Pitcher Data, Rest Days, Calibration

### Correlated Bracket Dedup & Per-Game Cap Reduction
- **Problem:** Automated execution was stacking 3 of 5 bets on the same game (e.g., Over 221.5, Over 224.5, Over 228.5 on BOS@MIL). These are highly correlated — they win or lose together.
- **Fix 1:** New `dedup_correlated_brackets()` in `kalshi_executor.py` — groups opportunities by `(event_key, category)` and keeps only the highest composite score from each group. Multiple totals lines on the same game collapse to the single best one.
- **Fix 2:** `MAX_PER_EVENT` default lowered from 3 to 2 (allows ML + totals on the same game, but not 3 correlated lines)
- **Fix 3:** Scanner-level `_cap_per_game` in `edge_detector.py` also lowered from 3 to 2
- New `--max-per-game N` CLI flag on both `edge_detector.py` and `kalshi_executor.py` for session-level override
- `size_order()` accepts `max_per_event` parameter instead of using the global directly

### S1. MLB Starting Pitcher Data (`scripts/shared/pitcher_stats.py`)
- New module fetching probable pitchers + season stats from MLB Stats API (free, no key)
- **Stats fetched:** ERA, FIP (approximated), WHIP, K/9, innings pitched, record, days rest
- **Pitcher tiers:** ace (ERA ≤ 3.20), mid (ERA ≤ 4.50), back (ERA > 4.50 or TBD)
- **Matchup classification** with stdev adjustments to the total probability model:
  - ace vs ace: -0.3 stdev (tighter game, lean under)
  - ace vs mid: -0.15 stdev (lean under)
  - mid vs mid: no adjustment (neutral)
  - mid vs back: +0.2 stdev (lean over)
  - bullpen day: +0.5 stdev (high variance, lean over)
- **Integration in `edge_detector.py`:**
  - Pre-fetches all pitcher data per game date in `scan_all_markets()` (step 3c)
  - Totals: stdev adjusted by matchup quality, confidence bumped/dropped by pitcher signal
  - Games: pitcher info attached to details (informational — moneyline odds already price in starters)
  - `consensus_total_prob()` now accepts `stdev_adjustment` parameter
- **`prefetch_mlb_pitchers(date)`** — bulk pre-fetch for all games on a date, indexed by team abbreviation
- CLI: `python scripts/shared/pitcher_stats.py 2026-04-04` for a quick pitcher table

### S2. NBA/NHL Back-to-Back & Rest Day Detection (`scripts/shared/rest_days.py`)
- New module detecting back-to-backs and rest days via ESPN scoreboard API (free, no key)
- Checks 1-4 days back per team to calculate days since last game
- **NBA adjustments:** B2B adds +1.5 to stdev (more variance/fatigue), leans under. Well-rested (3+ days) tightens stdev by -0.5
- **NHL adjustments:** B2B adds +0.3 stdev, slight under lean
- Returns per team: `is_b2b`, `days_rest`, `opponent_is_b2b`, `rest_advantage`, `stdev_adjustment`, `confidence_signal`
- **Integration in `edge_detector.py`:**
  - Pre-fetches rest data for NBA/NHL in `scan_all_markets()` (step 3d)
  - Totals: stdev adjusted by rest situation, confidence bumped for under when B2B
  - Games/Spreads: confidence adjusted based on rest advantage (B2B team less likely to win/cover)
  - Rest info attached to opportunity details for transparency
- Auto-routes through `scan.py` — no extra flags needed
- CLI: `python scripts/shared/rest_days.py basketball_nba 2026-04-04` for a quick rest table

### W2. Model Calibration Tool (`scripts/kalshi/model_calibration.py`)
- New script analyzing settled trades to surface calibration issues and generate prioritized recommendations
- **Reports:** Overall Brier score, calibration curve (predicted vs realized by probability bucket), dimension breakdowns (category, confidence, sport, edge bucket), confidence x category cross-tab
- **Recommendations engine:** Prioritized HIGH/MEDIUM/LOW actions for stdev adjustments, confidence signal fixes, edge estimation issues
- **Parked until post-baseline data:** Calibration baseline set to 2026-04-03 — pre-baseline trades span multiple model versions and produce misleading recommendations. Re-run after 100+ post-baseline trades.
- CLI: `python scripts/kalshi/model_calibration.py --save --days 30`

### X4. Startup Doctor (previously implemented, marked DONE in roadmap)
- `scripts/doctor.py` verified functional — checks Python version, venv, credentials, data dirs, config, API connectivity, pre-commit hooks
- Fixed stale `MAX_PER_EVENT` default (3 → 2) in doctor display

---

## 2026-04-02 -- Execution Correctness, Risk Gates, Kelly Sizing, Display Overhaul

### X1. Portable Python Path
- `scan.py` now uses `sys.executable` instead of hardcoded `.venv/Scripts/python.exe`
- Works across any environment (CI, WSL, Docker, other machines)

### X2. Nine Risk Gates Enforced in Executor
- **Previously:** `kalshi_executor.py` loaded `KELLY_FRACTION`, `MAX_CONCENTRATION`, and `MAX_BET_SIZE` but never enforced them. Only 5 of 9 gates were active.
- **Now:** All 9 gates enforced before every order: daily loss, position count, edge, score, confidence, duplicate ticker, per-event cap, max concentration, max bet size
- **Kelly sizing:** Quarter-Kelly with flat unit as floor. High-edge bets get more contracts; low-edge bets stay at minimum unit size
- **Category-aware bet caps:** Sports ($50) vs prediction ($100) separate limits
- **Batch tracking:** Approved orders update the open ticker set and event counts in-flight so gates apply correctly across the run
- New env vars: `MAX_PER_EVENT=3`, `MAX_POSITION_CONCENTRATION=0.20`

### X3. Per-Event Position Caps (built into X2)
- Max 3 positions per game/event (configurable via `MAX_PER_EVENT`)
- Extracts event key from ticker (strips pick suffix) to group markets by game
- Prevents hidden concentration where 7 of 10 positions are on the same matchup

### D1. Bet Type Column
- Added Type column (ML/Spread/Total/Prop) to all 7 output tables across scan, execute, positions, and settlement views
- New `bet_type_from_ticker()` helper in `ticker_display.py`

### D2. Descriptive Pick Column
- Replaced raw YES/NO Side column with descriptive Pick: "Spurs win", "Over 220.5", "Blazers -7.5"
- New `format_pick_label()` helper in `ticker_display.py`
- Added Kalshi team abbreviation aliases (SAS, GSW, NOP, etc.)

### D3. Sport Column
- Added Sport column (NBA/NHL/MLB/NFL/NCAAB/etc.) to scan table, executor preview table, and markdown reports
- New `sport_from_ticker()` helper in `ticker_display.py`
- Added `KXNCAABB` prefix alias for NCAA basketball championship tickers

### D4. Context-Aware Report Saving
- When `--unit-size` is passed, saves an **execution report** (Sport, Bet, Type, Pick, Qty, Price, Cost, Edge, total cost) instead of the scan report
- When no `--unit-size`, saves the scan report as before (Mkt, Fair, Edge, Conf, Score)
- New `save_execution_report()` function in `report_writer.py`
- `execute_pipeline` now returns sized orders on preview (was returning `[]`) so the report writer can use them

### Same-Day Automated Execution Scripts
- New `scripts/schedulers/same_day_executions/same_day_scan.bat` — preview all sports today, top 10 across all sports
- New `scripts/schedulers/same_day_executions/same_day_execute.bat` — scan + execute, with portfolio status before/after
- Recommended run time: 8 AM ET (all markets posted, sportsbook lines sharp, Kalshi lag window open)
- Single command scans NFL, NBA, NHL, MLB together, ranked by composite score, 10 bets max total
- Next-day scripts also available at `scripts/schedulers/next_day_executions/` as reserve

### How Scoring Works (ARCHITECTURE.md)
- New section explaining the full flow: Fair Value → Edge → Confidence → Score
- Includes dependency diagram, confidence thresholds by market type, composite score formula with weights, and worked example

### Documentation Overhaul
- `docs/scripts/` subdirectory: 7 dedicated script docs (edge_detector, futures_edge, prediction_scanner, polymarket_edge, kalshi_executor, kalshi_settler, risk_check)
- `SCRIPTS_REFERENCE.md` slimmed to hub with routing table, common flags, daily workflow
- `kalshi_executor.py` reframed as Portfolio Status + Execution Library; `run` subcommand deprecated
- `scan.py` flags table added (13 flags documented)
- All 25 prompts updated + 6 new prompts added (totals-only, spreads-only, multi-sport-execute, weekly-review, risk-audit, full-prediction-execute)
- ARCHITECTURE.md, CLAUDE.md, README.md, SKILL.md, .env.example all updated with 9-gate risk model
- ROADMAP.md restructured with 6 tiers, informed by 3rd-party assessment

---

## 2026-03-31 -- Unified Scanner, Scheduler Reorganization, Env & Report Cleanup

### P9. Unified Scan Entry Point (`scripts/scan.py`)
- Single entry point routing to all 4 scanners: `sports`, `futures`, `prediction`, `polymarket`
- Auto-inserts `scan` subcommand when omitted
- Aliases: `sport`, `pred`, `poly`, `xref`
- All flags forwarded directly via subprocess — no duplicate argument parsing
- Updated Quick Start, More Examples, Daily Workflow, and Scripts Reference to use `scan.py`

### P10. Documentation Cleanup
- Updated SPORTS_GUIDE: replaced all `kalshi_executor.py run` with `scan.py sports`, removed duplicated daily workflow (defers to SCRIPTS_REFERENCE), fixed composite score dimensions (3 → 4 with weights), added roadmap cross-link
- Updated FUTURES_GUIDE and PREDICTION_MARKETS_GUIDE: `scan.py` commands, roadmap cross-links
- Updated ARCHITECTURE: replaced duplicated Phase 2-4 task lists with pointer to ROADMAP.md
- Added back-links from SCRIPTS_REFERENCE to all domain guides

### P11. Pre-Commit Hooks (`.pre-commit-config.yaml`)
- `detect-secrets` — credential leak prevention (requires `.secrets.baseline`)
- `black` — code formatting (line-length 100)
- `flake8` — linting (max-line-length 100, ignore E203/W503)
- `check-json`, `check-yaml` — config file validation
- `end-of-file-fixer`, `trailing-whitespace` — whitespace hygiene
- `no-commit-to-branch` — prevents direct commits to master
- Install: `make hooks` or `pip install pre-commit && pre-commit install`

### P12. Makefile
- 18 targets: `scan-mlb`, `scan-nba`, `scan-nhl`, `scan-nfl`, `scan-sports`, `scan-futures`, `scan-predictions`, `scan-polymarket`, `scan-all`, `status`, `risk`, `settle`, `report`, `reconcile`, `test`, `test-quick`, `install`, `hooks`
- `make help` for full reference
- Note: requires `make` installed (`choco install make` on Windows)

### Scheduler Directory Reorganization
- Moved 4 `.bat` morning scan jobs to `scripts/schedulers/morning_scans/`
- Moved 2 Python automation scripts to `scripts/schedulers/automation/`
- Fixed `PROJECT_ROOT` depth in `install_windows_task.py` for new path
- Updated all path references in CLAUDE.md, README.md, SCRIPTS_REFERENCE.md

### P7. `MAX_BET_SIZE_SPORTS` Added to `.env.example`
- Added `MAX_BET_SIZE_SPORTS=50` — was referenced in CLAUDE.md and used by `risk_check.py` but missing from the env template

### P8. Report Output Format Unified
- Confirmed all scanners support `--save` for markdown reports
- `kalshi_executor.py run` delegates scanning to dedicated scanners (which have `--save`), so no gap remains
- Marked complete in roadmap

---

## 2026-03-30 -- Unified CLI, Readable Displays, Date Filtering, Project Cleanup

### Unified CLI Flags Across All Scanners
- All 4 scanners (`edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`) now share the same execution flags: `--execute`, `--unit-size`, `--max-bets`, `--pick`, `--ticker`, `--save`
- Previously `--execute`/`--unit-size`/`--max-bets` only worked on `edge_detector.py` and `futures_edge.py`; prediction and polymarket scanners required routing through `kalshi_executor.py`

### Date & Open Position Filters
- Added `--date` flag to all scanners and executor: filter opportunities by game date
  - Accepts: `today`, `tomorrow`, `YYYY-MM-DD`, `MM-DD`, `mar31`
- Added `--exclude-open` flag: automatically skips markets where you already have an open position (both sides of the same game)
- Both filters work on all 5 entry points

### Shared Ticker Display Module (`scripts/shared/ticker_display.py`)
- New shared module for parsing Kalshi tickers into human-readable labels
- `parse_game_datetime()` -- extracts "Mar 30 6:40pm" from any ticker
- `parse_matchup()` -- extracts "White Sox @ Miami" from game tickers
- `parse_pick_team()` -- extracts picked team name from ticker suffix
- `format_bet_label()` -- best-effort readable label for any market type
- Team name lookups for MLB (30), NBA (30), NHL (32 teams)
- All 8 display tables across 7 scripts now show game date/time and readable matchup names

### Live Risk Dashboard (`scripts/kalshi/risk_check.py`)
- Rewritten to pull live data from Kalshi API (was reading empty local JSON files)
- Shows: account balance, risk limits, open positions with readable names + dates, resting orders, today's P&L, watchlist
- Positions table shows "Bet | When | Pick | Qty | Cost | P&L" instead of raw tickers

### Executor Status Improvements (`scripts/kalshi/kalshi_executor.py`)
- `status` command now shows readable matchups + game dates instead of raw tickers

### Markdown Report Format (`scripts/kalshi/kalshi_settler.py`)
- `report --detail --save` now generates proper markdown (tables, headers, bold values, code-formatted tickers)
- Changed file extension from `.txt` to `.md`

### MLB Filtering Guide (`docs/kalshi-sports-betting/MLB_FILTERING_GUIDE.md`)
- New comprehensive guide covering 10 filtering categories for MLB picks
- Includes composite strategies: "Strong MLB Play", "Weather Fade", "Sharp Follow", "Regression Fade", "Early Season Value"

### Markdown Scan Reports (`scripts/shared/report_writer.py`)
- New shared module: all scanners now save a markdown report alongside the JSON watchlist when `--save` is passed
- Reports include: readable matchups, game dates, edge/fair/market prices, confidence, composite score
- Saved to `reports/Sports/`, `reports/Futures/`, `reports/Predictions/` with date-stamped filenames
- Example: `reports/Sports/2026-03-30_mlb_sports_scan.md`

### Test Suite (83 tests)
- Created `tests/` with 4 test files covering the highest-value targets
- `test_risk_gates.py` (19 tests): position sizing (`unit_size_contracts`), all 5 risk gate rejections, bankroll capping, price clamping
- `test_ticker_display.py` (30 tests): team code splitting, date/time parsing, matchup rendering, date filtering, position exclusion
- `test_edge_detection.py` (14 tests): N-way de-vigging, normal CDF spread/total probability math
- `test_weather.py` (11 tests): MLB and NFL weather threshold adjustments, severity classification
- Shared fixtures in `conftest.py` for sample Opportunity objects

### Standardized Logging
- All 8 entry-point scripts migrated from `logging.basicConfig` + `logging.getLogger` to `setup_logging()` from `scripts/shared/logging_setup.py`
- Every script now gets console output (INFO+) plus a dedicated log file in `logs/` (DEBUG+)
- Zero `logging.basicConfig` calls remain in the codebase
- Library modules (`team_stats.py`, `line_movement.py`, etc.) correctly use `logging.getLogger()` to inherit config from entry points

### Consolidated Import Boilerplate
- Created `.venv/Lib/site-packages/edge_radar.pth` — auto-adds all script directories to `sys.path` when the venv is active
- Removed 16 `sys.path.insert(0, ...)` lines across 15 files
- Scripts now directly import shared modules without path setup boilerplate
- Created `scripts/bootstrap.py` as fallback for non-venv usage

### Removed Scheduler Framework
- Deleted `base_scheduler.py`, `sports_scheduler.py`, `prediction_scheduler.py`, `run_schedulers.py`, `scheduler_config.py`
- The framework was overengineered — every scheduler just called `scan_all_markets()` → `execute_pipeline()`, which the CLI scripts already do
- Replaced with direct Windows Task Scheduler / cron scheduling using the existing scanner scripts
- Kept `daily_sports_scan.py` (morning edge report) and `install_windows_task.py` (Task Scheduler helper)
- Removed `docs/schedulers/SCHEDULER_GUIDE.md`
- Added "Scheduling Your Own Scans" section to SCRIPTS_REFERENCE with `schtasks` examples

### Save Flag for Status & Risk Commands
- `kalshi_executor.py status --save` saves portfolio status as markdown to `reports/Accounts/Kalshi/kalshi_status_YYYY-MM-DD.md`
- `risk_check.py --save` saves full risk dashboard as markdown to `reports/Accounts/Kalshi/kalshi_dashboard_YYYY-MM-DD.md`
- Reports include: account balance, open positions (readable matchups + dates), today's P&L, resting orders, watchlist

### Project Cleanup
- Removed empty `strategies/` directory (edge detection is centralized in scanners, not strategy-pattern architecture)
- Updated CLAUDE.md project structure to reflect current state (`tests/`, `ticker_display.py`, `report_writer.py`)

---

## 2026-03-28 -- Polymarket Cross-Reference Integration

### Polymarket Edge Module (`scripts/polymarket/polymarket_edge.py`)
- New module: cross-references Kalshi market prices against Polymarket via the Gamma API (free, no key required)
- Fetches active Polymarket markets by category (crypto, weather, S&P, politics, companies)
- Fuzzy market matching engine using 4 signals: title similarity, strike price, expiry date, asset keyword overlap
- Standalone edge detection: surfaces price discrepancies between Kalshi and Polymarket as arbitrage-style signals
- Enrichment mode: boosts composite score when Polymarket confirms an existing edge, penalizes when it disagrees
- Standalone CLI: `polymarket_edge.py scan`, `polymarket_edge.py match TICKER`

### Prediction Scanner Integration (`scripts/prediction/prediction_scanner.py`)
- Added `--cross-ref` flag to enable Polymarket cross-referencing during scans
- Added `--filter polymarket` / `poly` / `xref` shortcuts (auto-enables cross-ref mode)
- When active, the scanner: (1) finds standalone cross-market edge opportunities, and (2) enriches all existing opportunities with Polymarket confirmation/disagreement signals
- New `cross_ref` parameter on `scan_prediction_markets()` for programmatic use

---

## 2026-03-23 -- Edge Model Overhaul, Scheduler Framework, Doc Consolidation

### Spread & Total Model Recalibration (`scripts/kalshi/edge_detector.py`)
- Replaced linear probability adjustment (`+3% per point`) with normal CDF model using `scipy.stats.norm`
- Infers expected score margin from book spread + implied probability, then calculates P(margin > strike) on the bell curve
- Added sport-specific standard deviations: NBA (12), NCAAB (11), NFL (13.5), MLB (3.5), NHL (2.5), soccer (1.8)
- Same fix applied to total (over/under) markets with separate total stdev values
- Old model systematically overestimated edge on alternate spreads (caused 1W-11L on NCAAB)

### Daily Morning Scan (`scripts/schedulers/daily_sports_scan.py`)
- New script: scans MLB, NBA, NHL, NFL each morning for top 25 opportunities
- Saves timestamped report to `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md`
- Report includes edge, fair value, market price, confidence, team stats, sharp signals, weather
- `--daemon` flag runs via APScheduler at 8:00 AM PST daily with automatic DST handling
- `--top N` to customize number of opportunities (default 25)

### Line Movement & Sharp Money Detection (`scripts/shared/line_movement.py`)
- New module: ESPN scoreboard API provides opening vs closing odds (DraftKings) for free
- Detects reverse line movement (spread moves away from favorite = sharp on underdog)
- Detects sharp total movement (total drops/rises >2 pts)
- Pre-fetched once per scan, integrated into game/spread/total confidence signals
- Sharp agreement boosts confidence; contradiction reduces it
- Covers NBA, NFL, NHL, MLB, NCAAB, NCAAF

### Weather Impact for Outdoor Sports (`scripts/shared/sports_weather.py`)
- New module: NWS hourly forecast for 31 NFL + 30 MLB venues (dome/outdoor classified)
- Scoring adjustment model: wind >15mph, rain >40%, cold <32F (NFL) / <45F (MLB)
- Integrated into `detect_edge_total()`: bad weather reduces over fair value, boosts under
- Dome stadiums automatically skipped (zero adjustment)
- Free NWS API, no key required

### Team Stats Integrated into Edge Detection (`scripts/kalshi/edge_detector.py`)
- Game and spread edge detectors now look up team win% via `team_stats.py`
- Stats signal: "supports" (win% >= 60% for YES, <= 40% for NO), "contradicts" (opposite), or "neutral"
- Confidence is bumped up one level when stats support the bet, dropped when stats contradict
- Team record and signal stored in opportunity details for transparency

### Sharp Book Weighting (`scripts/kalshi/edge_detector.py`, `scripts/kalshi/futures_edge.py`)
- Added `BOOK_WEIGHTS` map: Pinnacle/Circa at 3x, mid-tier at 1-1.5x, DraftKings/FanDuel/BetMGM at 0.7x
- Replaced simple median with `weighted_median()` across all consensus functions (game, spread, total, futures)
- Sharp books pull the consensus fair value toward their more accurate lines
- 21 books mapped with weights; unknown books default to 1.0x

### Team Stats Module (`scripts/shared/team_stats.py`)
- New module providing team performance data from free APIs (no keys required)
- ESPN API: NBA, NCAAB, NFL, NCAAF standings, win%, points for/against
- NHL Stats API: standings, goal differential, L10 record, streak
- MLB Stats API: standings, run differential, winning percentage
- 6 sports covered, unified `get_team_stats(team, sport)` lookup with fuzzy name matching
- Data cached per session to minimize API calls

### Closing Line Value Tracking (`scripts/kalshi/kalshi_settler.py`)
- Settler now captures closing price from Kalshi API when settling trades
- Calculates CLV = closing_price - entry_price per trade
- Performance report includes CLV section: average CLV and beat-the-close rate
- CLV is the gold standard for validating whether the model has real predictive value

### Rebranded to Edge-Radar
- Renamed from FinAgent / Finance-Agent-Pro / edge-hunter to Edge-Radar
- Updated all references across CLAUDE.md, README, ARCHITECTURE, agents, Python docstrings, User-Agent headers, reports, and memory

### Documentation Consolidation
- Merged `USER_GUIDE.md` + `BETTING_GUIDE.md` into single `SPORTS_GUIDE.md` (1117 → 405 lines)
- Replaced `KALSHI_STRATEGY_PLAN.md` with lean `ARCHITECTURE.md` (pipeline, risk gates, data flow)
- Trimmed `FUTURES_GUIDE.md` (456 → 359 lines) and `PREDICTION_MARKETS_GUIDE.md` (414 → 252 lines)
- Slimmed `README.md` (206 → 79 lines) with doc index linking to all guides
- Eliminated ~600 lines of duplicated risk gates, command examples, and filter tables across docs

---

## 2026-03-23 -- Scheduler Framework, Trade Log Cleanup, Report Export

### Scheduler Framework (`scripts/schedulers/`)
- New per-market scheduler architecture — each sport/market gets its own independent scheduler
- `BaseScheduler` class with DRY_RUN enforcement, consecutive failure auto-pause (5 strikes), structured logging
- `SportsScheduler` and `PredictionScheduler` subclasses calling existing pipelines directly (no subprocess wrapping)
- `scheduler_config.py` — profiles loaded from `SCHED_{NAME}_*` env vars (9 registered: NBA, NHL, MLB, NFL, NCAA, soccer, crypto, weather, SPX)
- `run_schedulers.py` — CLI entry point: `--list` (show all profiles), `--only nba` (single), or launch all enabled in parallel
- All schedulers disabled by default — enable via `SCHED_{NAME}_ENABLED=true` in `.env`
- Docs: `docs/schedulers/SCHEDULER_GUIDE.md`

### Trade Log Cleanup
- Cross-validated local trade log against Kalshi API fills — identified 32 demo trades mixed with 12 live trades
- Purged all demo trades from `kalshi_trades.json` and `kalshi_settlements.json`
- Backups saved: `kalshi_trades_pre_cleanup_2026-03-23.json`, `kalshi_settlements_pre_cleanup_2026-03-23.json`
- Report now shows accurate live-only data: 12 trades, $10.67 wagered

### Report File Export
- Added `--save` flag to `kalshi_settler.py report` — writes plain-text report to `reports/Accounts/Kalshi/kalshi_report_YYYY-MM-DD.txt`
- Report includes timestamp, strips Rich markup for clean text output

### Kalshi Client Hardening
- Changed default `KALSHI_BASE_URL` fallback from demo API to production API
- Prevents accidental demo connection if env var is unset

### Odds API Key Expansion
- Added 2 additional Odds API keys (3 total) for increased rate limit capacity
- Existing key rotation in `odds_api.py` handles this automatically

### Memory System
- Added `.claude/memory/` for cross-session project context
- CLAUDE.md updated to instruct Claude Code to check memory on startup

### Futures Betting Improvements (`scripts/kalshi/futures_edge.py`)
- Added `KXNBA` (NBA Finals Champion), `KXNHL` (Stanley Cup Champion), `KXMLB` (World Series Champion) to futures map — only conference/playoff markets were previously mapped
- Added human-readable labels to all futures: output now shows "NBA Finals Champion: Oklahoma City Thunder" instead of just the ticker
- `--filter nba-futures` now scans Finals champion + both conference winners
- `--filter nfl-futures` cleaned up (removed KXNFLMVP which has no Odds API data)
- Bet type label stored in `details["bet_type"]` and used as the display title
- CLI table shows "Bet Type" column instead of raw ticker
- Updated FUTURES_GUIDE.md with NBA Finals section and corrected filter descriptions

### Per-Game Opportunity Cap (`scripts/kalshi/edge_detector.py`)
- Limits scan results to top 3 opportunities per game (sorted by edge)
- Groups markets by date+matchup extracted from ticker (e.g., all spreads/totals/game for Michigan vs Alabama share one key)
- Prevents a single game from dominating the opportunity list

### PR #14 Review
- Reviewed and rejected Jules-generated PR "Automate Kalshi Betting Pipeline & Optimize Execution"
- Issues: missing `KELLY_FRACTION` constant (runtime crash), no `DRY_RUN` gate on scheduler, missing `apscheduler` dependency, unexplained `cryptography` addition
- Built proper scheduler framework as replacement (see above)

---

## 2026-03-22 -- Live Trading, Prediction Markets, Project Reorganization

### Switched to Live Trading
- Moved from Kalshi demo to live production API
- Set `DRY_RUN=false`, `MAX_BET_SIZE_PREDICTION=5`
- Demo credentials archived in `.env` comments

### Git Repository
- Published to GitHub as private repo: `michaelschecht/Edge-Radar`
- Working branch: `mike_desktop`

### Kalshi Bettor Agent & Skill
- New `.claude/agents/KALSHI_BETTOR.md` -- dedicated Kalshi betting agent
- New `.claude/skills/kalshi-bet/SKILL.md` -- `/kalshi-bet` slash command for scan/execute/settle
- Agent auto-runs status on startup, previews before executing, respects all risk gates

### Financial Analysis Skill
- New `.claude/skills/financial-analysis/` -- research and analysis skill
- Templates: stock analysis, earnings/corporate, global markets, market sentiment, investment strategy

### Futures / Championship Edge Detector (`scripts/kalshi/futures_edge.py`)
- N-way de-vigging of outright odds from 5-12 sportsbooks
- Fuzzy name matching between Kalshi candidates and Odds API outcomes with alias table
- Supported: NFL Super Bowl, NBA conference winners, NHL conference winners, MLB playoffs, NCAAB MOP, PGA golf
- Filter shortcuts: `futures`, `nba-futures`, `nhl-futures`, `mlb-futures`, `ncaab-futures`, `golf-futures`, `nfl-futures`
- Integrated routing from `edge_detector.py` -- `--filter nba-futures` auto-routes to futures scanner
- Browse-only: NBA/NHL awards, Heisman, soccer leagues, F1, NASCAR, IPL

### Unfiltered Scan Fix
- Running the scanner without `--filter` now scans all known sport prefixes instead of pulling 5000 generic multi-event markets
- Results: 959+ sport markets across NBA, NCAAB, MLB, NHL instead of 0

### Sport Filter Expansion
- Expanded `FILTER_SHORTCUTS` from 5 to 27 sports based on live Kalshi market discovery
- Added: NFL, NCAA women's basketball, NCAA football, MLS, Champions League, EPL, La Liga, Serie A, Bundesliga, Ligue 1, UFC, boxing, F1, NASCAR, PGA golf, IPL cricket, individual esports (CS2, LoL)
- Added NBA player props (3PT, rebounds, assists, steals, points) and awards (MVP, ROY, DPOY)
- Added NHL awards (Hart, Norris, Calder)

### Prediction Market Edge Detectors (`scripts/prediction/`)
- **`probability.py`** -- shared math: strike probability (log-normal model), weather probability (normal model), realized volatility
- **`crypto_edge.py`** -- BTC, ETH, XRP, DOGE, SOL edge detection via CoinGecko (free API, with rate limit retry)
- **`weather_edge.py`** -- NYC, Chicago, Miami, Denver temperature markets via NWS API (free, no key). Uncertainty scales with forecast horizon.
- **`spx_edge.py`** -- S&P 500 binary options using Yahoo Finance for price + VIX for implied volatility
- **`mentions_edge.py`** -- TV mention markets: Poisson model for KXLASTWORDCOUNT (word counts), historical YES rate for binary mention markets (KXPOLITICSMENTION, KXFOXNEWSMENTION, KXNBAMENTION)
- **`companies_edge.py`** -- KXBANKRUPTCY (normal distribution vs historical ~750/yr baseline), KXIPO (browse only)
- **`politics_edge.py`** -- KXIMPEACH, KXQUANTUM, KXFUSION: time-decay hazard model with calibrated annual probabilities
- **`prediction_scanner.py`** -- unified CLI scanner with filters: crypto, weather, spx, mentions, companies, politics, techscience, and individual asset/series shortcuts
- All detectors produce the same `Opportunity` dataclass compatible with the existing executor pipeline

### Project Reorganization
- **Scripts:** Moved all Kalshi scripts to `scripts/kalshi/`, new prediction scripts in `scripts/prediction/`
- **Docs:** Reorganized into `docs/kalshi-sports-betting/` and `docs/kalshi-prediction-betting/`
- Fixed all `parent.parent` path resolution for new script depth
- Updated all cross-references across CLAUDE.md, agents, skills, and docs
- Removed local filesystem paths from all committed files

### Architecture Optimization
- **`scripts/shared/opportunity.py`** -- single Opportunity dataclass (was duplicated in edge_detector + prediction_scanner)
- **`scripts/shared/trade_log.py`** -- centralized trade log I/O (was duplicated in executor, settler, edge_detector)
- **`scripts/shared/paths.py`** -- standardized path setup replacing ad-hoc sys.path hacks
- **`scripts/shared/config.py`** -- centralized config: risk limits, scoring weights, model params, all loaded from .env
- **`scripts/shared/logging_setup.py`** -- dual logging to console (INFO+) and daily log file (DEBUG+) in `logs/`
- **`--prediction` flag on executor** -- prediction scanner now feeds directly into the execution pipeline
- **`reconcile` command on settler** -- compares local trade log vs Kalshi API positions, flags discrepancies
- **CLAUDE.md** updated to reflect actual implementation status vs planned features
- **`.env.example`** updated with all actually-used variables

### Odds API Key Rotation (`scripts/shared/odds_api.py`)
- Supports multiple API keys via `ODDS_API_KEYS=key1,key2,key3` in `.env`
- Auto-rotates to next key on 401/429 (exhausted/rate limited)
- Tracks remaining requests per key from response headers
- Warns when a key drops below 10 remaining
- Backwards compatible with single key

### Prompt Library (`prompts/`)
- 18 ready-to-use prompts for agents across 3 categories:
  - `prompts/sports-betting/` (6): daily scan, sport-specific, execute, settle, high conviction, compare
  - `prompts/futures/` (5): championship scan, sport report, weekly tracker, best value, portfolio builder
  - `prompts/predictions/` (7): all predictions, crypto, weather, SPX, mentions, execute, morning brief

### Reports
- `reports/NFL/2026-03-22_superbowl_futures.md` -- Super Bowl analysis (KC NO +1.6% best edge)
- `reports/mlb/2026-03-22_mlb_playoff_futures.md` -- MLB playoffs (Cleveland YES +25.5%, Cincinnati YES +21.0%)
- `reports/NBA/2026-03-22_nba_championship_futures.md` -- NBA championship (OKC YES +26.3% biggest edge across all sports)

### README
- Complete rewrite focused on sports betting, futures, and prediction markets
- Project structure, quick start, all market categories, API reference
- Removed financial-analysis skill (project dedicated to betting)

### Repo Renamed
- `Finance-Agent-Pro` -> `edge-hunter` -> `Edge-Radar`

### New Skills
- `market-mechanics-betting` -- betting theory, Kelly criterion, scoring rules
- `polymarket` -- API reference, trading guides, getting started docs

### Documentation
- `docs/kalshi-sports-betting/BETTING_GUIDE.md` -- comprehensive sport-by-sport guide with all 27 filters
- `docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md` -- crypto, weather, S&P 500, mentions, companies, politics, tech/science
- `docs/kalshi-futures-betting/FUTURES_GUIDE.md` -- NFL, NBA, NHL, MLB, golf futures with N-way de-vig
- Updated KALSHI_BETTOR agent and kalshi-bet skill with futures + prediction commands
- Updated all docs to reflect live trading, new script paths, and new commands

---

## 2026-03-18 (Session 2) -- Settlement Tracker, Filters, Unit Sizing

### Settlement Tracker (`scripts/kalshi/kalshi_settler.py`)
- Polls Kalshi settlements API and matches results to trade log
- Falls back to checking individual market status if settlement not yet posted
- Calculates per-trade P&L: revenue, cost, fees, net P&L, ROI, win/loss
- Updates trade log records with `closed_at`, `net_pnl`, `settlement_result`, `settlement_won`
- Saves settlement history to `data/history/kalshi_settlements.json`
- Performance report with: win rate, profit factor, ROI, best/worst trades
- Edge calibration: estimated edge vs. realized edge, realization rate
- Breakdowns by confidence level and market category
- `--detail` flag for per-trade table

### Sport Filtering (`--filter`)
- Added `--filter` flag to both `edge_detector.py scan` and `kalshi_executor.py run`
- Named shortcuts: `ncaamb`, `nba`, `nhl`, `mlb`, `esports`
- Also accepts raw Kalshi ticker prefixes (e.g. `KXHIGHNY`, `KXINX`)
- Only fetches odds for the filtered sport, saving Odds API quota
- Added `KXNCAAMBGAME` to category map and odds sport mapping

### Fixed Unit Sizing
- Replaced Kelly criterion with fixed unit sizing
- Default unit size: $1.00 (configurable via `UNIT_SIZE` in `.env`)
- Contracts = round($unit / price), always at least 1
- Override per run with `--unit-size` flag
- Examples: $0.02 price -> 50 contracts, $0.50 price -> 2 contracts

### Kalshi Client Update
- Added `get_settlements()` method for settlement history endpoint

### Documentation
- `docs/kalshi-sports-betting/USER_GUIDE.md` -- Complete usage guide with filtering and unit sizing sections
- Updated all docs to reflect settlement tracker, filters, and unit sizing

---

## 2026-03-18 (Session 1) -- MVP Pipeline Complete

### Kalshi API Client (`scripts/kalshi/kalshi_client.py`)
- Built authenticated API client with RSA-PSS request signing
- Supports: get_markets, get_market, get_all_open_markets, get_balance, get_positions, get_fills, create_order, cancel_order, get_order, get_orders
- CLI for quick testing (balance, markets, positions, orders, market detail)
- DRY_RUN safety gate blocks live orders on non-demo environments
- Auto-resolves relative key paths from project root
- Tested against demo env -- all endpoints confirmed working

### Edge Detector (`scripts/kalshi/edge_detector.py`)
- Scans 5000+ open Kalshi markets via paginated API calls
- Categorizes markets by ticker prefix: game, spread, total, player_prop, esports, mention, other
- Integrates with The Odds API for sportsbook consensus pricing
- Three edge models implemented:
  - **Game outcomes:** De-vigs h2h odds from 8-12 books, takes median as fair value
  - **Spreads:** Adjusts book spread probability for Kalshi strike difference
  - **Totals:** Adjusts book total probability for Kalshi line difference
- Fuzzy team name matching between Kalshi and Odds API (alias table + substring matching)
- Composite scoring: 40% edge strength, 30% confidence, 20% liquidity, 10% time sensitivity
- CLI: `scan` (batch scan) and `detail` (single market deep dive)
- Saves scored opportunities to `data/watchlists/kalshi_opportunities.json`

### Automated Executor (`scripts/kalshi/kalshi_executor.py`)
- Full scan-to-execution pipeline in one command
- Risk management gates before every order:
  - Daily loss limit check
  - Max open positions check
  - Minimum edge threshold
  - Minimum composite score
  - Confidence level filter
- Quarter-Kelly position sizing with concentration caps
- Executes limit orders on Kalshi, logs all trades
- Trade logging to `data/history/kalshi_trades.json` with full context (edge, fair value, Kelly fraction, fees)
- Portfolio status dashboard: balance, positions, P&L, resting orders, daily activity
- CLI: `run` (preview or execute), `status` (dashboard)

### First Live Demo Execution
- Placed 6 orders on Kalshi demo (1 manual test + 5 automated)
- 5 filled immediately, 1 resting
- Portfolio: $38.44 balance, $59.72 portfolio value, 5 open positions
- Total wagered: $74.09 across NBA games, spreads, MLB

### Configuration & Setup
- Demo API keys configured in `keys/demo/`
- Production API keys stored in `keys/live/`
- `.env` configured for demo environment
- `ODDS_API_KEY` added for The Odds API (free tier, 500 req/month)
- Added `keys/`, `*.key`, `*.pem` to `.gitignore`

### Documentation
- `docs/kalshi-sports-betting/KALSHI_STRATEGY_PLAN.md` -- System overview, pipeline description, remaining work
- `docs/kalshi-sports-betting/KALSHI_API_REFERENCE.md` -- API endpoints, auth, rate limits, CLI reference
- `docs/CHANGELOG.md` -- This file

---

## Pre-2026-03-18 -- Project Foundation

### Existing Before This Session
- `CLAUDE.md` -- Master project manifest with risk limits, agent roster, execution chain
- `.claude/agents/` -- 5 agent specs (MARKET_RESEARCHER, TRADE_EXECUTOR, RISK_MANAGER, DATA_ANALYST, PORTFOLIO_MONITOR)
- `scripts/kalshi/fetch_odds.py` -- The Odds API integration for sports value betting
- `scripts/kalshi/fetch_market_data.py` -- Multi-asset data fetcher (stocks, prediction markets, crypto)
- `scripts/kalshi/risk_check.py` -- Portfolio risk dashboard
- `scripts/sql/init_db.sql` -- Database schema (8 tables, 2 views)
- `.env.example` -- Environment variable template
- `.gitignore` -- Configured for Python, data files, credentials
- `.venv` -- Python virtual environment with dependencies
