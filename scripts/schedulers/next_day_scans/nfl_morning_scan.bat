@echo off
cd /d D:\AI_Agents\Specialized_Agents\Edge_Radar
.venv\Scripts\python.exe scripts\kalshi\edge_detector.py scan --filter nfl --unit-size .5 --max-bets 100 --date tomorrow --save --report-dir "reports\Sports\schedulers\next-day\nfl"