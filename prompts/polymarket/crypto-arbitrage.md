# Crypto Cross-Market Arbitrage

Scan crypto markets on both Kalshi and Polymarket for price discrepancies. These are the most liquid cross-market opportunities.

```
python scripts/scan.py polymarket --filter crypto --min-edge 0.02 --top 15 --exclude-open
python scripts/scan.py prediction --filter crypto --cross-ref --min-edge 0.02 --top 15 --exclude-open
```

Compare the two views and tell me:
- Which BTC/ETH/SOL/XRP/DOGE strikes have the biggest Kalshi vs Polymarket gap
- Direction: should I buy YES on Kalshi or YES on Polymarket?
- Is this a true arbitrage (riskless) or a directional edge (one platform is wrong)?
- Match quality -- are these really the same underlying market? (raise `--min-match` if noisy)
- Hours until settlement
