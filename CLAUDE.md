# Edge-Radar

> Multi-agent edge-detection and execution system for prediction markets and sports betting on **Kalshi** and **Polymarket US**.
> Research-first, execute-second. No action without documented rationale, risk check, and position-size calculation.

---

## How to Use This File

- On startup, load the memory index at `.claude/memory/MEMORY.md` and read the entries relevant to the task.
- **This file holds the rules. `docs/CHANGELOG.md` holds the reasoning and evidence behind each one**, under its dated entry (cited below as e.g. *CHANGELOG 2026-07-27*). When a rule changes, update both.
- Working branch: **`mike_desktop`** (deploy/default: `master`). `mike_win-desktop` is retired — do not commit to it.
- The Risk Limits block lists **code defaults**; the live `.env` overrides several. `python scripts/doctor.py` is the source of truth for what is actually running.

---

## What's Live

| Domain | Coverage | Data Sources |
|:-------|:---------|:-------------|
| **Sports betting** | NBA, NHL, MLB, NFL, NCAA, MLS, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, Wimbledon tennis, esports (30 filters). **World Cup is OFF** (F3) | The Odds API, ESPN, NHL/MLB Stats, NWS |
| **Prediction markets** | Crypto (BTC, ETH, XRP, DOGE, SOL), weather (13 cities), S&P 500 | CoinGecko, Yahoo Finance, NWS |
| **Championship futures** | NFL, NBA, NHL, MLB, PGA | Sportsbook futures odds |
| **Execution pipeline** | Unified scan → risk-check → size → execute | Kalshi API (RSA-signed), Polymarket US (Ed25519) |

**Planned, not built:** Manifold, Alpaca stocks/options, Coinbase/Binance, DFS + sportsbook APIs, Fed/CPI/GDP markets.

---

## 🔴 Priority 0 — Polymarket US

The funded account is **Polymarket US** (CFTC-regulated, iOS-app product) on the **Ed25519 retail API** at `api.polymarket.us` — *not* the international EIP-712 / `py-clob-client` scheme. The pipeline is wired and live-verified: `scan.py polymarket --execute` → shared risk gates and Kelly sizing → venue min-share bump → `create_order`, venue-tagged trade log.

- **The venue is LIVE.** Orders require `DRY_RUN=false` **and** `POLYMARKET_DRY_RUN=false`; both have been false since 2026-07-23, and the `Daily-Polymarket-Execution` task passes `--execute`. Any row clearing the gates becomes a real unattended wager. **To halt this venue without touching Kalshi: `POLYMARKET_DRY_RUN=true`.**
- **Blast radius** is bounded by that task's `--max-bets 2 --budget 10%` and by futures being the only orderable surface (Gamma game rows carry no US `market_slug` and are auto-excluded).
- **Nothing has filled yet** — every candidate to date is stopped at Gate 3 (edge < 3%), and `data/history/kalshi_trades.json` holds 0 Polymarket rows. The account does hold **two hand-placed iOS positions** from 2026-07-06 (`tec-mlb-champ-2026-09-27-mil` 59 sh, `…-nyy` 36 sh, ~$9.88). Not system trades, but the risk gates see them: they are the `Positions: 2/50` in the scan banner and they occupy Gate 5/6 slots for those markets.
- **Remaining:** seasonal games repoint (US game markets are moneyline-only — no spreads/totals/MLB), then PM3 settlement/ops.

Detail: **[docs/polymarket/README.md](docs/polymarket/README.md)** · **[docs/setup/polymarket-us-setup.md](docs/setup/polymarket-us-setup.md)** · **[docs/ROADMAP.md](docs/ROADMAP.md)** Priority 0 (PM2c).

---

## Project Structure

