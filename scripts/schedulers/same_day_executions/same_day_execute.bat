@echo off
REM ============================================================================
REM  Same-Day Execute -- All Sports
REM
REM  Scans NFL, NBA, NHL, MLB together for today's games and EXECUTES the
REM  top 10 picks ranked by composite score across all sports.
REM
REM  Recommended run time: 8 AM ET (all markets posted, sportsbook lines sharp,
REM  Kalshi lag window open)
REM
REM  Unit size: $0.50 | Max bets: 5 total | Date: today
REM  All 9 risk gates enforced (Kelly sizing, per-event cap, concentration, etc.)
REM  Report saved to: reports\Sports\schedulers\same-day-executions
REM
REM  WARNING: This script places live orders. Verify DRY_RUN setting in .env.
REM ============================================================================

cd /d D:\AI_Agents\Specialized_Agents\Edge_Radar

echo ============================================================
echo  Edge-Radar Same-Day EXECUTE
echo  %date% %time%
echo ============================================================
echo.

echo --- Portfolio Status (Before) ---
.venv\Scripts\python.exe scripts\kalshi\kalshi_executor.py status
echo.

echo --- Scanning and Executing ---
.venv\Scripts\python.exe scripts\scan.py sports --unit-size .5 --max-bets 5 --date today --exclude-open --save --report-dir "reports\Sports\schedulers\same-day-executions" --execute
echo.

echo --- Portfolio Status (After) ---
.venv\Scripts\python.exe scripts\kalshi\kalshi_executor.py status
echo.

echo ============================================================
echo  Execution complete. Run 'make status' to verify positions.
echo ============================================================
