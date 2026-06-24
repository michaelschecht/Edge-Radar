# Environment Health Check

Validate that the environment is correctly configured **before** scanning or executing — catches missing API keys, bad `.env` values, and import problems up front instead of mid-scan.

```
python scripts/doctor.py
```

`doctor.py` checks:

- `.env` is present and required keys load (Kalshi RSA creds, Odds API, etc.)
- Python imports resolve (the `edge_radar.pth` path setup is working)
- `DRY_RUN` setting — confirm it's what you expect before any live run
- Data/log/report directories exist

## Odds API quota

Separately, check how many Odds API requests remain this month (the free tier resets on the 1st at 00:00 UTC):

```
python scripts/shared/check_odds_keys.py            # cached quota (free)
python scripts/shared/check_odds_keys.py --live      # probe each key live (costs N requests)
```

## What to report

- Pass/fail per check, with the exact fix for anything red
- Current `DRY_RUN` value and a reminder if it's `false` (live execution armed)
- Remaining Odds API quota and whether it's enough for today's planned scans
