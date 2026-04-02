@echo off
REM ============================================================================
REM  Next-Day Scan (Preview Only) -- All Sports
REM
REM  Scans NFL, NBA, NHL, MLB together for tomorrow's games. Ranks the best
REM  opportunities across all sports and shows the top 10. Saves report but
REM  does NOT place any bets.
REM
REM  Note: Tomorrow's markets may not all be posted yet. For maximum coverage,
REM  prefer the same-day scripts run at 8 AM ET instead. Use this script when
REM  you want to lock in early lines the night before (recommended 9 PM ET).
REM
REM  Unit size: $0.50 | Max bets: 10 total | Date: tomorrow
REM  Report saved to: reports\Sports\schedulers\next-day-executions
REM ============================================================================

cd /d D:\AI_Agents\Specialized_Agents\Edge_Radar

echo ============================================================
echo  Edge-Radar Next-Day Scan (Preview Only)
echo  %date% %time%
echo ============================================================
echo.

.venv\Scripts\python.exe scripts\scan.py sports --unit-size .5 --max-bets 10 --date tomorrow --exclude-open --save --report-dir "reports\Sports\schedulers\next-day-executions"

echo.
echo ============================================================
echo  Scan complete. Review report before running execute script.
echo ============================================================
