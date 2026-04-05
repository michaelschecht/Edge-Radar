@echo off
REM ============================================================================
REM  Monthly Account Report
REM
REM  Settles any completed markets, then generates a detailed P&L report
REM  covering the last 30 days plus a current portfolio risk snapshot.
REM
REM  Recommended schedule: 1st of each month at 9 AM ET
REM  Reports saved to: reports\Accounts\Kalshi\monthly\
REM ============================================================================

cd /d D:\AI_Agents\Specialized_Agents\Edge_Radar

echo ============================================================
echo  Edge-Radar Monthly Account Report
echo  %date% %time%
echo ============================================================
echo.

REM Step 1: Settle any completed markets first
echo [1/3] Settling completed markets...
.venv\Scripts\python.exe scripts\kalshi\kalshi_settler.py settle
echo.

REM Step 2: P&L report for the last 30 days (with per-trade detail)
echo [2/3] Generating monthly P&L report (last 30 days)...
.venv\Scripts\python.exe scripts\kalshi\kalshi_settler.py report --detail --days 30 --save
echo.

REM Step 3: Current portfolio risk snapshot
echo [3/3] Generating portfolio risk snapshot...
.venv\Scripts\python.exe scripts\kalshi\risk_check.py --report all --save
echo.

echo ============================================================
echo  Monthly report complete. Check reports\Accounts\Kalshi\
echo ============================================================
