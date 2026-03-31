---
name: project_daily_scan
description: Daily morning scan is live via Windows Task Scheduler at 8 AM local time
type: project
---

Daily morning sports scan is active as of 2026-03-23.

**What:** Scans MLB, NBA, NHL, NFL for top 25 opportunities by edge. Saves markdown report to `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md`.

**How:** Windows Task Scheduler under `Edge-Radar\DailyScan`. Runs at 8:00 AM local time daily.

**Manage:**
- `python scripts/schedulers/automation/install_windows_task.py status` — check task
- `python scripts/schedulers/automation/install_windows_task.py run` — trigger manually
- `python scripts/schedulers/automation/install_windows_task.py remove` — delete task
- `taskschd.msc` → Edge-Radar folder for GUI management
