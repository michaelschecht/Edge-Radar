# Edge-Radar End-User Setup Guide

This guide is the "operator playbook" for running Edge-Radar safely as an end-user (not as a developer).

It expands on the README quick start with:
- a complete API credential map,
- exact `.env` wiring,
- safe rollout from demo to live,
- automation/scheduling patterns,
- and ongoing monitoring + maintenance checks.

---

## Who this guide is for

Use this if you want to:
- run scans reliably on your own machine,
- place live Kalshi orders only after validation,
- automate daily workflows, and
- monitor risk limits and execution health.

If you have not installed the project yet, start with **[SETUP_GUIDE.md](./SETUP_GUIDE.md)** first, then come back here.

---

## 1) Credential & data-source map

Edge-Radar uses several market/data sources. Only two credentials are required for normal operation.

| Source | Purpose in Edge-Radar | Required? | Env variable(s) | Where to get docs/access |
|---|---|---|---|---|
| Kalshi API | Market data + order execution | Yes | `KALSHI_API_KEY`, `KALSHI_PRIVATE_KEY_PATH`, `KALSHI_BASE_URL` | https://docs.kalshi.com + account API key pages |
| The Odds API | Sportsbook prices for edge comparison | Yes for sports workflows | `ODDS_API_KEYS` (or legacy `ODDS_API_KEY`) | https://the-odds-api.com |
| Polymarket Gamma API | Cross-market reference scans | No (public endpoint) | none | https://docs.polymarket.com |
| CoinGecko / Yahoo Finance / NWS / ESPN / MLB / NHL APIs | Prediction/signal enrichment | No | none | Public endpoints used by scanner |
| Kalshi production fallback credentials | Optional split-credential setup | Optional | `KALSHI_PROD_API_KEY`, `KALSHI_PROD_PRIVATE_KEY_PATH`, `KALSHI_PROD_BASE_URL` | Kalshi account + docs |

> Note: `scripts/shared/odds_api.py` supports both `ODDS_API_KEYS` and fallback `ODDS_API_KEY`, but the recommended format is comma-separated `ODDS_API_KEYS` for key rotation.

---

## 2) Generate API keys and store them safely

### Kalshi keys (required)

1. Create API keys in either:
   - Demo: https://demo.kalshi.com/account/api-keys
   - Live: https://kalshi.com/account/api-keys
2. Download the private key PEM immediately (shown once).
3. Save private keys in local `keys/` folders (already gitignored):

```text
keys/
  demo/kalshi_private.key
  live/kalshi_private.key
```

4. Copy the key ID into `.env` as `KALSHI_API_KEY`.

### Odds API key(s) (required for sports)

1. Create account at https://the-odds-api.com.
2. Copy key(s) from dashboard.
3. Add as comma-separated values in `.env`:

```env
ODDS_API_KEYS=key1,key2,key3
```

---

## 3) Wire credentials into `.env`

Copy and edit:

```bash
cp .env.example .env
```

### Recommended demo-first configuration

```env
KALSHI_API_KEY=your-demo-key-id
KALSHI_PRIVATE_KEY_PATH=keys/demo/kalshi_private.key
KALSHI_BASE_URL=https://demo-api.kalshi.co/trade-api/v2

ODDS_API_KEYS=your-odds-api-key

DRY_RUN=true
UNIT_SIZE=1.00
KELLY_FRACTION=0.25
MAX_DAILY_LOSS=250
MAX_OPEN_POSITIONS=10
MAX_PER_EVENT=2
```

### Recommended live configuration (after validation)

```env
KALSHI_API_KEY=your-live-key-id
KALSHI_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2

ODDS_API_KEYS=key1,key2,key3

DRY_RUN=false
```

### Optional: explicit production fallback credentials

Use these only if you intentionally separate default vs production scanning credentials:

```env
KALSHI_PROD_API_KEY=...
KALSHI_PROD_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
KALSHI_PROD_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
```

---

## 4) Validate before first execution

Run these in order:

