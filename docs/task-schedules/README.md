<div align="center">

# ⏰ Edge-Radar Scheduled Tasks

**The repo owner's live Windows Task Scheduler setup — a full scan → execute → email → settle → reconcile → calibrate → review pipeline that runs unattended.**

[![Scheduler](https://img.shields.io/badge/Windows-Task%20Scheduler-0078D4?style=for-the-badge&logo=windows&logoColor=white)](#registering-the-tasks)
[![Pipeline](https://img.shields.io/badge/Pipeline-~20%20Tasks-8B5CF6?style=for-the-badge)](#at-a-glance--all-tasks)
[![Times](https://img.shields.io/badge/Times-PST%20%C2%B7%20ET%20noted-2ea44f?style=for-the-badge)](#daily-fire-sequence)
[![Templates](https://img.shields.io/badge/Templates-Copy%20%26%20Adapt-F97316?style=for-the-badge)](#reproducing-this-on-your-own-machine)

</div>

> [!NOTE]
> **This is the actual schedule the repo owner runs — published as a reference and recommended starting point, not a turnkey installer.** Build something similar, tuned to your own slate, time zone, and risk appetite. The owner's literal `.bat`/`.sh` files are gitignored (they hardcode a machine path and a private inbox), so this doc carries **sanitized templates** to copy — see [Reproducing this on your own machine](#reproducing-this-on-your-own-machine). Placeholders: `<YOUR_AGENTMAIL_INBOX>` is the agentmail address reports send **from** (`.env` → `AGENTMAIL_INBOX`); swap the destination `mikeschecht@gmail.com` for your own (`.env` → `NOTIFY_EMAIL`). Want just the minimal "execute + settle + calibration" core? Start with [`AUTOMATION_GUIDE.md`](../setup/AUTOMATION_GUIDE.md) and its one-command installer.

**Location:** `\Edge-Radar\` Task Scheduler folder &nbsp;·&nbsp; **Times:** PST (ET in parentheses) &nbsp;·&nbsp; the only active scheduling mechanism — legacy Claude Desktop email routines were consolidated here 2026-04-22, and any `SKILL.md` left under `~/.claude/scheduled-tasks/` is a stale artifact, not a live trigger.

<details>
<summary><b>Changelog</b></summary>

- **2026-07-20** — added `Hourly-Settle` (every hour at :35) — U1: hourly `kalshi_settler.py settle`, enabled by the M2 cross-process trade-log lock (concurrent settle+execute now merge-safe). Sharpens Gate 1 daily-loss accuracy intraday. `NightlySettle` kept as belt-and-suspenders during a validation week, then retire. Validated live (`LastTaskResult=0`).
- **2026-07-20** — added `Daily-Polymarket-DryRun` (daily 9:40 AM) — read-only Polymarket championship-futures scan appending to the PM2 edge-proving evidence log (`data/polymarket/dryrun_log.jsonl`). Places no orders; no paired email (output logs to `logs/polymarket_dryrun_scan.log`). Validated live (`LastTaskResult=0`).
- **2026-06-20** — added `Weekly-Futures-Execution` (Sat 9:00 AM, first futures automation) + paired `Email-Weekly-Futures` (Sat 9:20 AM); `futures_edge.py` now always writes a report on `--save` for 0-order-week proof-of-life. Both validated live (`LastTaskResult=0`, 0 bets, all gated).
- **2026-06-20** — per-task logging on every email shell script (`logs/email_*.log` with exit-code banners; see [Troubleshooting → Email task logs](#email-task-logs-added-2026-06-20)).
- **2026-05-31** — added `WeeklyAccountGraph` (Sun 9:00 AM) — publishes the account-growth graph to GitHub Pages via a `gh` push to master.
- **2026-05-17** — added daily 11 AM Midday-NoDateFilter + 2 PM Late-SameDay execute/email pairs; shifted `All-Sports-NextDay-Execution` 6:00 PM → 8:30 PM; retired the Mon/Thu 5:20 AM `All-Sports-NoDateFilter-Execution` + its email.

</details>

---

## At a Glance — All Tasks

### Active (Ready)

| # | Task | Schedule (PST) | What it does |
|:-:|:-----|:---------------|:-------------|
| 0a | `Daily-Summary` | Daily 4:50 AM | Generates morning P&L digest (yesterday settled + open exposure + today pending + 7-day context) |
| 0b | `Email-Daily-Summary` | Daily 5:00 AM | Emails the daily-summary report to `mikeschecht@gmail.com` |
| 1 | `All-Sports-SameDay-Execution` | Daily 5:05 AM | Scans NBA/NHL/MLB/NFL for **today's** games and places bets (`--date today`, budget 12%, max 7 bets) |
| 2 | `Email-SameDay` | Daily 5:25 AM | Emails the same-day execution report to `mikeschecht@gmail.com` |
| 3 | `All-Sports-NoDateFilter-Midday-Execution` | **Daily** 11:00 AM | Midday wide-net scan, no date filter (budget 8%, max 5 bets). Catches confirmed MLB starters, NBA/NHL morning-skate news, mid-morning sharp-money moves |
| 4 | `Email-NoDateFilter-Midday` | **Daily** 11:20 AM | Emails the midday wide-net report |
| 5 | `All-Sports-SameDay-Late-Execution` | **Daily** 2:00 PM | Late same-day scan (budget 5%, max 4 bets, `--date today`). Catches late-breaking scratches, goalie confirmations, weather, sharp moves on tonight's games |
| 6 | `Email-SameDay-Late` | **Daily** 2:20 PM | Emails the late same-day report |
| 7 | `All-Sports-NextDay-Execution` | **Sun-Thu** 8:30 PM | Scans for **tomorrow's** games (`--date tomorrow`, budget 12%, max 6 bets). Shifted from 6:00 PM 2026-05-17 — more next-day lines posted by 11:30 PM ET |
| 8 | `Email-NextDay` | **Sun-Thu** 8:50 PM | Emails the next-day execution report |
| 9 | `NightlySettle` | Daily 11:00 PM | Fetches settlement data from Kalshi API, updates trade log, calculates realized P&L |
| 10 | `Reconcile` | Daily 11:30 PM | Compares local trade log against Kalshi API positions, flags any drift |
| 11 | `Calibration` | **Sun** 7:00 PM | Weekly Brier-score refresh + calibration-curve report (`model_calibration.py --days 7`) |
| 12 | `Backtest` | **Sun** 7:30 PM | Weekly equity curve, drawdown, Sharpe, strategy-comparison report |
| 13 | `Weekly-Analysis` | **Sun** 11:45 PM | End-of-week 7-day `betting_analysis.py` (headline, by sport/category/side/edge/confidence/price, calibration, longshots, streaks, daily P&L, full trade ledger) |
| 14 | `Email-Weekly-Analysis` | **Sun** 11:55 PM | Emails the weekly performance analysis report |
| 15 | `MonthlyCalibration` | **1st of each month** 2:00 AM | Monthly 30-day Brier-score refresh + calibration-curve report (`model_calibration.py --days 30 --save`) |
| 18 | `WeeklyAccountGraph` | **Sun** 9:00 AM | Refreshes the Kalshi account-growth graph (live snapshot → HTML/PNG) and publishes it to the public Pages site via a `gh` single-file push to master (`refresh_account_graph.py`) |
| 19 | `Weekly-Futures-Execution` | **Sat** 9:00 AM | Scans + executes championship/outright **futures** (NFL Super Bowl, NBA/NHL/MLB titles, NCAAB MOP, golf majors) via `scan.py futures --execute` (budget 5%, max 3, unit $1, `--exclude-open`). Offseason series with no Odds API outright data are skipped; golf only prices the 4 majors during their weeks. First futures automation (added 2026-06-20) |
| 20 | `Email-Weekly-Futures` | **Sat** 9:20 AM | Emails the weekly futures execution report (20-min buffer after task #19). Sends even on 0-order weeks as proof-of-life. Subject `Edge-Radar \| Weekly Futures Execution Report` |
| 21 | `Daily-Polymarket-DryRun` | Daily 9:40 AM | **Read-only** Polymarket championship-futures scan (`scan.py polymarket --filter futures --save`) — appends each run to the PM2 edge-proving evidence log `data/polymarket/dryrun_log.jsonl` + markdown to `reports/Polymarket/`. Places NO orders (Phase 1); ~4 Odds API requests/run |
| 22 | `Hourly-Settle` | **Every hour** at :35 | U1: runs `kalshi_settler.py settle` hourly (direct python, same pattern as NightlySettle). Keeps the trade log fresh all day → Gate 1 daily-loss checks see intraday settlements. Safe alongside the execute tasks via the M2 cross-process lock. Subsumes `NightlySettle` (kept during validation week) |
| 16 | `R8-Review` | **One-shot 2026-05-29 6:00 AM** | R8 cross-category dedup A/B review (~30 days post-ship). Slices ML/Total/Spread same-game cohorts and recommends per-sport `CROSS_CATEGORY_DEDUP_<SPORT>` flips |
| 17 | `U2-Review` | **One-shot 2026-05-14 7:00 AM** | U2 daily-summary digest 2-week post-ship review. Scans last 14 `daily_summary_*.md` files for firing-reliability + section coverage, spawns `claude -p` for code review pass, writes recommendations + operational checklist |

### Disabled (kept for reference, not running)

| # | Task | Prior Schedule | Why disabled |
|:-:|:-----|:---------------|:-------------|
| 11 | `All-Sports-SameDay-Scan` | Daily 4:55 AM | Preview-only variant of task #1; execution variant is what runs |
| 12 | `All-Sports-NoDateFilter-Scan` | Daily 9:00 AM | Preview-only variant of task #2 |
| 13 | `MLB-NextDay-Scan` | 6:00 PM | Per-sport scan; replaced by consolidated `All-Sports-NextDay-Execution` |
| 14 | `NBA-NextDay-Scan` | 6:05 PM | Per-sport; replaced |
| 15 | `NHL-NextDay-Scan` | 6:10 PM | Per-sport; replaced |
| 16 | `NFL-NextDay-Scan` | 6:15 PM | Per-sport; replaced |

### Daily Fire Sequence

```
 2:00 AM  1st      ─ MonthlyCalibration    (30-day calibration refresh, monthly)
 4:50 AM  Daily    ─ Daily-Summary         (yesterday P&L + exposure digest)
 5:00 AM  Daily    ─ Email-Daily-Summary
 5:05 AM  Daily    ─ All-Sports-SameDay-Execution
 5:25 AM  Daily    ─ Email-SameDay
 9:00 AM  Sun      ─ WeeklyAccountGraph    (refresh + publish account graph to Pages)
 9:00 AM  Sat      ─ Weekly-Futures-Execution (futures scan + execute)
 9:20 AM  Sat      ─ Email-Weekly-Futures     (emails the futures report)
 9:40 AM  Daily    ─ Daily-Polymarket-DryRun  (read-only PM evidence scan, no orders)
11:00 AM  Daily    ─ All-Sports-NoDateFilter-Midday-Execution
11:20 AM  Daily    ─ Email-NoDateFilter-Midday
 2:00 PM  Daily    ─ All-Sports-SameDay-Late-Execution
 2:20 PM  Daily    ─ Email-SameDay-Late
 8:30 PM  Sun-Thu  ─ All-Sports-NextDay-Execution
 8:50 PM  Sun-Thu  ─ Email-NextDay
 7:00 PM  Sun      ─ Calibration
 7:30 PM  Sun      ─ Backtest
11:00 PM  Daily    ─ NightlySettle
11:30 PM  Daily    ─ Reconcile
11:45 PM  Sun      ─ Weekly-Analysis       (end-of-week 7-day report)
11:55 PM  Sun      ─ Email-Weekly-Analysis (emails the weekly report)

  :35 every hour   ─ Hourly-Settle          (settle sweep; :35 slot is clear of all task minutes)
```

### Fires-Per-Day Totals

| Day | Morning | Midday | Afternoon | Evening | Nightly | Day total |
|:----|:-------:|:------:|:---------:|:-------:|:-------:|:---------:|
| Mon-Thu | 3 (same-day + email + Polymarket-DryRun @ 9:40) | 2 (Midday-NoDateFilter + email) | 2 (Late-SameDay + email) | 2 (NextDay + email) | 2 | **11** |
| Fri | 3 (same-day + email + Polymarket-DryRun) | 2 | 2 | 0 | 2 | **9** |
| Sat | 5 (same-day + email + Futures-Execution + email @ 9:00/9:20 + Polymarket-DryRun @ 9:40) | 2 | 2 | 0 | 2 | **11** |
| Sun | 3 (same-day + email + Polymarket-DryRun) + WeeklyAccountGraph @ 9:00 | 2 | 2 | 4 (NextDay + email + Calibration + Backtest) | 4 (Settle + Reconcile + Weekly-Analysis + Email) | **16** |

**Monthly add-on:** on the **1st of each month** an additional `MonthlyCalibration` fire lands at 2:00 AM (adds +1 to that day's total).

**Hourly add-on (2026-07-20):** `Hourly-Settle` fires 24×/day at :35 — excluded from the per-day totals above to keep them readable.

---

## Reproducing this on your own machine

The roster above is what the owner runs. To stand up the equivalent, you recreate two kinds of files from the sanitized templates below, then register each with `schtasks`. You do **not** need all 20 tasks — see the [minimal core](#minimal-viable-automation) note.

### Placeholders

Substitute these everywhere they appear:

| Placeholder | Meaning | Example |
|:--|:--|:--|
| `<REPO_ROOT>` | Absolute path to your Edge-Radar checkout | `C:\Users\you\Edge-Radar` |
| `<YOUR_EMAIL>` | Inbox you want reports delivered **to** | `you@example.com` |
| `<YOUR_AGENTMAIL_INBOX>` | agentmail.to address reports are sent **from** | `yourinbox@agentmail.to` |
| `<GIT_BASH>` | Path to `bash.exe` from Git for Windows | `C:\Program Files\Git\bin\bash.exe` |

`<YOUR_EMAIL>` and `<YOUR_AGENTMAIL_INBOX>` have homes in `.env` (`NOTIFY_EMAIL`, `AGENTMAIL_INBOX`) — see [`../../.env.example`](../../.env.example). The email templates read them from there.

> **Time zone:** all schedule times in this doc are the owner's local PST, with ET in parentheses. Task Scheduler fires on **your** machine's local time — pick times that make sense where you are, not these literal values.

### Template A — execute/scan wrapper (`.bat`)

A self-locating wrapper avoids hardcoding your path: `%~dp0` is the directory the `.bat` lives in, so `cd /d "%~dp0..\..\.."` walks up to the repo root (adjust the number of `..` to match where you save it). Save as e.g. `same_day_execute.bat`:

```batch
@echo off
REM ── Same-Day Execute — all sports, today's games ──────────────────────────
REM  WARNING: places live orders when DRY_RUN=false in .env. Verify first.

REM Self-locate the repo root (adjust ..\..\.. to your folder depth):
cd /d "%~dp0..\..\.."

echo --- Portfolio Status (Before) ---
.venv\Scripts\python.exe scripts\kalshi\kalshi_executor.py status

echo --- Scanning and Executing ---
.venv\Scripts\python.exe scripts\scan.py sports ^
  --unit-size .5 --max-bets 7 --min-bets 3 --budget 12%% ^
  --date today --exclude-open --save ^
  --report-dir "reports\Sports\schedulers\same-day-executions" --execute

echo --- Portfolio Status (After) ---
.venv\Scripts\python.exe scripts\kalshi\kalshi_executor.py status
```

> If you'd rather not rely on `%~dp0`, replace the `cd /d` line with the absolute `cd /d <REPO_ROOT>`. The `%%` on `12%%` is required — a literal `%` must be doubled inside a `.bat`.

The other execute variants are the same wrapper with different flags + `--report-dir`:

| Variant | Flags that differ |
|:--|:--|
| Same-day (morning) | `--max-bets 7 --budget 12% --date today` |
| Midday wide-net | `--max-bets 5 --budget 8%` *(no `--date` — scans all dates)* |
| Late same-day | `--max-bets 4 --budget 5% --date today` |
| Next-day | `--max-bets 6 --budget 12% --date tomorrow` |

### Template B — maintenance wrapper (`.bat`)

Settle, reconcile, calibration, backtest, weekly-analysis, and daily-summary are all the same one-line pattern — just a different Python entry point:

```batch
@echo off
cd /d "%~dp0..\..\.."
.venv\Scripts\python.exe scripts\kalshi\kalshi_settler.py settle
```

Swap the last line for the job you're wrapping:

| Task | Last line |
|:--|:--|
| Settle | `… scripts\kalshi\kalshi_settler.py settle` |
| Reconcile | `… scripts\kalshi\kalshi_settler.py reconcile` |
| Calibration (weekly) | `… scripts\kalshi\model_calibration.py --days 7 --save` |
| MonthlyCalibration | `… scripts\kalshi\model_calibration.py --days 30 --save` |
| Backtest | `… scripts\backtest\backtester.py --simulate --save` |
| Weekly-Analysis | `… scripts\kalshi\betting_analysis.py --days 7 --save` |
| Daily-Summary | `… scripts\kalshi\daily_summary.py --save` |

### Template C — report emailer (`.sh`)

The email tasks call a tiny shell script that spawns a headless Claude to read today's report and send it. Save as e.g. `SameDay-Execution-Report.sh`:

```bash
#!/bin/bash
# Edge-Radar | report emailer — reads today's report, emails it via agentmail.
set -a; source "<REPO_ROOT>/.env"; set +a   # loads NOTIFY_EMAIL / AGENTMAIL_INBOX

TODAY=$(date +"%Y-%m-%d")

claude --dangerously-skip-permissions -p "Collect today's execution report from \
<REPO_ROOT>/reports/Sports/schedulers/same-day-executions. Find the file timestamped \
today ($TODAY). Email it to ${NOTIFY_EMAIL} from inbox ${AGENTMAIL_INBOX}, including \
the full report contents in the body, styled as a clean dark-themed HTML email with a \
gradient header and per-order cards. Use the agentmail skill to send. Subject = \
'Edge-Radar | Same Day Execution Report'. If no report exists for $TODAY, report the \
most recent available and do NOT send an email (prevents stale sends)."
```

> Point the report folder + subject line at whichever execute task this emailer pairs with (`no-date-filter-midday-executions`, `same-day-late-executions`, `next-day-executions`, or `reports/Performance` for the digest/weekly jobs). The "don't send if missing" instruction keeps a failed execute from producing a stale email. (The owner's live scripts also tee output to `logs/email_*.log` — see [Troubleshooting → Email task logs](#email-task-logs-added-2026-06-20).)

### Registering the tasks

All tasks live in a `\Edge-Radar\` Task Scheduler folder. Two `schtasks` shapes cover everything.

**A `.bat`-backed task (scan/execute/maintenance):**

```powershell
schtasks /Create /TN "\Edge-Radar\All-Sports-SameDay-Execution" `
  /TR "<REPO_ROOT>\scripts\schedulers\same_day_executions\same_day_execute.bat" `
  /SC DAILY /ST 05:05 /F
```

**An email task (bash + `.sh`, path has spaces → escaped quotes):**

```powershell
schtasks /Create /TN "\Edge-Radar\Email-SameDay" `
  /TR "\"<GIT_BASH>\" \"<REPO_ROOT>\scripts\custom\Shell-Scripts\Run-Reports\SameDay-Execution-Report.sh\"" `
  /SC DAILY /ST 05:25 /F
```

**Schedule shapes you'll need:**

| Cadence | `schtasks` flags |
|:--|:--|
| Every day | `/SC DAILY /ST HH:MM` |
| Sun–Thu only | `/SC WEEKLY /D SUN,MON,TUE,WED,THU /ST HH:MM` |
| Sundays | `/SC WEEKLY /D SUN /ST HH:MM` |
| Saturdays | `/SC WEEKLY /D SAT /ST HH:MM` |
| 1st of each month | `/SC MONTHLY /D 1 /ST HH:MM` |

Settle can use direct python (no wrapper) if you prefer:

```powershell
schtasks /Create /TN "\Edge-Radar\NightlySettle" `
  /TR "<REPO_ROOT>\.venv\Scripts\python.exe <REPO_ROOT>\scripts\kalshi\kalshi_settler.py settle" `
  /SC DAILY /ST 23:00 /F
```

> **Running this from Git Bash instead of PowerShell?** Prefix every `schtasks` call with `MSYS_NO_PATHCONV=1` or Git Bash mangles the `/TN` path into a filesystem path. See [Setup Gotchas](#setup-gotchas-for-future-reference).

### Minimal viable automation

The full pipeline is ~20 tasks; you don't need them all. **Minimal core = `All-Sports-SameDay-Execution` + `NightlySettle`** (execute today's games, settle them at night). Add `MonthlyCalibration` for model health, then layer in the emails and the midday/late/next-day runs as you trust the pipeline. Always run the [Dry-Run Testing Workflow](#dry-run-testing-workflow) before any execute task can place real money.

---

## Active Tasks (State: Ready)

### 0a. `Daily-Summary` — Daily 4:50 AM PST (7:50 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\schedulers\maintenance\daily_summary.bat` |
| **Runs** | `daily_summary.py --save` |
| **Purpose** | Morning P&L digest — yesterday's settled W/L/$ (rolling 24h) + per-sport breakdown + currently open exposure + today's pending positions + live Kalshi balance + 7-day rolling context |
| **Report output** | `reports\Performance\daily_summary_YYYY-MM-DD.md` |
| **Empty-day behavior** | Still produces a report — proof-of-life pattern matches the SameDay email policy |

**Why 4:50 AM PST:** After the 11:00 PM PST `NightlySettle` (yesterday's bets are settled in the log) and before the 5:05 AM PST `All-Sports-SameDay-Execution` (so the "Open Exposure" view reflects overnight carry rather than today's new fills mixing in). Sets up the 5:00 AM Email-Daily-Summary 10 minutes later.

---

### 0b. `Email-Daily-Summary` — Daily 5:00 AM PST (8:00 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\Daily-Summary-Report.sh` |
| **Invocation** | `"C:\Program Files\Git\bin\bash.exe" "<script>.sh"` |
| **Purpose** | Emails the daily-summary report produced 10 min earlier |
| **Email subject** | `Edge-Radar | Daily Summary` |
| **From inbox** | `<YOUR_AGENTMAIL_INBOX>` |

**10-min buffer from 4:50 generate:** `daily_summary.py` is fast (no API fetches except a single optional balance call) and finishes in <5s; 10 min is generous. Keeps the digest in the inbox before the 5:25 SameDay email so the "what happened yesterday" arrives ahead of "what I bet today".

---

### 1. `All-Sports-SameDay-Execution` — Daily 5:05 AM PST (8:05 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\schedulers\same_day_executions\same_day_execute.bat` |
| **Flags** | `--unit-size .5 --max-bets 7 --min-bets 1 --budget 12% --date today --exclude-open` |
| **Purpose** | Places bets on today's games across NBA/NHL/MLB/NFL |
| **Report output** | `reports\Sports\schedulers\same-day-executions\YYYY-MM-DD_sports_execution.md` |
| **Max exposure** | 12% of bankroll / 7 bets |
| **Risk gates** | All 11 enforced (see `CLAUDE.md`) |

**Why 5:05 AM PST:** MLB starters announced, NHL morning skate behind us, weather forecasts stabilized, Kalshi liquidity building, before sharp money fully hits market. Sweet spot for lineup/weather/pitcher freshness.

---

### 2. `Email-SameDay` — Daily 5:25 AM PST (8:25 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\SameDay-Execution-Report.sh` |
| **Invocation** | `"C:\Program Files\Git\bin\bash.exe" "<script>.sh"` |
| **Purpose** | Reads today's same-day execution report, emails to `mikeschecht@gmail.com` |
| **Email subject** | `Edge-Radar | Same Day Execution Report` |
| **From inbox** | `<YOUR_AGENTMAIL_INBOX>` |

**Mechanism:** Shell script spawns `claude --dangerously-skip-permissions -p "..."` subprocess. The inner Claude invocation uses the `agentmail` skill to send a dark-themed HTML email with per-order cards.

**Behavior if no report:** If no report exists for today's date, the subprocess reports the most recent available and does NOT send an email (correct behavior — prevents stale emails).

**20-min buffer from 5:05 execute:** Ensures execute completes (3-8 min typical) and writes report before email fires.

---

### 3. `All-Sports-NoDateFilter-Midday-Execution` — Daily 11:00 AM PST (2:00 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\schedulers\no_date_filter_executions\no_date_filter_execution_midday.bat` |
| **Flags** | `--unit-size .5 --max-bets 5 --min-bets 1 --budget 8% --exclude-open` (no `--date`) |
| **Purpose** | Midday wide-net scan across all sports + all dates. The only NoDateFilter run after the Mon/Thu 5:20 AM task was retired 2026-05-17 |
| **Report output** | `reports\Sports\schedulers\no-date-filter-midday-executions\YYYY-MM-DD_sports_execution.md` |
| **Max exposure** | 8% of bankroll / 5 bets |

**Why daily 11:00 AM PST (2:00 PM ET):** Per `timing-analysis-2026-05-17.md`, the data showed `NoDateFilter` (no date filter, all sports, all dates) hits 100% of the time while `SameDay` (`--date today`) is empty 71% of mornings. The 2026-05-05 datapoint was decisive: at 15:37 PT SameDay returned 0 bets, at 15:41 PT NoDateFilter returned 6 — same Kalshi book, same minute. The slate-width filter is the bottleneck, not the time of day. 11:00 AM also picks up MLB pitcher confirmations (~10-11 AM ET) and NBA/NHL morning-skate news that the 5:05 AM SameDay run misses.

**Replaces the Mon/Thu 5:20 AM `All-Sports-NoDateFilter-Execution`** (retired 2026-05-17). The prior cadence covered only 2 days/week with a redundant scope to what daily Midday now covers. Daily Midday + Gate 5 (`--exclude-open`) + Gate 7 (series dedup) is the cleaner design.

---

### 4. `Email-NoDateFilter-Midday` — Daily 11:20 AM PST (2:20 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\NoDateFilter-Midday-Execution-Report.sh` |
| **Invocation** | `"C:\Program Files\Git\bin\bash.exe" "<script>.sh"` |
| **Purpose** | Emails the midday wide-net execution report produced 20 min earlier |
| **Email subject** | `Edge-Radar | NoDateFilter Midday Execution Report` |
| **From inbox** | `<YOUR_AGENTMAIL_INBOX>` |

**20-min buffer from 11:00 execute:** Same pattern as Email-SameDay.

---

### 5. `All-Sports-SameDay-Late-Execution` — Daily 2:00 PM PST (5:00 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\schedulers\same_day_executions\same_day_execute_late.bat` |
| **Flags** | `--unit-size .5 --max-bets 4 --min-bets 1 --budget 5% --date today --exclude-open` |
| **Purpose** | Late same-day scan — catches late-breaking news on tonight's games |
| **Report output** | `reports\Sports\schedulers\same-day-late-executions\YYYY-MM-DD_sports_execution.md` |
| **Max exposure** | 5% of bankroll / 4 bets (third bite at the same-day apple after 5:05 AM + 11:00 AM) |

**Why daily 2:00 PM PST (5:00 PM ET):** Catches NBA/NHL pre-game news on evening games — scratches, goalie confirmations, mid-afternoon sharp-money moves. The `--date today` filter is intentional: this scan is specifically chasing late-breaking developments on tonight's slate, not the broader week. Smallest budget cap of any execute task because it's the most speculative — first 2-4 weeks of data will show whether it's pulling its weight or mostly returning Gate-5-blocked noise.

**Note on experimental status:** Marked Tier 2 ("moderate confidence") in the timing-analysis recommendation. The manual midday SameDay runs that informed the decision were mixed (only 1/4 hit). If the first 2-4 weeks show consistently empty reports OR consistently duplicate Gate-5-blocked markets, disable.

---

### 6. `Email-SameDay-Late` — Daily 2:20 PM PST (5:20 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\SameDay-Late-Execution-Report.sh` |
| **Invocation** | `"C:\Program Files\Git\bin\bash.exe" "<script>.sh"` |
| **Purpose** | Emails the late same-day execution report produced 20 min earlier |
| **Email subject** | `Edge-Radar | Same-Day Late Execution Report` |

---

### 7. `All-Sports-NextDay-Execution` — Sun-Thu 8:30 PM PST (11:30 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun, Mon, Tue, Wed, Thu |
| **Script** | `scripts\schedulers\next_day_executions\next_day_execute.bat` |
| **Flags** | `--unit-size .5 --max-bets 6 --min-bets 1 --budget 12% --date tomorrow --exclude-open` |
| **Purpose** | Locks in early lines for tomorrow's games |
| **Report output** | `reports\Sports\schedulers\next-day-executions\YYYY-MM-DD_sports_execution.md` |
| **Max exposure** | 12% of bankroll / 6 bets |

**Why Sun-Thu 8:30 PM PST (11:30 PM ET):** Shifted from 6:00 PM 2026-05-17 per `timing-analysis-2026-05-17.md`. Previous 6:00 PM PT (9:00 PM ET) timing had a 43% empty-report rate — many sportsbooks hadn't posted tomorrow's lines by 9 PM ET, especially Kalshi tomorrow markets which thin out for next-day events. 11:30 PM ET catches: full posting of next-day lines by Vegas books, fuller Kalshi liquidity after East Coast slate completes, West Coast NBA/NHL games winding down.

Sun-Thu only — Fri + Sat still skipped so the Sunday-morning 5:05 AM run handles Sunday NFL with fresher data.

---

### 8. `Email-NextDay` — Sun-Thu 8:50 PM PST (11:50 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun, Mon, Tue, Wed, Thu |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\NextDay-Edge-Report.sh` |
| **Purpose** | Emails the next-day execution report |
| **Email subject** | `Edge-Radar | Next-Day Edge Report` |

---

### 9. `NightlySettle` — Daily 11:00 PM PST (2:00 AM ET next day)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Executable** | `.venv\Scripts\python.exe` |
| **Arguments** | `scripts\kalshi\kalshi_settler.py settle` |
| **Purpose** | Updates trade log with settled game results, calculates P&L |
| **Dependencies** | Kalshi API reachable; open positions file writable |

**Why 11:00 PM PST (2:00 AM ET):**
- Catches all late west-coast NBA/NHL games (typically end by 10:00 PM PST)
- Runs after the day's final East Coast events have settled on Kalshi
- Earlier settle times would miss late games

**Output:** Updates `data/positions/open_positions.json`, `data/history/YYYY-MM-DD_trades.json`. Closed positions moved to history file.

---

### 10. `Reconcile` — Daily 11:30 PM PST (2:30 AM ET next day)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\schedulers\maintenance\reconcile.bat` |
| **Runs** | `kalshi_settler.py reconcile` |
| **Purpose** | Compares local trade log against Kalshi API, flags discrepancies |
| **Dependencies** | Runs AFTER NightlySettle (30-min buffer) |

**Why 30 min after settle:**
- Lets NightlySettle fully complete (typical 2-5 min runtime)
- Reconcile checks for drift that settle would have fixed — better data if settle ran first
- Any drift caught here signals either: missed settlement, API lag, or local-log corruption

---

### 11. `Calibration` — Sun 7:00 PM PST (10:00 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun |
| **Script** | `scripts\schedulers\maintenance\calibration.bat` |
| **Runs** | `model_calibration.py --days 7 --save` |
| **Purpose** | Weekly Brier score refresh, per-sport calibration curves, dimension breakdowns |
| **Output** | `reports/` calibration report |

**What it reports:**
- Brier score (predicted probability vs realized outcome)
- Calibration curve: predicted win rate vs actual win rate by decile
- Per-sport, per-confidence, per-edge-bucket breakdowns
- Prioritized recommendations (e.g., "NBA edge floor should move to 10%")

**Why Sunday 7 PM:** Full week of settled trades available; captures NBA Sunday afternoon + NFL Sunday + weekend MLB; runs before Monday's weekly-broad execute so any calibration recommendations can be applied immediately.

---

### 12. `Backtest` — Sun 7:30 PM PST (10:30 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun |
| **Script** | `scripts\schedulers\maintenance\backtest.bat` |
| **Runs** | `backtester.py --simulate --save` |
| **Purpose** | Equity curve, max drawdown, Sharpe, strategy comparison |
| **Dependencies** | Runs AFTER Calibration (fresh data) |

**What it reports:**
- Equity curve and running drawdown
- Win/lose streaks
- Profit factor, Sharpe ratio, ROI
- Breakdowns by sport, category (ML/Spread/Total), confidence, edge bucket
- Strategy simulation: compares filter strategies (e.g., "confidence >= medium only" vs "edge >= 10% only")

---

### 13. `Weekly-Analysis` — Sun 11:45 PM PST (2:45 AM ET Mon)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun |
| **Script** | `scripts\schedulers\maintenance\weekly_analysis.bat` |
| **Runs** | `betting_analysis.py --days 7 --save` |
| **Purpose** | End-of-week 7-day performance review driving the `/edge-radar-analysis` skill output |
| **Output** | `reports\Performance\betting_analysis_YYYY-MM-DD_7d.md` |
| **Dependencies** | Runs AFTER `NightlySettle` (11:00 PM) + `Reconcile` (11:30 PM) — 15-min buffer |

**What it reports:** Headline stats, by-sport / by-category / by-side (YES/NO) / edge buckets / confidence / market price breakdowns, calibration, longshots, win-loss streaks, daily P&L, and full trade ledger.

**Why Sun 11:45 PM:**
- NightlySettle + Reconcile have just completed — trade log is fresh and drift-checked
- Captures the full week including Sunday NFL/NBA/MLB
- Sets up the `Email-Weekly-Analysis` send 10 minutes later, before end-of-day UTC rollover

---

### 14. `Email-Weekly-Analysis` — Sun 11:55 PM PST (2:55 AM ET Mon)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\Weekly-Analysis-Report.sh` |
| **Invocation** | `"C:\Program Files\Git\bin\bash.exe" "<script>.sh"` |
| **Purpose** | Emails the weekly performance analysis report produced 10 min earlier |
| **Email subject** | `Edge-Radar | Weekly Performance Analysis` |
| **From inbox** | `<YOUR_AGENTMAIL_INBOX>` |

**Mechanism:** Same pattern as the other email tasks — shell script spawns `claude --dangerously-skip-permissions -p "..."` which reads `reports\Performance\betting_analysis_<today>_7d.md` and sends a dark-themed HTML email via the `agentmail` skill.

**Behavior if no report:** If today's 7-day report file is missing, the subprocess reports the most recent available and does NOT send an email (prevents stale sends).

**10-min buffer from 11:45 Weekly-Analysis:** Tighter than the morning email buffers because `betting_analysis.py` is pure-local (no API fetches) and typically finishes in <2 min.

---

### 15. `MonthlyCalibration` — 1st of each month 2:00 AM PST (5:00 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Monthly (1st of every month, all 12 months) |
| **Executable** | `.venv\Scripts\python.exe` (direct invocation — no .bat wrapper) |
| **Arguments** | `scripts\kalshi\model_calibration.py --days 30 --save` |
| **Purpose** | Monthly 30-day Brier refresh — longer sample than the weekly 7-day run, catches slow calibration drift |
| **Output** | `reports/Calibration/YYYY-MM-DD_calibration_report.md` |

**What it reports:** Same structure as the weekly `Calibration` task (overall Brier, calibration curve, per-sport/per-confidence/per-edge-bucket breakdowns, prioritized recommendations), but over a 30-day window.

**Why 1st of the month, 2:00 AM PST:**
- Runs after month-end settlements have closed on Kalshi (late-night ET games on the 30/31st resolve by 11 PM PT via NightlySettle) — ensures the final day of the prior month is included in the 30-day window
- 2:00 AM is off-peak — no conflict with daily 11:00 PM settle or 11:30 PM reconcile
- 30-day window smooths out weekly noise the 7-day `Calibration` can't — catches slow structural drift visible only month-over-month

**Relationship to weekly `Calibration` task (#9):**
- Weekly (Sun 7 PM) — `--days 7`, short horizon, detects fast-moving issues
- Monthly (1st 2 AM) — `--days 30`, longer horizon, detects slow drift and structural biases
- Both write to `reports/Calibration/` with date-prefixed filenames — no collision

---

### 18. `WeeklyAccountGraph` — Sun 9:00 AM PST (12:00 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun |
| **Executable** | `.venv\Scripts\python.exe` (direct invocation — no .bat wrapper) |
| **Arguments** | `scripts\schedulers\automation\refresh_account_graph.py` |
| **Purpose** | Keeps the public account-growth graph current. Pulls the live Kalshi snapshot, regenerates the interactive HTML + static PNG, copies the HTML into `.claude/html/account-40c3eb1d3d3cb9c4e07fee61.html`, then pushes **only that one file** to `master` via the `gh` contents API — which fires the GitHub Pages deploy |
| **Output** | `docs/my-documents/account-graph/latest/` (local) + the published file on `master`; log at `logs/account_graph_refresh.log` |
| **Install** | `python scripts/schedulers/automation/install_windows_task.py install account-graph` |

**Why Sunday 9:00 AM PST:** Weekend morning, after Saturday's slate has settled (NightlySettle 11 PM Sat) and well clear of the Sun 5:05 AM SameDay execute. Once-a-week is plenty for a balance chart.

**Why a `gh` push instead of a normal commit:** generation must run locally (needs the `.env` Kalshi keys + the gitignored local settlements ledger), but the Pages deploy only watches `master`. Pushing the single file via `gh api PUT .../contents/...` updates `master` directly without touching the `mike_win-desktop` working branch or requiring a PR. `.claude/html/account-*.html` is gitignored so the file is managed solely by this task and never collides with branch PRs. The push is best-effort — if `gh` is unavailable the local graph still regenerates and the failure is logged.

**Privacy note:** the published graph shows **real dollar figures** (balance, deposit, P&L) on a public, unauthenticated site. It's at an unguessable filename with a `noindex, nofollow` meta tag — *lightly hidden, not access-controlled*. Treat the graph as public.

---

### 19. `Weekly-Futures-Execution` — Sat 9:00 AM PST (12:00 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sat |
| **Script** | `scripts\schedulers\futures_executions\weekly_futures_execute.bat` |
| **Runs** | `scan.py futures --unit-size 1 --max-bets 3 --min-bets 1 --budget 5% --exclude-open --save --report-dir "reports\Futures\schedulers" --execute` |
| **Purpose** | First **futures** automation — scans championship/outright winner markets (NFL Super Bowl, NBA Finals, NHL Stanley Cup, MLB World Series, NCAAB MOP, golf majors) and executes top picks. Offseason series with no Odds API outright data are skipped automatically; golf only prices the 4 majors during their play weeks |
| **Output** | `reports\Futures\schedulers\YYYY-MM-DD_futures_scan.md` + portfolio status before/after |

**Why Saturday 9:00 AM PST:** the lightest day in the schedule (no other Edge-Radar task fires Saturday morning), so no contention. Outright lines are posted and sharp by mid-morning, and golf majors (Thu–Sun) are mid-tournament. Once-a-week matches the slow-moving nature of futures.

**Why conservative sizing (5% budget / max 3 / unit $1):** futures boards are thin and longshot-heavy, and the game-tuned gates (composite ≥ 6.0, `MIN_MARKET_PRICE` floor, NO-favorite guard) reject most outright candidates — so this task often places **0 bets**, by design. All standard risk gates + the `MAX_BET_SIZE` cap apply. `--min-bets 1` aborts cleanly when nothing qualifies (no over-concentration).

**Install (one-time, from Git Bash):**
```bash
MSYS_NO_PATHCONV=1 schtasks /create /tn "\Edge-Radar\Weekly-Futures-Execution" \
  /tr "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\futures_executions\weekly_futures_execute.bat" \
  /sc weekly /d SAT /st 09:00 /f
```

**Validated 2026-06-20 (install day):** registered (State=Ready, DaysOfWeek=64=Sat, next run 2026-06-27 9:00 AM), fired via `schtasks /run` → `LastTaskResult=0`. The day's 4 futures candidates (NFL LAR, MLB NYY, 2× U.S. Open golf) were all correctly rejected by the gates (score/price) → **0 bets placed**, balance untouched — a safe live end-to-end test.

**WARNING:** places live orders when `DRY_RUN=false`. Verify `.env` before relying on it.

---

### 20. `Email-Weekly-Futures` — Sat 9:20 AM PST (12:20 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sat |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\Weekly-Futures-Execution-Report.sh` |
| **Invocation** | `"C:\Program Files\Git\bin\bash.exe" "<script>.sh"` |
| **Purpose** | Emails the weekly futures execution report produced 20 min earlier by task #19 |
| **Email subject** | `Edge-Radar | Weekly Futures Execution Report` |
| **From inbox** | `<YOUR_AGENTMAIL_INBOX>` |
| **Log** | `logs/email_futures.log` |

**Mechanism:** same pattern as the other email tasks — spawns `claude --dangerously-skip-permissions -p "..."` which uses the `agentmail` skill to send a styled HTML email of today's `reports\Futures\schedulers\YYYY-MM-DD_futures_execution.md`.

**Proof-of-life on empty weeks:** futures boards are thin, so most weeks place 0 bets. The futures scanner (`futures_edge.py`) was updated 2026-06-20 to **always** write a report on `--save` — an empty "0 orders" execution report when nothing clears — so this email fires every week regardless (matches the policy behind the same-day email fix 156d5e5). Without that, the email would silently skip nearly every Saturday.

**Install (one-time, from Git Bash):**
```bash
MSYS_NO_PATHCONV=1 schtasks /create /tn "\Edge-Radar\Email-Weekly-Futures" \
  /tr "\"C:\Program Files\Git\bin\bash.exe\" \"D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\custom\Shell-Scripts\Run-Reports\Weekly-Futures-Execution-Report.sh\"" \
  /sc weekly /d SAT /st 09:20 /f
```

**Validated 2026-06-20:** fired via `schtasks /run` → `LastTaskResult=0`; email delivered to `mikeschecht@gmail.com` (the day's 0-order proof-of-life report), next run 2026-06-27 9:20 AM.

---

### 21. `Daily-Polymarket-DryRun` — Daily 9:40 AM PST (12:40 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\schedulers\polymarket_scans\daily_polymarket_scan.bat` |
| **Runs** | `scan.py polymarket --filter futures --save` |
| **Purpose** | **Read-only** Polymarket championship-futures scan (World Cup, NFL Super Bowl, MLB World Series, NBA Finals, NHL Stanley Cup) priced against sportsbook consensus. Appends every run — timestamp, filter, opportunity count, each opportunity with its preflight gate verdict, **including 0-opportunity runs** — to the PM2 edge-proving evidence log. This is the dry-run window that must demonstrate edge before Phase 2 (real-money execution) starts (`docs/ROADMAP.md` Priority 0) |
| **Output** | `data\polymarket\dryrun_log.jsonl` (append-only evidence) + `reports\Polymarket\YYYY-MM-DD_futures_polymarket_scan.md` (only when rows surface) |
| **Log** | `logs\polymarket_dryrun_scan.log` (no paired email task — this is evidence collection, not actionable output) |
| **Cost** | ~4 Odds API requests per run (one per active outright sport key) |

**Why daily 9:40 AM PST:** quiet slot — after the 5:05/5:25 morning pair, before the 11:00/11:20 midday pair, and clear of Saturday's 9:00/9:20 futures pair. Morning outright lines are posted and sharp. Daily (vs the weekly Kalshi futures cadence) because the edge-proving window wants sample size, and a read-only run is cheap.

**Places NO orders:** the Phase 1 scanner refuses `--execute` by design until PM2 ships. The `.bat` sets `PYTHONIOENCODING=utf-8` — required because the rich table output contains Unicode that crashes cp1252 when the console is redirected to the log file.

**Install (one-time, from PowerShell):**
```powershell
schtasks /Create /TN "\Edge-Radar\Daily-Polymarket-DryRun" `
  /TR "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\polymarket_scans\daily_polymarket_scan.bat" `
  /SC DAILY /ST 09:40 /F
```

**Validated 2026-07-20 (install day):** registered (State=Ready, next run 2026-07-21 9:40 AM), fired via `Start-ScheduledTask` → `LastTaskResult=0`; evidence record appended to `dryrun_log.jsonl` and the day's report written (1 opportunity: NBA Spurs +4.0%, low confidence, correctly gated on score → 0 would-bet).

---

### 22. `Hourly-Settle` — Every hour at :35

| Property | Value |
|:---------|:------|
| **Schedule** | Hourly (`/SC HOURLY /MO 1 /ST 00:35`) |
| **Executable** | `.venv\Scripts\python.exe` (direct invocation — no .bat wrapper, same pattern as NightlySettle) |
| **Arguments** | `scripts\kalshi\kalshi_settler.py settle` |
| **Purpose** | U1: settle throughout the day instead of once at 11 PM. Keeps `data/history` fresh so **Gate 1 (daily loss limit)** sees intraday settlements, positions clear as games end, and R4 resting-order cleanup runs timely |
| **Why now** | Enabled by **M2** (2026-07-20): the cross-process trade-log lock + merge-safe `append_trades` make a settle that overlaps an execute task merge instead of clobber — exactly the race that made hourly settling unsafe before |
| **Why :35** | The only minute slot clear of every existing task (:00 executes, :05 SameDay, :20/:25 emails, :30 Reconcile/NextDay, :40 Polymarket, :45 Weekly-Analysis, :50 Daily-Summary, :55 email) |
| **NightlySettle** | Kept as belt-and-suspenders during a ~1-week validation (settle is idempotent — the 11:00 PM run just finds nothing new after the 10:35 PM sweep). Retire it once Hourly-Settle shows a week of `LastTaskResult=0` |

**Install (one-time, from PowerShell):**
```powershell
schtasks /Create /TN "\Edge-Radar\Hourly-Settle" `
  /TR "D:\AI_Agents\Specialized_Agents\Edge_Radar\.venv\Scripts\python.exe D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_settler.py settle" `
  /SC HOURLY /MO 1 /ST 00:35 /F
```

**Validated 2026-07-20 (install day):** registered, fired via `Start-ScheduledTask` → `LastTaskResult=0`, next fire on the :35.

---

### 17. `U2-Review` — One-shot 2026-05-14 7:00 AM PT (10:00 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | One-time (`/sc once /sd 05/14/2026 /st 07:00`) |
| **Script** | `scripts\schedulers\maintenance\u2_2week_review.bat` |
| **Runs** | `u2_2week_review.py` |
| **Purpose** | Post-ship review of U2 daily-summary digest (~2 weeks after 2026-04-30 ship). Local pass scans `reports/Performance/daily_summary_*.md` for the last 14 days to surface firing-reliability + section coverage (which sections were consistently empty across the window). Then spawns a `claude --dangerously-skip-permissions -p` subprocess (same pattern as the email tasks) to do a code-review pass on `scripts/kalshi/daily_summary.py` + tests, with explicit instructions to be opinionated about what to drop. Combines both into a single recommendation report with an operational checklist for the user to fill in (which sections they actually read each morning, any rendering issues, anything missing from the digest) |
| **Output** | `reports\Performance\u2_2week_review_YYYY-MM-DD.md` |

**Why 2026-05-14 7:00 AM PT:** ~2 weeks after U2 ship (2026-04-30) — long enough for ~14 actual digest files to exist (firing-reliability signal) and a meaningful operational pattern to emerge, before the format choices calcify. Off-peak local time, no conflict with any daily/weekly task. One-shot — fires once and `Status: Ready` flips after.

**Migrated from a remote routine** (`trig_01Q6iNTVkob15MewHYS5CKYH`, now disabled) per the established pattern (see "One-shot review pattern" in `project_scheduled_tasks.md` memory + R8-Review precedent). The local-script approach is strictly better here because the remote agent literally couldn't see `reports/Performance/daily_summary_*.md` (gitignored) — the firing-reliability signal lives only on the user's machine.

**One-shot task management:** if 2026-05-14 fires before enough digest data has accumulated (e.g. user installed the Daily-Summary tasks late), re-arm with:

```bash
MSYS_NO_PATHCONV=1 schtasks /change /tn "\Edge-Radar\U2-Review" /sd <new-date> /st 07:00
```

Or delete entirely with `Unregister-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'U2-Review'`.

---

### 16. `R8-Review` — One-shot 2026-05-29 6:00 AM PT (9:00 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | One-time (`/sc once /sd 05/29/2026 /st 06:00`) |
| **Script** | `scripts\schedulers\maintenance\r8_review.bat` |
| **Runs** | `r8_cross_category_review.py` |
| **Purpose** | Post-hoc A/B review of R8 (cross-category dedup, shipped 2026-04-29). Slices `data/history/kalshi_settlements.json` into ML/Total/Spread cohorts per `(sport, game_id)`, simulates the R8-on outcome (highest-edge bet kept), and recommends per-sport FLIP ON / FLIP OFF / NEED MORE DATA |
| **Output** | `reports\Performance\R8_cross_category_review_YYYY-MM-DD.md` |

**Why 2026-05-29 6:00 AM PT:** ~30 days after R8 ship (2026-04-29) — long enough for a meaningful cohort sample, before the change is "old news". Off-peak local time, no conflict with any daily/weekly task. One-shot — fires once and `Status: Ready` flips after.

**Recommendation rules** (encoded in the script):
- **FLIP ON** — status-quo cohort ROI ≤ 0 AND R8-on - status-quo > 5pp AND n_xcat ≥ 10
- **NEED MORE DATA** — n_xcat < 10
- **FLIP OFF (keep default)** — everything else

The report includes an `.env` snippet listing the exact `CROSS_CATEGORY_DEDUP_<SPORT>=true` lines to paste in for sports that meet the FLIP ON bar. User reviews and applies manually.

**One-shot task management:** if 2026-05-29 produces NEED MORE DATA across the board, re-arm with:

```bash
MSYS_NO_PATHCONV=1 schtasks /change /tn "\Edge-Radar\R8-Review" /sd <new-date> /st 06:00
```

Or delete entirely with `Unregister-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'R8-Review'`.

---

## Disabled Tasks (retained for reference)

These remain in `\Edge-Radar\` but are not enabled. They were part of prior experiments or replaced by consolidated equivalents.

| Task | Script | Why disabled |
|:-----|:-------|:-------------|
| `All-Sports-NoDateFilter-Scan` | `no_date_filter_scan.bat` | Scan-only variant; execution variant is what runs |
| `All-Sports-SameDay-Scan` | `same_day_scan.bat` | Scan-only variant; execution variant is what runs |
| `MLB-NextDay-Scan` | `mlb_morning_scan.bat` | Per-sport variant; replaced by consolidated `All-Sports-NextDay-Execution` |
| `NBA-NextDay-Scan` | `nba_morning_scan.bat` | Per-sport variant; replaced |
| `NFL-NextDay-Scan` | `nfl_morning_scan.bat` | Per-sport variant; replaced |
| `NHL-NextDay-Scan` | `nhl_morning_scan.bat` | Per-sport variant; replaced |

Keep these in place — useful reference for how to structure per-sport scans if that pattern is ever needed again.

---

## Daily / Weekly Timeline

### A typical Mon-Thu
```
05:05 AM  All-Sports-SameDay-Execution         → bets today's NBA/MLB/NHL games
05:25 AM  Email-SameDay                        → email same-day report
09:40 AM  Daily-Polymarket-DryRun              → read-only PM evidence scan (no orders)
11:00 AM  All-Sports-NoDateFilter-Midday-Exec  → midday wide-net (no date filter)
11:20 AM  Email-NoDateFilter-Midday            → email midday wide-net report
02:00 PM  All-Sports-SameDay-Late-Execution    → late same-day catch-up
02:20 PM  Email-SameDay-Late                   → email late same-day report
08:30 PM  All-Sports-NextDay-Execution         → bets tomorrow's games
08:50 PM  Email-NextDay                        → email next-day report
11:00 PM  NightlySettle                        → settle today's completed bets
11:30 PM  Reconcile                            → verify local vs API
```

### A typical Sunday
```
05:05 AM  All-Sports-SameDay-Execution  (Sunday's NBA/MLB/NFL)
05:25 AM  Email-SameDay
09:40 AM  Daily-Polymarket-DryRun       (read-only PM evidence scan)
11:00 AM  All-Sports-NoDateFilter-Midday-Execution
11:20 AM  Email-NoDateFilter-Midday
02:00 PM  All-Sports-SameDay-Late-Execution
02:20 PM  Email-SameDay-Late
07:00 PM  Calibration                   (weekly Brier refresh)
07:30 PM  Backtest                      (weekly strategy review)
08:30 PM  All-Sports-NextDay-Execution  (Monday's games)
08:50 PM  Email-NextDay
11:00 PM  NightlySettle
11:30 PM  Reconcile
11:45 PM  Weekly-Analysis
11:55 PM  Email-Weekly-Analysis
```

### A typical Fri
```
05:05 AM  All-Sports-SameDay-Execution
05:25 AM  Email-SameDay
09:40 AM  Daily-Polymarket-DryRun           (read-only PM evidence scan)
11:00 AM  All-Sports-NoDateFilter-Midday-Execution
11:20 AM  Email-NoDateFilter-Midday
02:00 PM  All-Sports-SameDay-Late-Execution
02:20 PM  Email-SameDay-Late
          (All-Sports-NextDay-Execution skipped — Sunday morning run will handle Sunday NFL)
11:00 PM  NightlySettle
11:30 PM  Reconcile
```

### A typical Sat
```
05:05 AM  All-Sports-SameDay-Execution
05:25 AM  Email-SameDay
09:00 AM  Weekly-Futures-Execution          (futures scan + execute; often 0 bets)
09:20 AM  Email-Weekly-Futures              (futures report — proof-of-life even on 0-bet weeks)
09:40 AM  Daily-Polymarket-DryRun           (read-only PM evidence scan)
11:00 AM  All-Sports-NoDateFilter-Midday-Execution
11:20 AM  Email-NoDateFilter-Midday
02:00 PM  All-Sports-SameDay-Late-Execution
02:20 PM  Email-SameDay-Late
          (All-Sports-NextDay-Execution skipped — Sunday morning run will handle Sunday NFL)
11:00 PM  NightlySettle
11:30 PM  Reconcile
```

---

## Daily Bet Count Estimate

| Day | Max new bets | Notes |
|:----|:-------------|:------|
| Mon-Thu | **7 (SameDay) + 5 (Midday-NoDateFilter) + 4 (Late-SameDay) + 6 (NextDay) = 22** | Gate 7 series dedup + `--exclude-open` reduce practical count significantly |
| Fri | **7 + 5 + 4 = 16** | (NextDay skipped Fri/Sat) |
| Sat | **7 + 5 + 4 + 3 (Weekly-Futures) = 19** | NextDay skipped; futures rarely fills (gates reject most outrights) |
| Sun | **7 + 5 + 4 + 6 = 22** | |

Hard ceiling: Gate 2 (max open positions = 50) prevents runaway accumulation. Settle at 11 PM clears ~50% of opens each night. The Midday-NoDateFilter (8%) and Late-SameDay (5%) tasks use smaller budgets than the morning SameDay (12%) and evening NextDay (12%) runs to preserve daily-cap headroom.

---

## Manual Trigger Commands

Run any task immediately via Git Bash (prepend `MSYS_NO_PATHCONV=1` to prevent path translation):

```bash
# Daily summary digest
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Daily-Summary"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-Daily-Summary"

# Betting execute tasks
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\All-Sports-SameDay-Execution"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\All-Sports-NoDateFilter-Midday-Execution"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\All-Sports-SameDay-Late-Execution"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\All-Sports-NextDay-Execution"

# Email tasks
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-SameDay"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-NoDateFilter-Midday"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-SameDay-Late"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-NextDay"

# Polymarket dry-run evidence scan (read-only)
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Daily-Polymarket-DryRun"

# Maintenance
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Hourly-Settle"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\NightlySettle"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Reconcile"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Calibration"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\MonthlyCalibration"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Backtest"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Weekly-Analysis"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-Weekly-Analysis"

# One-shot reviews (can be triggered manually any time)
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\R8-Review"      # fires 2026-05-29
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\U2-Review"      # fires 2026-05-14
```

From PowerShell (no prefix needed):

```powershell
Start-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'All-Sports-NextDay-Execution'
```

---

## Management Commands

### List all tasks in folder
```powershell
Get-ScheduledTask -TaskPath '\Edge-Radar\' | Select-Object TaskName, State | Format-Table
```

### See next run time + last result
```powershell
Get-ScheduledTask -TaskPath '\Edge-Radar\' | ForEach-Object {
  $info = Get-ScheduledTaskInfo -TaskName $_.TaskName -TaskPath $_.TaskPath
  [PSCustomObject]@{
    Name = $_.TaskName
    State = $_.State
    NextRun = $info.NextRunTime
    LastRun = $info.LastRunTime
    LastResult = $info.LastTaskResult  # 0 = success
  }
} | Sort-Object NextRun | Format-Table -AutoSize
```

### Disable a task (doesn't delete)
```powershell
Disable-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'All-Sports-NextDay-Execution'
```

### Enable a task
```powershell
Enable-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'All-Sports-NextDay-Execution'
```

### View full task definition (XML)
```powershell
Export-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'All-Sports-NextDay-Execution'
```

### Delete a task
```powershell
Unregister-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'TaskName' -Confirm:$false
```

---

## Wrapper Scripts (`scripts/schedulers/maintenance/`)

Created 2026-04-22 for maintenance tasks that need consistent CWD + venv python:

| File | Contents |
|:-----|:---------|
| `settle.bat` | `cd /d D:\...\Edge_Radar && .venv\Scripts\python.exe scripts\kalshi\kalshi_settler.py settle` |
| `reconcile.bat` | Same pattern, runs `reconcile` |
| `calibration.bat` | Runs `model_calibration.py --days 7 --save` |
| `backtest.bat` | Runs `backtester.py --simulate --save` |
| `weekly_analysis.bat` | Runs `betting_analysis.py --days 7 --save` |
| `daily_summary.bat` | Runs `daily_summary.py --save` (morning P&L digest, paired with `Email-Daily-Summary`) |
| `r8_review.bat` | Runs `r8_cross_category_review.py` (one-shot, scheduled 2026-05-29) |
| `u2_2week_review.bat` | Runs `u2_2week_review.py` (one-shot, scheduled 2026-05-14) |

**Note:** `NightlySettle` and `MonthlyCalibration` are set up with direct python invocation (no .bat wrapper). The wrappers exist for manual invocation convenience and to keep CWD + venv python consistent.

---

## Troubleshooting

### Email task logs (added 2026-06-20)

Each email shell script now tees its `claude -p` stdout+stderr to a per-task log and records a timestamped start/end banner with the real exit code. The script preserves the `claude` exit code (via `set -o pipefail` + `${PIPESTATUS[0]}`), so Task Scheduler still sees the true success/failure even though output is piped through `tee`.

| Email task | Log file |
|:-----------|:---------|
| `Email-SameDay` | `logs/email_sameday.log` |
| `Email-NoDateFilter-Midday` | `logs/email_nodatefilter_midday.log` |
| `Email-SameDay-Late` | `logs/email_sameday_late.log` |
| `Email-NextDay` | `logs/email_nextday.log` |
| `Email-Daily-Summary` | `logs/email_daily_summary.log` |
| `Email-Weekly-Analysis` | `logs/email_weekly_analysis.log` |
| `Email-NoDateFilter` (legacy) | `logs/email_nodatefilter.log` |

`logs/` is gitignored. When an email task shows a non-zero `LastTaskResult`, read the tail of its log first — the actual Claude/agentmail error is now captured there instead of being lost.

### Exit code 1 (0x00000001)

The `claude -p` subprocess ran but failed. Most common cause: **Claude CLI auth lapsed** — the token expired and the headless invocation couldn't authenticate (re-`/login` in an interactive session fixes it). Other causes: agentmail skill/API error, or a malformed prompt. Check the per-task log (table above) for the captured error.

**Historical note (2026-06-20):** `Email-SameDay` failed with exit 1 at 5:25 AM while the paired execute task succeeded and wrote a valid empty "0 orders" report. Root cause was a lapsed Claude CLI auth token; a manual re-run after re-login succeeded. This failure left no diagnostic trail, which is what prompted adding the per-task logging above.

### Exit code 127 (bash: No such file or directory)

If an email task shows exit code `0x0000007F` (127), the shell script path is wrong. Check:

```powershell
$a = (Get-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'Email-SameDay').Actions
Write-Host $a.Arguments
```

Verify the path matches the actual file location. Shell scripts live at `scripts\custom\Shell-Scripts\Run-Reports\`.

**Historical note (2026-04-22):** Initial task creation used path `Shell-Scripts\<script>.sh` but scripts had been reorganized into `Run-Reports/` subfolder. All 3 email tasks failed with exit 127 on first dry-run test. Fixed by recreating tasks with the correct subfolder path.

### Exit code 0 but no email received

Script found today's date and returned successfully but nothing arrived. Causes to check:

1. **Shell script points to the wrong report folder.** Exit 0 happens when claude subprocess finds no report for today and correctly skips sending. Verify the path in the `.sh` file matches the actual output folder of the paired execute task.

2. **Historical note (2026-04-22):** `NextDay-Edge-Report.sh` was written for an older per-sport scan setup (`next-day/mlb/`, `next-day/nba/`, etc.) but consolidated `next_day_execute.bat` writes to `next-day-executions/` (flat, no sport subfolders). Also the script looked for TOMORROW's date but file is named with the run date (TODAY). Fixed by rewriting the script to match the SameDay pattern.

3. **Report file was written but for a different date** — filename uses the RUN date, not the target date. A next-day execute run today writes `YYYY-MM-DD_sports_execution.md` where YYYY-MM-DD = today (despite containing tomorrow's bets).

4. **Historical note (2026-06-15):** Two consecutive missing same-day emails (6/14, 6/15) traced to `edge_detector.py` only saving a report when at least one opportunity cleared the edge threshold (`if args.save and opportunities:`). On no-opportunity days the scan returned early, **no report was written**, and the email task correctly skipped — so empty days silently produced no email, contradicting the proof-of-life policy (`feedback_sameday_empty_emails`). Fixed so `--save` now **always** writes a report; a no-opportunity day emits an empty "0 orders" execution report. After this fix, "exit 0 but no email" on a no-opportunity day should no longer happen — if it does, the execute task itself failed before the save step (check the `.bat` actually ran the scan, not just the trailing `status` call whose exit code masks scan crashes).

### Exit code 267009 (still running)

`0x00041301` means the task hasn't finished yet. Email tasks typically run 30-120 seconds (claude subprocess + agentmail API call).

### Exit code 267011 (never run)

`0x00041303` means the task has not yet been triggered since creation. Normal for newly-created tasks.

---

## Setup Gotchas (for future reference)

### Git Bash + schtasks
```bash
# WRONG — Git Bash translates /tn to a path
schtasks /create /tn "Foo" /tr "..." /sc daily /st 08:00
# → ERROR: Invalid argument/option - 'C:/Program Files/Git/create'

# CORRECT
MSYS_NO_PATHCONV=1 schtasks /create /tn "Foo" /tr "..." /sc daily /st 08:00
```

### Folder targeting
```bash
# WRONG — lands in root `\`
schtasks /create /tn "MyTask" ...

# CORRECT — lands in \Edge-Radar\
schtasks /create /tn "\Edge-Radar\MyTask" ...
```

### Email task invocation
Shell scripts need bash.exe wrapper. Location of Git Bash on this system: `C:\Program Files\Git\bin\bash.exe`.

```bash
# /tr argument needs escaped quotes because path has spaces
/tr "\"C:\Program Files\Git\bin\bash.exe\" \"D:\path\to\script.sh\""
```

### Days of week bitmask
When checking task triggers via PowerShell, `DaysOfWeek` is a bitmask:

| Day | Bit | Value |
|:----|:----|:------|
| Sunday | 2^0 | 1 |
| Monday | 2^1 | 2 |
| Tuesday | 2^2 | 4 |
| Wednesday | 2^3 | 8 |
| Thursday | 2^4 | 16 |
| Friday | 2^5 | 32 |
| Saturday | 2^6 | 64 |

So `DaysOfWeek = 18` means `2 + 16` = Monday + Thursday.

---

## Dry-Run Testing Workflow

Before letting scheduled tasks place live bets:

1. **Set dry-run in `.env`:**
   ```
   DRY_RUN=true
   ```

2. **Suggested test order (safest first):**
   | Order | Task | Why |
   |:-----:|:-----|:----|
   | 1 | `Reconcile` | Read-only, quickest sanity check |
   | 2 | `Calibration` | Read-only, generates calibration report |
   | 3 | `Backtest` | Read-only, generates backtest report |
   | 4 | `NightlySettle` | Writes to local files but no external bets |
   | 5 | `All-Sports-NextDay-Execution` | Would place bets but dry-run blocks |
   | 6 | `All-Sports-NoDateFilter-Execution` | Biggest unknown, the new weekly broad |
   | 7 | `Email-SameDay` | Verify email pickup of existing report |
   | 8 | `Email-NoDateFilter-Midday`, `Email-SameDay-Late`, `Email-NextDay` | Verify email pickup after executes produce reports |

3. **Manual trigger:** See "Manual Trigger Commands" section above.

4. **Check logs:** Scripts echo to console + write reports to `reports/Sports/schedulers/<mode>/`.

5. **Verify results:**
   - Execute tasks: report file exists, no positions opened (dry-run), exit code 0
   - Email tasks: email received, HTML renders correctly, report content matches file
   - Settle/Reconcile: no errors, no drift reported

6. **Flip to live:** When confident, set `DRY_RUN=false` in `.env`.

---

## Output File Structure

```
reports/Sports/schedulers/
├── same-day-executions/
│   └── 2026-04-22_sports_execution.md             ← Daily 5:05 AM
├── no-date-filter-executions/
│   └── 2026-04-22_sports_execution.md             ← (legacy, Mon/Thu task retired 2026-05-17)
├── no-date-filter-midday-executions/
│   └── 2026-05-17_sports_execution.md             ← Daily 11:00 AM (added 2026-05-17)
├── same-day-late-executions/
│   └── 2026-05-17_sports_execution.md             ← Daily 2:00 PM (added 2026-05-17)
└── next-day-executions/
    └── 2026-04-22_sports_execution.md             ← Sun-Thu 8:30 PM (shifted from 6:00 PM 2026-05-17)

reports/
├── Calibration/
│   ├── 2026-04-26_calibration_report.md  ← Sun 7:00 PM (weekly, 7-day)
│   └── 2026-05-01_calibration_report.md  ← 1st of month 2:00 AM (monthly, 30-day)
├── backtest/
│   └── 2026-04-26_backtest.md            ← Sun 7:30 PM
└── Performance/
    └── betting_analysis_2026-04-26_7d.md ← Sun 11:45 PM (weekly 7-day analysis)

data/
├── positions/open_positions.json          ← updated by execute + settle
└── history/2026-04-22_trades.json         ← updated by settle
```

---

## Email Delivery Architecture

```
Execute task runs (5:05 / 5:20 / 6:00 PM)
         ↓
Writes report file to reports/Sports/schedulers/<mode>/YYYY-MM-DD_*.md
         ↓
(wait 20 min for execute to finish reliably)
         ↓
Email task fires (5:25 / 5:40 / 6:20 PM)
         ↓
Shell script invokes: claude --dangerously-skip-permissions -p "<prompt>"
         ↓
Inner Claude reads report file, formats HTML, invokes agentmail skill
         ↓
Email sent from <YOUR_AGENTMAIL_INBOX> → mikeschecht@gmail.com
         ↓
Subject: "Edge-Radar | <Mode> Execution Report"
```

**Why 20-min buffer:** Execute tasks typically run 3-8 minutes but MLB parallel pitcher fetches can occasionally stretch to 15 min on slow API days. 20 min is a safe margin.

**If execute fails or produces no report:** Email task correctly detects missing report for today's date and skips sending (no stale emails).

---

## Installing the Daily-Summary tasks (one-time)

> **Status (2026-04-30):** all three tasks (`Daily-Summary`, `Email-Daily-Summary`, `U2-Review`) are **already installed** in `\Edge-Radar\`. Snippets below are kept for reproducibility (e.g. reinstalling on a new machine, or after deleting + recreating to change the schedule).

Both tasks live in `\Edge-Radar\` and are installed manually via `schtasks` (same pattern as the other email/maintenance tasks per R24c). Run once from Git Bash:

```bash
# 1. Daily-Summary — generates the digest at 4:50 AM PST
MSYS_NO_PATHCONV=1 schtasks /create /tn "\Edge-Radar\Daily-Summary" \
  /tr "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\maintenance\daily_summary.bat" \
  /sc daily /st 04:50 /f

# 2. Email-Daily-Summary — emails the digest at 5:00 AM PST
MSYS_NO_PATHCONV=1 schtasks /create /tn "\Edge-Radar\Email-Daily-Summary" \
  /tr "\"C:\Program Files\Git\bin\bash.exe\" \"D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\custom\Shell-Scripts\Run-Reports\Daily-Summary-Report.sh\"" \
  /sc daily /st 05:00 /f
```

**Verify:**
```powershell
Get-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'Daily-Summary','Email-Daily-Summary' | Format-Table TaskName, State
```

**Dry-run test (won't place bets — read-only generators):**
```bash
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Daily-Summary"
# wait ~5s, then verify report exists:
ls -la D:/AI_Agents/Specialized_Agents/Edge_Radar/reports/Performance/daily_summary_*.md
# then trigger the email:
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-Daily-Summary"
```

### Empty-day expected output (verified 2026-04-30 dry-run)

Running both tasks manually on 2026-04-30 produced a successful email with three blank sections (Yesterday / Open Exposure / Pending Today) and one populated section (Context: balance + 7-day rolling). **This is correct** — proof-of-life pattern matches `feedback_sameday_empty_emails`. Causes that day:

- Trade log had been reset/wiped earlier (only 1 resting order, no filled positions)
- No settlements in the rolling 24h window
- No open positions on today's slate (follows from the above)

The Context section pulls from the historical `data/history/kalshi_settlements.json` (173 entries) so it's never empty. **If a week from now all three sections are still blank every morning,** that's a real signal — either the trade log isn't capturing fills, the settler isn't finding settlements, or the bet pipeline is paused. The U2-Review one-shot on 2026-05-14 (§ 15) surfaces that pattern explicitly via the section-coverage table.

### Bonus: install the one-shot U2-Review (fires 2026-05-14 at 7 AM PT)

> **Status (2026-04-30):** already installed. Snippet kept for reproducibility / re-arm on a new date.

Pairs with the Daily-Summary tasks — runs ~2 weeks later to scan the digest output and produce a recommendation report. Mirrors the R8-Review one-shot pattern.

```bash
MSYS_NO_PATHCONV=1 schtasks /create /tn "\Edge-Radar\U2-Review" \
  /tr "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\maintenance\u2_2week_review.bat" \
  /sc once /sd 05/14/2026 /st 07:00 /f
```

**Verify + dry-run test:**
```bash
MSYS_NO_PATHCONV=1 schtasks /query /tn "\Edge-Radar\U2-Review"
# Run now (works any time — the script is read-only):
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\U2-Review"
# Output: reports/Performance/u2_2week_review_YYYY-MM-DD.md
```

The script spawns a `claude --dangerously-skip-permissions -p` subprocess for the code-review pass (same pattern as the email tasks). To skip that and get only the local firing-reliability scan, run directly with `--skip-claude`:

```bash
.venv/Scripts/python.exe scripts/schedulers/maintenance/u2_2week_review.py --skip-claude
```

---

## References

- [`../../CLAUDE.md`](../../CLAUDE.md) — Master instructions, risk gates, risk limits
- [`../../skills/edge-radar/SKILL.md`](../../skills/edge-radar/SKILL.md) — Unified scanner reference (`/edge-radar`)
- [`../setup/AUTOMATION_GUIDE.md`](../setup/AUTOMATION_GUIDE.md) — One-command installer for the minimal core tasks
- [`../../.env.example`](../../.env.example) — Every tunable, including `NOTIFY_EMAIL` / `AGENTMAIL_INBOX` for the email scripts

---

<p align="center">
  <a href="../README.md">Docs index</a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="../setup/AUTOMATION_GUIDE.md">Automation Guide</a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="../../CLAUDE.md">Risk gates</a>&nbsp;&nbsp;·&nbsp;&nbsp;<a href="#-edge-radar-scheduled-tasks">Back to top</a>
</p>
