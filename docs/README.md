# 📖 Edge-Radar Documentation

<p align="center">
  <img src="https://img.shields.io/badge/Documentation-Index-0078d4?style=for-the-badge&labelColor=09090b" alt="Documentation Index">
  <img src="https://img.shields.io/badge/Platform-Kalshi-e74c3c?style=for-the-badge&labelColor=09090b" alt="Platform">
  <img src="https://img.shields.io/badge/Stack-Python%20%7C%20Streamlit-2ea44f?style=for-the-badge&labelColor=09090b" alt="Stack">
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
*   [task-schedules.md](./setup/task-schedules.md) — Reference for Windows Task Scheduler cron entries.
*   [mcp-servers.md](./setup/mcp-servers.md) — MCP Server setup for Edge-Radar.
*   [pipeline-diagram.md](./setup/pipeline-diagram.md) — End-to-end pipeline & data-flow diagram (scan → edge models → risk gating → execution → calibration feedback).

### 🎯 Betting Guides & Coverage — [`kalshi/`](./kalshi/)
*   **[kalshi/README.md](./kalshi/README.md) — start here: the sports/markets coverage matrix (what's configured, what bet types) and links to every betting guide.**
*   [SPORTS_GUIDE.md](./kalshi/kalshi-sports-betting/SPORTS_GUIDE.md) — Sports edge model: weighted de-vig consensus, CDF spreads/totals, sportsbook weighting tiers.
*   [MLB_FILTERING_GUIDE.md](./kalshi/kalshi-sports-betting/MLB_FILTERING_GUIDE.md) — Pitcher/matchup and weather filtering for baseball wagers.
*   [KALSHI_API_REFERENCE.md](./kalshi/kalshi-sports-betting/KALSHI_API_REFERENCE.md) — Kalshi REST/auth reference (RSA signing, endpoints).
*   [FUTURES_GUIDE.md](./kalshi/kalshi-futures-betting/FUTURES_GUIDE.md) — Championship and division futures de-vigging models.
*   [PREDICTION_MARKETS_GUIDE.md](./kalshi/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md) — Scanners for Weather (NWS), Crypto (CoinGecko), and S&P 500.

### ⚙️ Scripts & CLI — [`scripts/`](./scripts/)
*   [SCRIPTS_REFERENCE.md](./scripts/SCRIPTS_REFERENCE.md) — Complete CLI reference for every script, flag, and batch command.
*   [per-script/](./scripts/per-script/) — Deep-dive docs for each script (edge_detector, futures_edge, prediction_scanner, kalshi_executor, kalshi_settler, risk_check, backtester).

### 💻 Web App — [`web-app/`](./web-app/)
*   [LOCAL.md](./web-app/LOCAL.md) — Running the local Streamlit dashboard.
*   [CLOUD.md](./web-app/CLOUD.md) — Streamlit Cloud deployment guide.

### 📈 Roadmap & Changelog
*   [enhancements/ROADMAP.md](./enhancements/ROADMAP.md) — Priorities, consolidated action items, completed milestones, and the findings log (incl. the 90-day review, F45–F49).
*   [CHANGELOG.md](./CHANGELOG.md) — Project commit and feature changelog history.

> Periodic performance audits live under `docs/my-documents/` (git-ignored, local-only). Their conclusions are folded into the ROADMAP findings log, which is the tracked, canonical record.

---

> [!NOTE]
> All automated scheduler files and execution paths in this repository are designed for Windows 11 using PowerShell (`pwsh`) and Command Prompt (`cmd`) scripts.

<p align="center">
  Built with <a href="https://modelcontextprotocol.io">MCP</a> · <a href="https://streamlit.io">Streamlit</a> · <a href="https://kalshi.com">Kalshi API</a>
</p>
