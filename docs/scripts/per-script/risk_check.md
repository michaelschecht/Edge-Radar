# risk_check.py — Portfolio Risk Dashboard

**Location:** `scripts/kalshi/risk_check.py`

**When to use:** Comprehensive portfolio dashboard with risk limits, position details, P&L, and watchlist. Pulls live data from the Kalshi API. Shows readable matchups, bet types, and game dates. Use `--report positions` for just open bets, or `--gate` in automation to block execution when limits are breached.

For a quick balance/positions check, `kalshi_executor.py status` is faster.

---

## Usage

```bash
python scripts/kalshi/risk_check.py [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--report TYPE` | `all` | `all`, `positions`, `pnl`, `limits`, `watchlist` |
| `--gate` | off | Exit code 1 if any risk limit is breached (for automation) |
| `--save` | off | Save dashboard as markdown to `reports/Accounts/Kalshi/kalshi_dashboard_YYYY-MM-DD.md` |

---

## Examples

```bash
# Full dashboard
python scripts/kalshi/risk_check.py

# Full dashboard + save markdown
python scripts/kalshi/risk_check.py --save

# Just check if limits are breached (for scripts/schedulers)
python scripts/kalshi/risk_check.py --gate

# Show only open positions
python scripts/kalshi/risk_check.py --report positions

# Show only P&L
python scripts/kalshi/risk_check.py --report pnl
```

---

## Report Sections

### `all` (default)
Shows everything below in one view.

### `positions`
Open positions table with: Bet (matchup), Type (ML/Spread/Total/Prop), When, Pick, Qty, Cost, P&L.

### `pnl`
Today's realized P&L, total exposure, and fees.

### `limits`
Risk limit status vs configured thresholds:
- Daily loss limit (`MAX_DAILY_LOSS`)
- Max open positions (`MAX_OPEN_POSITIONS`)
- Max portfolio risk per trade (`MAX_PORTFOLIO_RISK_PCT`)
- Single bet limit (`MAX_BET_SIZE`)

### `watchlist`
Current watchlist from the last scan (if saved).

---

## Automation: `--gate`

Use in shell scripts or schedulers to abort execution when risk limits are breached:

```bash
python scripts/kalshi/risk_check.py --gate && python scripts/scan.py sports --filter mlb --execute
```

If any limit is breached, `--gate` exits with code 1 and the scan never runs.