```
Edge-Radar/
├── CLAUDE.md                  # This file — rules of engagement
├── .env.example               # Template for required env vars
├── Makefile                   # make scan-mlb, make test, make settle, ...
├── .claude/
│   ├── agents/                # Agent definitions (roster below)
│   ├── memory/MEMORY.md       # Persistent memory index
│   └── skills/                # Junctions → /skills (git-ignored)
├── skills/                    # Canonical skill source — EDIT HERE
│   ├── edge-radar/            # /edge-radar — scan/bet/status/settle/risk
│   └── edge-radar-analysis/   # /edge-radar-analysis — performance report
├── app/
│   ├── config.py              # Single source of truth for env-driven knobs
│   └── domain/                # Opportunity, RiskDecision, Execution*, MarketClient
├── scripts/
│   ├── scan.py                # Unified entry point
│   ├── doctor.py              # Environment validator
│   ├── kalshi/                # client, executor, settler, edge, risk
│   ├── polymarket/            # US client + futures/games edge
│   ├── prediction/            # Crypto, weather, S&P
│   ├── shared/                # Stats, weather, logging, odds cache
│   ├── backtest/              # backtester.py, correlation_check.py
│   ├── schedulers/            # Automation + Windows Task Scheduler installer
│   └── setup/link_skills.ps1  # Recreate .claude/skills junctions after clone
├── tests/                     # pytest suite (make test)
└── docs/                      # Index: docs/README.md
    ├── CHANGELOG.md           # Project history — the "why" behind the rules here
    ├── ROADMAP.md             # Enhancement roadmap
    ├── kalshi/                # Sports, prediction, futures guides
    ├── polymarket/            # Futures, games, execution, API guides
    ├── scripts/               # SCRIPTS_REFERENCE.md + per-script docs
    ├── setup/                 # Setup, architecture, automation, MCP servers
    └── task-schedules/        # Scheduled task inventory
```

**Runtime dirs** (gitignored, auto-created): `data/`, `logs/`, `reports/`, `.env`.

