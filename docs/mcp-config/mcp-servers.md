# MCP Servers — FinAgent Platform
## Reference, Configuration & Setup Guide

---

## Overview

This file documents all MCP servers used by the FinAgent platform, their purpose, installation commands, and configuration snippets for `claude_desktop_config.json` on Windows/WSL.

---

## Server Roster

| Priority | Server | Category | Purpose |
|---|---|---|---|
| 🔴 Essential | `filesystem` | Core | Read/write positions, logs, data files |
| 🔴 Essential | `fetch` | Core | HTTP requests to market APIs |
| 🔴 Essential | `memory` | Core | Cross-session position & research memory |
| 🟡 Important | `brave-search` | Research | Real-time news, injury reports |
| 🟡 Important | `sqlite` | Data | Trade history & strategy database |
| 🟡 Important | `alpaca-mcp` | Execution | Stock/options paper + live trading |
| 🟠 Optional | `tavily` | Research | AI-powered search for deep research |
| 🟠 Optional | `postgres` | Data | Production database (when scaling) |
| 🟠 Optional | `ax-gcp` | Coordination | AX Platform workspace integration |
| 🟠 Optional | `playwright` | Automation | DFS entry automation, web scraping |

---

## Complete claude_desktop_config.json

```json
{
  "mcpServers": {

    "filesystem": {
      "command": "C:\\Users\\USERNAME\\AppData\\Roaming\\npm\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "C:\\Projects\\financial-agent-project"
      ]
    },

    "fetch": {
      "command": "C:\\Users\\USERNAME\\AppData\\Roaming\\npm\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-fetch"
      ]
    },

    "memory": {
      "command": "C:\\Users\\USERNAME\\AppData\\Roaming\\npm\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ]
    },

    "brave-search": {
      "command": "C:\\Users\\USERNAME\\AppData\\Roaming\\npm\\npx.cmd",
      "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search"
      ],
      "env": {
        "BRAVE_API_KEY": "${BRAVE_API_KEY}"
      }
    },

    "sqlite": {
      "command": "uvx",
      "args": [
        "mcp-server-sqlite",
        "--db-path",
        "C:\\Projects\\financial-agent-project\\data\\finagent.db"
      ]
    },

    "tavily": {
      "command": "C:\\Users\\USERNAME\\AppData\\Roaming\\npm\\npx.cmd",
      "args": [
        "-y",
        "tavily-mcp@0.1.4"
      ],
      "env": {
        "TAVILY_API_KEY": "${TAVILY_API_KEY}"
      }
    },

    "ax-gcp": {
      "command": "C:\\Users\\USERNAME\\AppData\\Roaming\\npm\\npx.cmd",
      "args": [
        "-y",
        "@ax-platform/ax-gcp-mcp"
      ],
      "env": {
        "AX_API_KEY": "${AX_API_KEY}",
        "AX_WORKSPACE_ID": "${AX_WORKSPACE_ID}"
      }
    },

    "playwright": {
      "command": "C:\\Users\\USERNAME\\AppData\\Roaming\\npm\\npx.cmd",
      "args": [
        "-y",
        "@playwright/mcp@latest"
      ]
    }

  }
}
```

> **Windows Note:** Always use full absolute paths for `command`. Replace `USERNAME` with your actual Windows username. For WSL-based servers, use `wsl.exe` as the command with the appropriate WSL path.

---

## Per-Server Setup Details

### 1. `filesystem` — Local File Access
```bash
npm install -g @modelcontextprotocol/server-filesystem
```
**What it enables:** Reading/writing all project files — positions, trade history, reports, watchlists, strategies.

**Key paths to expose:**
- `C:\Projects\financial-agent-project\data\` — live data
- `C:\Projects\financial-agent-project\strategies\` — strategy configs
- `C:\Projects\financial-agent-project\scripts\` — utility scripts

---

### 2. `fetch` — HTTP API Calls
```bash
npm install -g @modelcontextprotocol/server-fetch
```
**What it enables:** Direct HTTP calls to any market API endpoint — odds APIs, Polymarket CLOB, Kalshi, Alpaca, Coinbase.

**Common usage patterns:**
```
# Check odds on The Odds API
GET https://api.the-odds-api.com/v4/sports/basketball_nba/odds?apiKey={KEY}&regions=us&markets=h2h,spreads,totals

# Polymarket market list
GET https://clob.polymarket.com/markets?limit=20&active=true

