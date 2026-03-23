# Execute Top Picks

Scan for the best opportunities on `<sport>` and execute the top picks. Be disciplined -- only bet where edge is real.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/kalshi_executor.py run --filter <sport> --min-edge 0.05 --max-bets 5 --unit-size 1
```

1. First show me the preview -- what you plan to bet and why
2. Wait for my confirmation before executing
3. After execution, show me: orders placed, fill status, total cost, updated balance
4. Remind me when to run settlement
