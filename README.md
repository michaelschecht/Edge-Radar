# Finance Agent Pro

Automated sports betting, futures, and prediction market system built on [Kalshi](https://kalshi.com). Scans thousands of markets, detects edge by cross-referencing external data sources, sizes bets with risk management, and executes through the Kalshi API.

**Live trading** on Kalshi with real money. Research-first, execute-second.

---

## What It Does

| Capability | How It Works |
|------------|-------------|
| **Sports betting** | De-vigs sportsbook odds from 8-12 books (The Odds API), compares to Kalshi prices, finds mispricing |
| **Futures betting** | N-way de-vigging of outright championship odds (Super Bowl, NBA, NHL, MLB, golf) |
| **Prediction markets** | Crypto (CoinGecko), weather (NWS), S&P 500 (VIX), TV mentions (historical rates), politics (time-decay) |
| **Risk management** | Position limits, daily loss limits, minimum edge thresholds, composite scoring |
| **Execution** | Automated order placement through Kalshi API with trade logging and settlement tracking |

---

## Quick Start

```bash
# Activate virtual environment
.venv\Scripts\activate  # Windows

# Check your Kalshi balance and positions
python scripts/kalshi/kalshi_executor.py status

# Scan for sports betting opportunities
python scripts/kalshi/kalshi_executor.py run --filter nba

# Scan for NFL Super Bowl futures
python scripts/kalshi/futures_edge.py scan --filter nfl-futures

# Scan prediction markets (crypto, weather, S&P 500)
python scripts/prediction/prediction_scanner.py scan --filter crypto

# Execute bets (after previewing)
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --max-bets 5

# Settle completed bets and check P&L
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail
```

---

## Project Structure

```
Finance_Agent_Pro/
├── scripts/
│   ├── kalshi/                        # Sports & futures betting
│   │   ├── kalshi_client.py           # Authenticated Kalshi API client
│   │   ├── kalshi_executor.py         # Scan -> risk-check -> size -> execute
│   │   ├── kalshi_settler.py          # Settlement, P&L reporting, reconciliation
│   │   ├── edge_detector.py           # Sports edge detection (27 sport filters)
│   │   ├── futures_edge.py            # Championship/futures edge detection
│   │   ├── fetch_odds.py              # The Odds API integration
│   │   ├── fetch_market_data.py       # Multi-asset data fetcher
│   │   └── risk_check.py              # Portfolio risk dashboard
│   ├── prediction/                    # Prediction market edge detection
│   │   ├── prediction_scanner.py      # Unified CLI for all prediction categories
│   │   ├── crypto_edge.py             # BTC, ETH, XRP, DOGE, SOL (CoinGecko)
│   │   ├── weather_edge.py            # Temperature markets (NWS API)
│   │   ├── spx_edge.py                # S&P 500 binary options (Yahoo + VIX)
│   │   ├── mentions_edge.py           # TV mention markets (historical rates)
│   │   ├── companies_edge.py          # Bankruptcy counts, IPOs
│   │   ├── politics_edge.py           # Impeachment, quantum, fusion (time-decay)
│   │   └── probability.py             # Shared probability math
│   └── shared/                        # Shared modules
│       ├── opportunity.py             # Opportunity dataclass (single source of truth)
│       ├── trade_log.py               # Trade log I/O
│       ├── paths.py                   # Standardized path setup
│       ├── config.py                  # Centralized configuration
│       └── logging_setup.py           # File + console logging
├── .claude/
│   ├── agents/
│   │   ├── KALSHI_BETTOR.md           # Dedicated Kalshi betting agent
│   │   ├── MARKET_RESEARCHER.md       # Market research & scanning
│   │   ├── TRADE_EXECUTOR.md          # Order execution
│   │   ├── RISK_MANAGER.md            # Risk gating
│   │   ├── DATA_ANALYST.md            # Quantitative modeling
│   │   └── PORTFOLIO_MONITOR.md       # P&L tracking
│   └── skills/
│       ├── kalshi-bet/                # /kalshi-bet slash command
│       ├── kalshi-markets/            # Market browsing & analysis
│       ├── market-mechanics-betting/  # Betting theory & Kelly criterion
│       └── polymarket/                # Polymarket API reference
├── docs/
│   ├── kalshi-sports-betting/         # Sports betting guides
│   │   ├── BETTING_GUIDE.md           # Sport-by-sport commands (27 filters)
│   │   ├── USER_GUIDE.md              # Daily workflow & system usage
│   │   ├── KALSHI_API_REFERENCE.md    # API endpoints & auth
│   │   └── KALSHI_STRATEGY_PLAN.md    # Architecture & roadmap
│   ├── kalshi-futures-betting/        # Futures & championship guides
│   │   └── FUTURES_GUIDE.md           # NFL, NBA, NHL, MLB, golf futures
│   ├── kalshi-prediction-betting/     # Prediction market guides
│   │   └── PREDICTION_MARKETS_GUIDE.md
│   └── CHANGELOG.md
├── data/
│   ├── history/                       # Trade logs & settlements (gitignored)
│   └── watchlists/                    # Saved opportunity scans (gitignored)
├── CLAUDE.md                          # Master project instructions
├── .env                               # API keys & config (gitignored)
└── .env.example                       # Template for required env vars
```

---

## Sports Betting

27 sport filters with automated edge detection via sportsbook odds cross-referencing:

| Sport | Filter | Edge Detection |
|-------|--------|----------------|
| NBA | `nba` | Games, spreads, totals, player props |
| NHL | `nhl` | Games, spreads, totals, player props |
| MLB | `mlb` | Games |
| NFL | `nfl` | Games, spreads, totals *(seasonal)* |
| NCAA Men's Basketball | `ncaamb` | Games, spreads, totals |
| NCAA Women's Basketball | `ncaawb` | Games |
| NCAA Football | `ncaafb` | Games *(seasonal)* |
| MLS | `mls` | Games, spreads, totals |
| UFC | `ufc` | Fight winners |
| Boxing | `boxing` | Fight winners |
| Esports (CS2, LoL) | `esports` | Map/match winners |

Plus soccer leagues, F1, NASCAR, PGA, IPL. See [docs/kalshi-sports-betting/BETTING_GUIDE.md](docs/kalshi-sports-betting/BETTING_GUIDE.md) for the full list.

---

## Futures Betting

Championship and season-long markets with N-way de-vigged outright odds:

| Filter | Market | Odds Source |
|--------|--------|-------------|
| `nfl-futures` / `superbowl` | NFL Super Bowl winner | Sportsbook outrights |
| `nba-futures` | NBA Conference winners | Sportsbook outrights |
| `nhl-futures` | NHL Conference winners | Sportsbook outrights |
| `mlb-futures` | MLB Playoff qualifiers | Sportsbook outrights |
| `ncaab-futures` | NCAAB Most Outstanding Player | Sportsbook outrights |
| `golf-futures` | PGA tournament winners | Sportsbook outrights |

Browse-only (no automated edge): NBA/NHL awards, NFL MVP, Heisman, soccer leagues, F1, NASCAR, IPL. See [docs/kalshi-futures-betting/FUTURES_GUIDE.md](docs/kalshi-futures-betting/FUTURES_GUIDE.md).

---

## Prediction Markets

Non-sports markets with dedicated edge detection models:

| Filter | Category | Data Source |
|--------|----------|-------------|
| `crypto` | BTC, ETH, XRP, DOGE, SOL | CoinGecko (realized vol model) |
| `weather` | NYC, Chicago, Miami, Denver temps | NWS forecasts |
| `spx` | S&P 500 binary options | Yahoo Finance + VIX |
| `mentions` | TV word count / mention markets | Historical settlement rates |
| `companies` | Corporate bankruptcy counts | Historical baseline |
| `politics` | Impeachment timelines | Time-decay hazard model |
| `techscience` | Quantum computing, nuclear fusion | Time-decay hazard model |

See [docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md](docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md).

---

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```env
KALSHI_API_KEY=<your-key-id>
KALSHI_PRIVATE_KEY_PATH=keys/live/kalshi_private.key
KALSHI_BASE_URL=https://api.elections.kalshi.com/trade-api/v2
ODDS_API_KEY=<your-odds-api-key>
UNIT_SIZE=1.00
MAX_BET_SIZE_PREDICTION=5
DRY_RUN=false
```

See `.env.example` for all available settings including risk limits, scoring thresholds, and logging.

---

## Claude Code Integration

This project is built for [Claude Code](https://claude.com/claude-code) with:

- **Agents** -- `KALSHI_BETTOR` for dedicated betting sessions (`claude --agent kalshi-bettor`)
- **Skills** -- `/kalshi-bet nba`, `/kalshi-bet nfl-futures`, `/kalshi-bet crypto`
- **CLAUDE.md** -- master instructions for project context

---

## External APIs

| API | Purpose | Cost |
|-----|---------|------|
| [Kalshi](https://kalshi.com) | Market data + order execution | Free (funded account required) |
| [The Odds API](https://the-odds-api.com) | Sportsbook odds (8-12 books) | Free tier: 500 req/month |
| [CoinGecko](https://coingecko.com) | Crypto prices + history | Free (rate limited) |
| [NWS](https://weather.gov) | Weather forecasts | Free, no key |
| [Yahoo Finance](https://finance.yahoo.com) | S&P 500 + VIX | Free, no key |
