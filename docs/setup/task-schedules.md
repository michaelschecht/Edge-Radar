# Scheduled-Task Reference & Setup

A reproducible blueprint for the full Edge-Radar automation pipeline: a set of Windows Task Scheduler jobs that **scan → execute → email a report → settle → reconcile → calibrate → review**, end to end, with no manual intervention.

This is the *complete* roster. If you just want the minimal "execute + settle + calibration" setup, start with **[`AUTOMATION_GUIDE.md`](AUTOMATION_GUIDE.md)** and its one-command installer (`install_windows_task.py`), then come back here when you want the email reports, the midday/late runs, or the weekly analytics.

> **Why this lives in docs instead of shipping the scripts:** the author's actual `.bat`/`.sh` files and personal task-schedule notes are gitignored — they hardcode an absolute machine path, a personal email, and a private agentmail inbox. Rather than leak those, this guide carries **sanitized templates inline** so you can recreate the equivalents on your own machine. Everything you need is below.

---

## Placeholders used throughout

Substitute these everywhere they appear:

| Placeholder | Meaning | Example |
|:--|:--|:--|
| `<REPO_ROOT>` | Absolute path to your Edge-Radar checkout | `C:\Users\you\Edge-Radar` |
| `<YOUR_EMAIL>` | Inbox you want reports delivered **to** | `you@example.com` |
| `<YOUR_AGENTMAIL_INBOX>` | agentmail.to address reports are sent **from** | `yourinbox@agentmail.to` |
| `<GIT_BASH>` | Path to `bash.exe` from Git for Windows | `C:\Program Files\Git\bin\bash.exe` |

`<YOUR_EMAIL>` and `<YOUR_AGENTMAIL_INBOX>` have homes in `.env` (`NOTIFY_EMAIL`, `AGENTMAIL_INBOX`) — see [`.env.example`](../../.env.example). The email templates below read them from there.

> **Time zone:** all schedule times below are the author's local PST, with ET in parentheses for reference. Task Scheduler always fires on **your** machine's local time — pick times that make sense where you are, not these literal values.

---

## At a Glance — the full roster

A complete daily/weekly pipeline is ~17 tasks. You do **not** need all of them — the table marks a suggested **minimal** core. Add the rest as you want more coverage.

| # | Task | Schedule (local) | Core? | What it does |
|:-:|:-----|:-----------------|:-----:|:-------------|
| 0a | `Daily-Summary` | Daily 4:50 AM | | Morning P&L digest (yesterday settled + open exposure + today pending + 7-day context) |
| 0b | `Email-Daily-Summary` | Daily 5:00 AM | | Emails the daily-summary digest |
| 1 | `All-Sports-SameDay-Execution` | Daily 5:05 AM | ✅ | Scans NBA/NHL/MLB/NFL for **today's** games and places bets (`--date today`) |
| 2 | `Email-SameDay` | Daily 5:25 AM | | Emails the same-day execution report |
| 3 | `All-Sports-NoDateFilter-Midday-Execution` | Daily 11:00 AM | | Midday wide-net scan, no date filter — catches confirmed starters & sharp moves |
| 4 | `Email-NoDateFilter-Midday` | Daily 11:20 AM | | Emails the midday report |
| 5 | `All-Sports-SameDay-Late-Execution` | Daily 2:00 PM | | Late same-day scan — late scratches, goalie confirmations, weather |
| 6 | `Email-SameDay-Late` | Daily 2:20 PM | | Emails the late same-day report |
| 7 | `All-Sports-NextDay-Execution` | Sun–Thu 8:30 PM | | Scans **tomorrow's** games (`--date tomorrow`) — early lines |
| 8 | `Email-NextDay` | Sun–Thu 8:50 PM | | Emails the next-day report |
| 9 | `NightlySettle` | Daily 11:00 PM | ✅ | Fetches settlements from Kalshi, updates trade log, realized P&L |
| 10 | `Reconcile` | Daily 11:30 PM | | Compares local trade log vs Kalshi positions, flags drift |
| 11 | `Calibration` | Sun 7:00 PM | | Weekly Brier-score + calibration-curve report (`--days 7`) |
| 12 | `Backtest` | Sun 7:30 PM | | Weekly equity curve, drawdown, Sharpe, strategy comparison |
| 13 | `Weekly-Analysis` | Sun 11:45 PM | | End-of-week 7-day `betting_analysis.py` (full breakdown) |
| 14 | `Email-Weekly-Analysis` | Sun 11:55 PM | | Emails the weekly analysis report |
| 15 | `MonthlyCalibration` | 1st of month 2:00 AM | | 30-day Brier refresh — catches slow drift the weekly run can't |

