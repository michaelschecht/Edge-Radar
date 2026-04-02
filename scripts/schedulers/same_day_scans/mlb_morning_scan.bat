@echo off
cd /d D:\AI_Agents\Specialized_Agents\Edge_Radar
.venv\Scripts\python.exe scripts\kalshi\edge_detector.py scan --filter mlb --unit-size .5 --max-bets 100 --date today --save --report-dir "reports\Sports\schedulers\same-day\mlb"