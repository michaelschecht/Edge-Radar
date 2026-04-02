# kalshi_executor.py — Portfolio Status & Execution Library

**Location:** `scripts/kalshi/kalshi_executor.py`

**Role:** Two purposes:
1. **`status` subcommand** -- Quick portfolio dashboard (balance, positions, P&L)
2. **Internal execution library** -- All scanners call `execute_pipeline()` from this module when `--execute` is passed to `scan.py`

> **Note:** The `run` subcommand is a deprecated legacy entry point that predates `scan.py`. Use `scan.py` for all scanning and execution.

---

## `status` -- Portfolio Dashboard

```bash
python scripts/kalshi/kalshi_executor.py status [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--save` | off | Save status report as markdown to `reports/Accounts/Kalshi/kalshi_status_YYYY-MM-DD.md` |

Shows: balance, portfolio value, open positions (with bet type, pick label, matchup, and dates), today's P&L, resting orders.

### Examples

```bash
# Console only
python scripts/kalshi/kalshi_executor.py status

# Console + save markdown report
python scripts/kalshi/kalshi_executor.py status --save
```

---

## Execution Pipeline (Library)

When any scanner is called with `--execute`, it imports `execute_pipeline()` from this module. The pipeline:

1. **Portfolio state** -- fetches balance, open positions, today's P&L
2. **Risk check** -- validates daily loss limit, max open positions, per-trade sizing
3. **Sizing** -- calculates contract count based on `--unit-size` and market price
4. **Preview table** -- shows all approved orders with Bet, Type, Pick, When, Qty, Price, Cost, Edge
5. **Execution** (if `--execute` is passed) -- places limit orders via Kalshi API
6. **Trade logging** -- records each trade to `data/history/`

### Risk Gates

The pipeline rejects opportunities that fail any of these checks:

| Gate | Rule |
|------|------|
| Confidence | Must meet minimum (default: `medium`) |
| Composite score | Must meet minimum (default: `6.0`) |
| Daily loss limit | Today's losses must be under `MAX_DAILY_LOSS` |
| Max open positions | Must be under `MAX_OPEN_POSITIONS` |
| Duplicate ticker | Can't already hold a position in this market |

---

## `run` -- Legacy Scan & Execute (Deprecated)

Use `scan.py` instead. See [scan.py flags](../SCRIPTS_REFERENCE.md#scanpy--unified-scanner).

```bash
# OLD (deprecated):
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --unit-size 2

# NEW (use this instead):
python scripts/scan.py sports --filter nba --execute --unit-size 2
```
