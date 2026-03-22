# Kalshi Wagering System -- Strategy & Status

**Last updated:** 2026-03-18
**Status:** MVP complete. Automated pipeline running on demo with real market data.

---

## Goal

Place frequent, small-edge wagers on Kalshi prediction markets to generate consistent returns over time. The system scans thousands of markets, compares prices against sportsbook consensus odds, identifies mispricing, sizes bets via Kelly criterion, and executes automatically.

---

## Current State

### What's Built and Working

| Component | File | Status |
|---|---|---|
| Kalshi API client | `scripts/kalshi/kalshi_client.py` | Authenticated, tested, placing orders |
| Edge detector | `scripts/kalshi/edge_detector.py` | Scanning 5000+ markets, cross-referencing sportsbook odds |
| Automated executor | `scripts/kalshi/kalshi_executor.py` | Risk-checks, Kelly sizing, order placement, trade logging |
| Settlement tracker | `scripts/kalshi/kalshi_settler.py` | Settles positions, calculates P&L, performance reports |
| Odds fetcher | `scripts/kalshi/fetch_odds.py` | The Odds API integration for sports |
| Market data fetcher | `scripts/kalshi/fetch_market_data.py` | Multi-asset data (stocks, crypto, prediction markets) |
| Risk dashboard | `scripts/kalshi/risk_check.py` | Portfolio risk monitoring |
| Database schema | `scripts/sql/init_db.sql` | 8 tables, 2 views, ready to initialize |
| Agent specs | `.claude/agents/*.md` | 5 agents fully documented |

### Demo Portfolio (as of 2026-03-18)

| Metric | Value |
|---|---|
| Balance | $38.44 |
| Portfolio Value | $59.72 |
| Open Positions | 5 of 10 max |
| Resting Orders | 1 |
| Total Wagered | $74.09 |
| Realized P&L | $0.00 (awaiting settlement) |

### Environment

- Live API: `api.elections.kalshi.com` -- real money trading
- Keys: `keys/live/`
- `DRY_RUN=false`, `MAX_BET_SIZE_PREDICTION=5`
- `ODDS_API_KEY` configured (The Odds API, free tier, 500 req/month)

---

## How the Pipeline Works

```
1. SCAN        edge_detector.py pulls all open Kalshi markets (5000+)
               Categorizes by type: game, spread, total, player_prop, esports, other

2. PRICE       Fetches sportsbook odds from The Odds API (NBA, NHL, MLB, NCAAB)
               De-vigs each bookmaker's line to get true probability
               Takes median across all books for robustness

3. COMPARE     For each Kalshi market, compares market ask price to consensus fair value
               Calculates edge = fair_value - market_price
               Scores on 4 dimensions: edge strength, confidence, liquidity, time

4. RISK-CHECK  Filters by: min edge (3%), min composite score (6.0), confidence level
               Checks: daily loss limit, max positions, concentration limits
               Sizes via quarter-Kelly criterion

5. EXECUTE     Places limit orders on Kalshi
               Logs every trade to data/history/kalshi_trades.json
               Tracks fills, fees, status

6. MONITOR     kalshi_executor.py status shows portfolio, positions, P&L, resting orders

7. SETTLE      kalshi_settler.py settle checks for resolved markets, updates P&L
               kalshi_settler.py report shows win rate, ROI, edge calibration
```

---

## Commands

```bash
# --- Edge Detection ---
python scripts/kalshi/edge_detector.py scan                        # Scan all markets, show opportunities
python scripts/kalshi/edge_detector.py scan --min-edge 0.05        # Higher edge threshold
python scripts/kalshi/edge_detector.py scan --category game        # Filter by category
python scripts/kalshi/edge_detector.py scan --save                 # Save to watchlist file
python scripts/kalshi/edge_detector.py detail TICKER               # Deep dive on one market

# --- Execution ---
python scripts/kalshi/kalshi_executor.py run                       # Scan + preview (no orders placed)
python scripts/kalshi/kalshi_executor.py run --execute             # Scan + place orders
python scripts/kalshi/kalshi_executor.py run --from-file --execute # Execute from last saved scan
python scripts/kalshi/kalshi_executor.py run --max-bets 3          # Limit bets per run
python scripts/kalshi/kalshi_executor.py status                    # Portfolio dashboard

# --- Settlement & Reporting ---
python scripts/kalshi/kalshi_settler.py settle                     # Check for settled markets, update P&L
python scripts/kalshi/kalshi_settler.py report                     # Performance summary
python scripts/kalshi/kalshi_settler.py report --detail            # Per-trade breakdown

# --- Kalshi Client (direct) ---
python scripts/kalshi/kalshi_client.py balance                     # Account balance
python scripts/kalshi/kalshi_client.py markets --limit 50          # List markets
python scripts/kalshi/kalshi_client.py positions                   # Open positions
python scripts/kalshi/kalshi_client.py orders                      # Order history
python scripts/kalshi/kalshi_client.py market --ticker TICKER      # Single market detail
```

