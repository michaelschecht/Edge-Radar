# Web Dashboard Usage

**Navigating the Edge-Radar Streamlit dashboard — local or cloud.**

---

## Access

| Environment | URL |
|-------------|-----|
| **Cloud** | Your Streamlit Cloud URL (see [Setup Guide](SETUP.md#cloud-deployment)) |
| **Local** | `http://localhost:8501` |

### Starting Locally

```bash
streamlit run webapp/app.py
```

### Stopping Locally

Press `Ctrl+C` in the terminal, or:

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

- The dashboard and CLI are fully interchangeable — same scripts, same risk gates, same data
- `DRY_RUN=true` prevents real orders from both the CLI and the dashboard
- Scan results persist in the browser session until you scan again or refresh the page
- Click **Show scan log** after a scan to see the full pipeline output (odds fetch, edge calculations, etc.)
- On Cloud, credentials come from Streamlit secrets; locally, from `.env`

---

**See also:** [Setup Guide](SETUP.md) — installation, authentication, and Cloud deployment.
