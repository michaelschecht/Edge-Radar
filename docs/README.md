# 📖 Edge-Radar Documentation

<p align="center">
  <img src="https://img.shields.io/badge/Documentation-Index-0078d4?style=for-the-badge&labelColor=09090b" alt="Documentation Index">
  <img src="https://img.shields.io/badge/Platform-Kalshi%20%7C%20Polymarket-e74c3c?style=for-the-badge&labelColor=09090b" alt="Platform">
  <img src="https://img.shields.io/badge/Stack-Python-2ea44f?style=for-the-badge&labelColor=09090b" alt="Stack">
  <img src="https://img.shields.io/badge/Status-Active%20Execution-8b5cf6?style=for-the-badge&labelColor=09090b" alt="Status">
</p>

Welcome to the central documentation index for **Edge-Radar**. This index organizes the setup manuals, strategy guides, system architecture definitions, and repository analyses.

---

## 🗺️ Documentation Directory

Only `README.md` and `CHANGELOG.md` live at the root of `docs/`. Everything else is grouped into the subfolders below.

### 🚀 Setup & Architecture — [`setup/`](./setup/)
*   [SETUP_GUIDE.md](./setup/SETUP_GUIDE.md) — Step-by-step instructions to configure API keys, venv, and RSA private credentials.
*   [ARCHITECTURE.md](./setup/ARCHITECTURE.md) — In-depth overview of the pipeline, Kelly sizing equations, and risk gating conditions.
*   [AUTOMATION_GUIDE.md](./setup/AUTOMATION_GUIDE.md) — Setting up the automated scanners and schedulers.
*   [mcp-servers.md](./setup/mcp-servers.md) — MCP Server setup for Edge-Radar.
*   [pipeline-diagram.md](./setup/pipeline-diagram.md) — End-to-end pipeline & data-flow diagram (scan → edge models → risk gating → execution → calibration feedback).

### ⏰ Automation Schedule — [`task-schedules/`](./task-schedules/)
*   **[task-schedules/README.md](./task-schedules/README.md) — the full ~20-task automation pipeline the repo owner actually runs** (scan → execute → email → settle → reconcile → calibrate → review). Documented as a recommended starting point, with sanitized `.bat`/`.sh` templates and `schtasks` registration so you can build the equivalent on your own machine. Start with [AUTOMATION_GUIDE.md](./setup/AUTOMATION_GUIDE.md) for the minimal installer-driven core.

### 🎯 Betting Guides & Coverage — [`kalshi/`](./kalshi/)
*   **[kalshi/README.md](./kalshi/README.md) — start here: the sports/markets coverage matrix (what's configured, what bet types) and links to every betting guide.**
*   [SPORTS_GUIDE.md](./kalshi/kalshi-sports-betting/SPORTS_GUIDE.md) — Sports edge model: weighted de-vig consensus, CDF spreads/totals, sportsbook weighting tiers.
*   [MLB_FILTERING_GUIDE.md](./kalshi/kalshi-sports-betting/MLB_FILTERING_GUIDE.md) — Pitcher/matchup and weather filtering for baseball wagers.
*   [KALSHI_API_REFERENCE.md](./kalshi/kalshi-sports-betting/KALSHI_API_REFERENCE.md) — Kalshi REST/auth reference (RSA signing, endpoints).
*   [FUTURES_GUIDE.md](./kalshi/kalshi-futures-betting/FUTURES_GUIDE.md) — Championship and division futures de-vigging models.
*   [PREDICTION_MARKETS_GUIDE.md](./kalshi/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md) — Scanners for Weather (NWS), Crypto (CoinGecko), and S&P 500.

### 🟣 Polymarket Integration — [`polymarket/`](./polymarket/)
*   **[polymarket/README.md](./polymarket/README.md) — start here: coverage matrix (what's executable vs evidence-only), integration status, and links to every Polymarket guide.**
*   [FUTURES_GUIDE.md](./polymarket/polymarket-futures-betting/FUTURES_GUIDE.md) — Championship futures: the **only executable surface** on Polymarket US.
*   [GAMES_GUIDE.md](./polymarket/polymarket-games-betting/GAMES_GUIDE.md) — Per-game ML/spread/total via Gamma (dry-run evidence only, not orderable on US).
*   [EXECUTION_GUIDE.md](./polymarket/polymarket-execution/EXECUTION_GUIDE.md) — Two-flag dry-run safety, shared risk gates, venue min-share handling, slug registry.
*   [POLYMARKET_API_REFERENCE.md](./polymarket/polymarket-api/POLYMARKET_API_REFERENCE.md) — Ed25519 retail API: signing scheme, endpoints, response shapes.
*   [polymarket-us-setup.md](./setup/polymarket-us-setup.md) — Generating API keys and wiring `.env`.

### ⚙️ Scripts & CLI — [`scripts/`](./scripts/)
*   [SCRIPTS_REFERENCE.md](./scripts/SCRIPTS_REFERENCE.md) — Complete CLI reference for every script, flag, and batch command.
*   [per-script/](./scripts/per-script/) — Deep-dive docs for each script (edge_detector, futures_edge, prediction_scanner, kalshi_executor, kalshi_settler, risk_check, backtester).

### 🔬 Strategy Reviews — [`enhancements/`](./enhancements/)
*   [betting-strategy-review-2026-08-26.md](./enhancements/betting-strategy-review-2026-08-26.md) — Full review of the settled record (402 bets), the defects found (CLV never computed, no cumulative-exposure gate, taker-only fee drag), and a four-phase action plan: stop waste → install CLV measurement → remove trading cost → scale only on evidence.

### 📈 Roadmap & Changelog
*   [ROADMAP.md](./ROADMAP.md) — Priorities, consolidated action items, completed milestones, and the findings log (incl. the 90-day review, F45–F49). **Top item: Polymarket integration (Priority 0).**
*   [CHANGELOG.md](./CHANGELOG.md) — Project commit and feature changelog history.

> Periodic performance audits live under `docs/my-documents/` (git-ignored, local-only). Their conclusions are folded into the ROADMAP findings log, which is the tracked, canonical record.

---

> [!NOTE]
> All automated scheduler files and execution paths in this repository are designed for Windows 11 using PowerShell (`pwsh`) and Command Prompt (`cmd`) scripts.

<p align="center">
  Built with <a href="https://modelcontextprotocol.io">MCP</a> · <a href="https://kalshi.com">Kalshi API</a>
</p>
