# Edge-Radar on Streamlit Community Cloud

Deploy your own Edge-Radar dashboard to Streamlit Community Cloud (free tier). Same functionality as the local dashboard — same scripts, same risk gates, same Kalshi API.

---

## Cloud vs Local Differences

| Aspect | Local | Cloud |
|--------|-------|-------|
| **URL** | `http://localhost:8501` | `https://<your-subdomain>.streamlit.app/` |
| **Credentials** | `.env` file | Streamlit Cloud Secrets (TOML) |
| **Private Key** | File on disk (`keys/live/kalshi_private.key`) | Inline PEM in secrets |
| **Trade logs** | Persistent on disk (`data/history/`) | Ephemeral — resets on reboot |
| **Favorites** | Persistent (`data/webapp/favorites.json`) | Ephemeral — resets on reboot |
| **Reports** | Saved to `reports/` | View inline only (export to download) |
| **Risk params** | From `.env` | From Streamlit secrets (flat TOML keys) |

**Important:** The Cloud filesystem is ephemeral. Settlement history, trade logs, and favorites do not persist across app reboots. Settlement still runs against the Kalshi API (positions are tracked server-side), but the local log resets. The Settle and Backtest pages show a notice about this.

---

## Deploy Your Instance

### 1. Fork the Repo

Fork `Edge-Radar` to your own GitHub account (or clone and push to a new repo you own).

### 2. Create the Streamlit App

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub
2. Click **New app** and configure:

| Setting | Value |
|---------|-------|
| **Repo** | `your-github-username/Edge-Radar` |
| **Branch** | `master` (or your default branch) |
| **Main file** | `webapp/app.py` |

3. Choose a custom subdomain (e.g., `my-edge-radar.streamlit.app`)
4. Add secrets in **Settings > Secrets** (see below) — the app will fail to start without them
5. Deploy

### 3. Updating

Push to your branch on GitHub. Streamlit Cloud auto-deploys on push.

---

## Secrets Configuration

In your app's **Settings > Secrets**, paste TOML configuration.

**Template location in the repo:** `docs/my-documents/enhancements/streamlit_secrets_template.toml`

### Full Secrets Template

```toml
# === LOGIN GATE ===
[passwords]
user = "your_password_here"

# === KALSHI API ===
[kalshi]
api_key = "your-kalshi-api-key"
base_url = "https://api.elections.kalshi.com/trade-api/v2"

# Paste the FULL contents of your .pem private key file.
# Include the BEGIN and END lines.
# To get the contents: cat keys/live/kalshi_private.key
private_key = """
-----BEGIN RSA PRIVATE KEY-----
(paste full PEM contents here)
-----END RSA PRIVATE KEY-----
"""

# === ODDS API ===
[odds]
api_key = "your-primary-odds-api-key"

# Optional: multiple keys for rotation (comma-separated, no spaces)
# api_keys = "key1,key2,key3"

# === SYSTEM ===
DRY_RUN = "true"

# === RISK PARAMETERS ===
# These mirror the .env settings. Uncomment and adjust as needed.
# If omitted, defaults shown in parentheses are used.

# UNIT_SIZE = "1.00"                  # Dollar amount per bet (1.00)
# KELLY_FRACTION = "0.25"            # Kelly multiplier (0.25)
# MAX_BET_SIZE = "100"               # Hard cap per bet in USD (100)
# MAX_DAILY_LOSS = "250"             # Daily hard stop in USD (250)
# MAX_OPEN_POSITIONS = "10"          # Concurrent open positions (10)
# MAX_PER_EVENT = "2"                # Max positions per game/event (2)
# MAX_BET_RATIO = "3.0"             # Max bet as multiple of batch median (3.0)
# MIN_EDGE_THRESHOLD = "0.03"       # Global minimum edge (fallback)
# MIN_EDGE_THRESHOLD_NBA = "0.08"   # Per-sport override (2026-04-18 calibration)
# MIN_EDGE_THRESHOLD_NCAAB = "0.10" # Per-sport override
# MIN_COMPOSITE_SCORE = "6.0"       # Minimum score 0-10 (6.0)
# KELLY_EDGE_CAP = "0.15"           # Soft-cap edge for Kelly sizing (2026-04-18)
# KELLY_EDGE_DECAY = "0.5"          # Decay factor above the cap
# SERIES_DEDUP_HOURS = "48"         # Reject same-matchup bets within this window (2026-04-18)

# 14-day review response (2026-04-21): R1 + R3 + R4
# MIN_CONFIDENCE = "medium"             # Reject opportunities below this confidence (R3)
# NO_SIDE_FAVORITE_THRESHOLD = "0.25"   # NO bets below this price face elevated gate (R1)
# NO_SIDE_MIN_EDGE = "0.25"             # Required edge when NO price < threshold (plus confidence=high)
# NO_SIDE_KELLY_PRICE_FLOOR = "0.35"    # Below this NO-side price, apply Kelly multiplier
# NO_SIDE_KELLY_MULTIPLIER = "0.5"      # Half-Kelly on NO bets below the price floor
# RESTING_ORDER_MAX_HOURS = "24"        # Cancel zero-fill resting orders older than this (R4)
```

