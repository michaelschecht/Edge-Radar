<h1 align="center">
  <br>
  Edge-Radar
  <br>
</h1>

<p align="center">
  <b>Prediction Market & Sports Betting Intelligence Platform</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-Kalshi-blue?style=flat-square" alt="Kalshi">
  <img src="https://img.shields.io/badge/python-3.11+-green?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/status-live%20trading-red?style=flat-square" alt="Live Trading">
  <img src="https://img.shields.io/badge/edge%20model-normal%20CDF-purple?style=flat-square" alt="Normal CDF">
  <img src="https://img.shields.io/badge/license-private-gray?style=flat-square" alt="Private">
</p>

<p align="center">
  Scans thousands of markets. Detects mispricing. Sizes bets. Executes automatically.
</p>

---

## How It Works

```
  Sportsbooks (12 books)          External Data
  ========================        ==============
  Pinnacle | FanDuel | ...        ESPN | NWS | CoinGecko | VIX
        \       |       /              |      |       |
         v      v      v               v      v       v
       +-----------------------------------+
       |  Weighted De-Vig & Consensus      |  Sharp books count 3x
       |  Normal CDF Spread/Total Model    |  Sport-specific stdev
       |  Team Stats Confidence Signal     |  Win% validation
       |  Weather Impact (NFL/MLB)         |  NWS hourly forecasts
       +-----------------------------------+
                      |
                      v
              Fair Value vs Kalshi Price
                      |
                 Edge > 3%?
                /           \
              YES            NO
              |               |
        Risk Gates         Skip
        Kelly Sizing
              |
         EXECUTE on Kalshi
              |
         Log + Track CLV
```

---

## Supported Markets

| Category | Markets | Edge Source | Coverage |
|:---------|:--------|:-----------|:---------|
| **Sports Betting** | NBA, NHL, MLB, NFL, NCAAB, NCAAF, MLS, soccer, UFC, F1, golf | Sportsbook consensus (12 books) | 27 sport filters |
| **Championship Futures** | Super Bowl, NBA Finals, Stanley Cup, World Series, PGA | N-way de-vigged outrights | 7 leagues |
| **Prediction Markets** | BTC, ETH, XRP, DOGE, SOL, weather, S&P 500, politics | CoinGecko, NWS, VIX, time-decay | 11 categories |

---

## Quick Start

```bash
# Install
pip install -r requirements.txt
cp .env.example .env   # fill in KALSHI_API_KEY, ODDS_API_KEYS

# Scan (preview only -- no money risked)
python scripts/kalshi/kalshi_executor.py run --filter nba
python scripts/kalshi/kalshi_executor.py run --filter nba-futures
python scripts/kalshi/kalshi_executor.py run --prediction --filter crypto

# Execute after reviewing preview
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --max-bets 5

# Settle and report
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail --save
```

---

## Edge Detection Features

| Feature | Description |
|:--------|:------------|
| **Normal CDF Model** | Spreads and totals modeled as normal distribution with sport-specific stdev (NBA: 12, NFL: 13.5, MLB: 3.5, NHL: 2.5) |
| **Sharp Book Weighting** | Pinnacle/Circa weighted 3x, DraftKings/FanDuel 0.7x -- sharp lines pull consensus |
| **Team Stats Signal** | ESPN, NHL, MLB APIs provide win% to validate or challenge book consensus |
| **Weather Adjustment** | NWS hourly forecasts for 61 NFL/MLB venues -- wind, rain, cold reduce total scoring expectations |
| **Book Disagreement** | Spread range across books detects injury news and stale lines |
| **CLV Tracking** | Closing Line Value captured at settlement -- validates model accuracy over time |
| **Per-Game Cap** | Top 3 opportunities per matchup to force diversification |

---

## Project Structure

```
Edge-Radar/
├── scripts/
│   ├── kalshi/           # Execution pipeline (scan, size, execute, settle)
│   ├── prediction/       # Crypto, weather, S&P 500, politics edge detectors
│   ├── shared/           # Config, team stats, weather, trade log, odds API
│   └── schedulers/       # Automated per-market recurring pipelines
├── docs/                 # Guides, architecture, CLI reference, changelog
├── data/                 # Trade history, settlements, watchlists
├── reports/              # Generated performance and futures reports
└── .claude/              # Agents, skills, memory for Claude Code
```

---

## Documentation

| | |
|:---|:---|
| **[Scripts Reference](docs/SCRIPTS_REFERENCE.md)** | Every script, flag, and example |
| **[Sports Guide](docs/kalshi-sports-betting/SPORTS_GUIDE.md)** | 27 sport filters, edge detection, workflow |
| **[Futures Guide](docs/kalshi-futures-betting/FUTURES_GUIDE.md)** | NFL, NBA, NHL, MLB, golf championship markets |
| **[Prediction Markets](docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md)** | Crypto, weather, S&P 500, politics |
| **[Architecture](docs/ARCHITECTURE.md)** | Pipeline, risk gates, data flow |
| **[Scheduler Guide](docs/schedulers/SCHEDULER_GUIDE.md)** | Automated per-market scheduling |
| **[Edge Roadmap](docs/enhancements/EDGE_OPTIMIZATION_ROADMAP.md)** | Model improvements (7/9 complete) |
| **[Changelog](docs/CHANGELOG.md)** | Full project history |

---

## External APIs

| API | Purpose | Auth |
|:----|:--------|:-----|
| [Kalshi](https://kalshi.com) | Market data + order execution | API key + RSA signing |
| [The Odds API](https://the-odds-api.com) | Sportsbook odds from 12 US books | Free tier (500 req/mo) |
| [ESPN](http://site.api.espn.com) | Team stats: NBA, NCAAB, NFL, NCAAF | Free, no key |
| [NHL Stats API](https://api-web.nhle.com) | NHL standings, goal differential, L10 | Free, no key |
| [MLB Stats API](https://statsapi.mlb.com) | MLB standings, run differential | Free, no key |
| [NWS](https://weather.gov) | Hourly weather for 61 sports venues | Free, no key |
| [CoinGecko](https://coingecko.com) | Crypto prices + 24h volatility | Free, rate limited |
| [Yahoo Finance](https://finance.yahoo.com) | S&P 500 + VIX implied volatility | Free, no key |

---

<p align="center">
  Built with <a href="https://claude.com/claude-code">Claude Code</a>
</p>
