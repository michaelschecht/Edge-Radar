# Edge-Radar Local Dashboard

Run the full Edge-Radar dashboard on your machine at `http://localhost:8501`.

---

## Quick Start

```bash
# Activate venv
.venv\Scripts\activate

# Launch
streamlit run webapp/app.py
```

Opens at `http://localhost:8501`. Stop with `Ctrl+C` or `taskkill /F /IM streamlit.exe`.

---

## Prerequisites

- Python 3.11+ with project venv active
- Dependencies installed: `pip install -r requirements.txt`
- `.env` configured with Kalshi API keys and risk parameters (same file the CLI uses)
- RSA private key at the path specified by `KALSHI_PRIVATE_KEY_PATH` in `.env`

---

## Authentication (Optional)

Create `webapp/.streamlit/secrets.toml` (already gitignored):

```toml
[passwords]
user = "your_password_here"
```

When no secrets file exists, the password gate is bypassed — the dashboard is open to anyone on your network.

---

## How It Works

The dashboard is a thin UI layer over the same Python functions the CLI uses. All business logic (scanning, risk gates, Kelly sizing, settlement) lives in `scripts/`. The webapp imports and calls those functions directly.

```
Browser  ->  Streamlit (webapp/)  ->  services.py  ->  scripts/kalshi/*.py
                                                       scripts/prediction/*.py
                                                       scripts/shared/*.py
```

**Credentials:** Reads from `.env` via `python-dotenv`, same as the CLI.

---

## Directory Structure

```
webapp/
├── .streamlit/
│   ├── config.toml         # Dark theme + server settings
│   └── secrets.toml        # Local password (gitignored)
├── app.py                  # Entry point — auth, sidebar, page routing
├── theme.py                # Custom CSS, color palette, styled components
├── favorites.py            # Save/load favorite scan configs (data/webapp/favorites.json)
├── services.py             # Bridge to core scripts + secrets injection
└── views/
    ├── scan_page.py        # Scan & Execute — filters, preview, order placement
    ├── portfolio_page.py   # Balance, positions, P&L, risk status
    ├── settle_page.py      # Settlement + P&L reports
    └── backtest_page.py    # Strategy analysis & equity curves
```

---

## Pages

### Scan & Execute

The primary workflow page. Configure filters, scan for opportunities, preview sizing, and place orders.

**Filters** (top row, adapts per market type):

| Control | CLI Flag | Description |
|---------|----------|-------------|
| Market Type | `sports` / `futures` / `prediction` | Which scanner to run |
| Filter | `--filter` | Sport or asset — options change per market type. Supports comma-separated (e.g., `mlb,nhl`) |
| Category | `--category` | Market category (game, spread, total, etc.) — disabled for futures |
| Date | `--date` | today, tomorrow, or all dates — sports only (futures/prediction ignore) |

**Execution Parameters** (second row):

| Control | CLI Flag | Default | Notes |
|---------|----------|---------|-------|
| Min Edge % | `--min-edge` | 3% | Slider 1-25% |
| Top N | `--top` | 20 | Max opportunities to return |
| Unit Size ($) | `--unit-size` | $0.50 | Dollar amount per bet |
| Max Bets | `--max-bets` | 5 | Cap on bets placed |
| Min Bets | `--min-bets` | (none) | Abort if fewer pass risk checks |
| Exclude Open | `--exclude-open` | off | Skip markets with existing positions |
| Budget % | `--budget` | (none) | Max batch cost as % of bankroll (sports only) |

**Workflow:**

1. Configure filters and parameters (or click a **Quick Scan** / **Favorite** in the sidebar)
2. Click **SCAN MARKETS** — fetches markets, calculates edge, displays results table
3. Optionally select specific rows from the multiselect dropdown
4. Click **PREVIEW** — runs full pipeline (risk gates, Kelly sizing, budget cap). Shows order table with Ticker, Side, Contracts, Price, Cost, Edge, Status
5. Click **EXECUTE** — opens confirmation dialog showing mode (DRY RUN / LIVE), order summary, and real-money warning if live. Click **Confirm** to place orders
6. Click **CLEAR** to wipe all results and start fresh

