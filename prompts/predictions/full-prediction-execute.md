# Full Prediction Market Execute Session

Scan all prediction categories and execute the best opportunities.

## Steps

1. Check portfolio:
```bash
python scripts/kalshi/kalshi_executor.py status
```

2. Settle any outstanding prediction bets:
```bash
python scripts/kalshi/kalshi_settler.py settle
```

3. Scan all prediction markets:
```bash
python scripts/scan.py prediction --min-edge 0.03 --top 20 --exclude-open
```

4. Or scan by category for focused analysis:
```bash
python scripts/scan.py prediction --filter crypto --min-edge 0.03 --top 10 --exclude-open
python scripts/scan.py prediction --filter weather --min-edge 0.05 --top 10 --exclude-open
python scripts/scan.py prediction --filter spx --min-edge 0.03 --top 10 --exclude-open
```

5. Execute top picks:
```bash
python scripts/scan.py prediction --min-edge 0.05 --max-bets 5 --unit-size 1 --exclude-open --execute
```

6. Or cherry-pick from preview:
```bash
python scripts/scan.py prediction --min-edge 0.03 --exclude-open --execute --pick '1,4,7'
```

## Output

The scan table shows: Title, Date, Cat. (crypto/weather/spx/mentions), Side, Mkt, Fair, Edge, Conf, Score.

## Category notes

- **Crypto**: Model uses CoinGecko price + trend. Best when market is clearly mispriced vs current price.
- **Weather**: Model uses NWS forecast. Most accurate 1-2 days out. Temperature strikes far from forecast have the most edge.
- **SPX**: Model uses Yahoo Finance + VIX. VIX spikes create the most mispricing.
- **Mentions**: Historical settlement patterns. High base-rate YES markets often mispriced.
