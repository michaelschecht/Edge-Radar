# Streamlit Community Cloud Deployment

**Status:** In Progress
**Date Started:** 2026-04-08
**URL:** https://edge-radar.streamlit.app/
**Goal:** Make the Edge-Radar Streamlit dashboard publicly accessible behind a login gate.

---

## Platform Decision

Evaluated several options and selected **Streamlit Community Cloud** for:

- Zero infrastructure cost (free tier)
- Native GitHub integration (auto-deploys on push)
- Built-in secrets management for API keys
- Custom subdomain (`yourapp.streamlit.app`)

Other options considered: Cloudflare Tunnel, Vercel, Railway/Render/Fly.io, Azure/AWS/GCP.

---

## Code Changes Completed

### 1. `webapp/app.py` — sys.path fix for Cloud deployment

Streamlit Community Cloud runs from the repo root, not from `webapp/`. The bare imports in `app.py` (`from theme import ...`, `from favorites import ...`, `from views import ...`) require `webapp/` to be on `sys.path`.

**Added** at the top of `webapp/app.py`:

```python
import sys
from pathlib import Path

# Ensure webapp/ is on sys.path so bare imports (theme, favorites, views) work
# regardless of CWD (needed for Streamlit Community Cloud which runs from repo root)
_webapp_dir = str(Path(__file__).resolve().parent)
if _webapp_dir not in sys.path:
    sys.path.insert(0, _webapp_dir)
```

### 2. Authentication gate (already existed)

`webapp/app.py` already has a `check_password()` function that reads from `st.secrets["passwords"]["user"]`. If no secret is configured, the gate is bypassed — so secrets must be set in Cloud for auth to be active.

### 3. Script imports (already handled)

`webapp/services.py` already inserts `scripts/kalshi`, `scripts/shared`, `scripts/prediction`, `scripts/polymarket` onto `sys.path` using `PROJECT_ROOT`, so core scanner/executor imports work regardless of CWD.

### 4. Loosened dependency pins (`requirements.txt`)

Streamlit Cloud runs Python 3.14 which can't build `scipy==1.11.4` from source (no Fortran compiler). Changed all active dependency pins from `==` to `>=` so pre-built wheels are used.

### 5. Repo public-readiness audit

Removed tracked files that shouldn't be public before making the repo visible:

- `reports/` — betting analysis reports (were committed before gitignore rule)
- `.claude/memory/` — personal project context and user profile
- Added `.claude/memory/` to `.gitignore`

### 6. Kalshi credentials — inline PEM support for Cloud (`kalshi_client.py`)

**Problem:** Streamlit Cloud has no filesystem for `.pem` key files. The original `KalshiClient` only supported loading the private key from a file path (`KALSHI_PRIVATE_KEY_PATH`). With an empty path on Cloud, it resolved to the project root directory and crashed with `[Errno 21] Is a directory`.

**Solution:** Added a dual-mode credential loading system:

| Mode | Where | How key is provided |
|------|-------|---------------------|
| **Inline PEM** (Cloud) | `st.secrets["kalshi"]["private_key"]` or `KALSHI_PRIVATE_KEY` env var | PEM content as a string |
| **File path** (local) | `KALSHI_PRIVATE_KEY_PATH` in `.env` | Path to `.pem` file on disk |

**Priority order:**
1. `private_key_content` constructor argument
2. `KALSHI_PRIVATE_KEY` environment variable
3. `st.secrets["kalshi"]["private_key"]` (Streamlit secrets)
4. `KALSHI_PRIVATE_KEY_PATH` file path (existing local behavior)

**Changes in `kalshi_client.py`:**

```python
# New parameter in __init__
def __init__(self, api_key=None, private_key_path=None,
             private_key_content=None, base_url=None):

# New static method to check inline sources
@staticmethod
def _resolve_key_content() -> str:
    """Check for inline PEM content from env var or Streamlit secrets."""
    content = os.getenv("KALSHI_PRIVATE_KEY", "")
    if content:
        return content
    try:
        import streamlit as st
        return st.secrets["kalshi"]["private_key"]
    except Exception:
        return ""
```

**Changes in `webapp/services.py`:**

