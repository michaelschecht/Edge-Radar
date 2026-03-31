# Portfolio Status Check

Give me a complete picture of my current portfolio and risk exposure.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/risk_check.py
```

I want to see:
- Account balance and buying power
- All open positions with readable names, game dates, cost, and current P&L
- Resting orders that haven't filled yet
- Today's P&L vs daily loss limit
- Risk limit utilization (how close am I to max exposure?)
- Active watchlist items

Save the snapshot: add `--save` to `risk_check.py`.
