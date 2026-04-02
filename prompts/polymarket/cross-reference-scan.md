# Polymarket Cross-Reference Scan

Find markets where Kalshi and Polymarket disagree on price. Price discrepancies between exchanges are the strongest edge signal.

```
python scripts/scan.py polymarket --min-edge 0.03 --top 20 --exclude-open
```

For each opportunity show:
- The market question in plain English
- Kalshi YES price vs Polymarket YES price
- The discrepancy and which side to bet on each platform
- Match quality score (how confident the pairing is the same market)
- Settlement date

Which category (crypto, weather, spx, politics, companies) has the biggest cross-market discrepancies right now?

Filter to a specific category:
```
python scripts/scan.py polymarket --filter crypto --min-edge 0.03 --exclude-open
python scripts/scan.py polymarket --filter weather --min-edge 0.03 --exclude-open
python scripts/scan.py polymarket --filter spx --min-edge 0.03 --exclude-open
python scripts/scan.py polymarket --filter politics --min-edge 0.03 --exclude-open
python scripts/scan.py polymarket --filter companies --min-edge 0.03 --exclude-open
```

Raise the match quality threshold if too many weak pairings appear:
```
python scripts/scan.py polymarket --filter crypto --min-match 0.7 --exclude-open
```

Look up a single Kalshi ticker against Polymarket:
```
python scripts/scan.py polymarket match TICKER-HERE
```
