# Build a Futures Portfolio

I want to allocate $10-$20 across futures bets. Build me a diversified portfolio.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py futures --min-edge 0.005 --top 30 --exclude-open
```

Constraints:
- Spread across at least 3 different sports
- No single bet more than 25% of the portfolio
- Prefer YES bets (lower cost, higher ROI potential) where edge supports it
- Consider settlement timing -- mix of near-term and long-term
- Flag any picks where liquidity looks too thin to actually fill

Output columns from scan: Bet Type, Candidate, Date, Side, Mkt, Fair, Edge, Conf.

Build a portfolio table:
| Sport | Team | Side | Cost | Edge | Settlement | ROI if correct |

Include total cost, expected value, and diversification score.