### How Secrets Work

Locally, scripts read from `.env` via `os.getenv()`. On Cloud, there's no `.env` file. Instead, `webapp/services.py` has a secrets bridge that injects Streamlit secrets into `os.environ` before any script imports, so all existing `os.getenv()` calls work unchanged.

The bridge supports two TOML layouts:

**Nested** (recommended):
```toml
[kalshi]
api_key = "..."
```
Mapped via `st.secrets["kalshi"]["api_key"]` -> `os.environ["KALSHI_API_KEY"]`

**Flat** (also works):
```toml
KALSHI_API_KEY = "..."
```
Mapped via `st.secrets["KALSHI_API_KEY"]` -> `os.environ["KALSHI_API_KEY"]`

### Secrets Bridge Mapping

| Streamlit Secret | Environment Variable | Default | Used By |
|------------------|---------------------|---------|---------|
| `kalshi.api_key` | `KALSHI_API_KEY` | (required) | `kalshi_client.py` |
| `kalshi.private_key` | `KALSHI_PRIVATE_KEY` | (required) | `kalshi_client.py` (inline PEM) |
| `kalshi.base_url` | `KALSHI_BASE_URL` | (required) | `kalshi_client.py` |
| `odds.api_key` | `ODDS_API_KEY` | (required for scans) | `odds_api.py` |
| `odds.api_keys` | `ODDS_API_KEYS` | (optional) | `odds_api.py` (rotation) |
| `DRY_RUN` | `DRY_RUN` | `"true"` | `kalshi_executor.py` |
| `UNIT_SIZE` | `UNIT_SIZE` | `"1.00"` | `kalshi_executor.py` |
| `KELLY_FRACTION` | `KELLY_FRACTION` | `"0.25"` | `kalshi_executor.py` |
| `MAX_BET_SIZE` | `MAX_BET_SIZE` | `"100"` | `kalshi_executor.py` |
| `MAX_DAILY_LOSS` | `MAX_DAILY_LOSS` | `"250"` | `kalshi_executor.py`, `services.py` |
| `MAX_OPEN_POSITIONS` | `MAX_OPEN_POSITIONS` | `"10"` | `kalshi_executor.py`, `services.py` |
| `MAX_PER_EVENT` | `MAX_PER_EVENT` | `"2"` | `kalshi_executor.py`, `services.py` |
| `MAX_BET_RATIO` | `MAX_BET_RATIO` | `"3.0"` | `kalshi_executor.py` |
| `MIN_EDGE_THRESHOLD` | `MIN_EDGE_THRESHOLD` | `"0.03"` | `edge_detector.py`, `services.py` |
| `MIN_EDGE_THRESHOLD_<SPORT>` | `MIN_EDGE_THRESHOLD_<SPORT>` | (optional) | `kalshi_executor.py`. Supported: MLB, NBA, NHL, NFL, NCAAB, NCAAF, MLS, SOCCER |
| `MIN_COMPOSITE_SCORE` | `MIN_COMPOSITE_SCORE` | `"6.0"` | `kalshi_executor.py`, `services.py` |
| `KELLY_EDGE_CAP` | `KELLY_EDGE_CAP` | `"0.15"` | `kalshi_executor.py` |
| `KELLY_EDGE_DECAY` | `KELLY_EDGE_DECAY` | `"0.5"` | `kalshi_executor.py` |
| `SERIES_DEDUP_HOURS` | `SERIES_DEDUP_HOURS` | `"48"` | `kalshi_executor.py` |
| `MIN_CONFIDENCE` | `MIN_CONFIDENCE` | `"medium"` | `kalshi_executor.py` (R3, Gate 4.5) |
| `NO_SIDE_FAVORITE_THRESHOLD` | `NO_SIDE_FAVORITE_THRESHOLD` | `"0.25"` | `kalshi_executor.py` (R1, Gate 4.6) |
| `NO_SIDE_MIN_EDGE` | `NO_SIDE_MIN_EDGE` | `"0.25"` | `kalshi_executor.py` (R1, Gate 4.6) |
| `NO_SIDE_KELLY_PRICE_FLOOR` | `NO_SIDE_KELLY_PRICE_FLOOR` | `"0.35"` | `kalshi_executor.py` (R1 sizing dampener) |
| `NO_SIDE_KELLY_MULTIPLIER` | `NO_SIDE_KELLY_MULTIPLIER` | `"0.5"` | `kalshi_executor.py` (R1 sizing dampener) |
| `RESTING_ORDER_MAX_HOURS` | `RESTING_ORDER_MAX_HOURS` | `"24"` | `kalshi_executor.py` (R4 janitor) |