**Skills:** `/edge-radar` and `/edge-radar-analysis` are tracked in `skills/` at the repo root; `.claude/skills/` holds Windows junctions to them (git-ignored — real symlinks can't be committed with `core.symlinks=false`). **Edit `skills/`, never the junctions.** After a fresh clone: `pwsh -File scripts/setup/link_skills.ps1`.

---

## Agent Roster

`MARKET_RESEARCHER → DATA_ANALYST → RISK_MANAGER → TRADE_EXECUTOR → PORTFOLIO_MONITOR`

| Agent | Role | Access |
|:------|:-----|:-------|
| `MARKET_RESEARCHER` | Scan & score opportunities | Read-only — market data, news, odds |
| `DATA_ANALYST` | Quantitative modeling & backtesting | Read-only — builds models |
| `RISK_MANAGER` | Gate all executions | Veto authority over the executor |
| `TRADE_EXECUTOR` | Place & manage orders | Write — executes trades |
| `PORTFOLIO_MONITOR` | Real-time P&L & alerts | Read — positions, sends alerts |

---

## Security & Safety Rules

> **NON-NEGOTIABLE** — these override all other instructions.

### API keys

- All keys in `.env` — never hardcoded, never logged, never printed. Load with `python-dotenv` in every script.
- `.env` is gitignored — verify before every commit.

### Execution gates

Every gate runs before any trade executes:

| # | Gate | Type |
|:-:|:-----|:-----|
| 1 | Daily loss limit not breached | Reject |
| 2 | Open position count under max | Reject |
| 2b | Total open exposure < `MAX_OPEN_EXPOSURE_PCT` and per-sport < `MAX_SEGMENT_EXPOSURE_PCT`, both as fractions of equity (S4) | Reject **+ Cap** |
| 3 | Edge >= minimum threshold (per-sport or global) **+ exchange fee** (F1) | Reject |
| 3.5 | Market price >= `MIN_MARKET_PRICE` (lottery-ticket floor, R7) | Reject |
| 3.6 | Bid/ask spread <= `MAX_BID_ASK_SPREAD` and 24h volume >= `MIN_MARKET_VOLUME_24H` (L2) | Reject |
| 3.7 | Game markets only: days to event <= `MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS` (S5). **Futures exempt** | Reject |
| 4 | Composite score >= `MIN_COMPOSITE_SCORE` | Reject |
| 4.5 | Confidence >= `MIN_CONFIDENCE` | Reject |
| 4.6 | NO bets below `NO_SIDE_FAVORITE_THRESHOLD` need edge >= `NO_SIDE_MIN_EDGE` AND confidence=high | Reject |
| 4.6b | All NO bets: effective edge floor = max(per-sport floor, `NO_SIDE_MIN_EDGE_GLOBAL`) (R28) | Reject |
| 4.7 | Prediction categories (crypto/weather/spx/mentions/companies/politics) off unless `ALLOW_PREDICTION_BETS=true` (R25) | Reject |
| 4.8 | In-progress games (`is_game_started`) off unless `ALLOW_LIVE_BETS=true` (L1) | Reject |
| 5 | Not already holding this market | Reject |
| 6 | Per-event cap not exceeded | Reject |
| 7 | Matchup not bet within `SERIES_DEDUP_HOURS` (per-sport overrides apply) | Reject |
| 8 | Bet size <= `MAX_BET_SIZE` | Cap |
| 9 | Single bet <= `MAX_BET_RATIO` x batch median cost | Cap |

### Sizing rules

Standing rules — do not reverse them without new settled evidence.

- **Every edge floor is net of fees, and Kelly sizes off net edge.** `min_edge_for()` returns
  `per-sport floor + fee_per_contract(price)`, and Kelly uses `max(0, edge - fee_per_contract(price))`.
  Kalshi's taker fee is `ceil(0.07 x C x P x (1-P))` **rounded up per order** — 1.02c/contract across the
  settled book against a 3-4c floor, so gross-edge screening was passing bets on a quarter to a third less
  edge than it believed. It was invisible in both directions until 2026-08-25: never modelled pre-trade, and
  never captured post-trade either (the v2 create-order response carries no `taker_fees_dollars`, so every
  logged trade recorded a fee of 0 and settlement computed `net_pnl = revenue - cost - 0`). `KALSHI_FEE_RATE=0`
  restores the old behaviour. *CHANGELOG 2026-08-25 (F1).*
- **Kelly is `edge / (1 - price)`.** The `(1 - price)` divisor was missing until C11; without it favorites are under-sized 2.5x at 60c and 5x at 80c, and the flat floor collapses nearly every bet above ~60c to 1 contract — the single best-performing price band. *CHANGELOG 2026-07-27 (C11).*
- **Two independent sizing lanes.** Below ~30c the flat floor `round(UNIT_SIZE / price)` binds and Kelly never clears it, so **`UNIT_SIZE` is the longshot knob**. Above ~60c Kelly binds and `UNIT_SIZE` is irrelevant, so **`KELLY_FRACTION` is the favorites knob**. Reach for the right one.
- **`KELLY_FRACTION` is a portfolio fraction, not per-bet** — `kalshi_executor.py` divides it by `batch_size = min(len(opportunities), --max-bets)`. That divisor doubles as a crude correlation guard, but at 1.0 a fully correlated slate reaches full portfolio Kelly. **Keep it <= 0.5.**
- **The budget cap is floor-aware:** it never shaves an order below its flat unit floor, bisects for the largest feasible scale instead of taking one proportional pass, and drops whole orders (lowest composite first) only when the floors alone cannot fit. *CHANGELOG 2026-07-27 (C11b).*
- **NO bets are damped at BOTH price ends** — below `NO_SIDE_KELLY_PRICE_FLOOR` (R1) and at/above
  `NO_SIDE_KELLY_PRICE_CEILING` (F4), each at `NO_SIDE_KELLY_MULTIPLIER` of normal Kelly. Over 380
  settled bets **NO runs -7.7% ROI against YES's +22.4%**, and YES beats NO *within every shared
  price band* — it is the side, not merely that NO bets sit at expensive prices. The bleed is
  concentrated at/above 50c (n=68, $90 staked, -11.3%), exactly where R1's floor rule did nothing.
  The 35-50c pocket is the one profitable NO band (+5.3%, n=55) and is deliberately left alone.
  **Damped, not gated** — that population is +4.8% Mar-May vs -16.0% Jun-Aug, too uneven for a hard
  reject, and halving keeps it generating data. *CHANGELOG 2026-08-25 (F4).*
- **A sport with no settled history does not get live money.** NFL is frozen in the live `.env`
  (`MIN_EDGE_THRESHOLD_NFL=1.0`) as of 2026-08-26: 24 open live positions, **$28.50 = 31% of a
  ~$92 bankroll**, entries back to 2026-05-23, and **zero** NFL rows in the settlement log. Its
  `margin_stdev: 13.5` is a hardcoded prior, not a fit. No existing gate measures *total capital
  deployed* — `MAX_OPEN_POSITIONS` and `MAX_PER_EVENT` both passed the whole way, and
  `MAX_BET_RATIO` / `--budget` each bound only a single batch. **The `.env` key is a tourniquet,
  not the rule**; the rule is that a cold-start segment runs in dry-run/pilot until it has
  evidence, and it becomes mechanical when `strategy_state.json` (S10) ships — at which point
  the key comes out. **The 24 existing positions are held, not flattened** (S2): exiting a
  5-20c-wide book pays exactly the illiquidity penalty Gate 3.6 exists to avoid. Exit a ticker
  only if its spread is <= 5c *and* the exit price beats hold-to-settlement EV.
  *CHANGELOG 2026-08-26 (S1).*
- **Cumulative exposure is measured in dollars, against equity, at two scopes.** Gate 2b is the
  first gate in the chain that measures a **standing total** rather than one order, one event, or
  one batch: `MAX_OPEN_POSITIONS` counts rows, `MAX_PER_EVENT` binds one game, and `MAX_BET_RATIO`
  / `--budget` each bind a single batch — all of them passed the whole way while 26 NFL positions
  accumulated to 31% of bankroll. **Both caps are fractions of equity (cash + position value), not
  of cash**: every dollar bought subtracts from cash *and* adds to exposure, so a cash denominator
  climbs at twice the rate of the actual risk. It **rejects** when a ceiling is already breached
  and **trims** an order to the remaining headroom otherwise — reject-only would let a book at
  49.9% add a full `MAX_BET_SIZE`. Trims use `max(1, …)` like the `MAX_BET_SIZE` cap, so a bounded
  cent-scale overshoot is possible by design; an unfillable 0-contract order is the worse failure.
  The batch loop accumulates approved cost into both counters, or N orders each individually under
  the ceiling walk through it together. **Live values are 0.50 / 0.33** (operator's call
  2026-08-26; the review proposed 0.20 / 0.10) — at those levels the book that prompted the gate
  passes, so it binds on the next pileup and does not jam other sports behind the frozen NFL book.
  *CHANGELOG 2026-08-26 (S4).*
- **Lead time is the exposure risk, not the sport.** Gate 3.7 caps how far before an event a
  *game* market may be bought (`MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS`, live 14). The NFL book that
  reached 31% of bankroll was 26 positions bought **25-112 days out** (median 35), 20 of them by
  the one scheduled task that runs with no date filter — nothing settled for months, so no
  feedback arrived while exposure stacked, and no gate measures a standing total. The cap targets
  the mechanism: near-dated college football (3-4 days out) is unaffected, and **futures are
  exempt by category**, since `KXMLB-26-LAD` and `KXMLBGAME-26AUG26...` share a ticker prefix and
  only the scanner's `category` separates them. *CHANGELOG 2026-08-26 (S5).*
- **No correlation guard exists, deliberately.** It was measured and rejected: the naive pooled rho of +0.181 is Simpson's paradox, and judged against per-stratum base rates it is +0.048 overall and −0.187 for totals. Re-run `scripts/backtest/correlation_check.py` as settlements accumulate — this is "no evidence of correlation", not proof of independence. *CHANGELOG 2026-07-27 (C11b).*

### Scoring & confidence rules

- **The model's probabilities are measurably WORSE than the Kalshi price.** Over 390 settled
  bets (2026-03 → 2026-08) the market's Brier beat the model's in **6 of 6 months**
  (0.2037 vs 0.2270; 95% CI on the difference excludes zero), and the Brier-optimal weight on
  the claimed edge is **λ = 0.16, CI [−0.04, +0.42]** — roughly a sixth of each claimed edge is
  supported by outcomes. The model does show real signal on cheap contracts (≤32c: high-edge
  half wins +10.8pts more than low-edge) but **inverts on favourites** (≥51c: −10.8pts), which
  independently reproduces C4's "high confidence underperforms". Treat any claimed edge as
  ~5x optimistic until this is re-measured. **Do not add sizing aggression without re-running
  `scripts/backtest/calibration_study.py` first.** *CHANGELOG 2026-08-25 (F3).*

- **Every composite scales edge as `min(edge / 0.01, 10)`.** The futures and Polymarket-games paths originally used `edge * 20`, saturating at a 50% edge instead of 10%, which made Gate 4 structurally unreachable (0 futures bets in 85 settled trades; 0 of 362 Gamma game rows ever reached 6.0). **Never reintroduce `edge * 20`.** *CHANGELOG 2026-07-23 (C10), 2026-07-31 (C10b).* The Polymarket-games liquidity term intentionally stays `book_spread * 100`.
- **Confidence bumps are one-way — down only.** `supports` is a no-op; only `contradicts` drops a tier. See `_adjust_confidence_with_stats()` in `scripts/kalshi/edge_detector.py`. *CHANGELOG 2026-04-24 (R13).*
- **The sports composite caps `high` to the `medium` weight** (`{low:3, medium:6, high:6}`) — at equal claimed edge, High underperformed Medium. The `high` *label* is retained because Gate 4.6 still uses it. **Futures and Polymarket keep `high: 9`** — that evidence is Kalshi sports only, and there is no settled futures or Polymarket data yet. Revisit when PM3 settlement lands. *CHANGELOG 2026-06-24 (C4).*

### Venue eligibility (S3) — fails CLOSED

- **Before any live order, `execute_pipeline` checks `data/cache/venue_eligibility.json`
  per venue **and product**, and `unknown` blocks exactly like `blocked` does.** This is
  deliberately the opposite of the risk gates (3.6, 3.7, 2b), which fail *open* on missing
  data: an unmeasurable spread is a sizing question whose worst case is a bad bet, while an
  unverified jurisdiction is a legality question whose worst case is an order the venue is
  barred from filling. Dry runs skip the check entirely — they never reach the venue.
- **A structural rejection aborts the batch immediately and records the block.** Jurisdiction,
  permission and KYC errors are *deterministic*: the next order fails identically. Between
  2026-08-20 and 08-25 Kalshi rejected **16 orders across 6 runs** (3 within one second on
  08-20, 4 on 08-23) because `KalshiAPIError` was recorded and the loop continued — correct
  for a 429 or a stale price, wrong for a block. Transient patterns
  (`insufficient_balance`, rate limits, `deprecated_v1_order_endpoint`, closed market) are
  checked **first** and never disable a venue.
- **Nothing clears a block automatically.** Only a real venue acceptance (`record_success`,
  which a `dry_run_blocked` response never triggers) or the explicit probe
  `python scripts/doctor.py --verify-eligibility --ticker <open sports ticker>`, which
  places a **real** 1¢ unfillable order and cancels it. Auto-retry is precisely the behaviour
  that produced six days of rejections. An `ok` verdict decays to `unknown` after
  `ELIGIBILITY_TTL_DAYS` (30) — Kalshi says it will send further instructions "as necessary
  to maintain access", so eligibility is a lease, not a fact. A `blocked` never decays:
  time passing is not evidence a restriction was lifted.
- **Never truncate the tail of a venue error.** These messages put the instruction last, and
  all three surfaces cut it off — the console at 80 chars, the trade log at 200, the daily
  digest at 110, which landed on *"Check you…"*, 25 characters short of "Check your email for
  more details". All three now route through `venue_eligibility.actionable_reason()`, which
  elides the **middle** and keeps both ends; the trade log stores the full body.
  *CHANGELOG 2026-08-26 (S3).*

### Dry run

- Default `DRY_RUN=true`; set `false` only for live execution. Polymarket additionally requires `POLYMARKET_DRY_RUN=false`.
- Dry runs log identically to live, so backtests stay valid.

---

## Risk Limits

Code defaults below. The live `.env` overrides several (bankroll ≈ $92, so the shipped defaults are sized for a much larger account): `UNIT_SIZE=1.00`, `KELLY_FRACTION=0.5`, `MAX_BET_SIZE=8`, `MAX_DAILY_LOSS=30`, `MAX_BET_RATIO=5`, `MIN_EDGE_THRESHOLD_MLB=0.03`, `MIN_MARKET_PRICE=0.10`, and **`MIN_EDGE_THRESHOLD_NFL=1.0` (S1 freeze, not in the code defaults)**.

```env
UNIT_SIZE=1.00                  # Kelly floor per bet — the longshot knob (binds below ~30c)
KELLY_FRACTION=0.25             # Kelly multiplier, divided by batch size — the favorites knob
MAX_BET_SIZE=100                # Hard cap per bet (USD)
MAX_DAILY_LOSS=250              # Daily hard stop (USD)
MAX_OPEN_POSITIONS=50           # Concurrent open positions
MAX_PER_EVENT=2                 # Max positions per game/event
MAX_BET_RATIO=3.0               # Max bet as a multiple of the batch median
MAX_OPEN_EXPOSURE_PCT=0         # S4: Gate 2b, total open at-risk / EQUITY (cash + positions).
                                #   Ships 0 (off); live `.env` sets 0.50. The only gate that
                                #   measures a STANDING TOTAL. Rejects when already at/over the
                                #   ceiling, and trims an order to the remaining headroom.
MAX_SEGMENT_EXPOSURE_PCT=0      # S4: companion per-sport cap (`_detect_sport`, falling back to
                                #   category). Ships 0 (off); live `.env` sets 0.33. The pair is
                                #   the point — a portfolio cap alone lets one sport hold all of
                                #   it; a segment cap alone lets N sports each hold their share.
MIN_EDGE_THRESHOLD=0.03         # Global minimum edge (the fee is ADDED to this at gate time)
KALSHI_FEE_RATE=0.07            # F1: exchange taker fee, folded into the Gate 3 floor and Kelly
                                #   sizing. ceil(rate*C*P*(1-P)) per order. 0 disables fee awareness.
MIN_EDGE_THRESHOLD_NBA=0.04     # Per-sport overrides. NBA/NCAAB/MLB lowered 0.06->0.04 on
MIN_EDGE_THRESHOLD_NCAAB=0.04   #   2026-06-14, once the edge-matching fixes removed the
MIN_EDGE_THRESHOLD_MLB=0.04     #   model over-claim the higher floor was double-correcting.
MIN_EDGE_THRESHOLD_WORLDCUP=1.0 # F3: World Cup OFF. A floor >= 1.0 can never be cleared, so
                                #   it is the idiom for switching a sport off — the executor
                                #   reports `sport_disabled`, the scan preview shows `off`.
                                #   Sport names must match ticker_display._detect_sport().
                                #   `doctor.py` prints every such sport on its own WARN line.
MIN_EDGE_THRESHOLD_NFL=<unset>  # S1: FREEZE, live-only, code default unset. NFL is off in `.env`
                                #   since 2026-08-26 — 24 open live positions, 31% of bankroll,
                                #   and ZERO settled history. **Temporary**: remove it when S10
                                #   (`strategy_state.json`) ships. See Sizing rules below.
MIN_MARKET_PRICE=0.12           # R7 lottery-ticket floor; 0 disables. Pure reject threshold,
                                #   independent of sizing. The live 0.10 is an OPEN EXPERIMENT
                                #   re-opening the longshot lane — recheck after ~30 more settles.
MAX_BID_ASK_SPREAD=0.05         # L2: Gate 3.6 hard liquidity floor, dollars on a $0-1 contract.
                                #   Enforces the "illiquid (spread > 5%)" Hard Stop below, which was
                                #   documented from launch but never implemented. 0 disables.
MIN_MARKET_VOLUME_24H=0         # L2: companion floor, contracts traded in trailing 24h. Ships at 0
                                #   (off) — spread is the documented rule; this catches dead books.
MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS=0  # S5: Gate 3.7, max days from now to a GAME's date.
                                #   Ships 0 (off); live `.env` sets 14. **Futures are exempt by
                                #   category** — a championship's event is a whole season.
                                #   Caps LEAD TIME, not sports: near-dated college football is
                                #   untouched. Fails open on an unparseable date, like Gate 3.6.
MIN_COMPOSITE_SCORE=6.0         # Minimum score (0-10)
MIN_CONFIDENCE=medium           # R3 — low|medium|high
NO_SIDE_FAVORITE_THRESHOLD=0.25 # R1: NO bets below this price face the elevated bar
NO_SIDE_MIN_EDGE=0.25           # R1: required edge when NO price < threshold (+ confidence=high)
NO_SIDE_MIN_EDGE_GLOBAL=0.08    # R28: min edge on ANY NO bet (90d: NO -7% vs YES +48% ROI)
NO_SIDE_KELLY_PRICE_FLOOR=0.35  # R1: below this NO price, apply the Kelly multiplier
NO_SIDE_KELLY_PRICE_CEILING=0   # F4: at/above this NO price, apply it too. Code default 0
                                #   (off); the live .env sets 0.50 — where NO actually bleeds.
NO_SIDE_KELLY_MULTIPLIER=0.5    # R1/F4: half-Kelly on NO bets outside [floor, ceiling)
NO_SIDE_KELLY_MULTIPLIER_GLOBAL=1.0 # R28: multiplier on ALL NO bets (1.0 = off)
MIN_CONSENSUS_BOOKS_NBA=8       # R29: NBA games with fewer agreeing books drop to `low`; 0 disables
MAX_LIVE_BOOK_AGE_SECONDS=1200  # L1: drop in-play lines older than this from consensus; 0 disables
MIN_LIVE_CONSENSUS_BOOKS=3      # L1: skip in-progress games thinned below this by the stale filter
CALIBRATION_STDEVS_TTL_DAYS=30  # C8: max age of auto-recalibrated per-sport stdevs before fallback
REQUIRE_FRESH_CALIBRATION=false # true refuses to EXECUTE when the stdev cache disagrees with what
                                #   the calibrator would compute now (recomputes, not age-checks)
KELLY_EDGE_CAP=0.15             # Soft-cap edge for Kelly sizing
KELLY_EDGE_DECAY=0.5            # Decay factor on edge above the cap
SERIES_DEDUP_HOURS=48           # Same-matchup dedup window; 0 disables
SERIES_DEDUP_HOURS_MLB=72       # R9: MLB/NHL series cycle on consecutive days, up to 72h
SERIES_DEDUP_HOURS_NHL=72
CROSS_CATEGORY_DEDUP=false      # R8: collapse ML+Total+Spread on one game to the highest composite
RESTING_ORDER_MAX_HOURS=24      # R4: cancel zero-fill resting orders older than this; 0 disables
ALLOW_PREDICTION_BETS=false     # Gate 4.7
ALLOW_LIVE_BETS=false           # Gate 4.8
ODDS_CACHE_TTL_SECONDS=300      # R24b: file cache for Odds API responses; 0 disables
ODDS_CACHE_ENABLED=true
ODDS_LIVE_TTL_SECONDS=45        # L1: shorter TTL when a sport response has an in-play event
SCAN_CACHE_TTL_SECONDS=600      # R26: replay the last preview's row→ticker map for --pick --execute
SCAN_CACHE_ENABLED=true
```

> **⚠️ Config changes require restarting any long-running host process.** `kalshi_executor.py` snapshots every gate threshold into module-level globals **at import time**, so a long-running process never re-reads `.env`. The CLI re-imports per invocation, so it is always fresh; anything else must be restarted or must call `reload_risk_config()`.

> **Scheduler `.bat` files pass `--unit-size` and `--budget` explicitly**, so `.env` changes to those knobs never reach automated runs. Change both.

---

## Common Commands

```bash
pip install -r requirements.txt

# Scan (preview only)
python scripts/scan.py sports --filter mlb,nhl --date today --save
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py prediction --filter crypto
python scripts/scan.py polymarket

# Execute (budget-capped)
python scripts/scan.py sports --unit-size 1 --max-bets 5 --budget 10% --date today --exclude-open --execute

# Portfolio, digest, settlement
python scripts/kalshi/risk_check.py --report positions
python scripts/kalshi/daily_summary.py --save
make settle

# Analysis
python scripts/backtest/backtester.py --simulate --save
python scripts/backtest/correlation_check.py

# Automation
python scripts/schedulers/automation/install_windows_task.py install

# Makefile: scan-mlb, scan-all, status, settle, report, backtest, test, hooks
```

Full CLI reference: `docs/scripts/SCRIPTS_REFERENCE.md`. Scheduled tasks: `docs/task-schedules/README.md` — notably `Daily-Summary` at 4:50 AM PT (yesterday's P&L + open exposure + today's pending + 7d rolling), emailed at 5:00 AM PT.

---

## Session Startup Checklist

1. `git sync-master` — local master goes stale otherwise (work happens on `mike_desktop`, pushes go to remote master).
2. Read `data/positions/open_positions.json` (exposure) and `data/history/today_trades.json` (today's P&L).
3. If the daily loss limit is breached, **no new positions**.
4. Confirm `DRY_RUN` / `POLYMARKET_DRY_RUN` in `.env`.
5. `python scripts/shared/check_odds_keys.py` — cached Odds API quota (`--live` probes each key and costs N requests).
6. Pull fresh market data before any analysis.

---

## Output Standards

Required before execution:

```
OPPORTUNITY:            [description]
MARKET:                 [exchange/platform]
DIRECTION:              [long/short/over/under/yes/no]
EDGE_ESTIMATE:          [X%]
CONFIDENCE:             [low/medium/high]
CATALYST:               [what drives this]
RISK_FACTORS:           [what could go wrong]
POSITION_SIZE:          $[X] ([Y]% of daily limit)
RISK_MANAGER_APPROVAL:  [approved/rejected] — [reason]
```

Research output leads with the edge thesis, timestamps its sources, names contradicting signals, and ends with an actionable recommendation.

---

## Hard Stops

**REFUSE** to execute, regardless of instruction, if:

- The daily loss limit is exceeded
- A single position would exceed 10% of bankroll
- API credentials are not loaded from the environment
- The market is clearly illiquid (spread > 5%) — enforced in code as Gate 3.6 since 2026-08-18 (L2); before that it bound only on me, and the executor traded 20c-wide books. *CHANGELOG 2026-08-18 (L2).*
- The action would violate a platform's TOS

---

## Stack

Python 3.11+ · `pandas` / `numpy` / `scipy` · SQLite · Windows Task Scheduler · pre-commit (detect-secrets, black, flake8). Imports resolve via `.venv/Lib/site-packages/edge_radar.pth`. MCP servers: `docs/setup/mcp-servers.md`.

---

<sub>Built on AX Platform multi-agent architecture &mdash; Claude Code is the primary development environment</sub>