- `get_client()` tries `st.secrets["kalshi"]` first (Cloud), falls back to `.env` (local dev).
- Secrets-to-env bridge: before any script imports, `services.py` injects Streamlit secrets into `os.environ` so all existing `os.getenv()` calls (in `odds_api.py`, `edge_detector.py`, etc.) work without modification.

---

## Streamlit Cloud Secrets Configuration

In the app's **Settings > Secrets**, add the following TOML:

```toml
[passwords]
user = "your-chosen-password"

[kalshi]
api_key = "your-kalshi-api-key"
private_key = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA...
(paste entire .pem file contents here)
...
-----END RSA PRIVATE KEY-----
"""
base_url = "https://api.elections.kalshi.com/trade-api/v2"

[odds]
api_key = "your-odds-api-key"
# For multiple keys (rotation), use comma-separated:
# api_keys = "key1,key2,key3"

DRY_RUN = "true"
```

### How the secrets bridge works

`services.py` maps Streamlit secrets to environment variables before scripts are imported:

| Streamlit Secret | Environment Variable | Used By |
|------------------|---------------------|---------|
| `kalshi.api_key` | `KALSHI_API_KEY` | `kalshi_client.py` |
| `kalshi.private_key` | `KALSHI_PRIVATE_KEY` | `kalshi_client.py` |
| `kalshi.base_url` | `KALSHI_BASE_URL` | `kalshi_client.py` |
| `odds.api_key` | `ODDS_API_KEY` | `odds_api.py`, `edge_detector.py` |
| `odds.api_keys` | `ODDS_API_KEYS` | `odds_api.py` (rotation) |
| `DRY_RUN` | `DRY_RUN` | `kalshi_executor.py` |

This means all existing scripts work unchanged — they still use `os.getenv()` and `load_dotenv()` locally, but on Cloud the values are already in the environment before import.

### How to get the PEM content

```bash
# On your local machine, print the key file contents:
cat keys/your-kalshi-key.pem

# Copy the entire output including the BEGIN/END lines
# Paste into the Streamlit secrets editor between triple-quotes
```

### Environment variables that scripts read

These should be added as top-level secrets or under appropriate sections:

| Variable | Purpose | Required for |
|----------|---------|--------------|
| `KALSHI_API_KEY` | Kalshi API key ID | All Kalshi operations |
| `KALSHI_PRIVATE_KEY` | RSA private key (PEM content) | All Kalshi operations |
| `KALSHI_BASE_URL` | API endpoint | Optional (defaults to prod) |
| `ODDS_API_KEY` | The Odds API key | Sports edge detection |
| `DRY_RUN` | `true`/`false` | Trade execution |

---

## Deployment Checklist

- [x] Fix `webapp/app.py` sys.path for Cloud CWD
- [x] Loosen pinned dependencies for Python 3.14 compatibility
- [x] Audit and remove sensitive files from git tracking
- [x] Add `.claude/memory/` to `.gitignore`
- [x] Implement inline PEM credential support for `KalshiClient`
- [x] Update `services.py` to read from `st.secrets`
- [x] Create app on [share.streamlit.io](https://share.streamlit.io)
  - **Repo:** `michaelschecht/Edge-Radar`
  - **Branch:** `master`
  - **Main file path:** `webapp/app.py`
- [ ] Add secrets in app Settings > Secrets (see config above)
- [ ] Merge latest fixes from `mike_win-desktop` into `master`
- [ ] Verify login gate works (password required)
- [ ] Verify scan, portfolio, settle pages load correctly
- [ ] Bookmark the live URL

---

## Troubleshooting

### `[Errno 21] Is a directory`
Kalshi private key path is empty or not set. Add `[kalshi]` section to Streamlit secrets with inline PEM content.

### `scipy` build failure (no Fortran compiler)
Pin was too strict. Use `scipy>=1.11.4` (not `==`) so a pre-built wheel is installed.

### Import errors (`ModuleNotFoundError`)
Ensure `webapp/app.py` has the `sys.path` insert for `webapp/` directory, and `services.py` has the inserts for `scripts/` subdirectories.

---

## Notes

- The `docs/enhancements/` directory is gitignored, so this doc stays local.
- Streamlit Community Cloud free tier has resource limits (1 GB RAM, apps sleep after inactivity).
- If the app needs always-on or heavier compute, consider upgrading to a paid platform later.
- Local dev workflow is unchanged — `.env` + file path still works as before.
