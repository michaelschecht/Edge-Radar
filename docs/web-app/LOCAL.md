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

## Changing `.env` (Restart Required)

**A running Streamlit app does not pick up `.env` edits.** The risk-gate thresholds (`MIN_MARKET_PRICE`, `MIN_EDGE_THRESHOLD_*`, `MIN_COMPOSITE_SCORE`, `MIN_CONFIDENCE`, the NO-side gates, etc.) are snapshotted into module-level globals in `kalshi_executor.py` **at import time** — once, when the process starts. The CLI re-imports on every invocation so it's always fresh, but the long-running webapp keeps its startup values until you restart it.

> **Symptom this prevents:** the dashboard approving a bet the current config should reject — e.g. a `$0.05` longshot showing "APPROVED" while `MIN_MARKET_PRICE=0.06`. That means the app is still running on a pre-edit config snapshot.

**After any `.env` change:**

```bash
# In the terminal running Streamlit:
Ctrl+C                      # stop the server
streamlit run webapp/app.py # restart — re-reads .env on import
```

Or force-kill and relaunch: `taskkill /F /IM streamlit.exe` then `streamlit run webapp/app.py`.

**Verify:** open the **Config** page — it renders every variable against the
live process environment, with a `Source` column showing whether each value
came from `.env`/Secrets or from the code default in `app/config.py`. Then
re-run the same scan/preview: bets that violate the new floor should drop out,
or show the expected reject reason in the scan log (**Show scan log**).

> Scan and execute both call `reload_risk_config()` before running, so most
> **gate** edits do apply without a restart. The restart is still required for
> anything read at import time and for the Config page's own mode summary.

> Editing `.env` only affects the **local** app. The Streamlit **Cloud** app reads Secrets, not `.env` — see [CLOUD.md](CLOUD.md#changing-risk-parameters-or-secrets-reboot-required).

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

The auth gate uses an `st.form` so the password only submits when you click **Sign in** (or press Enter while focused inside the form). Typing then tabbing/clicking away does NOT auto-authenticate (form-staging semantics).

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
    ├── portfolio_page.py   # Balance, positions, P&L, risk status (per venue)
    ├── settle_page.py      # Settlement + P&L reports
    ├── backtest_page.py    # Strategy analysis & equity curves
    └── config_page.py      # Live env-var table + execution-mode summary
```

---

## Pages

### Scan & Execute

The primary workflow page. Configure filters, scan for opportunities, preview sizing, and place orders.

**Filters** (top row, adapts per market type):

| Control | CLI Flag | Description |
|---------|----------|-------------|
| Market Type | `sports` / `futures` / `prediction` / `polymarket` | Which scanner to run. `polymarket` switches the execution venue too |
| Filter | `--filter` | Sport or asset — options change per market type. Supports comma-separated (e.g., `mlb,nhl`) |
| Category | `--category` | Market category (game, spread, total, etc.) — disabled for futures and polymarket |
| Date | `--date` | today, tomorrow, or all dates — sports only (futures/prediction/polymarket ignore) |

**Execution Parameters** (second row):

| Control | CLI Flag | Default | Notes |
|---------|----------|---------|-------|
| Min Edge % | `--min-edge` | 3% | Slider 1-20% |
| Top N | `--top` | 20 | Max opportunities to return |
| Unit Size ($) | `--unit-size` | $1.00 | Dollar amount per bet (C11: the longshot knob) |
| Max Bets | `--max-bets` | 6 | Cap on bets placed |
| Min Bets | `--min-bets` | (none) | Abort if fewer pass risk checks |
| Exclude Open | `--exclude-open` | on | Skip markets with existing positions |
| Budget % | `--budget` | 10% | Max batch cost as % of bankroll. Available for **every** market type (was sports-only before 2026-07-31) |

**Results table columns:** `#`, Sport, Bet, Type, Pick, When, Started (`LIVE` for
in-progress games), Price, Fair, Edge, Conf, Score, **Gate**, and **Exec** on
Polymarket scans.

- **Gate** is the same read-only risk-gate preflight the CLI preview shows —
  `ok` means the row would pass the per-opportunity gates. Portfolio-state
  gates (daily loss, open-position count) are only evaluated at execute time,
  so `ok` is necessary but not sufficient.
- **Exec** appears only on Polymarket scans: `YES` means the row carries a US
  `market_slug` and is orderable; `—` means it came from international Gamma
  and is dry-run evidence only.

**Workflow:**

1. Configure filters and parameters (or click a **Quick Scan** / **Favorite** in the sidebar)
2. Click **SCAN MARKETS** — fetches markets, calculates edge, displays results table
3. Optionally select specific rows from the multiselect dropdown
4. Click **PREVIEW** — runs full pipeline (risk gates, Kelly sizing, budget cap). Shows order table with Ticker, Sport, Bet (matchup), Type (ML/Spread/Total/Prop), Pick, When (game time), Side, Contracts, Price, Cost, Edge, Status. (Matchup/Pick/When columns added 2026-04-29; previously the preview showed only the raw ticker.)
5. Click **EXECUTE** — opens confirmation dialog showing the venue and its mode (DRY RUN / LIVE), order summary, budget cap, and a real-money warning if live. Click **Confirm** to place orders
6. Click **CLEAR** to wipe all results and start fresh

