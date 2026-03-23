# Scan All Prediction Markets

Run a full scan across all prediction market categories and show me the best opportunities.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/prediction/prediction_scanner.py scan --min-edge 0.03 --top 20
```

Group results by category (crypto, weather, S&P 500, mentions, companies, politics, tech) and for each:
- How many opportunities found
- Top 1-2 picks with plain English explanation
- Data source and confidence level
- When it settles

Which category has the most actionable edge right now?
