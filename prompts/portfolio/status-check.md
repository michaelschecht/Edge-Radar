# Portfolio Status Check

Give me a complete picture of my current portfolio and risk exposure.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/risk_check.py
```

I want to see:
- Account balance and buying power
- All open positions with Bet, Type (ML/Spread/Total/Prop), Pick, When, Qty, Cost, and current P&L
- Resting orders that haven't filled yet
- Today's P&L vs daily loss limit
- Risk limit utilization (how close am I to max exposure?)
- Active watchlist items

For individual reports:
```
python scripts/kalshi/risk_check.py --report positions   # open positions only
python scripts/kalshi/risk_check.py --report limits      # risk limit status
python scripts/kalshi/risk_check.py --report pnl         # today's P&L
python scripts/kalshi/risk_check.py --gate               # exit 1 if limits breached
```

Save the snapshot:
```
python scripts/kalshi/risk_check.py --save
python scripts/kalshi/kalshi_executor.py status --save
```