**Quick Scan:** Sidebar buttons (Sports, Futures, Prediction) jump to the scan page with that market type pre-selected.

**Favorites:** Toggle **MANAGE FAVORITES** to save the current filter config with a name. Saved favorites appear in the sidebar as clickable buttons. Stored at `data/webapp/favorites.json`.

---

### Portfolio

Live portfolio dashboard with auto-refresh support.

**Displays:**
- **Account Summary** — Balance, Portfolio Value, Open Positions (count/limit), Today's P&L
- **Daily Loss Progress Bar** — Green-to-amber-to-red gradient showing how much of the daily loss limit has been used. Shows **HARD STOP** alert if limit is breached
- **DRY RUN badge** — if `DRY_RUN=true`
- **Open Positions Table** — Sport, Bet, Type, Side (YES/NO), Qty, Avg Price, Cost, Value, P&L. Includes W/L/Flat summary and unrealized P&L total. Export CSV button
- **Resting Orders** — Unfilled limit orders (if any)
- **Today's Trades** — Orders placed today

**Auto-refresh:** Toggle on for 30-second automatic refresh via Streamlit's `@st.fragment(run_every=...)` pattern. Toggle off for manual **REFRESH** button only.

---

### Settle & Report

**Settle:** Polls the Kalshi API for resolved markets and updates the trade log with outcomes.

- Click **SETTLE** to run
- Shows count of newly settled positions and optional raw settle log
- Settlement history table below: Result (W/L), Ticker, Side, Contracts, Cost, Revenue, P&L, ROI, Edge, Date
- Summary line with total W/L counts and cumulative P&L
- Export CSV button

**Generate Report:** Renders a full P&L markdown report inline.

| Option | Choices |
|--------|---------|
| Time Range | All time, Last 7 days, Last 30 days |
| Per-trade detail | Toggle on/off |

Report includes: account balance, open positions, settlement summary (record, P&L, ROI, profit factor), edge calibration, dimensional breakdowns (by sport, type, side), and per-trade detail table when enabled. Export as `.md` file.

---

### Backtest

Strategy analysis over your settled trade history.

**Filters:**
- Sport: All, NBA, NCAAB, MLB, NHL, NFL
- Category: All, game, spread, total
- Confidence: All, low, medium, high
- Min Edge: slider

**Displays:**
- **Performance Summary** — Record, Win Rate, Net P&L, ROI
- **Advanced Metrics** — Profit Factor, Sharpe Ratio, Max Drawdown, Best/Worst Win/Lose Streaks
- **Breakdowns** — By Sport, By Category, By Confidence, By Edge Bucket (each as a table with Trades, Record, Win %, P&L, ROI, Avg Edge)
- **Calibration Curve** — Predicted vs Actual win rate per bucket, with bar chart
- **Equity Curve** — Line chart of cumulative P&L over time, plus daily P&L table
- **Strategy Simulation** — Runs all filter combinations against your full trade history and ranks by ROI, Sharpe, P&L. Highlights the best-performing strategy

---

## Tips

- Dashboard and CLI are fully interchangeable — same scripts, same risk gates, same data files
- `DRY_RUN=true` in `.env` prevents real orders from both CLI and dashboard
- Scan results persist in the browser session until you scan again or refresh the page
- Click **Show scan log** after a scan to see the full pipeline output (odds fetch, edge calculations, risk checks)
- All risk gates are enforced identically to the CLI (see `CLAUDE.md` §"Execution Gates")
- Favorites persist across sessions (stored on disk, not in browser)
- The date pre-filter optimization applies here too — when you select "today" or "tomorrow", only sports with games on that date trigger Odds API calls

---

## Verify Installation

```bash
python -c "import streamlit; print(f'streamlit {streamlit.__version__}')"
streamlit run webapp/app.py
```
