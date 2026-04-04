# Edge-Radar

**Automated Edge Detection & Execution for Prediction Markets**

[![Kalshi Live Trading](https://img.shields.io/badge/Kalshi-Live%20Trading-e74c3c?style=flat-square)](https://kalshi.com)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-2ea44f?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Normal CDF](https://img.shields.io/badge/Edge%20Model-Normal%20CDF-8B5CF6?style=flat-square)](docs/ARCHITECTURE.md)
[![Markets](https://img.shields.io/badge/Markets-27%20Sports-0078D4?style=flat-square)](#-supported-markets)
[![Edge Detection](https://img.shields.io/badge/Edge-7%20Signals-8B5CF6?style=flat-square)](#-edge-detection)
[![Risk Gates](https://img.shields.io/badge/Risk-9%20Gates%20%2B%20Kelly-e74c3c?style=flat-square)](#%EF%B8%8F-risk--position-sizing)
[![Docs](https://img.shields.io/badge/Docs-8%20Guides-6B7280?style=flat-square)](#-documentation)
[![APIs](https://img.shields.io/badge/APIs-9%20Free-F97316?style=flat-square)](#-data-sources)

<p align="center">
  <img src=".claude/images/logos/logo.png" alt="Edge-Radar Banner" width="600">
</p>

> Scans thousands of Kalshi markets, cross-references 12 sportsbooks + 7 free APIs (including Polymarket), identifies mispriced contracts with a normal CDF probability model, sizes bets with quarter-Kelly criterion, enforces 9 risk gates, and executes limit orders — logging every decision for closing line value tracking.

---

## 📊 Supported Markets

| 🏀 Sports Betting | 🏆 Championships | 🔮 Prediction Markets |
| --- | --- | --- |
| NFL, NBA, and MLB | NFL Super Bowl | Cryptocurrency |
| NCAAB & NCAAF | NBA Finals | US Stock Market |
| UFC and Boxing | NHL Stanley Cup | Politics |
| NHL and Soccer | MLB World Series | Weather |
| Golf & NASCAR | PGA Tour | TV and Pop Culture |

---

## ⚡ Edge Detection

|  | Feature | Description |
| --- | --- | --- |
| 📐 | **Normal CDF Model** | Spread/total probabilities via bell curve with sport-specific stdev |
| ⚖️ | **Sharp Book Weighting** | Pinnacle 3x, DraftKings 0.7x — sharp lines pull consensus |
| 📈 | **Team Stats** | ESPN/NHL/MLB win% validates or challenges book fair value |
| 💰 | **Sharp Money** | ESPN open-vs-close odds detect reverse line movement |
| 🌧️ | **Weather** | NWS forecasts for 61 NFL/MLB venues adjust total expectations |
| ⚠️ | **Book Disagreement** | >4pt spread range across books flags injury news |
| 📊 | **CLV Tracking** | Closing line value validates model accuracy over time |

> [!IMPORTANT]
> Every scan defaults to **preview mode**. No money is risked until you pass `--execute`.

---

## 🛡️ Risk & Position Sizing

### Quarter-Kelly Sizing

Bet size scales with edge strength. Higher-edge opportunities get more capital; marginal edges stay at the minimum unit. This is the core differentiator — flat sizing leaves money on the table.

```
bet_size = max(unit_size, 0.25 × edge × bankroll)
```

| Edge | Bankroll $50 | Contracts @ $0.40 | vs Flat ($0.50 unit) |
| --- | --- | --- | --- |
| 3% | $0.38 | 1 (flat floor) | Same |
| 8% | $1.00 | 3 | 2x more |
| 15% | $1.88 | 5 | 4x more |
| 25% | $3.13 | 8 | 7x more |

The result is capped by max bet size ($50 sports / $100 prediction), max concentration (20% of bankroll), and available balance.

### 9 Risk Gates

Every order must pass all nine gates before execution:

|  | Gate | What it blocks |
| --- | --- | --- |
| 1 | **Daily loss limit** | No new bets after -$250 today |
| 2 | **Position count** | Max 10 concurrent open positions |
| 3 | **Edge threshold** | Minimum 3% edge required |
| 4 | **Composite score** | Must score 6.0+ across edge, confidence, liquidity |
| 5 | **Confidence floor** | Medium or higher — requires 5+ books agreeing |
| 6 | **Duplicate check** | Can't double up on the same market |
| 7 | **Per-event cap** | Max 2 positions on the same game |
| 8 | **Concentration limit** | No single position > 20% of bankroll |
| 9 | **Bet size cap** | $50/sports, $100/prediction hard ceiling |

All limits are configurable via `.env`. See [Architecture](docs/ARCHITECTURE.md) for details on how scoring, confidence, and sizing interact.

---

## 🚀 Quick Start

> **New here?** See the full **[Setup Guide](docs/setup/SETUP_GUIDE.md)** for step-by-step instructions on API keys, private key generation, environment configuration, and your first scan.

```bash
# 1. Install and configure
pip install -r requirements.txt
cp .env.example .env  # See setup guide for API key instructions

# 2. Verify everything works
python scripts/doctor.py

# 3. Scan for opportunities (preview only)
python scripts/scan.py sports --filter nba

# 4. Execute after reviewing
python scripts/scan.py sports --filter nba --execute --unit-size 1 --max-bets 5

# 5. Settle and check P&L
python scripts/kalshi/kalshi_settler.py report --detail --save
```

> [!TIP]
> All scanners share the same flags: `--execute`, `--unit-size`, `--max-bets`, `--pick`, `--ticker`, `--save`, `--date`, `--exclude-open`. Use `--date tomorrow --exclude-open` to avoid double-betting.

<details>
<summary><b>More Examples</b></summary>

**Sports Betting**

```bash
# Scan any sport directly
python scripts/scan.py sports --filter nhl
python scripts/scan.py sports --filter mlb
python scripts/scan.py sports --filter ncaamb

# Execute with custom sizing
python scripts/scan.py sports --filter mlb --execute --unit-size 1 --max-bets 10

# Tomorrow's games only, skip games you already bet on
python scripts/scan.py sports --filter mlb --date tomorrow --exclude-open

# Save scan results to watchlist
python scripts/scan.py sports --filter nba --save
```

**Championship Futures**

```bash
# Scan futures markets
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py futures --filter nhl-futures

# Execute futures picks
python scripts/scan.py futures --filter mlb-futures --execute --unit-size 2 --max-bets 5

# Save futures scan to watchlist
python scripts/scan.py futures --filter nba-futures --save
```

**Prediction Markets**

```bash
# Scan by category
python scripts/scan.py prediction --filter crypto
python scripts/scan.py prediction --filter weather
python scripts/scan.py prediction --filter spx

# Execute with sizing
python scripts/scan.py prediction --filter crypto --execute --unit-size 1 --max-bets 5

# Cross-reference against Polymarket
python scripts/scan.py prediction --filter crypto --cross-ref
```

**Polymarket Cross-Reference**

```bash
# Scan for cross-market edges
python scripts/scan.py polymarket
python scripts/scan.py polymarket --filter crypto

# Execute Polymarket-validated picks
python scripts/scan.py polymarket --execute --unit-size 1 --max-bets 5

# Save results and find matches
python scripts/scan.py polymarket --save
python scripts/polymarket/polymarket_edge.py match KXBTC-28MAR26-T88000
```

**Portfolio Management**

```bash
# Check portfolio status & open positions
python scripts/kalshi/kalshi_executor.py status

# Save status as markdown report
python scripts/kalshi/kalshi_executor.py status --save

# Risk dashboard (full or filtered)
python scripts/kalshi/risk_check.py
python scripts/kalshi/risk_check.py --report positions
python scripts/kalshi/risk_check.py --save

# Settle completed bets and update P&L
python scripts/kalshi/kalshi_settler.py settle

# Full performance report (saves markdown to reports/Accounts/Kalshi/)
python scripts/kalshi/kalshi_settler.py report --detail --save
```

</details>

---

## 🤖 Claude Code Skill

Edge-Radar includes a built-in `/edge-radar` slash command for [Claude Code](https://claude.ai/claude-code) that provides a natural language interface to the entire system. Type `/edge-radar` followed by what you want to do:

```
/edge-radar status                          # Balance, open positions, P&L
/edge-radar scan nba                        # Preview NBA opportunities
/edge-radar bet mlb --unit-size 1           # Scan MLB + execute on confirm
/edge-radar settle                          # Settle bets + P&L report
/edge-radar risk                            # Full risk dashboard
/edge-radar detail KXNBAGAME-26APR01-...    # Deep dive on a single market
/edge-radar crypto --cross-ref              # Prediction markets + Polymarket xref
```

The skill routes natural language to the correct scanner, enforces all risk gates, and always previews before executing. All flags (`--date`, `--exclude-open`, `--pick`, `--save`, etc.) work inline. Or just describe what you want in plain English — Claude handles the routing.

> [!NOTE]
> Requires [Claude Code](https://claude.ai/claude-code) CLI, Desktop, or IDE extension. The skill is defined in `.claude/skills/edge-radar/SKILL.md`.
>
> **Using Gemini CLI or OpenAI Codex?** The `/edge-radar` slash command is Claude Code-specific, but the commands and workflows are the same. Add the skill content from `.claude/skills/edge-radar/SKILL.md` to your `GEMINI.md` or `AGENTS.md` file to get equivalent functionality in those tools.

---

## 🔄 Automated Daily Execution

Pre-built scripts scan NFL, NBA, NHL, and MLB in a single command, rank the top 10 opportunities across all sports by composite score, and execute with Kelly sizing.

```bash
# Preview today's best picks (no bets placed)
scripts\schedulers\same_day_executions\same_day_scan.bat

# Scan + execute (places live orders via Kalshi API)
scripts\schedulers\same_day_executions\same_day_execute.bat
```

**Recommended schedule:** 8 AM ET via Windows Task Scheduler. By 8 AM, all markets are posted, sportsbooks have sharpened lines overnight, and Kalshi's lag window is open.

```bash
schtasks /Create /TN "Edge-Radar\Daily" /TR "path\to\same_day_execute.bat" /SC DAILY /ST 08:00
```

Reports save to `reports/Sports/schedulers/same-day-executions/` with full execution details (Sport, Bet, Type, Pick, Qty, Price, Cost, Edge).

---

## 🏗️ How It Works

```
  12 Sportsbooks                     7 Free APIs
  ─────────────────                  ──────────────────
  Pinnacle  (3x)                     ESPN    (standings + line movement)
  Circa     (3x)                     NHL API (goal diff, L10)
  BetMGM    (0.7x)                   MLB API (run diff)
  FanDuel   (0.7x)                   NWS     (61 venue forecasts)
  DraftKings (0.7x)                  CoinGecko (crypto volatility)
  + 7 more books                     Yahoo Finance (S&P 500 + VIX)
                                     Polymarket (cross-market prices)
          |                                  |
          v                                  v
  +------------------------------------------------+
  |           EDGE DETECTION ENGINE                 |
  |                                                 |
  |   Weighted De-Vig   ──>  Fair Value Consensus   |
  |   Normal CDF Model  ──>  Spread/Total Probs     |
  |   Team Stats         ──>  Confidence Signal      |
  |   Sharp Money        ──>  Line Movement Signal   |
  |   Weather            ──>  Outdoor Total Adjust   |
  +------------------------------------------------+
                        |
                  Edge >= 3%?  ── NO ──>  Skip
                        |
                       YES
                        |
              +-------------------+
              |  RISK GATES (9)   |
              |   Daily loss cap  |
              |   Position limit  |
              |   Per-event cap   |
              |   Concentration   |
              |   Kelly sizing    |
              +-------------------+
                        |
                EXECUTE on Kalshi
                        |
                Log  +  Track CLV
```

**Project Structure**

```
Edge-Radar/
├── scripts/
│   ├── scan.py              # Unified entry point → sports/futures/prediction/polymarket
│   ├── kalshi/              # Scan ── Size ── Execute ── Settle
│   ├── prediction/          # Crypto, weather, S&P, politics edge
│   ├── polymarket/          # Polymarket cross-reference edge detection
│   ├── shared/              # Config, team stats, weather, ticker display
│   └── schedulers/          # Automation & scheduled scan jobs
│       ├── morning_scans/   # Per-sport .bat scan jobs (MLB, NBA, NFL, NHL)
│       └── automation/      # Python scripts (daily scan, Windows Task Scheduler)
├── tests/                   # 83 pytest tests (risk gates, edge math, weather)
├── docs/                    # 8 guides (see Documentation below)
├── data/                    # Trade history, settlements, watchlists
├── reports/                 # Markdown scan reports + P&L reports
└── .claude/                 # Agents, skills, memory
```

---

## 📖 Documentation

| Guide | Description |
| --- | --- |
| **[Setup Guide](docs/setup/SETUP_GUIDE.md)** | API keys, private keys, environment config, first scan |
| **[Scripts Reference](docs/SCRIPTS_REFERENCE.md)** | Every script, flag, and example |
| **[Sports Guide](docs/kalshi-sports-betting/SPORTS_GUIDE.md)** | 27 filters, edge detection, daily workflow |
| **[Futures Guide](docs/kalshi-futures-betting/FUTURES_GUIDE.md)** | NFL, NBA, NHL, MLB, golf championships |
| **[Prediction Markets](docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md)** | Crypto, weather, S&P 500, politics |
| **[Architecture](docs/ARCHITECTURE.md)** | Pipeline, risk gates, data flow |
| **[MLB Filtering](docs/kalshi-sports-betting/MLB_FILTERING_GUIDE.md)** | 10 filter categories for MLB picks |
| **[Roadmap](docs/enhancements/ROADMAP.md)** | All enhancements — edge model, project quality, pending |
| **[Changelog](docs/CHANGELOG.md)** | Full project history |

---

## 🔌 Data Sources

All external data is **free**. Only Kalshi requires a funded account.

| API | What It Provides |
| --- | --- |
| **[Kalshi](https://kalshi.com)** | Market data, order execution (API key + RSA signing) |
| **[The Odds API](https://the-odds-api.com)** | Sportsbook odds from 12 US books (500 free req/mo) |
| **[ESPN](http://site.api.espn.com)** | NBA, NFL, NCAAB, NCAAF standings + open/close odds |
| **[NHL Stats API](https://api-web.nhle.com)** | Standings, goal differential, last 10 record |
| **[MLB Stats API](https://statsapi.mlb.com)** | Standings, run differential, winning percentage |
| **[NWS](https://weather.gov)** | Hourly forecasts for 61 NFL/MLB outdoor venues |
| **[CoinGecko](https://coingecko.com)** | Crypto prices and 24-hour volatility |
| **[Yahoo Finance](https://finance.yahoo.com)** | S&P 500 price and VIX implied volatility |
| **[Polymarket](https://polymarket.com)** | Cross-market price reference via Gamma API (free, no key) |

---

[![Back to top](https://img.shields.io/badge/%E2%86%91-Back%20to%20Top-6B7280?style=flat-square)](#top)