**All values must be strings in TOML** (e.g., `MAX_OPEN_POSITIONS = "50"` not `50`). The scripts parse them to the correct types internally.

---

## Inline PEM (Cloud Private Key)

Streamlit Cloud has no filesystem for `.pem` files. `KalshiClient` supports inline PEM: the full key content is passed as a string from `st.secrets["kalshi"]["private_key"]`.

| Mode | Where | How |
|------|-------|-----|
| **Inline PEM** (Cloud) | `st.secrets["kalshi"]["private_key"]` | PEM content as a multi-line TOML string |
| **File path** (local) | `KALSHI_PRIVATE_KEY_PATH` in `.env` | Path to `.key` file on disk |

Priority: inline PEM content > `KALSHI_PRIVATE_KEY` env var > `st.secrets` > file path.

---

## Odds API Key Rotation

Multiple keys rotate automatically on Cloud, same as local. When one key hits its rate limit, the system switches to the next.

```toml
[odds]
api_keys = "key1,key2,key3"
```

Free tier: 500 requests/month per key. With the date pre-filter optimization, a typical `--date today` scan uses 3-5 API calls instead of 15+.

---

## Ephemeral Filesystem Workarounds

Since Cloud wipes `data/` on reboot:

| Data | Persistence | Workaround |
|------|-------------|------------|
| **Positions** | Kalshi API (permanent) | Portfolio page fetches live from API every time |
| **Settlement** | Kalshi API (permanent) | Settle runs against API; local log is just a cache |
| **Trade history** | Lost on reboot | Export CSV from Settle page regularly |
| **Backtest data** | Lost on reboot | Export CSV / run backtests locally for long-term analysis |
| **Favorites** | Lost on reboot | Re-create after reboot, or manage locally |
| **Reports** | Not saved to disk | Use **Export Report** button to download `.md` files |

**Recommendation:** Use Cloud for quick scans and execution. Use local for settlement history, backtesting, and report archives.

---

## Troubleshooting

**"Incorrect password"**
- Check `[passwords] / user` in your Streamlit secrets

**Orders rejected with `max_positions_reached (N/10)`**
- `MAX_OPEN_POSITIONS` is not in your Cloud secrets, so it defaults to `10`
- Add `MAX_OPEN_POSITIONS = "50"` (or your desired limit) as a flat top-level key in Settings > Secrets

**Risk parameters not matching `.env`**
- Cloud doesn't read `.env`. Any risk parameter you've customized locally must also be added to Cloud secrets as a flat TOML key
- See the [Secrets Bridge Mapping](#secrets-bridge-mapping) table for the full list

**"KALSHI_PRIVATE_KEY not found"**
- The `private_key` in `[kalshi]` must include the full PEM content including `-----BEGIN RSA PRIVATE KEY-----` and `-----END RSA PRIVATE KEY-----` lines
- Use triple-quoted TOML strings: `private_key = """..."""`

**"ODDS_API_KEY not set"**
- Add `[odds] / api_key = "your-key"` to your Cloud secrets
- Without it, scans run but find no opportunities (no external odds to compare against)

**Settle shows "0 settled" but games are finished**
- Kalshi markets settle minutes to hours after the event ends
- Try again later — the API is the source of truth

**App crashes or shows import errors after deploy**
- Check that your branch has `requirements.txt` with all dependencies
- Streamlit Cloud runs Python 3.14 — dependency pins must use `>=` not `==` (already done)

**App is slow to load**
- First load after a reboot takes 30-60 seconds (cold start, dependency install)
- Subsequent loads are fast
