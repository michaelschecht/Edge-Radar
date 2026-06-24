# 🔌 Model Context Protocol (MCP) Setup Guide
## Edge-Radar Platform MCP Configurations

<p align="center">
  <img src="https://img.shields.io/badge/MCP-Protocol-blue?style=for-the-badge&logo=ai&logoColor=white" alt="MCP Protocol">
  <img src="https://img.shields.io/badge/OS-Windows_11-0078D4?style=for-the-badge&logo=windows&logoColor=white" alt="Windows 11">
  <img src="https://img.shields.io/badge/Status-Active-2ea44f?style=for-the-badge" alt="Status Active">
</p>

---

## 📖 Overview

Model Context Protocol (MCP) enables LLM environments (like Claude Desktop or Antigravity) to securely interact with the local filesystem, query APIs, perform web research, and execute trades on the **Edge-Radar** platform. 

This guide details all configured MCP servers, their setup, and the unified configuration for `claude_desktop_config.json` on Windows.

---

## 📊 Server Roster

| Priority | Server Name | Category | Purpose |
|:---|:---|:---|:---|
| 🔴 **Essential** | `filesystem` | Core | Read and write positions, logs, scan results, and configuration files |
| 🔴 **Essential** | `fetch` | Core | Execute HTTP queries to Kalshi, Alpaca, and external odds sources |
| 🔴 **Essential** | `memory` | Core | Maintain cross-session context, research notes, and watchlist history |
| 🟡 **Important** | `brave-search` / `serper` | Research | Real-time news aggregation, injury reports, and weather data |
| 🟡 **Important** | `sqlite` | Data | Trade auditing, calibration history, and strategy backtesting logs |
| 🟡 **Important** | `alpaca-mcp` | Execution | Stock, options, and ETF paper and live execution |
| 🟠 **Optional** | `playwright` | Automation | DFS entry automation and web scraping |
| 🟠 **Optional** | `ax-gcp` | Integration | AX platform multi-agent team workspace coordination |

---

## ⚙️ Configuration (`claude_desktop_config.json`)

On Windows, the configuration file is located at:
`%APPDATA%\Claude\claude_desktop_config.json`

Replace `USERNAME` with your actual Windows username and verify the project directory path matches your installation.

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "D:\\AI_Agents\\Specialized_Agents\\Edge_Radar"
      ]
    },
    "fetch": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-fetch"
      ]
    },
    "memory": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-memory"
      ]
    },
    "brave-search": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-brave-search"
      ],
      "env": {
        "BRAVE_API_KEY": "YOUR_BRAVE_API_KEY"
      }
    },
    "sqlite": {
      "command": "uvx",
      "args": [
        "mcp-server-sqlite",
        "--db-path",
        "D:\\AI_Agents\\Specialized_Agents\\Edge_Radar\\data\\finagent.db"
      ]
    },
    "tavily": {
      "command": "npx",
      "args": [
        "-y",
        "tavily-mcp@latest"
      ],
      "env": {
        "TAVILY_API_KEY": "YOUR_TAVILY_API_KEY"
      }
    },
    "playwright": {
      "command": "npx",
      "args": [
        "-y",
        "@playwright/mcp"
      ]
    }
  }
}
```

> [!IMPORTANT]
> - Ensure all absolute Windows paths use double-backslashes (`\\`) in the JSON config.
> - Never commit your API keys to version control. Pass them through `claude_desktop_config.json` or `.env` variables.

---

## 🔍 Per-Server Setup Details

### 1. 📁 `filesystem` — Local File Access
Allows the model to read and write runtime files under the workspace.
- **Exposure scope:**
  - `D:\AI_Agents\Specialized_Agents\Edge_Radar\data\` — Open positions, settlements, and P&L history
  - `D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\` — Scanners, risk checkers, and execution code
  - `D:\AI_Agents\Specialized_Agents\Edge_Radar\app\` — Core domain schemas and config classes

### 2. 🌐 `fetch` — HTTP API Queries
Provides permission-scoped HTTP clients to fetch real-time data.
- **Common endpoints:**
  - Kalshi Trading API: `https://api.elections.kalshi.com/trade-api/v2`
  - The Odds API: `https://api.the-odds-api.com/v4/sports`
  - Alpaca Markets: `https://paper-api.alpaca.markets/v2`

### 3. 🧠 `memory` — Persistent Research Context
Enables long-term recall of active watchlists, backtesting performance logs, and recurring market insights.
- **Namespaces:**
  - `research/ongoing` — Sports trends and market discrepancies
  - `positions/notes` — Rationale for active, open wagers
  - `strategy/learnings` — Backtest outcomes and manual calibration tuning notes

### 4. 🔎 `brave-search` / `serper` — Real-Time Research
Queries the live web for team statistics, injuries, line-ups, and news catalyst feeds.
- **Brave Search API Key:** Obtain from [brave.com/search/api](https://brave.com/search/api/)
- **Serper API Key:** Configure if using Google Search API under the hood

### 5. 🗄️ `sqlite` — Database Queries
Interfaces with the SQLite database for trading history audits and calibration runs.
- **Table schemas:**
  - `trades` — Auditable execution log
  - `positions` — Active exposure and cost basis
  - `model_calibration` — Brier scores and sport standard deviations

### 6. 📈 `alpaca-mcp` — Execution Integration
Regulates order tickets, buying power, and option chain retrievals via Alpaca.
- **Credentials:** Expose `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in the `env` dict.

---

## 🛠️ Troubleshooting Windows MCP Issues

### `spawn npx ENOENT`
If the command `npx` fails to start, specify the absolute path to `npx.cmd`:
- **Path:** `C:\Users\USERNAME\AppData\Roaming\npm\npx.cmd` or `C:\Program Files\nodejs\npx.cmd`
- **Lookup:** Run `where.exe npx` in command prompt or PowerShell to verify where the executable is located.

### Environment variables not loading
MCP servers run in isolated sub-processes. They do not automatically inherit your global Windows environment variables. Ensure any API keys (such as `BRAVE_API_KEY` or `TAVILY_API_KEY`) are explicitly defined in the server's `"env": {}` block.

---

<p align="center">
  Built for <a href="https://github.com/michaelschecht/Edge-Radar">Edge-Radar</a> · <a href="ARCHITECTURE.md">Architecture</a> · <a href="SETUP_GUIDE.md">Setup Guide</a>
</p>
