# Weekly Scheduled Bet Task — Recommendation

> **Date:** 2026-04-22
> **Context:** Daily same-day bet script is already running. This doc recommends the best slot for an additional weekly script with no date filter, plus a broader cadence for regular automated betting (needed for R12 calibration volume — target 100 trades).
> **Status:** Infrastructure exists — all scripts are built. Task Scheduler entries are currently disabled; this doc is about which ones to re-enable and when.

---

## TL;DR

| Question | Answer |
|:---------|:-------|
| **Best day for weekly broad run** | Monday + Thursday |
| **Best time** | 5:20 AM PST (8:20 AM ET) — 15-min buffer after daily same-day finishes |
| **Script to use** | `scripts\schedulers\no_date_filter_executions\no_date_filter_execution.bat` (already built) |
| **Also re-enable** | `next_day_execute.bat` (Sun-Thu at 6:00 PM PST / 9:00 PM ET) to cover tomorrow's slate with fresh data |
| **Keep running** | `same_day_execute.bat` daily at current 5:05 AM PST (8:05 AM ET) |
| **Key caveat** | `no_date_filter` places bets on games up to a week out where pitcher/weather/lineup data is stale — `--min-bets 3` floor and 15% budget cap already mitigate, but monitor Brier score |

---

## Existing Infrastructure (Audit, 2026-04-22)

All scripts are built and tested. Only Task Scheduler registration is missing.

### Execution scripts

| Script | Flags | Purpose |
|:-------|:------|:--------|
| `scripts\schedulers\same_day_executions\same_day_execute.bat` | `--unit-size .5 --max-bets 7 --min-bets 3 --budget 15% --date today --exclude-open` | Today's games only |
| `scripts\schedulers\next_day_executions\next_day_execute.bat` | `--unit-size .5 --max-bets 6 --min-bets 3 --budget 10% --date tomorrow --exclude-open` | Tomorrow's games only (catch early lines) |
| `scripts\schedulers\no_date_filter_executions\no_date_filter_execution.bat` | `--unit-size .5 --max-bets 6 --min-bets 3 --budget 15% --exclude-open` | All available dates |

### Scan-only previews (matching pairs)

| Script | Purpose |
|:-------|:--------|
| `same_day_scan.bat` | Preview today, no bets |
| `next_day_scan.bat` | Preview tomorrow, no bets |
| `no_date_filter_scan.bat` | Preview full horizon, no bets |

### Report emailers (shell scripts in `scripts\custom\Shell-Scripts\`)

| Script | Purpose |
|:-------|:--------|
| `SameDay-Execution-Report.sh` | Emails same-day execution report |
| `NextDay-Edge-Report.sh` | Emails next-day edge report |
| `NoDateFilter-Execution-Report.sh` | Emails no-date-filter execution report |

All three invoke Claude via `--dangerously-skip-permissions -p` and use the `agentmail` skill to email the daily-generated report to `mikeschecht@gmail.com`.

---

## Recommended Cadence

The goal is **regular automated betting volume** (target: 100 trades for R12 calibration re-run) without over-committing capital on stale-data games.

> **Timezone note:** User's system runs on PST. All times in the tables below show PST with ET in parentheses. `schtasks` on Windows uses local system time (PST).

### Tier 1 — Core Daily (run every day)

| Task | Time (PST / ET) | Script | Rationale |
|:-----|:----------------|:-------|:----------|
| **Same-day execute** | **5:05 AM / 8:05 AM** | `same_day_execute.bat` | Current schedule — keep as-is; lineups/weather/pitchers freshest; Kalshi lag window still open |
| **Settlement** | **8:00 PM / 11:00 PM** | `kalshi_settler.py settle` | Bankroll + P&L accurate for next-day sizing |

### Tier 2 — Weekly Broad (re-enable Monday + Thursday)

