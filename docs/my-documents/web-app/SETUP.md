# My Web Dashboard Setup

**Edge-Radar Streamlit dashboard — my live instance and local dev.**

---

## Live Dashboard

My dashboard is deployed on Streamlit Community Cloud:

**https://edge-radar.streamlit.app**

Password-gated. Credentials managed via Streamlit Cloud secrets.

---

## Local Development

### Prerequisites

- Python 3.11+ with the project venv active
- All Edge-Radar dependencies installed (`pip install -r requirements.txt`)
- `.env` configured with Kalshi API keys (same as CLI usage)

### Start the Dashboard

```bash
cd D:\AI_Agents\Specialized_Agents\Edge_Radar
streamlit run webapp/app.py
```

The dashboard opens at `http://localhost:8501`.

### Directory Structure

```
webapp/
├── .streamlit/
│   └── config.toml         # Dark theme + server settings
├── app.py                  # Entry point — auth, sidebar, page routing
├── theme.py                # Custom CSS, color palette, styled components
├── favorites.py            # Save/load favorite filter configs
├── services.py             # Bridge to core Edge-Radar scripts + secrets injection
└── views/
    ├── scan_page.py        # Scan & Execute — filters, preview, order placement
    ├── portfolio_page.py   # Balance, positions, P&L, risk status
    ├── settle_page.py      # Settlement + P&L reports
    └── backtest_page.py    # Strategy analysis & equity curves
```

---

## Authentication

### Local

My local secrets file: `webapp/.streamlit/secrets.toml` (gitignored):

```toml
[passwords]
user = "my_secure_password"
```

When no secrets file exists, the dashboard runs without a password gate.

### Streamlit Cloud

Secrets are managed in my app's **Settings > Secrets** panel at [share.streamlit.io](https://share.streamlit.io).

---

## My Cloud Deployment

Deployed on **Streamlit Community Cloud** (free tier).

### Configuration

| Setting | Value |
|---------|-------|
| **Repo** | `michaelschecht/Edge-Radar` |
| **Branch** | `master` |
| **Main file** | `webapp/app.py` |
| **URL** | `https://edge-radar.streamlit.app` |
| **Manage** | [share.streamlit.io](https://share.streamlit.io) |

### Secrets

In **Settings > Secrets**, my TOML config:

```toml
[passwords]
user = "my-password"

[kalshi]
api_key = "my-kalshi-api-key"
base_url = "https://api.elections.kalshi.com/trade-api/v2"
private_key = """
-----BEGIN RSA PRIVATE KEY-----
(full .pem contents)
-----END RSA PRIVATE KEY-----
"""

[odds]
api_keys = "key1,key2,key3"

DRY_RUN = "true"
```

### How Secrets Work on Cloud

Locally, scripts read credentials from `.env` via `os.getenv()`. On Streamlit Cloud, there's no `.env` file. Instead, `webapp/services.py` bridges Streamlit secrets into `os.environ` before any script imports, so all existing `os.getenv()` calls work unchanged.

| Streamlit Secret | Environment Variable | Used By |
|------------------|---------------------|---------|
| `kalshi.api_key` | `KALSHI_API_KEY` | `kalshi_client.py` |
| `kalshi.private_key` | `KALSHI_PRIVATE_KEY` | `kalshi_client.py` (inline PEM) |
| `kalshi.base_url` | `KALSHI_BASE_URL` | `kalshi_client.py` |
| `odds.api_keys` | `ODDS_API_KEYS` | `odds_api.py` (rotation) |
| `DRY_RUN` | `DRY_RUN` | `kalshi_executor.py` |

Both nested (`[kalshi] / api_key`) and flat (`KALSHI_API_KEY`) TOML layouts are supported.

### Kalshi Private Key on Cloud

Streamlit Cloud has no filesystem for `.pem` files. `KalshiClient` supports two modes:

| Mode | Where | How |
|------|-------|-----|
| **Inline PEM** (Cloud) | `st.secrets["kalshi"]["private_key"]` | PEM content as a string |
| **File path** (local) | `KALSHI_PRIVATE_KEY_PATH` in `.env` | Path to `.pem` file on disk |

Inline PEM is checked first. If not found, falls back to file path.

### Odds API Key Rotation on Cloud

Multiple keys rotate automatically, same as local. Use comma-separated values:

```toml
[odds]
api_keys = "key1,key2,key3"
```

---

## Verify Installation

```bash
.venv\Scripts\python -c "import streamlit; print(f'streamlit {streamlit.__version__}')"
```

---

**See also:** [Usage Guide](USAGE.md) | [Architecture](ARCHITECTURE.md)