**Quick Scan:** Sidebar buttons (Sports, Futures, Prediction, Polymarket) jump to the scan page with that market type pre-selected.

**Polymarket mode.** Selecting `polymarket` as the market type switches both
the scanner and the execution venue. Two things differ from Kalshi:

- **The venue has its own dry-run flag.** Orders are placed only when BOTH
  `DRY_RUN=false` and `POLYMARKET_DRY_RUN=false`. The page banner states the
  live two-flag status rather than assuming it, and the confirm dialog labels
  the mode per venue. Set `POLYMARKET_DRY_RUN=true` to halt Polymarket without
  touching Kalshi.
- **Only US futures are orderable.** Game rows come from international Gamma,
  a separate slug namespace the US retail API cannot address. They are scanned
  and shown as evidence but dropped before execution automatically — the
  confirm dialog counts only the orderable rows.

**Favorites:** Toggle **MANAGE FAVORITES** to save the current filter config with a name. Saved favorites appear in the sidebar as clickable buttons. Stored at `data/webapp/favorites.json`.

---

### Portfolio

Live portfolio dashboard with auto-refresh support, split into **Kalshi** and
**Polymarket** tabs. Each tab hits its own venue's API.

**Displays:**
- **Account Summary** — Balance, Portfolio Value, Open Positions (count/limit), and Today's P&L (Kalshi) or Buying Power (Polymarket, where the US retail API reports it separately from balance)
- **Daily Loss Progress Bar** — Green-to-amber-to-red gradient showing how much of the daily loss limit has been used. Shows **HARD STOP** alert if limit is breached. **This bar is shared across venues** — Gate 1 reads the common trade log, so one daily risk budget covers both
- **Mode badge** — `DRY_RUN=true` on Kalshi; the live two-flag state on Polymarket
- **Open Positions Table** — Kalshi: Sport, Bet, Type, Side, Qty, Avg Price, Cost, Value, P&L. Polymarket: Market, Slug, Side, Qty, Avg Price, Cost, Value, Unrealized, Realized. Both include a W/L summary and Export CSV
- **Resting Orders** — Unfilled limit orders (if any)
- **Today's Trades** — Orders placed today, filtered to that venue

**Auto-refresh:** Toggle on for 30-second automatic refresh via Streamlit's `@st.fragment(run_every=...)` pattern. Toggle off for manual **REFRESH** button only.

> Polymarket's positions payload uses Amount objects (`{"value": "4.98",
> "currency": "USD"}`) and reports cost basis where Kalshi reports market
> value, so the two tables are built by separate formatters. Unrealized P&L
> comes from the venue's `cashValue` (mark-to-market) minus cost and fees, and
> reconciles to the Portfolio Value tile above it.

---

### Settle & Report

**Settle:** Polls the Kalshi API for resolved markets and updates the trade log with outcomes.

**Kalshi only.** Polymarket US settlement and redemption (PM3) is not built
yet — its client returns an empty settlements list, so Polymarket-tagged
trades stay open in the log until that lands.

- Click **SETTLE** to run
- Shows count of newly settled positions and optional raw settle log
- Settlement history table below: Result (W/L), **Venue**, Ticker, Side, Contracts, Cost, Revenue, P&L, ROI, Edge, Date
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

### Config

Read-only view of what the running process is actually configured with.

**Execution Mode** — Kalshi order mode (DRY RUN / LIVE), Polymarket order mode
(LIVE / BLOCKED, resolved from the two-flag rule), Unit Size, and Kelly
Fraction. Warns when `KELLY_FRACTION` exceeds the 0.5 ceiling, since it is
divided by batch size at runtime and is therefore a *portfolio* fraction.

**Environment Variables** — every variable the system reads, with:

| Column | Meaning |
|--------|---------|
| Variable | Env var name |
| Value | Live value. Credentials show only a character count, never the value |
| Source | `set` (from `.env`/Secrets), `default` (code default in `app/config.py`), or `unset` |
| Group | Credentials, System, Risk limits, Sizing, Reject gates, Data quality, Caching, Per-sport overrides, Notifications, Integrations |
| Notes | What the knob does and which review introduced it |

Filter by group, or tick **Show unset** to include optional overrides you
haven't set. **Export .env template** downloads the whole list with live values
(secrets blanked) ready to paste into a fresh `.env`.

> The variable list lives in `webapp/services.py` as `ENV_VAR_SPEC` and is
> locked to `app/config.py` by `tests/test_webapp_env_registry.py` — if a new
> knob is added to config without being registered here, that test fails. This
> matters most on Cloud, where an unregistered variable set in Secrets is
> silently never read.

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
