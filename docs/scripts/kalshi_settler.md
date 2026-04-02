# kalshi_settler.py — Settlement & P&L Reporting

**Location:** `scripts/kalshi/kalshi_settler.py`

**When to use:** After games/events have resolved, to update your trade log with results and generate performance reports.

---

## `settle` -- Update Trade Log

```bash
python scripts/kalshi/kalshi_settler.py settle
```

Polls the Kalshi API for settlements, matches to your trade log, calculates P&L per trade, and updates records. No flags.

Run this after games complete to move trades from "open" to "settled" with realized P&L.

---

## `report` -- Performance Report

```bash
python scripts/kalshi/kalshi_settler.py report [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--detail` | off | Show per-trade breakdown table (with bet type and pick labels) |
| `--save` | off | Save markdown report to `reports/Accounts/Kalshi/kalshi_report_YYYY-MM-DD.md` |

### Examples

```bash
# Quick summary (win/loss, net P&L, ROI)
python scripts/kalshi/kalshi_settler.py report

# Full detail with file export
python scripts/kalshi/kalshi_settler.py report --detail --save
```

### Report Includes

- Win/loss record
- Net P&L and ROI
- Profit factor
- Best/worst trades
- Edge calibration (estimated vs. realized)
- Breakdowns by confidence level and category
- CLV (Closing Line Value) tracking

---

## `reconcile` -- Verify Trade Integrity

```bash
python scripts/kalshi/kalshi_settler.py reconcile
```

Compares your local trade log against the Kalshi API to find:

- Trades in your log but not on Kalshi (demo/cancelled)
- Positions on Kalshi not in your log (placed manually)
- Quantity mismatches between local and API

No flags. Run periodically to keep your trade log accurate.
