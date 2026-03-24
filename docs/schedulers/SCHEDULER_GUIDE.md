# Scheduler Framework Guide

## Overview

The scheduler framework provides two types of automated pipelines:

1. **Execution schedulers** — scan a specific market on a recurring interval and optionally place bets
2. **Report schedulers** — scan multiple markets on a schedule and save a ranked report (no execution)

**Key design principles:**
- Each market gets its own scheduler with its own interval, filters, and bet limits
- DRY_RUN from `.env` is always respected — schedulers never bypass the safety gate
- Consecutive failures auto-pause the scheduler to prevent runaway losses
- All schedulers log to `logs/sched_{name}_{date}.log` or `logs/daily_sports_scan_{date}.log`

---

## Architecture

```
scripts/schedulers/
├── __init__.py
├── scheduler_config.py      # SchedulerProfile dataclass + env var loading
├── base_scheduler.py        # BaseScheduler class (safety, logging, lifecycle)
├── sports_scheduler.py      # SportsScheduler (edge_detector → executor)
├── prediction_scheduler.py  # PredictionScheduler (prediction_scanner → executor)
├── run_schedulers.py        # CLI entry point (launch one, all, or list)
└── daily_sports_scan.py     # Daily morning report (MLB, NBA, NHL, NFL)
```

**Inheritance (execution schedulers):**
```
BaseScheduler
├── SportsScheduler      ← NBA, NHL, MLB, NFL, NCAA, soccer
└── PredictionScheduler  ← crypto, weather, S&P 500
```

**Standalone (report schedulers):**
```
daily_sports_scan.py     ← 8 AM PST daily, top 25, saves report
```

---

## Configuration

Each scheduler is configured via `SCHED_{NAME}_*` environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `SCHED_{NAME}_ENABLED` | `false` | Must be `true` to launch |
| `SCHED_{NAME}_INTERVAL_MINUTES` | `15` | Minutes between pipeline runs |
| `SCHED_{NAME}_FILTERS` | (empty) | Comma-separated Kalshi series tickers or prediction categories |
| `SCHED_{NAME}_MAX_BETS` | `5` | Max bets to place per cycle |
| `SCHED_{NAME}_PREDICTION` | `false` | Set `true` for prediction market schedulers |

### Example .env configuration

```bash
# NBA — scan every 10 minutes during game nights
SCHED_NBA_ENABLED=true
SCHED_NBA_INTERVAL_MINUTES=10
SCHED_NBA_FILTERS=KXNBA
SCHED_NBA_MAX_BETS=3

# Crypto — scan every 30 minutes
SCHED_CRYPTO_ENABLED=true
SCHED_CRYPTO_INTERVAL_MINUTES=30
SCHED_CRYPTO_FILTERS=crypto
SCHED_CRYPTO_MAX_BETS=5
SCHED_CRYPTO_PREDICTION=true

# MLB — disabled until season starts
SCHED_MLB_ENABLED=false
SCHED_MLB_INTERVAL_MINUTES=15
SCHED_MLB_FILTERS=KXMLB
SCHED_MLB_MAX_BETS=3
```

---

## Usage

```bash
# List all registered schedulers and their current config
python scripts/schedulers/run_schedulers.py --list

# Launch all enabled schedulers (runs in foreground)
python scripts/schedulers/run_schedulers.py

# Launch a single scheduler
python scripts/schedulers/run_schedulers.py --only nba

# Ctrl+C to gracefully stop
```

---

## Daily Morning Scan

A standalone report scheduler that scans MLB, NBA, NHL, and NFL every morning and saves a ranked edge report. No bets are placed — this is a read-only scan for daily research.

### What it does

1. Scans all four major sports via `edge_detector.scan_all_markets()`
2. Combines opportunities across sports, sorted by edge descending
3. Takes the top N (default 25)
4. Generates a plain-text report with: edge, fair value, market price, confidence, team stats, sharp money signals, weather annotations
5. Saves to `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md`
6. Prints the report to console

### Usage

```bash
# Run once now (top 25)
python scripts/schedulers/daily_sports_scan.py

# Top 50 opportunities
python scripts/schedulers/daily_sports_scan.py --top 50

# Run as daemon — scans at 8:00 AM PST daily (auto-adjusts for DST)
python scripts/schedulers/daily_sports_scan.py --daemon
```

