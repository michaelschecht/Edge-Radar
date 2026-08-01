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

# === POLYMARKET US (optional — only if you want the Polymarket venue) ===
# Ed25519 retail API keys from https://polymarket.us/developer (iOS app + KYC
# first). NOT the international EIP-712/py-clob-client wallet scheme.
# [polymarket]
# key_id = "your-polymarket-key-uuid"
# secret_key = "base64-ed25519-private-key"
# host = "https://api.polymarket.us"
# dry_run = "true"     # PM2c: orders need BOTH DRY_RUN and this false.

# === SYSTEM ===
DRY_RUN = "true"

# === RISK PARAMETERS ===
# These mirror the .env settings. Uncomment and adjust as needed.
# If omitted, defaults shown in parentheses are used.
#
# The dashboard's **Config** page renders this whole list against the live
# environment — variable, current value, and whether it came from Secrets or a
# code default. Check there rather than guessing whether a secret took effect.

# --- Core limits ---
# UNIT_SIZE = "1.00"                # Kelly floor per bet. C11: this is the LONGSHOT knob —
                                    # below ~30c the flat floor round(UNIT_SIZE/price) binds.
# KELLY_FRACTION = "0.25"           # C11: the FAVORITES knob. Divided by batch size at
                                    # runtime, so it is a PORTFOLIO fraction. Keep <= 0.5.
# MAX_BET_SIZE = "100"              # Hard cap per bet in USD (100)
# MAX_DAILY_LOSS = "250"            # Daily hard stop in USD (250). Shared across venues.
# MAX_OPEN_POSITIONS = "50"         # Concurrent open positions (50)
# MAX_PER_EVENT = "2"               # Max positions per game/event (2)
# MAX_BET_RATIO = "3.0"             # Max bet as multiple of batch median (3.0)

# --- Reject gates ---
# MIN_EDGE_THRESHOLD = "0.03"       # Global minimum edge (fallback)
# MIN_EDGE_THRESHOLD_MLB = "0.04"   # Per-sport override (2026-06-14, lowered from 0.06)
# MIN_EDGE_THRESHOLD_NBA = "0.04"   # Per-sport override (2026-06-14, lowered from 0.06)
# MIN_EDGE_THRESHOLD_NCAAB = "0.04" # Per-sport override (2026-06-14, lowered from 0.06)
# MIN_MARKET_PRICE = "0.12"         # Gate 3.5 lottery-ticket floor. Pure reject threshold,
                                    # independent of sizing. 0 disables.
# MIN_COMPOSITE_SCORE = "6.0"       # Gate 4. C10 (2026-07-23) aligned the futures composite
                                    # to the sports edge scale, so this now binds on futures.
# MIN_CONFIDENCE = "medium"         # Gate 4.5 (R3)
# SERIES_DEDUP_HOURS = "48"         # Gate 7 global default
# SERIES_DEDUP_HOURS_MLB = "72"     # R9: MLB series span up to 72h
# SERIES_DEDUP_HOURS_NHL = "72"     # R9: NHL series same as MLB
# CROSS_CATEGORY_DEDUP = "false"    # R8: collapse ML+Total+Spread on one game
# MIN_CONSENSUS_BOOKS_NBA = "8"     # R29: NBA games under this book count drop to `low`
# RESTING_ORDER_MAX_HOURS = "24"    # R4 janitor. Kalshi-only. 0 disables.

# --- NO-side guards ---
# NO_SIDE_FAVORITE_THRESHOLD = "0.25"    # Gate 4.6 trigger price (R1)
# NO_SIDE_MIN_EDGE = "0.25"              # Gate 4.6 required edge (plus confidence=high)
# NO_SIDE_MIN_EDGE_GLOBAL = "0.08"       # Gate 4.6b (R28): min edge on ANY NO bet
# NO_SIDE_KELLY_PRICE_FLOOR = "0.35"     # Below this NO price, apply the multiplier
# NO_SIDE_KELLY_MULTIPLIER = "0.5"       # Half-Kelly on NO bets below the price floor
# NO_SIDE_KELLY_MULTIPLIER_GLOBAL = "1.0"  # R28: multiplier on ALL NO bets. 1.0 = off.

