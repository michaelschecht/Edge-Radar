# Morning Routine

Full morning startup: check portfolio, settle overnight bets, then scan for today's opportunities across all markets.

```
# 1. Portfolio state
python scripts/kalshi/kalshi_executor.py status

# 2. Settle anything that resolved overnight
python scripts/kalshi/kalshi_settler.py settle

# 3. Check risk limits
python scripts/kalshi/risk_check.py --report limits

# 4. Scan today's sports
python scripts/scan.py sports --min-edge 0.03 --top 15 --date today --exclude-open

# 5. Scan predictions
python scripts/scan.py prediction --min-edge 0.03 --top 10

# 6. Check futures (weekly, not daily)
python scripts/scan.py futures --min-edge 0.01 --top 10
```

Give me a morning brief:
- **Overnight**: what settled, net P&L
- **Portfolio**: balance, open positions, risk room remaining
- **Today's sports**: top 3-5 picks across all sports
- **Predictions**: any crypto/weather/SPX edge worth taking?
- **Action plan**: where should I focus today?
