@echo off
REM ============================================================================
REM  Next-Day Execute -- All Sports
REM
REM  Scans NFL, NBA, NHL, MLB together for tomorrow's games and EXECUTES the
REM  top 10 picks ranked by composite score across all sports.
REM
REM  Note: Tomorrow's markets may not all be posted yet. For maximum coverage,
REM  prefer the same-day scripts run at 8 AM ET instead. Use this script when
REM  you want to lock in early lines the night before (recommended 9 PM ET).
REM
REM  Unit size: $0.50 | Max bets: 10 total | Date: tomorrow
REM  All 9 risk gates enforced (Kelly sizing, per-event cap, concentration, etc.)
REM  Report saved to: reports\Sports\schedulers\next-day-executions
REM
REM  WARNING: This script places live orders. Verify DRY_RUN setting in .env.
REM ============================================================================

cd /d D:\AI_Agents\Specialized_Agents\Edge_Radar

echo ============================================================
echo  Edge-Radar Next-Day EXECUTE
echo  %date% %time%
echo ============================================================
echo.

echo --- Portfolio Status (Before) ---
.venv\Scripts\python.exe scripts\kalshi\kalshi_executor.py status
echo.

echo --- Scanning and Executing ---
.venv\Scripts\python.exe scripts\scan.py sports --unit-size .5 --max-bets 10 --date tomorrow --exclude-open --save --report-dir "reports\Sports\schedulers\next-day-executions" --execute
echo.

echo --- Portfolio Status (After) ---
.venv\Scripts\python.exe scripts\kalshi\kalshi_executor.py status
echo.

echo ============================================================
echo  Execution complete. Run 'make status' to verify positions.
echo ============================================================
