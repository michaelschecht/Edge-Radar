# Crypto Edge Scan

Scan all crypto prediction markets (Bitcoin, Ethereum, XRP, Dogecoin, Solana) for mispriced binary options.

```
python scripts/prediction/prediction_scanner.py scan --filter crypto --min-edge 0.03 --top 15
```

For each opportunity tell me:
- The asset and strike price (e.g., "Bitcoin above $85,000 by Friday")
- Current price vs strike -- how far away are we?
- Our model's fair probability vs Kalshi's price
- Realized volatility from the last 7 days
- Hours until settlement
- Is this a momentum play or a mean-reversion play?

Which crypto asset has the most inefficient Kalshi pricing right now?