| Task | Time (PST / ET) | Script | Rationale |
|:-----|:----------------|:-------|:----------|
| **No-date-filter weekly (Mon)** | **5:20 AM / 8:20 AM** | `no_date_filter_execution.bat` | Captures week-ahead edges on NFL, futures, multi-day series |
| **No-date-filter weekly (Thu)** | **5:20 AM / 8:20 AM** | `no_date_filter_execution.bat` | Catches weekend slate (Sat/Sun NFL, weekend MLB/NBA/NHL) with fresher data than Monday |

**Why Monday + Thursday, not just Monday:**
- Monday Mon-Wed games covered by same-day; NFL Sunday games are 6 days out → stale
- Thursday catches NFL Sunday games at 3 days out (freshest actionable horizon) + weekend slate
- Two touchpoints double the calibration volume, which is the actual goal here
- `--exclude-open` and Gate 7 (series dedup, 48hr) prevent double-dipping

**Why 5:20 AM PST (not 5:05 AM with the daily):**
- Daily `same_day_execute.bat` at 5:05 AM PST typically runs 3-8 min (status + multi-sport scan with parallel MLB pitcher fetches + execute + status)
- 15-min buffer at 5:20 AM PST guarantees daily finishes first
- Gate 5 (already-holding) then naturally blocks the weekly script from re-betting today's markets
- Clean sequential logs, no race conditions on `open_positions.json`

### Tier 3 — Next-Day Overnight (optional, recommended)

| Task | Time (PST / ET) | Script | Rationale |
|:-----|:----------------|:-------|:----------|
| **Next-day execute** | **6:00 PM / 9:00 PM** (Sun-Thu) | `next_day_execute.bat` | Locks in early lines the night before for tomorrow's slate; complements same-day by catching openers |

Skip Fri + Sat nights — Sunday NFL bets should come from Thursday weekly; Saturday college bets are niche.

### Tier 4 — Maintenance (not betting but critical)

| Task | Time (PST / ET) | Script | Rationale |
|:-----|:----------------|:-------|:----------|
| **Weekly calibration** | Sun 7:00 PM / 10:00 PM | `model_calibration.py --days 7 --save` | Weekly Brier score, calibration curve refresh |
| **Weekly backtest** | Sun 7:30 PM / 10:30 PM | `backtester.py --after <last-sun> --save` | Catches regressions in strategy performance |
| **Daily reconcile** | 8:30 PM / 11:30 PM | `kalshi_settler.py reconcile` | After settle, verifies no drift between local log and API |

---

## Rationale: Monday 8:15 AM for Weekly

### Why Monday

| Factor | Why this works |
|:-------|:--------------|
| **Fresh weekend data** | Sunday settler + Sunday backtest = bankroll, P&L, calibration all current before Monday sizing |
| **Full weekly slate visible** | NBA/NHL/MLB schedules posted and markets liquid on Kalshi by Monday AM |
| **NFL lines matured** | Openers post Sunday night; sharp money hits overnight → Monday AM lines are honest |
| **Pitcher data usable** | MLB starters confirmed for Mon/Tue games — near-term edge model works |
| **Avoids Sunday paralysis** | Sunday-night openers are soft but too far from fresh settlement data |

### Why NOT other weekly slots

| Slot | Problem |
|:-----|:--------|
| Sunday night | Openers soft, but MLB pitchers/weather/NBA-NHL lineups too far out → edge model degrades past 48-72hr |
| Friday AM | Weekend NFL-heavy, but misses Mon-Thu MLB games (~30-40% of weekly volume) |
| Tuesday AM | Doubles coverage with Monday's daily, adds little new data |

### Why add Thursday

