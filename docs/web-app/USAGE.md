# Web Dashboard Usage

**Starting, stopping, and navigating the Edge-Radar dashboard.**

---

## Starting the Dashboard

```bash
cd D:\AI_Agents\Specialized_Agents\Edge_Radar
streamlit run webapp/app.py
```

The dashboard opens at `http://localhost:8501`. For network access:

```bash
streamlit run webapp/app.py --server.address 0.0.0.0
```

## Stopping the Dashboard

Press `Ctrl+C` in the terminal running Streamlit.

To kill a background instance:

```bash
taskkill /F /IM streamlit.exe
```

---

## Pages

### Scan & Execute

The primary workflow page. All controls are configured up front before scanning.

**Filters:**

| Control | Maps To | Description |
|---|---|---|
| Market Type | `sports`, `futures`, `prediction`, `polymarket` | Which scanner to use |
| Sport Filter | `--filter` | Sport or asset (mlb, nba, crypto, etc.) |
| Category | `--category` | Market type: game, spread, total, etc. |
| Date | `--date` | today, tomorrow, or all dates |

**Execution Parameters:**

| Control | Maps To | Description |
|---|---|---|
| Min Edge % | `--min-edge` | Minimum edge threshold to surface |
| Top N | `--top` | Number of opportunities to show |
| Unit Size ($) | `--unit-size` | Dollar amount per bet |
| Budget % | `--budget` | Max total batch cost as % of bankroll |
| Max Bets | `--max-bets` | Maximum bets to place |
| Min Bets | `--min-bets` | Minimum approved bets required (0 = none) |
| Max Per Game | `--max-per-game` | Max positions on the same game |
| Exclude Open | `--exclude-open` | Skip markets with existing positions |

**Workflow:**

1. Configure filters and parameters
2. Click **SCAN MARKETS** — finds opportunities, displays results table
3. Optionally select specific picks from the multiselect
4. Click **PREVIEW** — runs the full pipeline (risk gates, Kelly sizing, budget cap), shows contract quantities, costs, and approval status
5. Click **EXECUTE** — places real orders (unless `DRY_RUN=true` in `.env`)

### Portfolio

Live portfolio dashboard. Auto-fetches on first load, click **REFRESH** to update.

Shows:
- Balance and portfolio value
- Open position count vs limit
- Today's P&L with daily loss limit progress bar
- Open positions table (Sport, Bet, Type, Side, Qty, Price, Cost, Value, P&L)
- Resting orders (unfilled limit orders)
- Today's trades

### Settle & Report

**Settle** — Polls the Kalshi API for completed markets. Updates the trade log with outcomes and realized P&L. Always run this before generating a report.

**Generate Report** — Renders a full P&L report in markdown format directly in the dashboard. Options:
- Time range: All time, Last 7 days, Last 30 days
- Per-trade detail toggle

The report includes:
- Account balance summary
- Open positions
- Settlement summary (record, P&L, ROI, profit factor)
- Edge calibration (estimated vs realized edge)
- Dimensional breakdowns (by sport, type, side)
- Per-trade detail table (when enabled)

---

## Tips

- The dashboard reads the same `.env` and data files as the CLI — they are fully interchangeable
- `DRY_RUN=true` in `.env` prevents real orders from both the CLI and the dashboard
- Scan results persist in the browser session until you scan again or refresh the page
- The raw console output is available in expandable sections if you want to see the full pipeline log

---

**See also:** [Setup Guide](SETUP.md) — installation and authentication.
