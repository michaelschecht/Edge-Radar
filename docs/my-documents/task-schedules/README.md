# Edge-Radar Scheduled Tasks

> **Windows Task Scheduler location:** `\Edge-Radar\`
> **Last updated:** 2026-04-22
> **Timezone:** All schedules in PST (system local time). ET shown in parentheses for reference.
>
> **Only active scheduling mechanism:** Windows Task Scheduler `\Edge-Radar\` folder. Legacy Claude Desktop email routines were consolidated here 2026-04-22 and deleted from the Claude Desktop UI. Any `SKILL.md` files remaining at `~/.claude/scheduled-tasks/` are stale filesystem artifacts, not active triggers.

---

## At a Glance — All Tasks

### Active (Ready)

| # | Task | Schedule (PST) | What it does |
|:-:|:-----|:---------------|:-------------|
| 1 | `All-Sports-SameDay-Execution` | Daily 5:05 AM | Scans NBA/NHL/MLB/NFL for **today's** games and places bets (`--date today`, budget 15%, max 7 bets) |
| 2 | `All-Sports-NoDateFilter-Execution` | **Mon + Thu** 5:20 AM | Scans all sports across **all dates** for multi-day edge (no `--date` filter, budget 15%, max 6 bets) |
| 3 | `Email-SameDay` | Daily 5:25 AM | Emails the same-day execution report to `mikeschecht@gmail.com` |
| 4 | `Email-NoDateFilter` | **Mon + Thu** 5:40 AM | Emails the weekly-broad execution report |
| 5 | `NextDay-Execute` | **Sun-Thu** 6:00 PM | Scans for **tomorrow's** games (`--date tomorrow`, budget 10%, max 6 bets) |
| 6 | `Email-NextDay` | **Sun-Thu** 6:20 PM | Emails the next-day execution report |
| 7 | `NightlySettle` | Daily 11:00 PM | Fetches settlement data from Kalshi API, updates trade log, calculates realized P&L |
| 8 | `Reconcile` | Daily 11:30 PM | Compares local trade log against Kalshi API positions, flags any drift |
| 9 | `Calibration` | **Sun** 7:00 PM | Weekly Brier-score refresh + calibration-curve report (`model_calibration.py --days 7`) |
| 10 | `Backtest` | **Sun** 7:30 PM | Weekly equity curve, drawdown, Sharpe, strategy-comparison report |

### Disabled (kept for reference, not running)

| # | Task | Prior Schedule | Why disabled |
|:-:|:-----|:---------------|:-------------|
| 11 | `All-Sports-SameDay-Scan` | Daily 4:55 AM | Preview-only variant of task #1; execution variant is what runs |
| 12 | `All-Sports-NoDateFilter-Scan` | Daily 9:00 AM | Preview-only variant of task #2 |
| 13 | `MLB-NextDay-Scan` | 6:00 PM | Per-sport scan; replaced by consolidated `NextDay-Execute` |
| 14 | `NBA-NextDay-Scan` | 6:05 PM | Per-sport; replaced |
| 15 | `NHL-NextDay-Scan` | 6:10 PM | Per-sport; replaced |
| 16 | `NFL-NextDay-Scan` | 6:15 PM | Per-sport; replaced |

### Daily Fire Sequence

```
 5:05 AM  Daily    ─ All-Sports-SameDay-Execution
 5:20 AM  Mon Thu  ─ All-Sports-NoDateFilter-Execution
 5:25 AM  Daily    ─ Email-SameDay
 5:40 AM  Mon Thu  ─ Email-NoDateFilter
 6:00 PM  Sun-Thu  ─ NextDay-Execute
 6:20 PM  Sun-Thu  ─ Email-NextDay
 7:00 PM  Sun      ─ Calibration
 7:30 PM  Sun      ─ Backtest
