# End of Day Review

Close out the day: settle bets, review performance, and plan for tomorrow.

```
# 1. Settle completed bets
python scripts/kalshi/kalshi_settler.py settle

# 2. Reconcile trade log vs API
python scripts/kalshi/kalshi_settler.py reconcile

# 3. Full P&L report
python scripts/kalshi/kalshi_settler.py report --detail --save

# 4. Portfolio state
python scripts/kalshi/kalshi_executor.py status --save

# 5. Risk dashboard snapshot
python scripts/kalshi/risk_check.py --save

# 6. Preview tomorrow's slate
python scripts/scan.py sports --min-edge 0.03 --top 10 --date tomorrow --exclude-open
```

Give me an EOD summary:
- **Today's results**: W/L record, net P&L, ROI
- **CLV performance**: did we beat closing prices?
- **Best/worst bets**: what worked, what didn't, why (show Type and Pick)
- **Open positions**: anything still live overnight?
- **Tomorrow preview**: any early edge worth noting?
- **Strategy notes**: anything to adjust going forward?
