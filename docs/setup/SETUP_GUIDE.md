# Edge-Radar Setup Guide

Complete guide from clone → first scan → operating Edge-Radar in production. Covers installation, credentials, safe rollout, automation, and ongoing monitoring.

---

## Table of Contents

**Part 1 — Install & Configure**
- [Prerequisites](#prerequisites)
- [1. Clone and Install](#1-clone-and-install)
- [2. Credential & Data-Source Map](#2-credential--data-source-map)
- [3. Get Your API Keys](#3-get-your-api-keys)
- [4. Generate Kalshi Private Keys](#4-generate-kalshi-private-keys)
- [5. Set Up Your Keys Folder](#5-set-up-your-keys-folder)
- [6. Configure `.env`](#6-configure-env)
- [7. Verify Your Setup](#7-verify-your-setup)

**Part 2 — First Scan & Go Live**
- [8. First Scan](#8-first-scan)
- [9. Safe Rollout Plan](#9-safe-rollout-plan)

**Part 3 — Run It Every Day**
- [10. Automation & Scheduling](#10-automation--scheduling)
- [11. Monitoring & Operational Checks](#11-monitoring--operational-checks)

**Reference**
- [Troubleshooting](#troubleshooting)
- [Common Mistakes to Avoid](#common-mistakes-to-avoid)
- [Further Reading](#further-reading)

---

## Prerequisites

- **Python 3.11+** — [Download](https://python.org/downloads/)
- **Git** — [Download](https://git-scm.com/downloads)
- **A Kalshi account** — Free to create at [kalshi.com](https://kalshi.com)
- **An Odds API key** — Free tier at [the-odds-api.com](https://the-odds-api.com) (500 requests/month)

> **Note:** All other data sources (ESPN, NHL, MLB, NWS, CoinGecko, Yahoo Finance) are free and require no API keys. They work out of the box.

---

## 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/michaelschecht/Edge-Radar.git
cd Edge-Radar

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (Git Bash / cmd):
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> **Important:** Always run Edge-Radar from the activated virtual environment. The `.pth` file inside the venv auto-configures Python's import paths. Running with a bare `python` outside the venv will produce `ModuleNotFoundError`.

---

## 2. Credential & Data-Source Map

Only two credentials are strictly required. Everything else is a free public endpoint.

| Source | Purpose | Required? | Env variable(s) | Docs |
|:-------|:--------|:----------|:----------------|:-----|
| **Kalshi API** | Market data + order execution | Yes | `KALSHI_API_KEY`, `KALSHI_PRIVATE_KEY_PATH`, `KALSHI_BASE_URL` | [docs.kalshi.com](https://docs.kalshi.com) |
| **The Odds API** | Sportsbook prices for edge comparison | Yes (for sports workflows) | `ODDS_API_KEYS` (or legacy `ODDS_API_KEY`) | [the-odds-api.com](https://the-odds-api.com) |
| CoinGecko / Yahoo Finance / NWS / ESPN / MLB / NHL | Prediction/signal enrichment | No | — | Public endpoints used by scanner |
| Kalshi production fallback | Optional split-credential setup | Optional | `KALSHI_PROD_API_KEY`, `KALSHI_PROD_PRIVATE_KEY_PATH`, `KALSHI_PROD_BASE_URL` | — |

> The comma-separated `ODDS_API_KEYS` format enables automatic key rotation when one hits its monthly quota.

---

## 3. Get Your API Keys

### Kalshi (required)

Kalshi uses RSA key-pair authentication. You'll need an **API Key ID** and a **private key file**.

#### Demo Environment (recommended to start)

1. Go to [demo.kalshi.com](https://demo.kalshi.com) and create a free demo account
2. **Settings > API Keys** → [demo.kalshi.com/account/api-keys](https://demo.kalshi.com/account/api-keys)
3. Click **Create API Key**
4. Kalshi generates:
   - **API Key ID** — a short string like `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
   - **Private Key** — a PEM file download (saved immediately, shown only once)
5. Copy the API Key ID → goes in `.env` as `KALSHI_API_KEY`
6. Save the downloaded private key file — see [Section 5](#5-set-up-your-keys-folder) for where to put it

> **Demo API base URL:** `https://demo-api.kalshi.co/trade-api/v2`

#### Production Environment (real money)

1. [kalshi.com](https://kalshi.com) → log in to your funded account
2. **Settings > API Keys** → [kalshi.com/account/api-keys](https://kalshi.com/account/api-keys)
3. Create a new API key (same process as demo)
4. Save the API Key ID and private key file

> **Production API base URL:** `https://api.elections.kalshi.com/trade-api/v2`

### The Odds API (required for sports)

The Odds API provides sportsbook consensus odds from 12+ US books. Edge-Radar uses these to calculate fair values via weighted de-vig.

1. [the-odds-api.com](https://the-odds-api.com) → **Get API Key** (free tier)
2. Sign up with email — no credit card required
3. Your API key will be emailed and shown on the dashboard
4. Copy the key → goes in `.env` as `ODDS_API_KEYS`

**Free tier:** 500 requests/month. A typical `--date today` scan uses 3-5 calls. This is enough for several scans per day.

**Pro tip:** You can create multiple free accounts with different emails to get multiple keys. Edge-Radar supports key rotation — put them comma-separated:

```env
ODDS_API_KEYS=key1,key2,key3
```

The system automatically rotates to the next key when one is exhausted or rate-limited.

---

## 4. Generate Kalshi Private Keys

If Kalshi provided a private key download, skip this section — you already have it.

If you need to generate a key pair manually:

```bash
# Generate a 4096-bit RSA private key
openssl genrsa -out kalshi_private.key 4096

# Extract the public key (upload this to Kalshi)
openssl rsa -in kalshi_private.key -pubout -out kalshi_public.pem
```

Then upload `kalshi_public.pem` to Kalshi's API settings page and keep `kalshi_private.key` local.

---

## 5. Set Up Your Keys Folder

Edge-Radar expects private keys in a `keys/` directory at the project root. This directory is gitignored — keys are never committed.

```
Edge-Radar/
└── keys/
    ├── demo/
    │   └── kalshi_private.key    # Demo environment
    └── live/
        └── kalshi_private.key    # Production environment
```

Create the structure and move your key files:

```bash
# From the project root
mkdir -p keys/demo keys/live

# Move your downloaded demo key
mv ~/Downloads/kalshi_demo_private.key keys/demo/kalshi_private.key

# Move your downloaded production key (if applicable)
mv ~/Downloads/kalshi_prod_private.key keys/live/kalshi_private.key
```

> **Security:** The `keys/` directory and all `*.key` files are in `.gitignore`. Verify with `git status` — key files should never appear as untracked.

---

## 6. Configure `.env`

Copy the example environment file:

```bash
cp .env.example .env
```

Open `.env` in your editor and fill in the values.

### Recommended demo-first configuration

```env
# Kalshi Demo
KALSHI_API_KEY=your-demo-api-key-id
KALSHI_PRIVATE_KEY_PATH=keys/demo/kalshi_private.key
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2

# Odds API
ODDS_API_KEYS=your-odds-api-key

# Safety
DRY_RUN=true
UNIT_SIZE=1.00
KELLY_FRACTION=0.25
MAX_DAILY_LOSS=250
MAX_OPEN_POSITIONS=10
MAX_PER_EVENT=2
```

### Recommended live configuration (after validation)

```env
# Kalshi Production
KALSHI_API_KEY=your-prod-api-key-id
KALSHI_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2

# Odds API (multiple keys for more capacity)
ODDS_API_KEYS=key1,key2,key3

# Safety — flip to false only when ready to place real orders
DRY_RUN=false
```

### Optional: split-credential setup

Use these only if you intentionally separate default vs production scanning credentials:

```env
KALSHI_PROD_API_KEY=your-prod-api-key-id
KALSHI_PROD_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
KALSHI_PROD_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
```

### Risk limits (all have sane defaults)

The defaults work for getting started. Size these to your bankroll — a $250 daily loss limit assumes a bankroll well above that.

```env
UNIT_SIZE=1.00                  # Minimum bet size ($1)
KELLY_FRACTION=0.25             # Quarter-Kelly (conservative)
MAX_BET_SIZE=100                # Hard cap per single bet
MAX_DAILY_LOSS=250              # Stop all betting at -$250/day
MAX_OPEN_POSITIONS=10           # Max 10 concurrent positions
MAX_PER_EVENT=2                 # Max 2 positions per game
MAX_BET_RATIO=3.0               # Max single bet as multiple of batch median
MIN_EDGE_THRESHOLD=0.03         # Global minimum edge (fallback)
MIN_EDGE_THRESHOLD_NBA=0.12     # Per-sport override (R14, 2026-04-24 — worst Brier)
MIN_EDGE_THRESHOLD_NCAAB=0.10   # Per-sport override
MIN_COMPOSITE_SCORE=6.0         # Minimum opportunity score (0-10)
KELLY_EDGE_CAP=0.15             # Soft-cap edge for Kelly sizing
KELLY_EDGE_DECAY=0.5            # Decay factor above the cap
SERIES_DEDUP_HOURS=48           # Reject same-matchup bets within this window (0 disables)
```

> **Key paths are relative to the project root.** The client resolves `keys/live/kalshi_private.key` from the Edge-Radar directory automatically.

---

## 7. Verify Your Setup

Run the startup doctor to check everything:

```bash
python scripts/doctor.py
```

Expected output:

```
Edge-Radar Doctor

Environment
  PASS  Python 3.11+
  PASS  Running from venv

Credentials
  PASS  KALSHI_API_KEY set
  PASS  KALSHI_PRIVATE_KEY_PATH exists
  PASS  ODDS_API_KEYS set
    PASS  Odds API keys loaded: 1

Data Directories
  PASS  data/history/
  PASS  data/watchlists/
  ...

API Connectivity
  PASS  Kalshi API connected (balance: $100.00)
  PASS  Odds API keys loaded (1 keys)

All checks passed. Ready to scan.
```

If anything fails, the doctor tells you exactly what's wrong. See [Troubleshooting](#troubleshooting) below for specific fixes.

---

## 8. First Scan

Start with a preview scan — no money is risked:

```bash
# Scan NBA games today
python scripts/scan.py sports --filter nba --date today

# Scan MLB with pricing info
python scripts/scan.py sports --filter mlb --date today --unit-size 1

# Scan all sports
python scripts/scan.py sports --date today
```

The output shows a table of opportunities with edge, fair value, market price, confidence, and composite score. Without `--execute`, it's **preview only**.

Save a report:

```bash
python scripts/scan.py sports --filter mlb --date today --save
```

---

## 9. Safe Rollout Plan

Don't flip to live execution on day one. Use this phased approach.

### Phase A — Dry-run only (2-7 days)

- Keep `DRY_RUN=true`
- Save scans with `--save`
- Review confidence, edge, and skipped reasons in the reports
- Confirm the doctor passes every day, the pipeline renders clean tables, and nothing throws in the logs

### Phase B — Low-stakes live

- Switch to production credentials in `.env` (Kalshi prod API key + live private key)
- Set `DRY_RUN=false`
- Start small: `--unit-size 0.50 --max-bets 3`

```bash
# Preview first (always)
python scripts/scan.py sports --filter mlb --date today --unit-size 0.50 --max-bets 3

# Then execute
python scripts/scan.py sports --filter mlb --date today --unit-size 0.50 --max-bets 3 --execute
```

- Run settlement daily and inspect P&L drift
- Reconcile local log against API daily

### Phase C — Normal operations

- Increase sizing only after stable behavior across a full week
- Keep `MAX_DAILY_LOSS` and `MAX_OPEN_POSITIONS` conservative relative to bankroll
- Continue daily monitoring (see [Section 11](#11-monitoring--operational-checks))

> **Tip:** Even with `--execute`, the system shows a preview table first and logs every decision to `data/history/`. Check status any time with `python scripts/kalshi/kalshi_executor.py status`.

---

## 10. Automation & Scheduling

Edge-Radar ships with pre-built scripts that scan all sports, rank by composite score, and execute with Kelly sizing. Wire these to your OS scheduler.

### Suggested daily schedule

```bash
# Morning — scan + execute today's slate
python scripts/scan.py sports --date today --exclude-open --save --execute --max-bets 5 --unit-size 0.50

# Evening (optional) — lock in early lines for tomorrow's games
python scripts/scan.py sports --date tomorrow --exclude-open --save --execute --max-bets 3 --unit-size 0.50

# Nightly — settle and report
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail --save
```

### Scheduler options

- **Windows** — Task Scheduler (`taskschd.msc`). See [AUTOMATION_GUIDE.md](./AUTOMATION_GUIDE.md) for the installer helper.
- **Linux** — cron or systemd timers
- **macOS** — launchd

Use the same virtual environment interpreter path your manual runs use.

For command recipes, see [SCRIPTS_REFERENCE.md](../SCRIPTS_REFERENCE.md) and [AUTOMATION_GUIDE.md](./AUTOMATION_GUIDE.md).

---

## 11. Monitoring & Operational Checks

Run daily or after any config change:

```bash
python scripts/kalshi/kalshi_executor.py status        # Balance, open positions, P&L
python scripts/kalshi/risk_check.py                    # Full risk dashboard
python scripts/kalshi/kalshi_settler.py report --detail # Settlement-driven P&L report
python scripts/kalshi/kalshi_settler.py reconcile      # Catch local-vs-API drift
```

What to watch:

| Signal | What it means |
|:-------|:--------------|
| Growing open positions | Not settling fast enough — check `kalshi_settler.py settle` ran |
| Repeated gate rejections from one sport | Per-sport edge floor may be right; or data-source issue (check `doctor.py`) |
| Odds API quota exhaustion | Add more keys to `ODDS_API_KEYS` or wait for monthly reset |
| Stale resting orders | The R4 janitor cancels zero-fill orders older than `RESTING_ORDER_MAX_HOURS` on live runs |
| Partial-fill mismatches | Normal — settler handles these; reconcile verifies no drift |
| Reconcile flags drift | Investigate immediately — local log and API disagreement compounds over time |

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'paths'`

Running Python outside the venv. Activate first:

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Or use the full path: `.venv/Scripts/python scripts/scan.py ...`

### `FileNotFoundError: Kalshi private key not found`

`KALSHI_PRIVATE_KEY_PATH` in `.env` doesn't point to a valid file. Check:
- The path is relative to the project root (e.g., `keys/live/kalshi_private.key`)
- The file actually exists at that location
- You haven't accidentally quoted the path

### `Kalshi API: 401 Unauthorized`

- Wrong API key — make sure `KALSHI_API_KEY` matches the key ID shown on Kalshi's API settings page
- Wrong environment — demo keys don't work on prod URLs and vice versa
- Expired key — regenerate on Kalshi's API settings page

### `ODDS_API_KEYS not set`

Sports scans require at least one Odds API key. Get one free at [the-odds-api.com](https://the-odds-api.com).

### `All N Odds API keys returned 401/429 for <sport>`

Every configured key is either invalid or has hit its monthly quota (free tier = 500 req/month per key). Check `x-requests-remaining` usage in the scan log, add more keys to `ODDS_API_KEYS`, or wait for the monthly reset. The scanner tries every configured key once before giving up — a fresh scan with one working key will succeed.

### `No opportunities found`

- Check `--date` — if no games today, try `--date tomorrow`
- Check `--filter` — some sports are seasonal
- Minimum edge is 3% global, 12% for NBA, 10% for NCAAB (per-sport floors set 2026-04-18 from calibration; NBA raised 0.08 → 0.12 in R14 on 2026-04-24 after NBA Brier 0.3306 — worst-calibrated sport). Low-edge days happen.
- Gate 7 rejects same-matchup bets within 48h (`SERIES_DEDUP_HOURS`). Set `SERIES_DEDUP_HOURS=0` to disable or wait the window out.

---

## Common Mistakes to Avoid

- Running outside the venv and hitting import errors
- Using demo key IDs with live Kalshi base URLs (or the reverse)
- Forgetting to switch `DRY_RUN` to `false` when expecting live execution
- Setting aggressive `KELLY_FRACTION` before a meaningful sample size of settled trades
- Sizing `MAX_DAILY_LOSS` higher than your bankroll — it becomes a safety rail that can't catch you
- Automating execution before validating `doctor.py` + several preview scans

---

## Further Reading

### Internal docs

- **[Automation Guide](./AUTOMATION_GUIDE.md)** — Windows Task Scheduler setup walkthrough
- **[Scripts Reference](../SCRIPTS_REFERENCE.md)** — Full CLI reference for every script and flag
- **[Sports Guide](../kalshi-sports-betting/SPORTS_GUIDE.md)** — 27 sport filters, edge detection methodology
- **[Architecture](../ARCHITECTURE.md)** — How scoring, confidence, and risk gates work together
- **[Local Dashboard](../web-app/LOCAL.md)** — Run the Streamlit dashboard locally
- **[Cloud Dashboard](../web-app/CLOUD.md)** — Deploy your own to Streamlit Community Cloud
- **[Roadmap](../enhancements/ROADMAP.md)** — What's built and what's planned

### External docs

- [Kalshi API docs](https://docs.kalshi.com)
- [Kalshi production API keys](https://kalshi.com/account/api-keys) · [demo](https://demo.kalshi.com/account/api-keys)
- [Odds API docs](https://the-odds-api.com/liveapi/guides/v4/)
- [Python venv docs](https://docs.python.org/3/library/venv.html)
