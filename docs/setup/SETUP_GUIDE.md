# Edge-Radar Setup Guide

Step-by-step guide to get Edge-Radar running from scratch. Covers Python environment, API keys, private key generation, and first scan.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [1. Clone and Install](#1-clone-and-install)
- [2. Get Your API Keys](#2-get-your-api-keys)
  - [Kalshi (required)](#kalshi-required)
  - [The Odds API (required for sports)](#the-odds-api-required-for-sports)
- [3. Generate Kalshi Private Keys](#3-generate-kalshi-private-keys)
- [4. Set Up Your Keys Folder](#4-set-up-your-keys-folder)
- [5. Configure .env](#5-configure-env)
- [6. Verify Your Setup](#6-verify-your-setup)
- [7. First Scan](#7-first-scan)
- [8. Going Live](#8-going-live)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python 3.11+** — [Download](https://python.org/downloads/)
- **Git** — [Download](https://git-scm.com/downloads)
- **A Kalshi account** — Free to create at [kalshi.com](https://kalshi.com)
- **An Odds API key** — Free tier at [the-odds-api.com](https://the-odds-api.com) (500 requests/month)

> **Note:** All other data sources (ESPN, NHL, MLB, NWS, CoinGecko, Yahoo Finance, Polymarket) are free and require no API keys. They work out of the box.

---

## 1. Clone and Install

```bash
# Clone the repository
git clone https://github.com/michaelschecht/Edge-Radar.git
cd Edge-Radar

# Create a virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Important:** Always run Edge-Radar from the activated virtual environment. The `.pth` file inside the venv auto-configures Python's import paths. Running with a bare `python` outside the venv will produce `ModuleNotFoundError`.

---

## 2. Get Your API Keys

### Kalshi (required)

Kalshi uses RSA key-pair authentication. You'll need an **API key ID** and a **private key file**.

#### Demo Environment (recommended to start)

1. Go to [https://demo.kalshi.com](https://demo.kalshi.com) and create a free demo account
2. Once logged in, go to **Settings > API Keys** or visit [https://demo.kalshi.com/account/api-keys](https://demo.kalshi.com/account/api-keys)
3. Click **Create API Key**
4. Kalshi will generate a key pair:
   - **API Key ID** — a short string like `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
   - **Private Key** — a PEM file download (save this immediately, it's only shown once)
5. Copy the API Key ID — this goes in your `.env` as `KALSHI_API_KEY`
6. Save the downloaded private key file — see [Section 4](#4-set-up-your-keys-folder) for where to put it

> **Demo API base URL:** `https://demo-api.kalshi.co/trade-api/v2`

#### Production Environment (real money)

1. Go to [https://kalshi.com](https://kalshi.com) and log in to your funded account
2. Go to **Settings > API Keys** or visit [https://kalshi.com/account/api-keys](https://kalshi.com/account/api-keys)
3. Create a new API key (same process as demo)
4. Save the API Key ID and private key file

> **Production API base URL:** `https://api.elections.kalshi.com/trade-api/v2`

**Kalshi API docs:** [https://docs.kalshi.com](https://docs.kalshi.com) — covers authentication, rate limits, and the full API reference.

---

### The Odds API (required for sports)

The Odds API provides sportsbook consensus odds from 12+ US books. Edge-Radar uses these to calculate fair values via weighted de-vig.

1. Go to [https://the-odds-api.com](https://the-odds-api.com)
2. Click **Get API Key** (free tier)
3. Sign up with email — no credit card required
4. Your API key will be emailed to you and shown on the dashboard
5. Copy the key — this goes in your `.env` as `ODDS_API_KEYS`

**Free tier:** 500 requests/month. Each full scan uses ~5-10 requests (one per sport). This is enough for several scans per day.

**Pro tip:** You can create multiple free accounts with different emails to get multiple keys. Edge-Radar supports key rotation — put them comma-separated in your `.env`:

```
ODDS_API_KEYS=key1,key2,key3
```

The system automatically rotates to the next key when one is exhausted or rate-limited.

---

## 3. Generate Kalshi Private Keys

If Kalshi provided a private key download, skip this step — you already have it.

If you need to generate a key pair manually (some Kalshi API flows require this):

```bash
# Generate a 4096-bit RSA private key
openssl genrsa -out kalshi_private.key 4096

# Extract the public key (upload this to Kalshi)
openssl rsa -in kalshi_private.key -pubout -out kalshi_public.pem
```

Then upload `kalshi_public.pem` to Kalshi's API settings page and keep `kalshi_private.key` local.

---

## 4. Set Up Your Keys Folder

Edge-Radar expects private keys in a `keys/` directory at the project root. This directory is gitignored — keys are never committed.

```
Edge-Radar/
└── keys/
    ├── demo/
    │   └── kalshi_private.key    # Demo environment private key
    └── live/
        └── kalshi_private.key    # Production environment private key
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

## 5. Configure .env

Copy the example environment file and fill in your values:

```bash
cp .env.example .env
```

Open `.env` in your editor and set the required values:

### Minimum Configuration (Demo)

```env
# Kalshi Demo
KALSHI_API_KEY=your-demo-api-key-id-here
KALSHI_PRIVATE_KEY_PATH=keys/demo/kalshi_private.key
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2

# Odds API
ODDS_API_KEYS=your-odds-api-key-here

# Safety
DRY_RUN=true
```

### Production Configuration

```env
# Kalshi Production (for placing real orders)
KALSHI_API_KEY=your-prod-api-key-id-here
KALSHI_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2

# Optional: separate prod credentials for read-only market data scanning
# (useful if your main account is on demo but you want real market prices)
KALSHI_PROD_API_KEY=your-prod-api-key-here
KALSHI_PROD_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
KALSHI_PROD_BASE_URL=https://api.elections.kalshi.com/trade-api/v2

# Odds API (multiple keys for more capacity)
ODDS_API_KEYS=key1,key2,key3

# Safety — set to false only when you're ready to place real orders
DRY_RUN=true
```

### Risk Limits (all have sane defaults)

The defaults work well for getting started. Adjust as you gain confidence:

```env
UNIT_SIZE=1.00                  # Minimum bet size ($1)
KELLY_FRACTION=0.25             # Quarter-Kelly (conservative)
MAX_BET_SIZE=100                # Hard cap per single bet
MAX_DAILY_LOSS=250              # Stop all betting at -$250/day
MAX_OPEN_POSITIONS=10           # Max 10 concurrent positions
MAX_PER_EVENT=2                 # Max 2 positions per game
MAX_BET_RATIO=3.0               # Max single bet as multiple of batch median
MIN_EDGE_THRESHOLD=0.03         # Global minimum edge (fallback)
MIN_EDGE_THRESHOLD_NBA=0.08     # Per-sport override (2026-04-18 calibration)
MIN_EDGE_THRESHOLD_NCAAB=0.10   # Per-sport override
MIN_COMPOSITE_SCORE=6.0         # Minimum opportunity score (0-10)
KELLY_EDGE_CAP=0.15             # Soft-cap edge for Kelly sizing
KELLY_EDGE_DECAY=0.5            # Decay factor above the cap
SERIES_DEDUP_HOURS=48           # Reject same-matchup bets within this window (0 disables)
```

> **Key paths are relative to the project root.** The client resolves `keys/live/kalshi_private.key` from the Edge-Radar directory automatically.

---

## 6. Verify Your Setup

Run the startup doctor to check everything:

```bash
python scripts/doctor.py
```

You should see:

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

If anything fails, the doctor tells you exactly what's wrong.

---

## 7. First Scan

Start with a preview scan — no money is risked:

```bash
# Scan NBA games today
python scripts/scan.py sports --filter nba --date today

# Scan MLB with pricing info
python scripts/scan.py sports --filter mlb --date today --unit-size 1

# Scan all sports
python scripts/scan.py sports --date today
```

The output shows a table of opportunities with edge, fair value, market price, confidence, and composite score. When you see `--execute` is not passed, it's **preview only**.

To save a report:

```bash
python scripts/scan.py sports --filter mlb --date today --save
```

---

## 8. Going Live

When you're comfortable with the scan results and want to place real orders:

1. **Switch to production credentials** in `.env` (Kalshi prod API key + live private key)
2. **Set `DRY_RUN=false`** in `.env`
3. **Start small:** `--unit-size 0.50 --max-bets 3`

```bash
# Preview first (always)
python scripts/scan.py sports --filter mlb --date today --unit-size 0.50 --max-bets 3

# Then execute (adds --execute flag)
python scripts/scan.py sports --filter mlb --date today --unit-size 0.50 --max-bets 3 --execute
```

All 8 risk gates are enforced automatically. The system will reject bets that exceed your configured limits.

> **Tip:** Even with `--execute`, the system shows a preview table first and logs every decision to `data/history/`. You can always check what happened with `python scripts/kalshi/kalshi_executor.py status`.

---

## Troubleshooting

### `ModuleNotFoundError: No module named 'paths'`

You're running Python outside the virtual environment. Activate it first:

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Or use the full path: `.venv/Scripts/python scripts/scan.py ...`

### `FileNotFoundError: Kalshi private key not found`

Your `KALSHI_PRIVATE_KEY_PATH` in `.env` doesn't point to a valid file. Check:
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

Every configured key is either invalid or has hit its monthly quota (free tier = 500 req/month per key, resets on the key's billing anniversary). Check `x-requests-remaining` usage in the scan log, add more keys to `ODDS_API_KEYS`, or wait for the monthly reset. The scanner tries every configured key once before giving up — a fresh scan from a new session with one working key will succeed.

### `No opportunities found`

- Check `--date` — if no games today, try `--date tomorrow`
- Check `--filter` — some sports are seasonal (NFL is fall/winter, MLB is spring/summer)
- Minimum edge is 3% global, 8% for NBA, 10% for NCAAB (per-sport floors set 2026-04-18 from calibration). Low-edge days happen.
- Gate 7 rejects same-matchup bets within 48h (`SERIES_DEDUP_HOURS`). If you intentionally want to re-bet a matchup, set `SERIES_DEDUP_HOURS=0` in `.env` or wait the window out.

---

## Next Steps

- **[Scripts Reference](../SCRIPTS_REFERENCE.md)** — Full CLI reference for every script and flag
- **[Sports Guide](../kalshi-sports-betting/SPORTS_GUIDE.md)** — 27 sport filters, edge detection methodology, daily workflow
- **[Architecture](../ARCHITECTURE.md)** — How scoring, confidence, and risk gates work together
- **[Roadmap](../enhancements/ROADMAP.md)** — What's been built and what's planned