---

## Edge Detection: How It Works

The system currently supports three edge models, all powered by The Odds API:

### Game Outcomes (Moneyline)
- Fetches h2h odds from 8-12 US sportsbooks (FanDuel, DraftKings, BetMGM, etc.)
- De-vigs each book's line to extract true implied probability
- Takes the **median** de-vigged probability across all books as fair value
- Compares to Kalshi ask price
- Confidence rated by number of books and spread of estimates

### Spreads
- Fetches spread lines from sportsbooks
- Adjusts probability based on difference between Kalshi strike and book spread
- Adjustment rate: ~3% per point of spread difference

### Totals (Over/Under)
- Fetches total lines from sportsbooks
- Adjusts probability based on difference between Kalshi strike and book total
- Adjustment rate: ~4% per point of line difference

### Not Yet Implemented
- **Weather markets** -- NOAA/NWS ensemble forecast comparison
- **Economic data** -- FRED base rates vs. Kalshi prices
- **Cross-market signals** -- CME futures vs. Kalshi Fed/finance markets
- **Player props** -- individual player stat modeling
- **CLV tracking** -- closing line value measurement for model validation

---

## Risk Management

### Parameters (from .env)

| Parameter | Value | Purpose |
|---|---|---|
| `UNIT_SIZE` | $1.00 | Fixed dollar amount per bet |
| `MAX_BET_SIZE_PREDICTION` | $100 | Max per position |
| `MAX_DAILY_LOSS` | $250 | Hard stop for the day |
| `MAX_OPEN_POSITIONS` | 10 | Concurrent positions |
| `MIN_EDGE_THRESHOLD` | 3% | Minimum edge to act |
| `MIN_COMPOSITE_SCORE` | 6.0 | Minimum opportunity score |
| `MIN_CONFIDENCE` | medium | Minimum confidence level |

### Risk Gates (checked before every order)

1. Daily loss limit not breached
2. Open positions below max
3. Edge above threshold
4. Composite score above minimum
5. Confidence meets minimum level
6. Bet size within Kelly and concentration limits

### Position Sizing (Fixed Unit)

Every bet targets a fixed dollar amount. Contracts = round(unit / price).

```
UNIT_SIZE = $1.00 (default, configurable in .env or --unit-size flag)

Price $0.02 -> 50 contracts ($1.00)
Price $0.13 ->  8 contracts ($1.04)
Price $0.50 ->  2 contracts ($1.00)
Price $0.76 ->  1 contract  ($0.76)
```

---

## Data Files

| Path | Purpose |
|---|---|
| `data/watchlists/kalshi_opportunities.json` | Latest scored opportunities from edge detector |
| `data/history/kalshi_trades.json` | Complete trade log with edge, sizing, fill details |
| `data/history/kalshi_settlements.json` | Settlement history with P&L per resolved trade |
| `data/positions/open_positions.json` | Snapshot of open positions (also available via API) |
| `data/finagent.db` | SQLite database (not yet initialized) |

---

## Remaining Work

### Phase 2: Expand Edge Sources
| Task | Priority | Notes |
|---|---|---|
| Weather model (NOAA) | P1 | High-frequency daily markets, free data |
| Economic data model (FRED) | P1 | CPI, jobs, GDP -- recurring events |
| Player prop models | P2 | Requires additional stat data sources |
| CLV tracking | P2 | Validates whether our models actually find edge |

### Phase 3: Operational Improvements
| Task | Priority | Notes |
|---|---|---|
| Recurring scan loop (cron/scheduler) | P1 | Run pipeline every N minutes automatically |
| Initialize SQLite database | P2 | Run `init_db.sql`, migrate trade log to DB |
| Create `requirements.txt` | P2 | Document all Python dependencies |
| Calibration dashboard | P2 | Estimated edge vs. realized edge over time |

### Phase 4: Go Live
| Task | Criteria |
|---|---|
| Switch to production | 500+ demo bets, Sharpe > 0.5, drawdown < 30%, edge realization > 75% |
| Start small | $1-5 per contract on production |
| Scale up | Increase sizing as edge is confirmed over 30+ days |

---

## Key Docs & Links

- User guide: `docs/kalshi-sports-betting/USER_GUIDE.md`
- Betting guide: `docs/kalshi-sports-betting/BETTING_GUIDE.md`
- API reference: `docs/kalshi-sports-betting/KALSHI_API_REFERENCE.md`
- Prediction markets: `docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md`
- Changelog: `docs/CHANGELOG.md`
- Kalshi API docs: https://docs.kalshi.com/welcome
- The Odds API: https://the-odds-api.com