**Minimal viable automation** = tasks **1 + 9** (execute today's games, settle them at night). Add `MonthlyCalibration` for model health, then layer in emails and the midday/late/next-day runs as you trust the pipeline.

### Daily fire sequence (author's schedule, for reference)

```
 2:00 AM  1st      ─ MonthlyCalibration    (30-day calibration refresh, monthly)
 4:50 AM  Daily    ─ Daily-Summary         (yesterday P&L + exposure digest)
 5:00 AM  Daily    ─ Email-Daily-Summary
 5:05 AM  Daily    ─ All-Sports-SameDay-Execution
 5:25 AM  Daily    ─ Email-SameDay
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
11:45 PM  Sun      ─ Weekly-Analysis
11:55 PM  Sun      ─ Email-Weekly-Analysis
```

The recurring design principle: an **execute** task writes a dated report, then an **email** task fires ~20 min later to send it. Settlement runs late (after west-coast games finish); reconcile follows settlement; the weekly analytics run after the last settle of the week.

---

## How a task is wired

Each scheduled task points at one of two things:

1. **A `.bat` wrapper** (for the scan/execute/maintenance jobs) — sets the working directory + venv python, then runs the Python entry point.
2. **A `bash.exe` invocation of a `.sh` script** (for the email jobs) — spawns a headless `claude -p` that reads the report and sends a formatted email via the `agentmail` skill.

You recreate these two file types from the templates below, drop them anywhere under your checkout (the author keeps `.bat` wrappers in `scripts/schedulers/…` and email scripts in `scripts/custom/Shell-Scripts/Run-Reports/` — both gitignored), then register each with `schtasks`.

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

Settlement, reconcile, calibration, backtest, weekly-analysis, and daily-summary are all the same one-line pattern — just a different Python entry point:

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

> Point the report folder + subject line at whichever execute task this emailer pairs with (`no-date-filter-midday-executions`, `same-day-late-executions`, `next-day-executions`, or `reports/Performance` for the digest/weekly jobs). The "don't send if missing" instruction is what keeps a failed execute from producing a stale email.

---

## Registering the tasks

All tasks live in a `\Edge-Radar\` Task Scheduler folder. Two `schtasks` shapes cover everything.

### A `.bat`-backed task (scan/execute/maintenance)

```powershell
schtasks /Create /TN "\Edge-Radar\All-Sports-SameDay-Execution" `
  /TR "<REPO_ROOT>\scripts\schedulers\same_day_executions\same_day_execute.bat" `
  /SC DAILY /ST 05:05 /F
```

### An email task (bash + `.sh`, path has spaces → escaped quotes)

```powershell
schtasks /Create /TN "\Edge-Radar\Email-SameDay" `
  /TR "\"<GIT_BASH>\" \"<REPO_ROOT>\scripts\custom\Shell-Scripts\Run-Reports\SameDay-Execution-Report.sh\"" `
  /SC DAILY /ST 05:25 /F
```

### Schedule shapes you'll need

| Cadence | `schtasks` flags |
|:--|:--|
| Every day | `/SC DAILY /ST HH:MM` |
| Sun–Thu only | `/SC WEEKLY /D SUN,MON,TUE,WED,THU /ST HH:MM` |
| Sundays | `/SC WEEKLY /D SUN /ST HH:MM` |
| 1st of each month | `/SC MONTHLY /D 1 /ST HH:MM` |

Settle uses direct python (no wrapper needed) if you prefer:

```powershell
schtasks /Create /TN "\Edge-Radar\NightlySettle" `
  /TR "<REPO_ROOT>\.venv\Scripts\python.exe <REPO_ROOT>\scripts\kalshi\kalshi_settler.py settle" `
  /SC DAILY /ST 23:00 /F
```

> **Doing this from Git Bash instead of PowerShell?** Prefix every `schtasks` call with `MSYS_NO_PATHCONV=1` or Git Bash mangles the `/TN` path into a filesystem path. See [Gotchas](#gotchas).

---

## Managing tasks

```powershell
# List everything in the folder + state
Get-ScheduledTask -TaskPath '\Edge-Radar\' | Select-Object TaskName, State | Format-Table

# Next run time + last result (0 = success)
Get-ScheduledTask -TaskPath '\Edge-Radar\' | ForEach-Object {
  $i = Get-ScheduledTaskInfo -TaskName $_.TaskName -TaskPath $_.TaskPath
  [PSCustomObject]@{ Name=$_.TaskName; State=$_.State; NextRun=$i.NextRunTime; LastRun=$i.LastRunTime; LastResult=$i.LastTaskResult }
} | Sort-Object NextRun | Format-Table -AutoSize

