# Best Futures Value Across All Sports

Find the single best futures bet available right now across all sports. Scan everything and rank by edge.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py futures --min-edge 0.005 --top 30 --exclude-open
```

Tell me:
1. The #1 pick and why it's the best risk-adjusted bet
2. How the edge compares to sports game betting edges (typically 3-10%) -- futures edges of 0.5-2% are normal given lower liquidity
3. Capital efficiency: cost vs potential payout vs lockup period
4. What catalyst could make this edge disappear (draft, trade, injury)
5. Should I bet now or wait?

Output columns: Bet Type, Candidate, Date, Side, Mkt, Fair, Edge, Conf.

Be honest about Kalshi futures liquidity -- if the displayed prices look stale or unfillable, say so. If the best edge is under 0.5%, tell me honestly that futures aren't offering great value right now and suggest I focus on daily game betting instead.