- Monday bets on weekend NFL are 6 days out — lineup injuries/weather forecast variance kills edge quality
- Thursday catches Sunday NFL at 3 days out (Wednesday injury report is public, Friday's practice reports pending) — sweet spot
- Weekend MLB/NBA/NHL pitcher/lineup data better on Thursday than Monday

---

## The Core Caveat: Date-Unfiltered Scripts Have Edge Decay

Running `no_date_filter_execution.bat` means placing bets on games up to a week out. Signal reliability degrades by horizon:

| Signal | Usable Horizon | Breaks Beyond |
|:-------|:---------------|:--------------|
| MLB starter data (ERA, FIP, K/9) | ~48 hours | Starters not announced → model has no data |
| Weather (NFL/MLB venues) | ~72 hours | Forecast variance exceeds total-stdev adjustment |
| NBA/NHL lineups | ~24 hours | Load management / game-time decisions |
| Injury reports | ~24-36 hours | Questionable→out swings lines 3-6pts |
| Kalshi liquidity | 3-5 days out | Wider spreads, worse fills, slower resolution on resting orders |

**Existing mitigations in `no_date_filter_execution.bat`:**
- `--min-bets 3` floor — if fewer than 3 opportunities meet threshold, nothing fires
- `--budget 15%` cap — weekly exposure limited
- `--max-bets 6` — total position count controlled
- `--exclude-open` — no double-betting same market
- All 11 risk gates still enforced (including Gate 7 series dedup for 48hr)

**What to watch in calibration after 2-3 weeks:**
- Brier score delta between same-day bets and no-date-filter bets
- Win rate for bets placed >72hr before event vs <72hr
- ROI bucket by days-to-event at time of bet

If the >72hr bucket underperforms, tighten horizon (e.g., add `--date today,tomorrow,+2,+3` flag support, or split into a Friday script that only looks at Sat/Sun games).

---

## Scheduling Interaction Risks

### Gate 7 "Series Dedup Trap"

Gate 7 rejects same-matchup bets within 48hr (sport + team pair, date-agnostic).

**Example:** Weekly Monday script bets **Angels @ Yankees Monday night** → Gate 7 blocks the Tuesday daily from betting **Angels @ Yankees Tuesday night** for 48hr.

| Configuration | Outcome |
|:--------------|:--------|
| Weekly runs Monday + daily runs every morning | Intentional — prevents over-betting a single series |
| Weekly runs Monday AND Thursday | Thursday won't hit 48hr window for Mon MLB bets, so no conflict |
| Weekly runs Monday + Wednesday | Wednesday bets would block by Gate 7 if Monday already bet that matchup — wasted scan cycles |

**Conclusion:** Mon + Thu spacing is clean. Avoid Tue/Wed weekly slots.

### Gate 2 Max Open Positions (50)

A weekly broad run + daily runs + next-day runs can all stack. If you hit 50 open, everything else is rejected.

**Mitigation:**
- `--max-bets` limits per run (7 + 6 + 6 = 19 max new/day if everything hits)
- Settlement at 11 PM clears ~50% of opens each night
- Monitor with `make risk` weekly

### Gate 1 Daily Loss Limit

Weekly Monday bets consume Monday's loss budget. A bad Monday means Tuesday's daily hits the cap faster.

**Not a real problem** unless Monday concentrates too many bets — `--budget 15%` and `--max-bets 6` already prevent that.

---

## Sport-Specific Timing Notes

Reference table for tuning per-sport behavior later:

| Sport | Optimal bet window | Why |
|:------|:-------------------|:----|
| **MLB** | Morning-of or early afternoon | Pitchers confirmed ~8 AM ET; lineups posted ~2 hrs before first pitch |
| **NBA** | 2.5-4 hours before tip | Injury report drops 2.5hr before; official inactives swing totals 4-7pts |
| **NHL** | Morning-of after morning skate | Starting goalies announced ~11 AM ET — single highest-variance factor |
| **NFL** | Thu-Sat for Sunday games | Wed injury report; Fri practice reports; Sun AM inactives |
| **Futures** | Anytime, but NOT post-major-news | Capital locked for weeks — slippage cost > edge gain |
| **Prediction (crypto/weather/SPX)** | Catalyst-driven | Fed announcements, CPI prints, storm tracking |

---

## Implementation Plan

### Step 1 — Daily timing confirmed

Current daily runs at **5:05 AM PST (8:05 AM ET)**. This lands perfectly in the freshness window:
- MLB starters announced (~5 AM PT / 8 AM ET confirmations)
- NHL morning skate pending but lines already reflect expected goalies
- Weather forecasts stable for today's games
- Before sharp money fully hits the market
- Kalshi liquidity building

No change needed. Weekly slot sits at 5:20 AM PST to let daily finish first.

### Step 2 — Re-enable scheduled tasks

Using `install_windows_task.py`:

```bash
# Keep daily (whatever time decided in Step 1)
python scripts/schedulers/automation/install_windows_task.py install execute

# Add weekly broad (Mon + Thu)
# Note: may need manual schtasks entry if installer only supports daily
```

Or manually via `schtasks` (times are PST — local system time):

```bash
# Weekly broad runs — Mon + Thu at 5:20 AM PST (8:20 AM ET)
schtasks /create /tn "Edge-Radar NoDateFilter Mon" /tr "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\no_date_filter_executions\no_date_filter_execution.bat" /sc weekly /d MON /st 05:20
schtasks /create /tn "Edge-Radar NoDateFilter Thu" /tr "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\no_date_filter_executions\no_date_filter_execution.bat" /sc weekly /d THU /st 05:20

# Next-day execute — Sun-Thu at 6:00 PM PST (9:00 PM ET)
schtasks /create /tn "Edge-Radar NextDay" /tr "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\next_day_executions\next_day_execute.bat" /sc weekly /d SUN,MON,TUE,WED,THU /st 18:00

# Settlement — daily at 8:00 PM PST (11:00 PM ET)
schtasks /create /tn "Edge-Radar Settle" /tr "D:\AI_Agents\Specialized_Agents\Edge_Radar\.venv\Scripts\python.exe D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_settler.py settle" /sc daily /st 20:00

# Reconcile — daily at 8:30 PM PST (11:30 PM ET)
schtasks /create /tn "Edge-Radar Reconcile" /tr "D:\AI_Agents\Specialized_Agents\Edge_Radar\.venv\Scripts\python.exe D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_settler.py reconcile" /sc daily /st 20:30
```

Existing `same-day-execution-report` task continues running at 5:05 AM PST — do NOT recreate.

### Step 2b — Email delivery (consolidate to shell scripts)

User previously had both Claude Desktop direct-prompt routines AND `schtasks`-triggered shell scripts sending execution-report emails. Memory confirms this caused duplicate emails.

**Decision (2026-04-22): Consolidate to `schtasks`-only.** Disable the Claude Desktop email routines; the shell scripts already call `claude -p` with agentmail and produce identical output.

Each execution task gets a paired email task 20 min later:

```bash
# Same-day email — 5:25 AM PST (20 min after 5:05 execute)
schtasks /create /tn "Edge-Radar Email SameDay" /tr "bash D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\custom\Shell-Scripts\SameDay-Execution-Report.sh" /sc daily /st 05:25

# Weekly broad email — 5:40 AM PST Mon + Thu (20 min after 5:20 execute)
schtasks /create /tn "Edge-Radar Email NoDateFilter Mon" /tr "bash D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\custom\Shell-Scripts\NoDateFilter-Execution-Report.sh" /sc weekly /d MON /st 05:40
schtasks /create /tn "Edge-Radar Email NoDateFilter Thu" /tr "bash D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\custom\Shell-Scripts\NoDateFilter-Execution-Report.sh" /sc weekly /d THU /st 05:40

# Next-day email — 6:20 PM PST Sun-Thu (20 min after 6:00 execute)
schtasks /create /tn "Edge-Radar Email NextDay" /tr "bash D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\custom\Shell-Scripts\NextDay-Edge-Report.sh" /sc weekly /d SUN,MON,TUE,WED,THU /st 18:20
```

**Note on `bash` invocation:** `schtasks` needs a full path to `bash.exe` (e.g., Git Bash at `C:\Program Files\Git\bin\bash.exe`) or the shell scripts need to be wrapped in a `.bat` launcher. Verify your `bash` location and adjust the `/tr` arguments accordingly — may need quoting like `"C:\Program Files\Git\bin\bash.exe" D:\...\SameDay-Execution-Report.sh`.

### Step 2c — Disable Claude Desktop routines

After `schtasks` email tasks are confirmed working (2-3 successful email deliveries):

1. Open Claude Desktop
2. Find the 3 scheduled routines:
   - Same-day execution report email
   - Thursday no-date-filter email
   - Monday no-date-filter email
3. Disable or delete each
4. Monitor for 1 week to confirm no missing emails

Memory note `project_scheduled_tasks.md` will be updated to reflect single-source email delivery.

### Step 3 — Dry-run validation (first week)

Before enabling live execution:
- Set `DRY_RUN=true` in `.env`
- Let scheduled tasks run for one full week
- Review logs daily — are scans producing reasonable opportunities? Is `--min-bets 3` blocking too often?
- If clean for a week, flip `DRY_RUN=false`

### Step 4 — Monitor for 4 weeks (calibration target)

Track in the R12 recalibration window:
- Total bets placed (target: ~100 for R12 re-run)
- Brier score by days-to-event bucket
- Gate 7 rejection count (are Mon/Thu colliding with daily?)
- Gate 2 max-positions hits (is capital over-allocated?)
- ROI on weekly-script bets vs daily-script bets

---

## Monitoring & Kill Criteria

Re-disable scheduled tasks if any of these trigger:

| Condition | Signal | Action |
|:----------|:-------|:-------|
| Weekly bets ROI < -15% over 30 days | Settle report `--days 30` | Disable `no_date_filter` tasks, investigate |
| Brier score on >72hr bets > 0.32 | Calibration report | Tighten horizon on weekly script |
| Gate 2 hit > 3x in a week | Risk dashboard | Reduce `--max-bets` across scripts |
| Gate 1 hit more than once a week | Daily loss logs | Reduce `--budget` or `--max-bets` |
| Reconciliation drift > 2 bets | Reconcile output | Manual investigation + possible script pause |

---

## Open Questions

1. ~~**Existing daily time**~~ — Resolved: 5:05 AM PST (8:05 AM ET)
2. ~~**Skip Saturday next-day?**~~ — Resolved 2026-04-22: yes, skip Sat; Sunday-morning next-day run handles Sunday slate
3. ~~**Auto-email all executions?**~~ — Resolved 2026-04-22: consolidate to `schtasks`-triggered shell scripts; disable Claude Desktop email routines
4. **R12 calibration target** — Once 100 trades hit, should weekly cadence stay the same or reduce?
5. **Thu NFL horizon worry** — Thu 5:20 AM PST catches Sun NFL at ~3.5 days out. If Wed injury reports haven't all processed by early Thu morning, some lines may still be stale. Consider moving Thu weekly to Thu 5 PM PST (after practice reports) if NFL bets underperform
6. **`bash` invocation path** — Confirm location of `bash.exe` on this system (Git Bash typical: `C:\Program Files\Git\bin\bash.exe`) so email `schtasks` `/tr` arguments are correct

---

## References

- `CLAUDE.md` — Master instructions, 11 risk gates, risk limits
- `.claude/skills/edge-radar/SKILL.md` — Unified scanner reference
- `docs/setup/AUTOMATION_GUIDE.md` — Windows Task Scheduler setup
- Memory: `project_scheduled_tasks.md` — Scheduling history
- Memory: `project_edge_enhancement_priorities.md` — R12 calibration re-run target (100 trades)
- Memory: `project_correlated_bet_risk.md` — Gate 7 series dedup context
- Memory: `project_calibration_baseline.md` — Brier score baselines
