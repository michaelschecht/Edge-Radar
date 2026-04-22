# Edge-Radar — MCP Servers / APIs / Integrations

## Core Infrastructure

- **AX MCP Server** — Messages and Tasks (inter-agent communication, task delegation, workspace coordination)
- **AX Channel MCP** — Real-time message relay between AX agents and Claude Code sessions
- **GitHub MCP** — Version control, PR management, code search for the Edge-Radar repo (`michaelschecht/Edge-Radar`)
- **Filesystem MCP** — Read/write positions, logs, trade history, reports, watchlists in `data/` directory

## Market Data & Odds

- **The Odds API** — Primary sports odds feed across 27+ sports; line movement, multi-book comparison (API key in `.env`)
- **Kalshi Trading API** — Prediction market prices, orderbooks, trade execution; RSA-signed authentication
- **ESPN API** — Team stats, schedules, injury reports for NBA, NFL, MLB, NHL
- **MLB Stats API** — Pitcher data, bullpen stats, matchup history (pitcher edge detection)
- **NHL Stats API** — Player stats, goalie matchups, team performance metrics
- **CoinGecko API** — Crypto price feeds for BTC, ETH, XRP, DOGE, SOL prediction markets
- **Yahoo Finance API** — S&P 500 data, market indices for financial prediction markets
- **National Weather Service API** — Weather forecasts for 13 cities (weather prediction markets + outdoor sports)

## Cross-Market Research

- **Polymarket CLOB API** — Cross-reference Kalshi pricing against Polymarket for arbitrage detection
- **Serper MCP** — Google search for breaking news, injury reports, event context
- **Context7 MCP** — Library documentation lookup for Python dependencies and API references

## Data Storage & Persistence

- **SQLite** — Local trade history, strategy performance, model calibration database
- **Memory MCP** — Cross-session context: active research threads, monitored markets, data quality notes

## Notifications & Reporting

- **Slack Webhook** — Alert delivery for CRITICAL/WARNING portfolio events
- **Email (Gmail MCP)** — Daily scheduled scan results and performance reports

## Development & Automation

- **Claude Code CLI** — Primary development environment; runs scans, backtests, settlements
- **Windows Task Scheduler** — Automated daily scans (8 AM ET same-day, next-day reserve)
- **Streamlit** — Web dashboard at `edge-radar.streamlit.app` (password-gated, inline PEM)

## Optional / Planned

- **Alpaca MCP** — Stock/options paper + live trading (planned expansion)
- **Brave Search / Tavily** — Alternative real-time web research providers
- **PostgreSQL MCP** — Production database (future migration from SQLite)