# Alpaca account info (paper)
GET https://paper-api.alpaca.markets/v2/account
Headers: APCA-API-KEY-ID, APCA-API-SECRET-KEY
```

---

### 3. `memory` — Persistent Context
```bash
npm install -g @modelcontextprotocol/server-memory
```
**What it enables:** Cross-session memory for ongoing research threads, active watchlists, model notes, and agent state that doesn't fit in files.

**Key memory namespaces:**
- `research/ongoing` — Research threads in progress
- `positions/notes` — Manual notes on open positions
- `strategy/learnings` — Observed patterns and model updates
- `market/watchlist` — Items being monitored but not yet positions

---

### 4. `brave-search` — Real-Time Web Research
**Get API key:** https://brave.com/search/api/
```bash
npm install -g @modelcontextprotocol/server-brave-search
```
**What it enables:** Breaking news, injury reports, game previews, earnings news, prediction market research.

**Best for:**
- "Latest injury report [player name]"
- "[Team] vs [Team] preview analysis"
- "[Company] earnings forecast"
- "Polymarket [event] current market"

---

### 5. `sqlite` — Trade Database
```bash
pip install mcp-server-sqlite
# or
uvx mcp-server-sqlite
```
**What it enables:** Structured queries across trade history, strategy performance, and model calibration data.

**Core tables to create on init:**
```sql
-- Run scripts/init_db.sql on project setup
CREATE TABLE trades (...);
CREATE TABLE strategy_performance (...);
CREATE TABLE model_calibration (...);
CREATE TABLE daily_risk_reports (...);
```

---

### 6. `alpaca-mcp` — Stock/Options Trading
**Community MCP server for Alpaca Markets**

Install options:
```bash
# Option A: pip
pip install alpaca-mcp-server

# Option B: Clone and run
git clone https://github.com/YOUR_SOURCE/alpaca-mcp
cd alpaca-mcp && pip install -e .
```

**Required env vars:**
```
ALPACA_API_KEY=your_key
ALPACA_SECRET_KEY=your_secret
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # use paper until ready
```

**What it enables:**
- Place market/limit/stop orders
- Get account info and positions
- Stream real-time quote data
- Options chain data

---

### 7. `tavily` — AI-Powered Research
**Get API key:** https://tavily.com
```bash
npm install -g tavily-mcp
```
**What it enables:** Deep research queries that aggregate multiple sources — better than Brave for complex research questions like "What factors affect NBA totals in cold weather arenas?"

---

### 8. `ax-gcp` — AX Platform Workspace
```bash
npm install -g @ax-platform/ax-gcp-mcp
```
**What it enables:** Post updates to AX workspace, coordinate with other agents/tools in the platform, log significant events to workspace message board.

---

### 9. `playwright` — Browser Automation
```bash
npm install -g @playwright/mcp
npx playwright install chromium
```
**What it enables:** Automate DFS lineup entry, scrape odds pages without APIs, verify bet placement on platforms without APIs.

> ⚠️ Always verify TOS before automating any platform. Use responsibly.

---

## Environment Variables (.env template)

```bash
# === MARKET DATA ===
ODDS_API_KEY=                        # https://the-odds-api.com
RAPIDAPI_KEY=                        # https://rapidapi.com
SPORTRADAR_API_KEY=                  # https://sportradar.com

# === PREDICTION MARKETS ===
POLYMARKET_PRIVATE_KEY=              # Polygon wallet private key
KALSHI_API_KEY=                      # https://kalshi.com/api
KALSHI_API_SECRET=

# === STOCK/OPTIONS TRADING ===
ALPACA_API_KEY=                      # https://alpaca.markets
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# === CRYPTO ===
COINBASE_API_KEY=                    # https://docs.cloud.coinbase.com
COINBASE_API_SECRET=

# === DFS (data only — entry manual or via Playwright) ===
DRAFTKINGS_USERNAME=
FANDUEL_USERNAME=

# === RESEARCH ===
BRAVE_API_KEY=                       # https://brave.com/search/api
TAVILY_API_KEY=                      # https://tavily.com

# === INFRASTRUCTURE ===
AX_API_KEY=                          # AX Platform
AX_WORKSPACE_ID=
DATABASE_URL=sqlite:///data/finagent.db

# === SYSTEM ===
DRY_RUN=true                         # ALWAYS start true
MONITOR_INTERVAL=5                   # Minutes between position checks
LOG_LEVEL=INFO
```

---

## Troubleshooting Common MCP Issues (Windows)

### `spawn npx ENOENT`
Use full absolute path to `npx.cmd`:
```
C:\Users\USERNAME\AppData\Roaming\npm\npx.cmd
```
Find your path: run `where npx` in PowerShell

### `uvx` not found
Install via pip: `pip install uv`
Then use full path: `C:\Users\USERNAME\.local\bin\uvx.exe`

### Environment variables not loading
In `claude_desktop_config.json`, use `"env": {}` block per server.
Don't rely on system PATH for env vars — specify them explicitly per server config.

### WSL-based servers
```json
{
  "command": "wsl.exe",
  "args": ["-e", "bash", "-c", "cd /home/user/project && node server.js"],
  "env": { "KEY": "value" }
}
```

---

## MCP Servers — Future / Nice-to-Have

| Server | When to Add | Purpose |
|---|---|---|
| `postgres` | When scaling beyond SQLite | Production database |
| `slack` or `discord` | When adding team alerts | Bet alerts, P&L notifications |
| `google-sheets` | When sharing reports | Stakeholder P&L reporting |
| `neon` / `supabase` | Cloud DB option | Hosted PostgreSQL alternative |
| Custom `polymarket-mcp` | When prediction market activity grows | Full Polymarket CLOB integration |
| Custom `kalshi-mcp` | For regulated prediction markets | Full Kalshi trading API |