# --- Sizing dampeners ---
# KELLY_EDGE_CAP = "0.15"           # Soft-cap edge for Kelly sizing (2026-04-18)
# KELLY_EDGE_DECAY = "0.5"          # Decay factor above the cap

# --- Category / live-game gates ---
# ALLOW_PREDICTION_BETS = "false"   # Gate 4.7 (R25): crypto/weather/spx/mentions/
                                    # companies/politics. "true" to opt back in.
# ALLOW_LIVE_BETS = "false"         # Gate 4.8 (L1): bets on in-progress games.

# --- Live-odds freshness (L1) ---
# MAX_LIVE_BOOK_AGE_SECONDS = "1200"  # Drop in-play books staler than this. 0 disables.
# MIN_LIVE_CONSENSUS_BOOKS = "3"      # Skip a game the stale filter thinned below this.
# ODDS_LIVE_TTL_SECONDS = "45"        # Shorter cache TTL when a sport has an in-play event.

# --- Caching ---
# ODDS_CACHE_TTL_SECONDS = "300"    # R24b pre-game Odds API file cache. 0 disables.
# ODDS_CACHE_ENABLED = "true"
# SCAN_CACHE_TTL_SECONDS = "600"    # R26 row->ticker mapping for --pick replay
# SCAN_CACHE_ENABLED = "true"

# --- Calibration ---
# CALIBRATION_STDEVS_TTL_DAYS = "30"  # C8: max age of auto-recalibrated per-sport stdevs
# REQUIRE_FRESH_CALIBRATION = "false" # true = refuse to execute when calibration is behind
                                      # current settled data. Checks recomputation, not age.
                                      # NOTE on Cloud: the filesystem is ephemeral, so
                                      # data/cache/calibration_stdevs.json does not survive a
                                      # reboot and pricing falls back to the hardcoded stdevs.
                                      # Leave this false there or Cloud execution will refuse.
