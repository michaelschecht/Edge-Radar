# U6: Streamlit Web Dashboard

*Last updated: 2026-04-06*

**Status:** v1.0 BUILT
**Priority:** Tier 5 (UX & Automation)
**Roadmap ID:** U6

---

## Current State (v1.0)

Dashboard is built and functional. Launch with `streamlit run webapp/app.py`.

### What's Done

| # | Task | Status |
|---|---|---|
| 1 | Create `webapp/` directory structure | Done |
| 2 | Build `services.py` — wrapper + rich output capture | Done |
| 3 | Build Scan & Execute page (all flags, scan/preview/execute flow) | Done |
| 4 | Build Portfolio page (balance, positions, P&L, risk status) | Done |
| 5 | Build Settle & Report page (settle + markdown P&L reports) | Done |
| 6 | Dark theme with custom CSS (`theme.py`) | Done |
| 7 | Add `.streamlit/secrets.toml` to `.gitignore` | Done |
| 8 | Optional password auth gate | Done |
| 9 | `generate_report()` returns markdown for web rendering | Done |
| 10 | Official `streamlit/agent-skills` skill installed | Done |
| 11 | Docs: `docs/web-app/` — SETUP.md, USAGE.md, ARCHITECTURE.md | Done |
| 12 | README updated with Web Dashboard link | Done |
| 13 | Quick-scan sidebar buttons (D1) — Sports, Futures, Prediction, Polymarket | Done |
| 14 | Favorite scans (D2) — save/load/delete scan configs, stored in `data/webapp/favorites.json` | Done |
| 15 | Default unit size changed to $0.50 (D4) | Done |
| 16 | Dynamic controls per market type — budget/max-per-game sports-only, cross-ref prediction-only, category/filter options adapt | Done |
| 17 | `favorites.py` module for persistence | Done |
| 18 | ANSI escape code stripping — clean console output in preview/logs | Done |
| 19 | Replaced all `st.expander` with toggle buttons (Material icon font broken in custom theme) | Done |
| 20 | Rich table stripping — preview shows clean summary + Streamlit dataframe, not box-drawing chars | Done |
| 21 | Clear button — wipes scan results, preview, and execution data for fresh start | Done |

### Known Limitations

- Sidebar toggle buttons hidden (Material icon font renders as broken text in dark theme) — sidebar always open
- `st.expander` widget unusable (same Material icon issue) — replaced with toggle buttons throughout
- `streamlit` not yet in `requirements.txt` (install manually)
- No favicon or site icon

---

## Architecture

```
webapp/
├── .streamlit/
│   └── config.toml         # Dark theme + server settings
├── app.py                  # Entry point — auth, sidebar nav, quick-scan buttons, page routing
├── theme.py                # Custom CSS, color palette, styled components
├── services.py             # Thin wrapper around existing Edge-Radar functions
├── favorites.py            # Save/load/delete favorite scan configs (JSON persistence)
└── views/
    ├── scan_page.py        # Scan & Execute — dynamic controls per market type, favorites, preview/execute
    ├── portfolio_page.py   # Balance, positions, P&L, risk status
    └── settle_page.py      # Settlement + P&L reports (rendered as markdown)
```

See `docs/web-app/ARCHITECTURE.md` for full details on the service layer and function mapping.

---

## Planned Enhancements

### From User (Priority)

| # | Enhancement | Description | Effort |
|---|---|---|---|
| D1 | **Quick-scan sidebar buttons** | **DONE** — Sports, Futures, Prediction, Polymarket buttons in sidebar, pre-selects market type | Small |
| D2 | **Favorite scans / quick links** | **DONE** — Save/load/delete named scan configs. Stored in `data/webapp/favorites.json`. Favorites appear in sidebar. | Medium |
| D3 | **Site icon and favicon** | Custom Edge-Radar icon for browser tab and PWA manifest | Small |
| D4 | **Default unit size to $0.50** | **DONE** — Changed from $1.00 to $0.50 | Trivial |

### Recommended (UX)

| # | Enhancement | Description | Effort |
|---|---|---|---|
| D5 | **Auto-refresh portfolio** | Periodic polling (30s) on Portfolio page to keep positions/P&L live without manual refresh | Small |
| D6 | **Scan result caching** | Cache scan results with TTL so page re-renders don't re-fetch from APIs | Small |
| D7 | **Position P&L color coding** | Green/red styling on position rows based on unrealized P&L | Small |
| D8 | **Execution confirmation dialog** | `@st.dialog` confirmation before placing real orders — shows total cost, bet count, DRY_RUN status | Small |
| D9 | **Toast notifications** | Success/error toasts after execution and settlement instead of inline messages | Trivial |
| D10 | **Mobile-responsive tweaks** | Reduce column count on small screens, stack controls vertically | Medium |

### Recommended (Functionality)

| # | Enhancement | Description | Effort |
|---|---|---|---|
| D11 | **Settlement history tab** | Add a tab or section to Settle page showing recent settlements with W/L/P&L | Medium |
| D12 | **Scan comparison view** | Side-by-side comparison of scan results from different times or filters | Medium |
| D13 | **Risk dashboard page** | Dedicated risk page with concentration heatmap, daily loss trend chart, per-sport exposure | Medium |
| D14 | **Export to CSV** | Download button for scan results and P&L reports | Small |
| D15 | **Watchlist page** | View and manage saved watchlist opportunities | Medium |

### Recommended (Infrastructure)

| # | Enhancement | Description | Effort |
|---|---|---|---|
| D16 | **Add `streamlit` to `requirements.txt`** | Track as a dependency | Trivial |
| D17 | **Fix sidebar toggle** | Re-enable sidebar collapse/expand once Streamlit fixes Material icon rendering in custom font themes | Blocked |
| D18 | **Tailscale/Cloudflare setup guide** | Step-by-step remote access guide in `docs/web-app/` | Small |
| D19 | **Health check endpoint** | Simple `/healthz` route for monitoring if the dashboard is up | Small |

---

## Dependencies

- `streamlit` (installed manually, not yet in `requirements.txt`)
- All existing Edge-Radar dependencies (already installed)
- No database changes — reads same JSON files and Kalshi API

---

## What This Does NOT Change

- CLI scripts and behavior — completely unchanged
- `.env` configuration — same keys, same values
- Risk gates and Kelly sizing — same execution pipeline
- Trade logging and settlement — same data files
- Scheduled tasks and `.bat` scripts — unchanged
