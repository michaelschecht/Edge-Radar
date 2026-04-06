# Web Dashboard Setup

**Install and configure the Edge-Radar Streamlit dashboard.**

---

## Prerequisites

- Python 3.11+ with the project venv active
- All Edge-Radar dependencies installed (`pip install -r requirements.txt`)
- `.env` configured with Kalshi API keys (same as CLI usage)

## Install Streamlit

```bash
cd D:\AI_Agents\Specialized_Agents\Edge_Radar
.venv\Scripts\pip install streamlit
```

> **Note:** Streamlit is not yet in `requirements.txt` to keep the core install lightweight. Install it manually when you want to use the dashboard.

## Directory Structure

```
webapp/
├── .streamlit/
│   └── config.toml         # Dark theme + server settings
├── app.py                  # Entry point — auth, sidebar, page routing
├── theme.py                # Custom CSS, color palette, styled components
├── services.py             # Thin wrapper around existing Edge-Radar functions
└── views/
    ├── scan_page.py        # Scan & Execute — filters, preview, order placement
    ├── portfolio_page.py   # Balance, positions, P&L, risk status
    └── settle_page.py      # Settlement + P&L reports (rendered as markdown)
```

## Authentication (Optional)

For remote access, create a secrets file:

```bash
# Create the file (already gitignored)
mkdir -p webapp/.streamlit
```

Create `webapp/.streamlit/secrets.toml`:

```toml
[passwords]
user = "your_secure_password_here"
```

When no secrets file exists, the dashboard runs without a password gate (local use).

For secure remote access, pair with one of:
- **Tailscale** — LAN-like access from any device, zero config
- **Cloudflare Tunnel** — free HTTPS with email OTP

## Verify Installation

```bash
.venv\Scripts\python -c "import streamlit; print(f'streamlit {streamlit.__version__}')"
```

---

**Next:** [Usage Guide](USAGE.md) — starting, stopping, and navigating the dashboard.