# Trigger one immediately (test)
Start-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'All-Sports-SameDay-Execution'

# Disable / enable without deleting
Disable-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'All-Sports-NextDay-Execution'
Enable-ScheduledTask  -TaskPath '\Edge-Radar\' -TaskName 'All-Sports-NextDay-Execution'

# Delete
Unregister-ScheduledTask -TaskPath '\Edge-Radar\' -TaskName 'TaskName' -Confirm:$false
```

---

## Dry-run before you go live

**Do this before any execute task can place real money.**

1. Set `DRY_RUN=true` in `.env`.
2. Test in safest-first order — read-only jobs, then writers, then execute, then email:

   | Order | Task | Why it's safe |
   |:-:|:--|:--|
   | 1 | `Reconcile` | Read-only |
   | 2 | `Calibration` / `Backtest` | Read-only report generators |
   | 3 | `NightlySettle` | Writes local files, no external bets |
   | 4 | an execute task | Would place bets, but `DRY_RUN=true` blocks them |
   | 5 | an email task | Verifies email pickup of an existing report |

3. Trigger manually with `Start-ScheduledTask` (above) and verify:
   - **Execute:** a report file appears under `reports/Sports/schedulers/<mode>/`, **no** positions opened, exit code 0.
   - **Email:** the message arrives, HTML renders, contents match the report file.
   - **Settle/Reconcile:** no errors, no drift.
4. Flip `DRY_RUN=false` only when all of the above check out.

---

## Gotchas

**Git Bash mangles `schtasks` paths.** Git Bash rewrites `/TN` into a Windows path. Prefix with `MSYS_NO_PATHCONV=1`:

```bash
# WRONG (Git Bash) → "Invalid argument/option - 'C:/Program Files/Git/create'"
schtasks /create /tn "\Edge-Radar\Foo" ...
# CORRECT
MSYS_NO_PATHCONV=1 schtasks /create /tn "\Edge-Radar\Foo" ...
```

**Folder targeting.** Prefix the task name with `\Edge-Radar\` or it lands in the root `\` folder.

**Email script needs the bash.exe wrapper + escaped quotes** (the path has spaces):

```
/TR "\"<GIT_BASH>\" \"<REPO_ROOT>\...\SameDay-Execution-Report.sh\""
```

**Exit codes you'll see:**

| Code | Hex | Meaning |
|:--|:--|:--|
| 0 | — | Success (an email task can exit 0 *and skip sending* if no report for today exists — that's correct behavior) |
| 127 | `0x7F` | `bash: No such file or directory` — wrong `.sh` path in the task |
| 267009 | `0x41301` | Still running (email tasks take 30–120 s for the claude subprocess) |
| 267011 | `0x41303` | Never run yet — normal for a freshly created task |
| 1 | `0x1` | Script ran but errored — run the `.bat`/`.sh` manually to see output; check `logs/` |

**Days-of-week bitmask** (when reading triggers back via PowerShell): Sun=1, Mon=2, Tue=4, Wed=8, Thu=16, Fri=32, Sat=64. So `DaysOfWeek = 18` = Mon + Thu.

---

## References

- [`AUTOMATION_GUIDE.md`](AUTOMATION_GUIDE.md) — one-command installer (`install_windows_task.py`) for the core scan/execute/settle/calibration tasks; flag reference; timing rationale.
- [`../../.env.example`](../../.env.example) — every tunable, including `NOTIFY_EMAIL` / `AGENTMAIL_INBOX` for the email scripts.
- `CLAUDE.md` (repo root) — the risk gates enforced on every automated run.
- `scripts/schedulers/automation/install_windows_task.py` — the portable installer the quick-setup guide drives.
