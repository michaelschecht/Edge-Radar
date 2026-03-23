# Weather Betting Opportunities

Scan weather markets for temperature mispricing. These are some of the most inefficient markets on Kalshi.

```
python scripts/prediction/prediction_scanner.py scan --filter weather --min-edge 0.05 --top 15
```

For each opportunity:
- City, date, and temperature threshold
- NWS forecast high vs the strike temperature
- Our estimated probability and Kalshi's price
- Days until settlement (closer = higher confidence)
- Forecast uncertainty (how sure is the NWS?)

Focus on tomorrow's markets where NWS forecasts are most accurate. Which cities have the biggest mispricing today?
