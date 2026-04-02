# Scan All Prediction Markets

Run a full scan across all prediction market categories and show me the best opportunities.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py prediction --min-edge 0.03 --top 20 --exclude-open
```

Output columns: Title | Date | Cat. | Side | Mkt | Fair | Edge | Conf | Score

Group results by category (crypto, weather, S&P 500, mentions, companies, politics) and for each:
- How many opportunities found
- Top 1-2 picks with plain English explanation
- Data source and confidence level
- When it settles

Which category has the most actionable edge right now?

To cross-reference against Polymarket:
```
python scripts/scan.py prediction --min-edge 0.03 --top 20 --exclude-open --cross-ref
```
