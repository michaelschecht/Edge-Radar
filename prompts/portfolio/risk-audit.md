# Portfolio Risk Audit

Deep dive into current risk exposure. Run when you feel overexposed or before scaling up bet sizes.

## Steps

1. Full risk dashboard:
```bash
python scripts/kalshi/risk_check.py --save
```

2. Open positions detail:
```bash
python scripts/kalshi/risk_check.py --report positions
```

3. Current P&L:
```bash
python scripts/kalshi/risk_check.py --report pnl
```

4. Portfolio status:
```bash
python scripts/kalshi/kalshi_executor.py status
```

## Analysis to provide

### Concentration risk
- How many positions are on the same game? (Same matchup, different bet types)
- How many positions are on the same sport?
- What percentage of total exposure is in the largest single position?
- Are there opposing bets (both over and under on same game)?

### Limit utilization
- Daily loss limit: how much room is left?
- Open positions vs max allowed
- Largest single position vs max bet size
- Total exposure vs balance (leverage ratio)

### Position quality
- List all positions with their current Type and Pick
- Flag any positions with expired or near-expired games that should have settled
- Flag any positions where the edge has likely closed (market price moved toward our entry)

### Recommendations
- Should any positions be reduced or hedged?
- Is the portfolio diversified across sports and bet types?
- Are risk limits appropriately sized for the current bankroll?
