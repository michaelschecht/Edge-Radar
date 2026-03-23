# Settle & Review Performance

Check for settled bets, update P&L, and give me a full performance breakdown.

```
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail
python scripts/kalshi/kalshi_settler.py reconcile
```

I want to know:
- How many bets settled since last check
- Win/loss record and win rate
- Net P&L and ROI
- Best and worst bets (and why they won/lost)
- Edge calibration: are our estimated edges matching reality?
- Any discrepancies between our log and Kalshi
- Suggestions for adjusting strategy based on results