11:00 PM  Daily    ─ NightlySettle
11:30 PM  Daily    ─ Reconcile
```

### Fires-Per-Day Totals

| Day | Morning | Evening | Nightly | Day total |
|:----|:-------:|:-------:|:-------:|:---------:|
| Mon / Thu | 4 (same-day + weekly-broad + both emails) | 2 (NextDay + email) | 2 | **8** |
| Tue / Wed | 2 (same-day + email) | 2 | 2 | **6** |
| Fri / Sat | 2 (same-day + email) | 0 | 2 | **4** |
| Sun | 2 (same-day + email) | 4 (NextDay + email + Calibration + Backtest) | 2 | **8** |

---

## Overview

Edge-Radar runs 10 active scheduled tasks that form an end-to-end betting pipeline: scan → execute → email report → settle → reconcile → calibrate. Plus 6 disabled tasks kept for reference.

**Pipeline cadence:**

```
Morning  5:05 AM  ─ Same-day execute (today's games)
         5:20 AM  ─ Weekly broad execute (Mon + Thu only)
         5:25 AM  ─ Email same-day report
         5:40 AM  ─ Email weekly-broad report (Mon + Thu only)

Evening  6:00 PM  ─ Next-day execute (tomorrow's games, Sun-Thu)
         6:20 PM  ─ Email next-day report (Sun-Thu)
        11:00 PM  ─ Settle today's completed bets
        11:30 PM  ─ Reconcile local log vs Kalshi API

Weekly (Sun)
         7:00 PM  ─ Calibration report (7-day Brier score refresh)
         7:30 PM  ─ Backtest report (equity curve, strategy review)
```

---

## Active Tasks (State: Ready)

### 1. `All-Sports-SameDay-Execution` — Daily 5:05 AM PST (8:05 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\schedulers\same_day_executions\same_day_execute.bat` |
| **Flags** | `--unit-size .5 --max-bets 7 --min-bets 3 --budget 15% --date today --exclude-open` |
| **Purpose** | Places bets on today's games across NBA/NHL/MLB/NFL |
| **Report output** | `reports\Sports\schedulers\same-day-executions\YYYY-MM-DD_sports_execution.md` |
| **Max exposure** | 15% of bankroll / 7 bets |
| **Risk gates** | All 11 enforced (see `CLAUDE.md`) |

**Why 5:05 AM PST:** MLB starters announced, NHL morning skate behind us, weather forecasts stabilized, Kalshi liquidity building, before sharp money fully hits market. Sweet spot for lineup/weather/pitcher freshness.

---

### 2. `All-Sports-NoDateFilter-Execution` — Mon + Thu 5:20 AM PST (8:20 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Mon + Thu (DaysOfWeek bitmask 18) |
| **Script** | `scripts\schedulers\no_date_filter_executions\no_date_filter_execution.bat` |
| **Flags** | `--unit-size .5 --max-bets 6 --min-bets 3 --budget 15% --exclude-open` (no `--date`) |
| **Purpose** | Scans ALL available dates for edge across all sports, executes top picks |
| **Report output** | `reports\Sports\schedulers\no-date-filter-executions\YYYY-MM-DD_sports_execution.md` |
| **Max exposure** | 15% of bankroll / 6 bets |

**Why Mon + Thu 5:20 AM PST:**
- **Mon** — fresh weekend data processed, full weekly slate visible, NFL lines matured overnight
- **Thu** — catches weekend slate (Sat/Sun NFL) with fresher data than Monday
- **5:20 AM** — 15-min buffer after `All-Sports-SameDay-Execution` (5:05 AM); Gate 5 (already-holding) then blocks re-betting today's markets
- **Mon + Thu spacing** — clean vs. Gate 7 (series dedup 48hr); Thursday's weekend bets don't collide with Monday's Mon-Wed bets

**Edge-decay caveat:** This script bets on games up to 5-7 days out where signals degrade:
- MLB starter data: ~48hr horizon
- Weather: ~72hr horizon
- NBA/NHL lineups: ~24hr horizon

Mitigated by `--min-bets 3` floor (nothing fires if <3 opportunities meet threshold) and 15% budget cap.

---

### 3. `Email-SameDay` — Daily 5:25 AM PST (8:25 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Daily |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\SameDay-Execution-Report.sh` |
| **Invocation** | `"C:\Program Files\Git\bin\bash.exe" "<script>.sh"` |
| **Purpose** | Reads today's same-day execution report, emails to `mikeschecht@gmail.com` |
| **Email subject** | `Edge-Radar | Same Day Execution Report` |
| **From inbox** | `braveselection583@agentmail.to` |

**Mechanism:** Shell script spawns `claude --dangerously-skip-permissions -p "..."` subprocess. The inner Claude invocation uses the `agentmail` skill to send a dark-themed HTML email with per-order cards.

**Behavior if no report:** If no report exists for today's date, the subprocess reports the most recent available and does NOT send an email (correct behavior — prevents stale emails).

**20-min buffer from 5:05 execute:** Ensures execute completes (3-8 min typical) and writes report before email fires.

---

### 4. `Email-NoDateFilter` — Mon + Thu 5:40 AM PST (8:40 AM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Mon + Thu |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\NoDateFilter-Execution-Report.sh` |
| **Invocation** | `"C:\Program Files\Git\bin\bash.exe" "<script>.sh"` |
| **Purpose** | Emails the weekly-broad execution report |
| **Email subject** | `Edge-Radar | NoDateFilter Execution Report` |

**20-min buffer from 5:20 execute:** Same pattern as Email-SameDay.

---

### 5. `NextDay-Execute` — Sun-Thu 6:00 PM PST (9:00 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun, Mon, Tue, Wed, Thu |
| **Script** | `scripts\schedulers\next_day_executions\next_day_execute.bat` |
| **Flags** | `--unit-size .5 --max-bets 6 --min-bets 3 --budget 10% --date tomorrow --exclude-open` |
| **Purpose** | Locks in early lines for tomorrow's games (catches openers) |
| **Report output** | `reports\Sports\schedulers\next-day-executions\YYYY-MM-DD_sports_execution.md` |
| **Max exposure** | 10% of bankroll / 6 bets (smaller than same-day since less info) |

**Why Sun-Thu 6:00 PM PST (9:00 PM ET):**
- Tomorrow's markets posted by evening
- Early lines = softer before sharp money
- Sun-Thu only — Fri + Sat skipped so the Sunday-morning 5:05 AM run handles Sunday NFL instead (fresher data)

---

### 6. `Email-NextDay` — Sun-Thu 6:20 PM PST (9:20 PM ET)

| Property | Value |
|:---------|:------|
| **Schedule** | Weekly Sun, Mon, Tue, Wed, Thu |
| **Script** | `scripts\custom\Shell-Scripts\Run-Reports\NextDay-Edge-Report.sh` |
| **Purpose** | Emails the next-day execution report |
| **Email subject** | `Edge-Radar | Next-Day Edge Report` |

---

### 7. `NightlySettle` — Daily 11:00 PM PST (2:00 AM ET next day)

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

### 8. `Reconcile` — Daily 11:30 PM PST (2:30 AM ET next day)

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

### 9. `Calibration` — Sun 7:00 PM PST (10:00 PM ET)

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

### 10. `Backtest` — Sun 7:30 PM PST (10:30 PM ET)

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

## Disabled Tasks (retained for reference)

These remain in `\Edge-Radar\` but are not enabled. They were part of prior experiments or replaced by consolidated equivalents.

| Task | Script | Why disabled |
|:-----|:-------|:-------------|
| `All-Sports-NoDateFilter-Scan` | `no_date_filter_scan.bat` | Scan-only variant; execution variant is what runs |
| `All-Sports-SameDay-Scan` | `same_day_scan.bat` | Scan-only variant; execution variant is what runs |
| `MLB-NextDay-Scan` | `mlb_morning_scan.bat` | Per-sport variant; replaced by consolidated `NextDay-Execute` |
| `NBA-NextDay-Scan` | `nba_morning_scan.bat` | Per-sport variant; replaced |
| `NFL-NextDay-Scan` | `nfl_morning_scan.bat` | Per-sport variant; replaced |
| `NHL-NextDay-Scan` | `nhl_morning_scan.bat` | Per-sport variant; replaced |

Keep these in place — useful reference for how to structure per-sport scans if that pattern is ever needed again.

---

## Daily / Weekly Timeline

### A typical Monday
```
05:05 AM  All-Sports-SameDay-Execution  → bets today's NBA/MLB/NHL games
05:20 AM  All-Sports-NoDateFilter-Exec  → bets week-horizon + futures
05:25 AM  Email-SameDay                 → email same-day report
05:40 AM  Email-NoDateFilter            → email weekly-broad report
06:00 PM  NextDay-Execute               → bets tomorrow's games
06:20 PM  Email-NextDay                 → email next-day report
11:00 PM  NightlySettle                 → settle today's completed bets
11:30 PM  Reconcile                     → verify local vs API
```

### A typical Thursday
```
Same as Monday — Thursday is the other weekly-broad day
```

### A typical Tue/Wed
```
05:05 AM  All-Sports-SameDay-Execution
05:25 AM  Email-SameDay
06:00 PM  NextDay-Execute
06:20 PM  Email-NextDay
11:00 PM  NightlySettle
11:30 PM  Reconcile
```

### A typical Sunday
```
05:05 AM  All-Sports-SameDay-Execution  (Sunday's NBA/MLB/NFL)
05:25 AM  Email-SameDay
06:00 PM  NextDay-Execute               (Monday's games — fresh enough)
06:20 PM  Email-NextDay
07:00 PM  Calibration                   (weekly Brier refresh)
07:30 PM  Backtest                      (weekly strategy review)
11:00 PM  NightlySettle
11:30 PM  Reconcile
```

### A typical Fri/Sat
```
05:05 AM  All-Sports-SameDay-Execution
05:25 AM  Email-SameDay
          (NextDay-Execute skipped — Sunday morning run will handle Sunday NFL)
11:00 PM  NightlySettle
11:30 PM  Reconcile
```

---

## Daily Bet Count Estimate

| Day | Max new bets | Notes |
|:----|:-------------|:------|
| Mon / Thu | **7 (same-day) + 6 (weekly-broad) + 6 (next-day) = 19** | Gate 7 series dedup + `--exclude-open` reduce practical count |
| Tue / Wed | **7 + 6 = 13** | |
| Fri / Sat | **7** | |
| Sun | **7 + 6 = 13** | |

Hard ceiling: Gate 2 (max open positions = 50) prevents runaway accumulation. Settle at 11 PM clears ~50% of opens each night.

---

## Manual Trigger Commands

Run any task immediately via Git Bash (prepend `MSYS_NO_PATHCONV=1` to prevent path translation):

```bash
# Betting execute tasks
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\All-Sports-SameDay-Execution"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\All-Sports-NoDateFilter-Execution"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\NextDay-Execute"

# Email tasks
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-SameDay"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-NoDateFilter"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Email-NextDay"

# Maintenance
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\NightlySettle"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Reconcile"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Calibration"
MSYS_NO_PATHCONV=1 schtasks /run /tn "\Edge-Radar\Backtest"
```

From PowerShell (no prefix needed):

```powershell
Start-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'NextDay-Execute'
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
Disable-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'NextDay-Execute'
```

### Enable a task
```powershell
Enable-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'NextDay-Execute'
```

### View full task definition (XML)
```powershell
Export-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'NextDay-Execute'
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

**Note:** `NightlySettle` was already set up previously with direct python invocation (not using `settle.bat`) and kept that way. The wrapper exists for manual invocation convenience.

---

## Troubleshooting

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
   | 5 | `NextDay-Execute` | Would place bets but dry-run blocks |
   | 6 | `All-Sports-NoDateFilter-Execution` | Biggest unknown, the new weekly broad |
   | 7 | `Email-SameDay` | Verify email pickup of existing report |
   | 8 | `Email-NoDateFilter`, `Email-NextDay` | Verify email pickup after executes produce reports |

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
│   └── 2026-04-22_sports_execution.md    ← Daily 5:05 AM
├── no-date-filter-executions/
│   └── 2026-04-22_sports_execution.md    ← Mon + Thu 5:20 AM
└── next-day-executions/
    └── 2026-04-22_sports_execution.md    ← Sun-Thu 6:00 PM

reports/
├── calibration/
│   └── 2026-04-26_calibration.md         ← Sun 7:00 PM
└── backtest/
    └── 2026-04-26_backtest.md            ← Sun 7:30 PM

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
Email sent from braveselection583@agentmail.to → mikeschecht@gmail.com
         ↓
Subject: "Edge-Radar | <Mode> Execution Report"
```

**Why 20-min buffer:** Execute tasks typically run 3-8 minutes but MLB parallel pitcher fetches can occasionally stretch to 15 min on slow API days. 20 min is a safe margin.

**If execute fails or produces no report:** Email task correctly detects missing report for today's date and skips sending (no stale emails).

---

## References

- `CLAUDE.md` — Master instructions, 11 risk gates, risk limits
- `.claude/skills/edge-radar/SKILL.md` — Unified scanner reference
- `docs/my-documents/betting-recommendations/weekly-schedule-recommendation.md` — Decision rationale for this schedule
- `docs/setup/AUTOMATION_GUIDE.md` — Original automation walkthrough
- Memory: `project_scheduled_tasks.md` — Short-form reference
