# 📖 Edge-Radar Documentation

<p align="center">
  <img src="https://img.shields.io/badge/Documentation-Index-0078d4?style=for-the-badge&labelColor=09090b" alt="Documentation Index">
  <img src="https://img.shields.io/badge/Platform-Kalshi-e74c3c?style=for-the-badge&labelColor=09090b" alt="Platform">
  <img src="https://img.shields.io/badge/Stack-Python%20%7C%20Streamlit-2ea44f?style=for-the-badge&labelColor=09090b" alt="Stack">
  <img src="https://img.shields.io/badge/Status-Active%20Execution-8b5cf6?style=for-the-badge&labelColor=09090b" alt="Status">
</p>

Welcome to the central documentation index for **Edge-Radar**. This index organizes the setup manuals, strategy guides, system architecture definitions, and repository analyses.

---

## 🏗️ Pipeline & Data Flow

The diagram below outlines how the Edge-Radar pipeline runs dynamically, from market scanning to execution and post-hoc calibration:

```mermaid
flowchart TD
    %% Nodes definition
    Markets["📡 Open Kalshi Markets"]
    Consensus["🏀 Sportsbooks Consensus\n(8-12 Odds Feeds)"]
    Models["🧠 Edge Models\n(Normal CDF, Devig, Volatility)"]
    
    Scan["🔍 Unified Scanner\n(scripts/scan.py)"]
    
    subgraph SIZING_GATING ["🛡️ Risk Sizing & Gating"]
        G1{"1. Daily Loss Limit?"}
        G2{"2. Max Open Positions?"}
        G3{"3. Min Edge / Price?"}
        G4{"4. Sizing Caps?\n(Max Bet / Batched Kelly)"}
    end
    
    Executor["⚙️ Kalshi Executor\n(kalshi_executor.py)"]
    DB[("💾 Trade & Settlement Logs\n(data/history/)")]
    
    WebUI["💻 Dashboard (webapp/)"]
    Calib["📊 Calibrator\n(model_calibration.py)"]

    %% Connections
    Markets & Consensus --> Scan
    Scan -->|Formulate Opportunity| Models
    Models -->|Fair Value Prob| G1
    G1 -- "Pass" --> G2
    G2 -- "Pass" --> G3
    G3 -- "Pass" --> G4
    G4 -->|Approved Bet Order| Executor
    
    Executor -->|Place Limit Orders| Markets
    Executor -->|Log Trades| DB
    
    DB -->|Read Performance| WebUI
    DB -->|Calibrate Stdevs| Calib
    Calib -->|Feedback Tuning| Models

    %% Styles
    classDef primary fill:#0078d4,stroke:#0284c7,stroke-width:2px,color:#fff;
    classDef secondary fill:#e74c3c,stroke:#b91c1c,stroke-width:2px,color:#fff;
    classDef storage fill:#27272a,stroke:#52525b,stroke-width:2px,color:#fff;
    classDef highlight fill:#8b5cf6,stroke:#6d28d9,stroke-width:2px,color:#fff;
    
    class Scan,Models primary;
    class G1,G2,G3,G4 secondary;
    class DB storage;
    class Calib highlight;
```

---

## 🗺️ Documentation Directory

### 🚀 Setup & Automation
*   [SETUP_GUIDE.md](./setup/SETUP_GUIDE.md) — Step-by-step instructions to configure API keys, venv, and RSA private credentials.
*   [AUTOMATION_GUIDE.md](./setup/AUTOMATION_GUIDE.md) — Setting up the automated scanners and schedulers.
*   [task-schedules.md](./setup/task-schedules.md) — Reference for Windows Task Scheduler cron entries.

### 🧠 Edge Models & Market Guides
*   [SPORTS_GUIDE.md](./kalshi/kalshi-sports-betting/SPORTS_GUIDE.md) — Sports betting edge model: weighted de-vig consensus, CDF spreads/totals, and sportsbook weighting tiers.
*   [MLB_FILTERING_GUIDE.md](./kalshi/kalshi-sports-betting/MLB_FILTERING_GUIDE.md) — Detailed pitcher/matchup and weather filtering for baseball wagers.
*   [FUTURES_GUIDE.md](./kalshi/kalshi-futures-betting/FUTURES_GUIDE.md) — Championship and division futures de-vigging models.
*   [PREDICTION_MARKETS_GUIDE.md](./kalshi/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md) — Scanners for Weather (NWS), Crypto (CoinGecko), and S&P 500 options.

### ⚙️ Architecture & CLI References
*   [ARCHITECTURE.md](./ARCHITECTURE.md) — In-depth overview of the 7-stage pipeline, Kelly sizing equations, and risk gating conditions.
*   [SCRIPTS_REFERENCE.md](./SCRIPTS_REFERENCE.md) — Complete CLI reference list of all script arguments, flags, and batch commands.

### 💻 Web App
*   [LOCAL.md](./web-app/LOCAL.md) — Running the local Streamlit dashboard web interface.
*   [CLOUD.md](./web-app/CLOUD.md) — Streamlit Cloud deployment guide.

### 📈 Reports & Analysis
*   [ROADMAP.md](./enhancements/ROADMAP.md) — Priorities, consolidated action items, and completed milestones history.
*   [CHANGELOG.md](./CHANGELOG.md) — Project commit and feature changelog history.
*   [analysis-6_23_26.md](./my-documents/repo-analysis/analysis-6_23_26.md) — 90-day comprehensive performance audit and logic recommendations.
*   [analysis-5_2_26.md](./my-documents/repo-analysis/analysis-5_2_26.md) — Legacy codebase audit.

---

> [!NOTE]
> All automated scheduler files and execution paths in this repository are designed for Windows 11 using PowerShell (`pwsh`) and Command Prompt (`cmd`) scripts.

<p align="center">
  Built with <a href="https://modelcontextprotocol.io">MCP</a> · <a href="https://streamlit.io">Streamlit</a> · <a href="https://kalshi.com">Kalshi API</a>
</p>
