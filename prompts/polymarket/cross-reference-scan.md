# Polymarket Cross-Reference Scan

Find markets where Kalshi and Polymarket disagree on price. Price discrepancies between exchanges are the strongest edge signal.

```
python scripts/scan.py polymarket --min-edge 0.03 --top 20
```

For each opportunity:
- The market question in plain English
- Kalshi YES price vs Polymarket YES price
- The discrepancy and which side to bet on each platform
- Match quality score (how confident are we it's the same market?)
- Settlement date

Which category (crypto, weather, SPX, politics) has the biggest cross-market discrepancies right now?

To filter to a specific category:
```
python scripts/scan.py polymarket --filter crypto --min-edge 0.03
python scripts/scan.py polymarket --filter weather --min-edge 0.03
python scripts/scan.py polymarket --filter spx --min-edge 0.03
```
