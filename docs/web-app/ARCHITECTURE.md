# Web Dashboard Architecture

**How the Streamlit dashboard connects to Edge-Radar's core scripts.**

---

## Deployment

| Environment | URL | Credentials |
|-------------|-----|-------------|
| **Cloud** | Your Streamlit Cloud URL | Streamlit Cloud secrets |
| **Local** | `http://localhost:8501` | `.env` + optional `secrets.toml` |

Both environments run the same code. See [Setup Guide](SETUP.md) for Cloud configuration.

## Design Principle

The dashboard is a **thin UI layer** over existing functions. All business logic (scanning, risk gates, Kelly sizing, settlement) lives in `scripts/` and is unchanged. The webapp imports and calls the same Python functions the CLI does.

```
Browser  →  Streamlit (webapp/)  →  services.py  →  scripts/kalshi/*.py
                                                     scripts/prediction/*.py
                                                     scripts/polymarket/*.py
                                                     scripts/shared/*.py
```

## Service Layer

`webapp/services.py` is the bridge between Streamlit and the core scripts. It:

1. **Injects Streamlit secrets into `os.environ`** — so all `os.getenv()` calls in scripts work on Cloud without modification
2. **Adds script directories to `sys.path`** — mirrors what the `.pth` file does for the venv
3. **Wraps core functions** — `run_scan()`, `run_execute()`, `run_settle()`, `run_report()`
4. **Captures console output** — redirects `sys.stdout` to a `StringIO` buffer during function calls, since the core scripts print via `rich` console
5. **Returns structured data** — opportunities as lists, portfolio as dicts, reports as markdown strings

## Key Function Mapping

| Dashboard Action | Service Function | Core Function |
|---|---|---|
| Scan | `run_scan()` | `edge_detector.scan_all_markets()` |
| Preview / Execute | `run_execute()` | `kalshi_executor.execute_pipeline()` |
| Portfolio | `get_portfolio_data()` | `risk_check.fetch_balance()`, `fetch_positions()` |
| Settle | `run_settle()` | `kalshi_settler.settle_trades()` |
| Report | `run_report()` | `kalshi_settler.generate_report()` |

## Theme

`webapp/theme.py` injects custom CSS for the dark terminal aesthetic. Colors, fonts, and component styles are defined as constants and applied via `st.markdown()` with `unsafe_allow_html=True`.

| Element | Font | Purpose |
|---|---|---|
| Headings | Outfit | Clean, modern display type |
| Data / Labels | JetBrains Mono | Monospace for prices, tickers, stats |

| Color | Hex | Usage |
|---|---|---|
| Cyan | `#00d4aa` | Primary accent, buttons, active states |
| Amber | `#f59e0b` | Warnings, DRY_RUN badge |
| Green | `#22c55e` | Positive P&L, success states |
| Red | `#ef4444` | Negative P&L, errors, hard stops |
| Surface | `#111827` | Card backgrounds |
| Deep | `#0a0e17` | Page background |

## What the Dashboard Does NOT Do

- Does not bypass any risk gates
- Does not store credentials locally (reads `.env` or Streamlit Cloud secrets)
- Does not modify core script behavior
- Does not replace the CLI (both interfaces are fully interchangeable)