### Daemon mode

With `--daemon`, the script:
- Runs one scan immediately on startup
- Schedules recurring scans at 8:00 AM Pacific time via APScheduler's `CronTrigger`
- Handles DST automatically (uses `America/Los_Angeles` timezone)
- Runs in the foreground — Ctrl+C to stop

### Report format

```
================================================================================
  EDGE-RADAR DAILY MORNING SCAN
  Monday, March 23, 2026 — 08:00 AM PST
  Sports: NBA, NHL, MLB, NFL
  Top 25 opportunities by edge
================================================================================

  SUMMARY
  ----------------------------------------
    spread          12 opportunities
    game            8 opportunities
    total           5 opportunities

    #    Edge   Fair    Mkt  Conf    Side  Bet
  ---------------------------------------------------------------------------
    1  +15.2%   0.65   0.50  HIGH    YES   Lakers wins by over 3.5 Points? (vs Celtics)
                                           [56-15 (supports), sharp: home]
    2  +12.8%   0.72   0.59  MED     NO    Rangers at Bruins: Total Goals
                                           [weather: moderate wind (18 mph)]
  ...
```

### Output location

Reports are saved to:
```
reports/Sports/daily_edge_reports/
├── 2026-03-23_morning_scan.md
├── 2026-03-24_morning_scan.md
└── ...
```

---

## Safety Features

### DRY_RUN enforcement
The global `DRY_RUN` setting in `.env` is checked on every cycle. When `DRY_RUN=true`, the pipeline scans and logs opportunities but does not place orders. This cannot be overridden by scheduler config.

### Consecutive failure pause
If a scheduler fails 5 times in a row (API errors, auth failures, etc.), it automatically pauses and logs a `CRITICAL` message. The scheduler will not resume until manually restarted. This prevents burning through API rate limits or placing erratic bets during outages.

### Daily loss limit
The underlying `kalshi_executor.py` pipeline checks the daily P&L before every execution. If `MAX_DAILY_LOSS` is breached, all bets are rejected regardless of scheduler state.

### Position limits
`MAX_OPEN_POSITIONS` is enforced per execution cycle across all schedulers. No single scheduler can exceed the global portfolio limits.

---

## Adding a New Scheduler

1. **Add the name** to `SCHEDULER_NAMES` in `scheduler_config.py`:
   ```python
   SCHEDULER_NAMES = [
       "nba",
       "nhl",
       "mlb",
       ...
       "your_new_market",  # add here
   ]
   ```

2. **Add env vars** to `.env`:
   ```bash
   SCHED_YOUR_NEW_MARKET_ENABLED=true
   SCHED_YOUR_NEW_MARKET_INTERVAL_MINUTES=20
   SCHED_YOUR_NEW_MARKET_FILTERS=KXYOUR
   SCHED_YOUR_NEW_MARKET_MAX_BETS=3
   SCHED_YOUR_NEW_MARKET_PREDICTION=false
   ```

3. **If it needs custom pipeline logic**, create a new subclass of `BaseScheduler`:
   ```python
   # scripts/schedulers/my_custom_scheduler.py
   from base_scheduler import BaseScheduler

   class MyCustomScheduler(BaseScheduler):
       def run_pipeline(self) -> bool:
           # your custom logic here
           return True
   ```
   Then register it in `run_schedulers.py`'s `create_scheduler()` factory.

4. **If it uses the standard sports or prediction pipeline**, no new code is needed — just add the env vars. The `SportsScheduler` or `PredictionScheduler` handles it based on the `PREDICTION` flag.

---

## Logging

Each scheduler writes to its own log file:
```
logs/sched_nba_2026-03-23.log
logs/sched_crypto_2026-03-23.log
```

Log format: `timestamp | sched_name | level | message`

All pipeline activity (scans, opportunities found, bets placed, rejections) is captured at DEBUG level in the log file and INFO+ on console.

---

## Monitoring

Call `scheduler.status()` on any scheduler instance to get a health summary:
```python
{
    "name": "nba",
    "enabled": True,
    "paused": False,
    "dry_run": True,
    "total_runs": 12,
    "total_failures": 1,
    "consecutive_failures": 0,
    "interval_minutes": 10,
    "filters": ["KXNBA"],
    "max_bets": 3,
    "prediction": False,
}
```