```bash
python scripts/doctor.py
python scripts/scan.py sports --filter mlb --date today
python scripts/scan.py prediction --filter crypto
python scripts/kalshi/kalshi_executor.py status
```

Expected behavior:
- `doctor.py` confirms credentials, key file paths, directories, and API connectivity.
- scan commands run in preview mode by default.
- no orders are sent unless `--execute` is present and `DRY_RUN=false`.

---

## 5) Safe rollout plan (strongly recommended)

### Phase A — Dry-run only (2–7 days)
- Keep `DRY_RUN=true`.
- Save scans with `--save`.
- Review confidence, edge, and skipped reasons.

### Phase B — Low-stakes live
- Set `DRY_RUN=false`.
- Start with `--unit-size 0.50 --max-bets 3`.
- Run settlement daily and inspect P&L drift.

### Phase C — Normal operations
- Increase sizing only after stable behavior.
- Keep `MAX_DAILY_LOSS` and `MAX_OPEN_POSITIONS` conservative.

---

## 6) Automation & scheduling

There is no single required scheduler script; use your OS scheduler with explicit commands.

### Suggested daily schedule

- **Morning scan/execute:**
  ```bash
  python scripts/scan.py sports --date today --exclude-open --save --execute --max-bets 5 --unit-size 0.50
  ```
- **Evening tomorrow-lines pass (optional):**
  ```bash
  python scripts/scan.py sports --date tomorrow --exclude-open --save --execute --max-bets 3 --unit-size 0.50
  ```
- **Nightly settlement/report:**
  ```bash
  python scripts/kalshi/kalshi_settler.py settle
  python scripts/kalshi/kalshi_settler.py report --detail --save
  ```

### Scheduler options

- Windows: Task Scheduler (`taskschd.msc`)
- Linux: cron / systemd timers
- macOS: launchd

Use the same virtual environment interpreter path your manual runs use.

For command recipes, see also **[../SCRIPTS_REFERENCE.md](../SCRIPTS_REFERENCE.md)** and **[./AUTOMATION_GUIDE.md](./AUTOMATION_GUIDE.md)**.

---

## 7) Monitoring and operational checks

Run these checks daily or after any config change:

```bash
python scripts/kalshi/kalshi_executor.py status
python scripts/kalshi/risk_check.py
python scripts/kalshi/kalshi_settler.py report --detail
python scripts/kalshi/kalshi_settler.py reconcile
```

What to watch:
- growing count of open positions,
- repeated gate rejections from one sport/filter,
- Odds API quota exhaustion,
- stale resting orders and unexpected partial-fill behavior,
- divergence between local trade log and API reconciliation.

---

## 8) Helpful references

### Project docs
- Setup: **[SETUP_GUIDE.md](./SETUP_GUIDE.md)**
- Automation: **[AUTOMATION_GUIDE.md](./AUTOMATION_GUIDE.md)**
- Architecture: **[../ARCHITECTURE.md](../ARCHITECTURE.md)**
- Script-by-script CLI: **[../SCRIPTS_REFERENCE.md](../SCRIPTS_REFERENCE.md)**
- Web app local usage: **[../web-app/LOCAL.md](../web-app/LOCAL.md)**

### External docs
- Kalshi API docs: https://docs.kalshi.com
- Kalshi account/API key pages: https://kalshi.com/account/api-keys and https://demo.kalshi.com/account/api-keys
- Odds API docs: https://the-odds-api.com/liveapi/guides/v4/
- Polymarket docs: https://docs.polymarket.com
- Python venv docs: https://docs.python.org/3/library/venv.html

---

## 9) Common mistakes to avoid

- Running outside the venv and hitting import errors.
- Using demo key IDs with live Kalshi base URLs (or the reverse).
- Forgetting to switch `DRY_RUN` to `false` when expecting live execution.
- Setting aggressive `KELLY_FRACTION` before enough sample size.
- Automating execution before validating `doctor.py` + preview scans.

If you want, this guide can be further split into:
1) **Beginner setup checklist**,
2) **Live-trading readiness checklist**, and
3) **Operations runbook (daily/weekly/monthly)**.
