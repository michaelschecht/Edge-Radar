# Edge-Radar

Automated sports betting, futures, and prediction market system built on [Kalshi](https://kalshi.com). Scans thousands of markets, detects edge by cross-referencing external data sources, sizes bets with risk management, and executes through the Kalshi API.

**Live trading** on Kalshi with real money. Research-first, execute-second.

---

## What It Does

| Capability | How It Works |
|---|---|
| Sports betting | De-vigs sportsbook odds from 8-12 books (The Odds API), compares to Kalshi prices, finds mispricing |
| Futures betting | N-way de-vigging of outright championship odds (Super Bowl, NBA, NHL, MLB, golf) |
| Prediction markets | Crypto (CoinGecko), weather (NWS), S&P 500 (VIX), TV mentions, politics (time-decay) |
| Risk management | Position limits, daily loss limits, minimum edge thresholds, composite scoring |
| Execution | Automated order placement through Kalshi API with trade logging and settlement tracking |

---

## Quick Start

```bash
# 1. Install dependencies and configure credentials
pip install -r requirements.txt
cp .env.example .env   # then fill in KALSHI_API_KEY, ODDS_API_KEY, etc.

# 2. Scan for sports betting opportunities (NBA example)
python scripts/kalshi/kalshi_executor.py run --filter nba

# 3. Scan prediction markets (crypto, weather, S&P 500)
python scripts/prediction/prediction_scanner.py scan --filter crypto

# 4. Execute bets after previewing results
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --max-bets 5

# 5. Check settlement results and P&L
python scripts/kalshi/kalshi_settler.py report --detail
```

See `.env.example` for all available settings including risk limits, scoring thresholds, and logging.

---

## Documentation

| Document | Description |
|---|---|
| [Scripts Reference](docs/SCRIPTS_REFERENCE.md) | Complete CLI reference for every script and flag |
| [Sports Guide](docs/kalshi-sports-betting/SPORTS_GUIDE.md) | Sports betting guide -- filters, edge detection, workflow |
| [Futures Guide](docs/kalshi-futures-betting/FUTURES_GUIDE.md) | Championship and futures markets |
| [Prediction Markets Guide](docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md) | Crypto, weather, S&P 500 predictions |
| [Architecture](docs/ARCHITECTURE.md) | System architecture and pipeline |
| [Kalshi API Reference](docs/kalshi-sports-betting/KALSHI_API_REFERENCE.md) | Kalshi API technical reference |
| [Scheduler Guide](docs/schedulers/SCHEDULER_GUIDE.md) | Automated scheduler framework |
| [Edge Optimization Roadmap](docs/enhancements/EDGE_OPTIMIZATION_ROADMAP.md) | Future improvements roadmap |
| [Changelog](docs/CHANGELOG.md) | Project history |

---

## Claude Code Integration

This project is built for [Claude Code](https://claude.com/claude-code) with:

- **Agents** -- `KALSHI_BETTOR` for dedicated betting sessions (`claude --agent kalshi-bettor`)
- **Skills** -- `/kalshi-bet nba`, `/kalshi-bet nfl-futures`, `/kalshi-bet crypto`
- **CLAUDE.md** -- master instructions for project context

---

## External APIs

| API | Purpose | Cost |
|---|---|---|
| [Kalshi](https://kalshi.com) | Market data + order execution | Free (funded account required) |
| [The Odds API](https://the-odds-api.com) | Sportsbook odds (8-12 books) | Free tier: 500 req/month |
| [CoinGecko](https://coingecko.com) | Crypto prices + history | Free (rate limited) |
| [NWS](https://weather.gov) | Weather forecasts | Free, no key |
| [Yahoo Finance](https://finance.yahoo.com) | S&P 500 + VIX | Free, no key |
