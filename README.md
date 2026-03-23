<a name="top"></a>

<p align="center">
  <img src=".claude/images/edge-radar-logo.png" alt="Edge-Radar Banner" width="700">
</p>

<h1 align="center">Edge-Radar</h1>

<p align="center">
  <b>Automated Edge Detection & Execution for Prediction Markets</b>
</p>

<p align="center">
  <a href="https://kalshi.com"><img src="https://img.shields.io/badge/Kalshi-Live%20Trading-e74c3c?style=for-the-badge" alt="Kalshi Live Trading"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11+-2ea44f?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="docs/ARCHITECTURE.md"><img src="https://img.shields.io/badge/Edge%20Model-Normal%20CDF-8B5CF6?style=for-the-badge" alt="Normal CDF"></a>
  <a href="docs/enhancements/EDGE_OPTIMIZATION_ROADMAP.md"><img src="https://img.shields.io/badge/Roadmap-8%2F9%20Complete-F97316?style=for-the-badge" alt="Roadmap"></a>
</p>

<p align="center">
  Scans thousands of Kalshi markets &middot; Cross-references 12 sportsbooks &middot; Detects mispricing &middot; Executes automatically
</p>

---

## About

Edge-Radar is an automated edge-detection and execution system for [Kalshi](https://kalshi.com) prediction markets and sports betting. It scans thousands of open markets, cross-references prices against sportsbook consensus odds from 12 US books and 6 free external APIs, identifies mispriced contracts using a normal CDF probability model with sharp book weighting, applies risk gates and position sizing, and executes limit orders -- logging every decision for post-hoc calibration and closing line value tracking.

The system covers **sports betting** (27 sport filters), **championship futures** (NFL, NBA, NHL, MLB, PGA), and **prediction markets** (crypto, weather, S&P 500, politics). All edge detection defaults to preview mode -- no money is risked until you explicitly confirm.

<p align="center">
  <a href="#-supported-markets">Supported Markets</a> &middot;
  <a href="#-edge-detection">Edge Detection</a> &middot;
  <a href="#-quick-start">Quick Start</a> &middot;
  <a href="#️-how-it-works">How It Works</a> &middot;
  <a href="#-documentation">Documentation</a> &middot;
  <a href="#-data-sources">Data Sources</a>
</p>

---

## 📊 Supported Markets

<table>
<tr>
<td width="33%">

### 🏀 Sports Betting
**27 sport filters** across:

NBA, NHL, MLB, NFL, NCAAB, NCAAF, MLS, Champions League, EPL, La Liga, Serie A, Bundesliga, UFC, Boxing, F1, NASCAR, PGA, IPL, Esports

**Edge source:** Sportsbook consensus from 12 US books via The Odds API

</td>
<td width="33%">

### 🏆 Championship Futures
**7 leagues** with outright odds:

- NFL Super Bowl
- NBA Finals + Conference
- NHL Stanley Cup + Conference
- MLB World Series + Playoffs
- PGA Tour events

**Edge source:** N-way de-vigged outright odds

</td>
<td width="33%">

### 🔮 Prediction Markets
**11 categories** including:

- Crypto (BTC, ETH, XRP, DOGE, SOL)
- Weather (13 US cities)
- S&P 500 binary options
- TV mentions, politics
- Companies, tech/science

**Edge source:** CoinGecko, NWS, VIX, time-decay models

</td>
</tr>
</table>

---

## ⚡ Edge Detection

| Feature | How It Works |
|:--------|:-------------|
| **Normal CDF Model** | Spreads and totals modeled as normal distribution with sport-specific stdev — NBA: 12, NFL: 13.5, MLB: 3.5, NHL: 2.5 |
| **Sharp Book Weighting** | Pinnacle/Circa weighted 3x in consensus, DraftKings/FanDuel 0.7x — sharp lines pull fair value |
| **Team Stats Validation** | ESPN, NHL, MLB APIs provide win% — stats that support the bet boost confidence, contradictions reduce it |
| **Sharp Money Detection** | ESPN open vs close odds detect reverse line movement — when sharps are on our side, confidence goes up |
| **Weather Adjustment** | NWS hourly forecasts for 61 NFL/MLB outdoor venues — wind, rain, cold reduce total scoring expectations |
| **Book Disagreement** | When sportsbooks disagree by >4 points, confidence drops — signals injury news or stale lines |
| **Closing Line Value** | CLV captured at settlement to validate whether the model consistently beats the market close |
| **Per-Game Cap** | Top 3 opportunities per matchup by edge — forces diversification across games |

> [!IMPORTANT]
> All edge detection is research-first. Every scan defaults to **preview mode** — no money is risked until you explicitly pass `--execute`.

---

## 🚀 Quick Start

```bash
# 1. Install and configure
pip install -r requirements.txt
cp .env.example .env          # fill in KALSHI_API_KEY, ODDS_API_KEYS

# 2. Scan for opportunities (preview only)
python scripts/kalshi/kalshi_executor.py run --filter nba
python scripts/kalshi/kalshi_executor.py run --filter nba-futures
python scripts/kalshi/kalshi_executor.py run --prediction --filter crypto

# 3. Execute after reviewing the preview table
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --max-bets 5

# 4. Settle and check P&L
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report --detail --save
```

> [!TIP]
> Use `--unit-size 0.50` for smaller bets while testing, and `--min-edge 0.10` for higher-conviction picks only.

---

## 🏗️ How It Works

```
  12 Sportsbooks                    6 Free APIs
  ==================                ==================
  Pinnacle (3x weight)              ESPN  (NBA/NFL/NCAAB/NCAAF)
  Circa    (3x weight)              NHL   (standings, L10)
  BetMGM   (0.7x weight)           MLB   (standings, run diff)
  FanDuel  (0.7x weight)           NWS   (61 venue forecasts)
  DraftKings (0.7x weight)         CoinGecko (crypto vol)
  + 7 more books                    Yahoo Finance (S&P + VIX)
        \       |       /                |       |       |
         v      v      v                 v       v       v
       +----------------------------------------------+
       |          EDGE DETECTION ENGINE                |
       |                                               |
       |  Weighted De-Vig    ->  Consensus Fair Value  |
       |  Normal CDF Model   ->  Spread/Total Probs    |
       |  Team Stats Signal  ->  Confidence Adjust     |
       |  Sharp Money Signal ->  Line Movement Detect  |
       |  Weather Impact     ->  NFL/MLB Total Adjust  |
       |  Book Disagreement  ->  Injury/News Detection |
       +----------------------------------------------+
                          |
                    Fair Value vs Kalshi Price
                          |
                   Edge >= 3%?  ──NO──>  Skip
                          |
                         YES
                          |
                +-----------------+
                |   RISK GATES    |
                |  Daily loss     |
                |  Position limit |
                |  Min score      |
                |  Kelly sizing   |
                +-----------------+
                          |
                  EXECUTE on Kalshi
                          |
                  Log + Track CLV
```

<details>
<summary><b>Project Structure</b></summary>

```
Edge-Radar/
├── scripts/
│   ├── kalshi/              # Execution pipeline
│   │   ├── edge_detector.py     # Normal CDF model, sharp weighting, team stats, weather
│   │   ├── kalshi_executor.py   # Risk gates, sizing, order placement
│   │   ├── kalshi_settler.py    # Settlement, CLV tracking, P&L reports
│   │   ├── futures_edge.py      # Championship N-way de-vig
│   │   ├── kalshi_client.py     # Authenticated Kalshi API client
│   │   ├── fetch_odds.py        # The Odds API integration
│   │   └── risk_check.py        # Portfolio risk dashboard
│   ├── prediction/          # Prediction market edge detectors
│   │   ├── prediction_scanner.py
│   │   ├── crypto_edge.py       # BTC, ETH, XRP, DOGE, SOL
│   │   ├── weather_edge.py      # Temperature markets (13 cities)
│   │   ├── spx_edge.py          # S&P 500 binary options
│   │   └── ...                  # mentions, politics, companies
│   ├── shared/              # Shared modules
│   │   ├── config.py            # Centralized .env configuration
│   │   ├── team_stats.py        # ESPN/NHL/MLB team performance
│   │   ├── sports_weather.py    # NWS weather for 61 venues
│   │   ├── line_movement.py     # ESPN line movement & sharp detection
│   │   ├── odds_api.py          # Multi-key rotation
│   │   └── trade_log.py         # Trade journal I/O
│   └── schedulers/          # Automated recurring pipelines
│       ├── base_scheduler.py    # DRY_RUN enforcement, failure pause
│       ├── sports_scheduler.py  # Per-sport scheduling
│       └── run_schedulers.py    # CLI entry point
├── docs/                    # Guides and references
├── data/                    # Trade history, settlements, watchlists
├── reports/                 # Generated performance and futures reports
└── .claude/                 # Agents, skills, memory
```

</details>

---

## 📖 Documentation

| Guide | Description |
|:------|:------------|
| **[Scripts Reference](docs/SCRIPTS_REFERENCE.md)** | Complete CLI reference — every script, flag, and example |
| **[Sports Guide](docs/kalshi-sports-betting/SPORTS_GUIDE.md)** | 27 sport filters, edge detection walkthrough, daily workflow |
| **[Futures Guide](docs/kalshi-futures-betting/FUTURES_GUIDE.md)** | NFL, NBA, NHL, MLB, golf championship markets |
| **[Prediction Markets](docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md)** | Crypto, weather, S&P 500, politics edge models |
| **[Architecture](docs/ARCHITECTURE.md)** | 7-step pipeline, risk gates, data flow, scoring |
| **[Scheduler Guide](docs/schedulers/SCHEDULER_GUIDE.md)** | Automated per-market scheduling with failure pause |
| **[Edge Roadmap](docs/enhancements/EDGE_OPTIMIZATION_ROADMAP.md)** | Model improvement plan (8/9 items complete) |
| **[Changelog](docs/CHANGELOG.md)** | Full project history |

---

## 🔌 Data Sources

| API | Purpose | Auth | Cost |
|:----|:--------|:-----|:-----|
| [Kalshi](https://kalshi.com) | Market data + order execution | API key + RSA | Free (funded account) |
| [The Odds API](https://the-odds-api.com) | Sportsbook odds from 12 US books | API key | Free (500 req/mo) |
| [ESPN](http://site.api.espn.com) | Team stats + line movement (open/close odds) | None | Free |
| [NHL Stats API](https://api-web.nhle.com) | Standings, goal diff, L10 record | None | Free |
| [MLB Stats API](https://statsapi.mlb.com) | Standings, run differential | None | Free |
| [NWS](https://weather.gov) | Hourly weather for 61 sport venues | None | Free |
| [CoinGecko](https://coingecko.com) | Crypto prices + 24h volatility | None | Free |
| [Yahoo Finance](https://finance.yahoo.com) | S&P 500 price + VIX | None | Free |

---

<p align="center">
  Built with <a href="https://claude.com/claude-code">Claude Code</a> &middot; Powered by <a href="https://kalshi.com">Kalshi</a>
</p>

<p align="center">
  <a href="#top">Back to top</a>
</p>
