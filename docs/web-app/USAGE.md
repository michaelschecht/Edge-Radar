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

**Filters** (adapt based on market type):

| Control | Maps To | Description |
|---|---|---|
| Market Type | `sports`, `futures`, `prediction`, `polymarket` | Which scanner to use |
| Filter | `--filter` | Sport or asset — options change per market type |
| Category | `--category` | Market category — disabled for futures/polymarket |
| Date | `--date` | today, tomorrow, or all dates |

**Execution Parameters:**

| Control | Maps To | Shown For |
|---|---|---|
| Min Edge % | `--min-edge` | All |
| Top N | `--top` | All |
| Unit Size ($) | `--unit-size` | All (default $0.50) |
| Max Bets | `--max-bets` | All |
| Min Bets | `--min-bets` | All |
| Exclude Open | `--exclude-open` | All |
| Budget % | `--budget` | Sports only |
| Max Per Game | `--max-per-game` | Sports only |
| Cross-Ref Polymarket | `--cross-ref` | Prediction only |

**Quick Scan:** Sidebar buttons (Sports, Futures, Prediction, Polymarket) navigate directly to the scan page with that market type pre-selected.

**Favorites:** Click **MANAGE FAVORITES** to save the current filter + param config with a name. Saved favorites appear in the sidebar — click to load all settings. Delete from the manage section.

**Workflow:**

1. Configure filters and parameters (or click a Quick Scan / Favorite)
2. Click **SCAN MARKETS** — finds opportunities, displays results table
3. Optionally select specific picks from the multiselect
4. Click **PREVIEW** — runs the full pipeline (risk gates, Kelly sizing, budget cap), shows clean summary + order table with costs
5. Click **EXECUTE** — places real orders (unless `DRY_RUN=true` in `.env`)
6. Click **CLEAR** to wipe all results and start fresh

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