```

> **Flat keys work too.** Every variable above can also be given as a flat
> top-level key instead of inside a `[section]` — the bootstrap in
> `webapp/services.py` lifts both layouts into the process environment before
> any script imports. A variable the app does not know about is silently
> ignored, which is why the **Config** page exists: it shows exactly which
> ones took effect.

### How Secrets Work

Locally, scripts read from `.env` via `app/config.py` (the typed config module — see `CONFIG_CENTRALIZATION_SUMMARY.md`). On Cloud, there's no `.env` file. Instead, `webapp/services.py` has a secrets bridge that injects Streamlit secrets into `os.environ` before any script imports, then calls `reset_config()` so the centralized config picks up the injected values. Same TOML schema as before; same env-var names downstream.

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
| `MAX_OPEN_POSITIONS` | `MAX_OPEN_POSITIONS` | `"50"` | `kalshi_executor.py`, `services.py` |
| `MAX_PER_EVENT` | `MAX_PER_EVENT` | `"2"` | `kalshi_executor.py`, `services.py` |
| `MAX_BET_RATIO` | `MAX_BET_RATIO` | `"3.0"` | `kalshi_executor.py` |
| `MIN_EDGE_THRESHOLD` | `MIN_EDGE_THRESHOLD` | `"0.03"` | `edge_detector.py`, `services.py` |
| `MIN_EDGE_THRESHOLD_<SPORT>` | `MIN_EDGE_THRESHOLD_<SPORT>` | (optional) | `kalshi_executor.py`. Supported: MLB, NBA, NHL, NFL, NCAAB, NCAAF, MLS, SOCCER |
| `MIN_COMPOSITE_SCORE` | `MIN_COMPOSITE_SCORE` | `"6.0"` | `kalshi_executor.py`, `services.py` |
| `KELLY_EDGE_CAP` | `KELLY_EDGE_CAP` | `"0.15"` | `kalshi_executor.py` |
| `KELLY_EDGE_DECAY` | `KELLY_EDGE_DECAY` | `"0.5"` | `kalshi_executor.py` |
| `SERIES_DEDUP_HOURS` | `SERIES_DEDUP_HOURS` | `"48"` | `kalshi_executor.py` |
| `SERIES_DEDUP_HOURS_<SPORT>` | `SERIES_DEDUP_HOURS_<SPORT>` | (optional) | R9 (2026-04-27): per-sport override of the global window. Live: MLB=72, NHL=72. Supported: MLB, NBA, NHL, NFL, NCAAB, NCAAF, MLS, SOCCER. |
| `MIN_CONFIDENCE` | `MIN_CONFIDENCE` | `"medium"` | `kalshi_executor.py` (R3, Gate 4.5) |
| `NO_SIDE_FAVORITE_THRESHOLD` | `NO_SIDE_FAVORITE_THRESHOLD` | `"0.25"` | `kalshi_executor.py` (R1, Gate 4.6) |
| `NO_SIDE_MIN_EDGE` | `NO_SIDE_MIN_EDGE` | `"0.25"` | `kalshi_executor.py` (R1, Gate 4.6) |
| `NO_SIDE_KELLY_PRICE_FLOOR` | `NO_SIDE_KELLY_PRICE_FLOOR` | `"0.35"` | `kalshi_executor.py` (R1 sizing dampener) |
| `NO_SIDE_KELLY_MULTIPLIER` | `NO_SIDE_KELLY_MULTIPLIER` | `"0.5"` | `kalshi_executor.py` (R1 sizing dampener) |
| `RESTING_ORDER_MAX_HOURS` | `RESTING_ORDER_MAX_HOURS` | `"24"` | `kalshi_executor.py` (R4 janitor) |

**All values must be strings in TOML** (e.g., `MAX_OPEN_POSITIONS = "50"` not `50`). The scripts parse them to the correct types internally.

---

## Changing Risk Parameters or Secrets (Reboot Required)

**There is no `.env` on Cloud.** Every risk knob you would set in `.env` locally lives in **Settings → Secrets** here. Editing your local `.env` has zero effect on the Cloud app — and vice versa.

### Why a reboot is needed

The risk-gate thresholds (`MIN_MARKET_PRICE`, `MIN_EDGE_THRESHOLD_*`, `MIN_COMPOSITE_SCORE`, `MIN_CONFIDENCE`, the NO-side gates, etc.) are snapshotted into **module-level globals in `kalshi_executor.py` at import time** — i.e. once, when the app process starts. A running app will keep using its startup values until the process restarts, no matter what you change in Secrets.

> **Symptom this prevents:** the dashboard approving bets that should be rejected — e.g. a `$0.10` longshot getting "APPROVED" even though the current floor is `MIN_MARKET_PRICE = 0.12`. That happens when the app is still running on a *pre-edit* config snapshot.

### How to apply a config change

| Method | When to use | Reboots? |
|--------|-------------|----------|
| **Edit Secrets** (Settings → Secrets → Save) | Changing any risk parameter or credential | ✅ Auto-reboots on save |
| **Reboot app** (manage menu → ⋮ → Reboot app) | Force a clean restart without changing anything | ✅ Yes |
| **Push to the deploy branch** | Code changes (also picks up new config) | ✅ Full redeploy |

**Steps to update a risk parameter:**

1. Go to [share.streamlit.io](https://share.streamlit.io) and open your app's workspace.
2. Open the app menu (**⋮** next to the app, or **Manage app** from the running app's bottom-right).
3. Click **Settings → Secrets**.
4. Edit the flat TOML key (e.g. `MIN_MARKET_PRICE = "0.12"`) and click **Save**.
5. Streamlit Cloud **automatically reboots** the app to load the new value. Wait ~30–60s for the cold start.
6. **Verify:** re-run the same scan/preview — bets that violate the new floor should now drop out (or show the expected reject reason in the scan log).

If a change doesn't seem to take effect, use **⋮ → Reboot app** to force a fresh process start.

> **Keep Cloud and local in sync:** if you change a risk gate in `.env` locally, mirror it in Cloud Secrets (and vice versa) — they are independent configs. See the [Secrets Bridge Mapping](#secrets-bridge-mapping) table for the full key list.

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
