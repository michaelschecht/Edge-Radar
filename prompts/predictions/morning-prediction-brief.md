# Morning Prediction Brief

Give me a quick morning overview of what's happening across all prediction markets.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py prediction --filter crypto --min-edge 0.03 --top 5
python scripts/scan.py prediction --filter weather --min-edge 0.05 --top 5
python scripts/scan.py prediction --filter spx --min-edge 0.03 --top 5
python scripts/scan.py prediction --filter mentions --min-edge 0.05 --top 3
```

Format as a brief:
- **Portfolio**: balance, open positions, yesterday's P&L
- **Crypto**: BTC/ETH current price, any edge on today's markets?
- **Weather**: which cities have mispriced temps today?
- **S&P 500**: current SPX/VIX, any binary option value?
- **Mentions**: any broadcasts tonight with edge?
- **Bottom line**: where should I focus today?
