# Automated Betting with Windows Task Scheduler

Set up Edge-Radar to scan for edges and place bets automatically on a daily schedule — no manual intervention required.

---

## How It Works

Edge-Radar includes pre-built `.bat` scripts that scan all sports, rank opportunities by composite score, and optionally execute bets through the Kalshi API. Windows Task Scheduler runs these scripts at the times you choose.

```
  8:00 AM ET ──> same_day_execute.bat ──> Scan + Execute today's games
  9:00 PM ET ──> next_day_execute.bat ──> Scan + Execute tomorrow's games (optional)
 11:00 PM ET ──> kalshi_settler.py    ──> Settle completed bets + update P&L
```

All risk gates are enforced on every automated run (see `CLAUDE.md` §"Execution Gates"). If the daily loss limit is hit, no new bets are placed.

---

## Prerequisites

Before setting up automation, make sure:

1. **Edge-Radar is installed and working** — run `python scripts/doctor.py` to verify
2. **You can run a scan manually** — `python scripts/scan.py sports --filter mlb`
3. **Your `.env` file is configured** with Kalshi credentials and Odds API keys
4. **`DRY_RUN=false`** in `.env` (otherwise automated execution won't place real orders)
5. **`KELLY_FRACTION`** is set to your preferred level in `.env` (default: 0.25)

---

## Quick Setup (Recommended)

The installer script creates Windows Scheduled Tasks for you:

```powershell
cd D:\AI_Agents\Specialized_Agents\Edge_Radar

# Install all four tasks at once
python scripts/schedulers/automation/install_windows_task.py install all

# Or install specific tasks
python scripts/schedulers/automation/install_windows_task.py install execute   # Morning execution
python scripts/schedulers/automation/install_windows_task.py install settle    # Nightly settlement
```

### Available Task Profiles

| Profile | Schedule | What It Does |
|---------|----------|-------------|
| `scan` | 8:00 AM daily | Preview scan — saves report, no bets placed |
| `execute` | 8:00 AM daily | Scan + execute — places live orders |
| `settle` | 11:00 PM daily | Settle completed bets, update trade log P&L |
| `next-day` | 9:00 PM daily | Scan + execute tomorrow's games (early lines) |

### Recommended Setup

For most users, install **execute** + **settle**:

```powershell
python scripts/schedulers/automation/install_windows_task.py install execute
python scripts/schedulers/automation/install_windows_task.py install settle
```

This gives you:
- **8 AM**: Scan all sports, execute top picks with Kelly sizing
- **11 PM**: Settle completed bets, update P&L records

### Managing Tasks

```powershell
# Check which tasks are installed and their status
python scripts/schedulers/automation/install_windows_task.py status

# Trigger a task immediately (test it)
python scripts/schedulers/automation/install_windows_task.py run execute

# Remove a specific task
python scripts/schedulers/automation/install_windows_task.py remove execute

# Remove all tasks
python scripts/schedulers/automation/install_windows_task.py remove all
```

You can also manage tasks in the GUI: open **Task Scheduler** (`taskschd.msc`) and look under the `Edge-Radar` folder.

---

## Manual Setup (Alternative)

If you prefer to create tasks manually via `schtasks`:

### Morning Execution (8 AM)

```powershell
schtasks /Create /TN "Edge-Radar\MorningExecute" /TR "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\same_day_executions\same_day_execute.bat" /SC DAILY /ST 08:00
```

### Nightly Settlement (11 PM)

```powershell
schtasks /Create /TN "Edge-Radar\NightlySettle" /TR "D:\AI_Agents\Specialized_Agents\Edge_Radar\.venv\Scripts\python.exe D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_settler.py settle" /SC DAILY /ST 23:00
```

### Next-Day Execution (9 PM, optional)

```powershell
schtasks /Create /TN "Edge-Radar\NextDayExecute" /TR "D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\schedulers\next_day_executions\next_day_execute.bat" /SC DAILY /ST 21:00
```

---

## What Each Script Does

### same_day_execute.bat

1. Shows portfolio status (before)
2. Scans all sports for today's games (`--date today`)
3. Excludes markets where you already have a position (`--exclude-open`)
4. Applies all risk gates + batch-aware Kelly sizing
5. Executes top picks via Kalshi API
6. Saves execution report to `reports/Sports/schedulers/same-day-executions/`
7. Shows portfolio status (after)

### same_day_scan.bat

Same as above, but **preview only** — no orders placed. Use this to review opportunities before committing to automated execution.

### next_day_execute.bat

Same as `same_day_execute.bat` but targets `--date tomorrow`. Useful for locking in early lines the night before. Note: not all tomorrow's markets may be posted yet.

### Settlement

Runs `kalshi_settler.py settle` which:
1. Checks all unsettled trades against Kalshi's settlement API
2. Calculates realized P&L for each settled trade
3. Captures closing line value (CLV) for model validation
4. Updates the trade log and settlement log

---

## Customizing the Scripts

The `.bat` scripts are in `scripts/schedulers/`. Key flags you might want to change:

| Flag | Default | What It Controls |
|------|---------|-----------------|
| `--unit-size` | `0.50` | Minimum dollar amount per bet (Kelly floor) |
| `--max-bets` | `5` (execute) / `10` (scan) | Maximum bets per run |
| `--date` | `today` or `tomorrow` | Which day's games to scan |
| `--exclude-open` | on | Skip markets with existing positions |
| `--filter` | *(all sports)* | Restrict to specific sports (e.g., `mlb`) |

### Example: MLB-only execution with larger sizing

Edit `same_day_execute.bat` and change the scan line:

```batch
.venv\Scripts\python.exe scripts\scan.py sports --filter mlb --unit-size 1 --max-bets 5 --date today --exclude-open --save --execute
```

### Key .env Settings for Automation

| Variable | Recommended | Purpose |
|----------|-------------|---------|
| `DRY_RUN` | `false` | Must be `false` for live execution |
| `KELLY_FRACTION` | `0.25` - `0.75` | Kelly sizing aggressiveness (divided by batch size at runtime) |
| `MAX_BET_SIZE` | `100` | Hard cap in USD for any single bet |
| `MAX_DAILY_LOSS` | `250` | Hard stop — no new bets after this daily loss |
| `MAX_OPEN_POSITIONS` | `10` - `50` | Maximum concurrent positions |
| `MAX_PER_EVENT` | `2` | Max positions on the same game |
| `MAX_BET_RATIO` | `3.0` | Max single bet as multiple of batch median cost |

---

## Timing Recommendations

| Time | Why |
|------|-----|
| **8:00 AM ET** | All major sports markets posted. Sportsbook lines sharpened overnight. Kalshi prices typically lag — this is where edge appears. |
| **9:00 PM ET** | Tomorrow's early lines available for MLB/NBA. Good for locking in value before overnight adjustments. |
| **11:00 PM ET** | Most games settled by this time. Settlement captures closing prices for CLV tracking. |

> **Important:** Task Scheduler uses your local time zone. If you're not in ET, adjust the times accordingly. The installer defaults can be customized by editing the script or creating tasks manually.

---

## Monitoring

After automation is running:

```powershell
# Check task status and last run results
python scripts/schedulers/automation/install_windows_task.py status

# Review today's trades
python scripts/kalshi/kalshi_executor.py status

# Full P&L report
python scripts/kalshi/kalshi_settler.py report --detail

# Risk dashboard
python scripts/kalshi/risk_check.py
```

Reports are saved automatically to `reports/Sports/schedulers/` on each run.

---

## Troubleshooting

### Task runs but no bets are placed
- Check `DRY_RUN` in `.env` — must be `false`
- Check `MIN_COMPOSITE_SCORE` — if set too high, opportunities are filtered out
- Run `python scripts/doctor.py` to verify API connectivity

### Task fails to run
- Open Task Scheduler GUI (`taskschd.msc`) and check the task's "Last Run Result"
- Common issue: the `.venv` path changed — reinstall the task
- Verify the project path hasn't moved

### Task shows "0x1" result
- The script ran but encountered an error
- Check `logs/` for error details
- Run the bat script manually in a terminal to see the full output

### Odds API rate limit
- The free tier allows 500 requests/month
- With 3 API keys configured, you get 1,500 requests/month
- Each scan uses ~3 requests per sport
- At 4 sports × 1 scan/day × 30 days = ~360 requests/month — well within limits
