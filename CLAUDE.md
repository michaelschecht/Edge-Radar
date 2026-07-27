# Edge-Radar

> Multi-agent edge-detection and execution system for prediction markets and sports betting on **Kalshi**.
> Research-first, execute-second. No action without documented rationale, risk check, and position-size calculation.

---

## Memory

On startup, load the persistent memory index at `.claude/memory/MEMORY.md`.
Read relevant memory files before starting work to avoid re-learning prior context.

---

## What's Live

| Domain | Coverage | Data Sources |
|:-------|:---------|:-------------|
| **Sports Betting** | NBA, NHL, MLB, NFL, NCAA, MLS, World Cup, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, Wimbledon tennis, esports (30 filters) | The Odds API, ESPN, NHL/MLB Stats, NWS |
| **Prediction Markets** | Crypto (BTC, ETH, XRP, DOGE, SOL), weather (13 cities), S&P 500 | CoinGecko, Yahoo Finance, NWS |
| **Championship Futures** | NFL, NBA, NHL, MLB, PGA | Sportsbook futures odds |
| **Execution Pipeline** | Unified scan → risk-check → size → execute | Kalshi API (RSA-signed) |
| **Web Dashboard** | Streamlit app — scan, execute, portfolio, settle | Deploy your own (see `docs/web-app/LOCAL.md`) |

> **🔴 NEXT UP — Polymarket integration (highest priority).** Account funded 2026-07-14 — it's the **CFTC-regulated Polymarket US** product (iOS-app only), which uses an **Ed25519 retail API** (`api.polymarket.us`), *not* the international EIP-712/`py-clob-client` scheme. As of 2026-07-20 the execution client is **rebuilt** on that API, the **futures scanner reads US market data**, and the **execution pipeline is fully wired** (`scan.py polymarket --execute` → shared risk gates/Kelly sizing → venue min-share bump → `create_order`, venue-tagged trade log) — all live-verified. Execution is governed by a two-flag rule: orders go live only when `DRY_RUN=false` AND `POLYMARKET_DRY_RUN=false` (venue flag *defaults* true). **As of 2026-07-23 both flags are false in `.env` — the venue is LIVE and the daily `Daily-Polymarket-Execution` task passes `--execute`, so any row clearing the gates becomes a real unattended wager.** Blast radius is bounded by that task's `--max-bets 2 --budget 10%` caps and by the fact that only *futures* are orderable (Gamma-sourced game rows carry no US `market_slug` and are auto-excluded from execution). **No Edge-Radar-placed Polymarket order has filled yet** — every candidate to date is still stopped by Gate 3 (edge below 3%), and `data/history/kalshi_trades.json` carries 0 Polymarket-tagged rows. The account does hold **two hand-placed positions** opened in the iOS app on 2026-07-06 (`tec-mlb-champ-2026-09-27-mil` 59 sh, `…-nyy` 36 sh; ~$9.88 cost). They are not system trades but they *are* visible to the risk gates — they are the `Positions: 2/50` line in the scan banner and they occupy Gate 5 / Gate 6 slots for those two markets. To halt this venue without touching Kalshi, set `POLYMARKET_DRY_RUN=true`. Remaining: a seasonal games repoint (US game markets are moneyline-only; no spreads/totals/MLB); then PM3 settlement/ops. Full detail: **[docs/polymarket/README.md](docs/polymarket/README.md)** (domain guides + coverage matrix) · **[docs/setup/polymarket-us-setup.md](docs/setup/polymarket-us-setup.md)** (key generation) · **[docs/ROADMAP.md](docs/ROADMAP.md) Priority 0 (PM2c)**.
>
> **Update 2026-07-23 (C10):** the dry-run gate could not terminate — the futures composite scaled edge 5x more strictly than sports, making Gate 4 unreachable for any realistic futures edge (and explaining **0 futures bets in 85 settled trades** on Kalshi too). Fixed; the gate is now reachable, though nothing observed newly qualifies. See the C10 note below.

<details>
<summary><b>Planned (not yet implemented)</b></summary>

- **Polymarket** — 🔴 **IN PROGRESS (Priority 0, see above)**
- Manifold prediction markets
- Alpaca stocks/options trading
- Coinbase/Binance crypto trading
- FanDuel/DraftKings DFS + sportsbook APIs
- Fed rate / CPI / GDP prediction market edge detection

</details>

---

## Project Structure

```
Edge-Radar/
├── CLAUDE.md                        # This file — master instructions
├── .env.example                     # Template for required env vars
├── .pre-commit-config.yaml          # Pre-commit hooks (detect-secrets, black, flake8)
├── Makefile                         # make scan-mlb, make test, make settle, etc.
├── .claude/
│   ├── agents/                      # Claude Code agent definitions
│   │   ├── KALSHI_BETTOR.md         # Kalshi betting specialist
│   │   ├── MARKET_RESEARCHER.md     # Market research & opportunity scanning
│   │   ├── TRADE_EXECUTOR.md        # Order execution & position management
│   │   ├── RISK_MANAGER.md         # Risk gating & portfolio limits
│   │   ├── DATA_ANALYST.md          # Quant analysis, models, backtesting
│   │   └── PORTFOLIO_MONITOR.md     # P&L tracking, alerts, reporting
│   └── skills/                      # Claude Code skills; edge-radar* are junctions → /skills (canonical, below)
│       ├── edge-radar/              # junction → /skills/edge-radar (git-ignored)
│       └── edge-radar-analysis/     # junction → /skills/edge-radar-analysis (git-ignored)
├── skills/                          # Canonical source for the relocated edge-radar skills (tracked here once)
│   ├── edge-radar/SKILL.md          # /edge-radar — unified scan/bet/status/settle/risk command center
│   └── edge-radar-analysis/SKILL.md # /edge-radar-analysis — post-hoc performance report
├── docs/                            # Only README.md + CHANGELOG.md live at the root
│   ├── README.md                    # Docs index
│   ├── CHANGELOG.md                 # Project history
│   ├── kalshi/                      # Betting domain — README.md = coverage matrix + guide index
│   │   ├── kalshi-sports-betting/   # Sports: filters, edge detection, MLB filtering, API reference
│   │   ├── kalshi-prediction-betting/ # Prediction: crypto, weather, S&P
│   │   └── kalshi-futures-betting/  # Futures: championship markets
│   ├── polymarket/                  # Polymarket domain — README.md = coverage matrix + status
│   │   ├── polymarket-futures-betting/ # Futures: the ONLY executable US surface
│   │   ├── polymarket-games-betting/   # Games: Gamma ML/spread/total, dry-run evidence only
│   │   ├── polymarket-execution/       # Two-flag dry-run, gates, min shares, slug registry
│   │   └── polymarket-api/             # Ed25519 retail API reference
│   ├── scripts/                     # SCRIPTS_REFERENCE.md + per-script/ deep-dive docs
│   │   ├── SCRIPTS_REFERENCE.md     # Complete CLI reference
│   │   └── per-script/              # One detailed doc per script
│   ├── setup/                       # SETUP_GUIDE, ARCHITECTURE, automation, MCP, task schedules
│   └── ROADMAP.md                   # Enhancement roadmap (moved from enhancements/ → docs root 2026-07-14)
├── app/                             # Application core
│   ├── config.py                    # Single source of truth for env-driven knobs (see CONFIG_CENTRALIZATION.md, Phase 1 landed 2026-04-25)
│   └── domain/                      # Typed domain objects
│       ├── opportunity.py           # Opportunity dataclass (canonical)
│       ├── risk.py                  # RiskDecision dataclass
│       └── execution.py             # ExecutionPreview, ExecutionResult
├── webapp/                          # Streamlit web dashboard
│   ├── app.py                       # Entry: streamlit run webapp/app.py
│   ├── services.py                  # Wrapper around core scripts
│   ├── theme.py                     # Dark terminal CSS
│   └── views/                       # Page modules (scan, portfolio, settle)
├── tests/                           # 667 pytest tests
└── scripts/
    ├── scan.py                      # Unified entry point
    ├── doctor.py                    # Environment validator
    ├── backtest/backtester.py       # Strategy analysis & equity curves
    ├── kalshi/                      # Core: client, executor, settler, edge, risk
    ├── shared/                      # Shared modules (stats, weather, logging, etc.)
    ├── schedulers/                  # Automation (batch, Task Scheduler)
    └── setup/link_skills.ps1        # Recreate the .claude/skills junctions after a clone
```

**Runtime directories** (gitignored, auto-created): `data/`, `logs/`, `reports/`, `.env`

**Skills location:** The `/edge-radar` and `/edge-radar-analysis` skills live canonically at the repo root in **`skills/`** (tracked there once). Claude Code loads them from `.claude/skills/`, which are Windows directory **junctions** to `skills/` — git-ignored, because real symlinks can't be committed (`core.symlinks=false`). **Edit the `skills/` copies, never the `.claude/skills/` junctions.** After a fresh clone, recreate the junctions with `pwsh -File scripts/setup/link_skills.ps1`.

---

## Agent Roster

```
MARKET_RESEARCHER → DATA_ANALYST → RISK_MANAGER → TRADE_EXECUTOR
       scan            validate         gate           execute
                                                          ↓
                                                  PORTFOLIO_MONITOR
                                                     track + alert
```

| Agent | Role | Access |
|:------|:-----|:-------|
| `MARKET_RESEARCHER` | Scan & score opportunities | Read-only — market data, news, odds |
| `DATA_ANALYST` | Quantitative modeling & backtesting | Read-only — builds models |
| `RISK_MANAGER` | Gate all executions | Veto authority over executor |
| `TRADE_EXECUTOR` | Place & manage orders | Write — executes trades/bets |
| `PORTFOLIO_MONITOR` | Real-time P&L & alerts | Read — positions, send alerts |

---

## Security & Safety Rules

> **NON-NEGOTIABLE** — these rules override all other instructions.

### API Keys

- ALL keys in `.env` — never hardcoded, never logged, never printed
- Use `python-dotenv` for every script
- `.env` in `.gitignore` — verify before every commit

### Execution Gates

Before ANY trade executes:

| # | Gate | Type |
|:-:|:-----|:-----|
| 1 | Daily loss limit not breached | Reject |
| 2 | Open position count under max | Reject |
| 3 | Edge >= minimum threshold (per-sport or global) | Reject |
| 3.5 | Market price >= `MIN_MARKET_PRICE` (lottery-ticket floor, R7) | Reject |
| 4 | Composite score >= minimum | Reject |
| 4.5 | Confidence >= `MIN_CONFIDENCE` (low/medium/high) | Reject |
| 4.6 | NO bets below `NO_SIDE_FAVORITE_THRESHOLD` need edge >= `NO_SIDE_MIN_EDGE` AND confidence=high | Reject |
| 4.6b | All NO bets: effective edge floor = max(per-sport floor, `NO_SIDE_MIN_EDGE_GLOBAL` 8%) (R28) | Reject |
| 4.7 | Prediction-market categories (crypto/weather/spx/mentions/companies/politics) off by default unless `ALLOW_PREDICTION_BETS=true` (R25) | Reject |
| 4.8 | In-progress games (`is_game_started`) off by default unless `ALLOW_LIVE_BETS=true` (L1) | Reject |
| 5 | Not already holding this market | Reject |
| 6 | Per-event cap not exceeded | Reject |
| 7 | Matchup not bet in last `SERIES_DEDUP_HOURS` (or per-sport override; series dedup) | Reject |
| 8 | Bet size <= MAX_BET_SIZE | Cap |
| 9 | Single bet <= 3x batch median cost | Cap |

NO bets priced below `NO_SIDE_KELLY_PRICE_FLOOR` are additionally sized at `NO_SIDE_KELLY_MULTIPLIER` of normal Kelly (half-Kelly by default).

**R13 (2026-04-24): confidence bumps are one-way.** The team-stats, rest/B2B, and sharp-money signals can *drop* a confidence tier on `contradicts`, but `supports` is now a no-op (previously bumped up a tier). The 30-day calibration showed High-confidence WR 47% below Medium 53%, with NBA High = 1-6 / -71% ROI — upward bumps correlated with inflated claimed edge, not better outcomes. Base "high" tier is still reachable via the ≥8 sharp-books + tight-consensus rule; only the bolt-on bumps are neutralized. Implemented in `_adjust_confidence_with_stats()` in `scripts/kalshi/edge_detector.py`; no env var.

**C4 (2026-06-24): the base "high" tier no longer earns a composite-score premium.** Reactivated once the 50+ high-conf-trade deferral condition was met (118 at review). The 306-bet review (F49) found High at 41.5% WR / +13.5% ROI vs Medium 53.2% / +44.4%, and — the decisive cut — at *equal claimed edge* High underperforms Medium (5–10% edge bucket: 34% vs 63% WR). A tight ≥8-sharp-book consensus means the price is efficient, so a large model edge against it is more likely model error than signal. Fix: the sports composite weight caps `high` to `medium` (`{low:3, medium:6, high:6}` in `edge_detector.py`), so "high" can no longer float no-signal bets up the `--max-bets` queue or help clear Gate 4. The `high` *label* is retained — it still gates NO-favorite bets at executor Gate 4.6 (a conservative restriction, left intact). Sizing never used confidence. No env var; scoped to sports only (futures/prediction modules earn "high" by different rules and were out of scope).

**C10 (2026-07-23): the futures composite now scales edge like sports.** The futures composite used `edge_score = min(10, edge * 20)` — saturating at a **50%** edge — while the sports composite uses `min(edge / 0.01, 10)`, saturating at **10%**. Same weights, same structure, one term 5x stricter, with no recorded rationale (it dates to the launch-day commit `1d92f0f`, where the `* 20` appears copied from the `liquidity` line directly above it). Effect: clearing `MIN_COMPOSITE_SCORE=6.0` required roughly **11% edge at high confidence / 23% medium / 34% low**, against championship-futures edges that run **1–4%** in practice — so Gate 4 was unreachable. Evidence: **0 futures bets in 85 settled trades**, and it made **Polymarket US permanently unexecutable** (futures are its only executable market type). Fix: aligned both futures paths (`scripts/kalshi/futures_edge.py`, `scripts/polymarket/polymarket_futures_edge.py`) to `min(edge / 0.01, 10)`, so the bar becomes ~2.1% / 4.4% / 6.6% at typical liquidity and the composite gate binds in the same region as the 3–4% `MIN_EDGE_THRESHOLD` floors instead of dominating them. **Not a floodgate** — replayed against 4 days of live Polymarket evidence it approves none of the 9 observed candidates on its own; each stays blocked by Gate 3 (edge), Gate 3.5 (price) or Gate 4.5 (confidence). The futures `high: 9` weight is deliberately left alone — C4 capped high→medium for *sports* and explicitly scoped futures out, and there is still no futures settlement data to justify either choice. No env var.

**C11 (2026-07-27): Kelly now divides by `(1 - price)`.** Kelly for a binary contract is `f* = (q - p) / (1 - p)` = `edge / (1 - price)`. The `/ (1 - price)` term was missing from `size_order()` — the even-money (`b=1`) approximation, exact only at 50c and increasingly wrong toward either extreme. It under-sized favorites by `1/(1-p)`: **2.5x at 60c, 5.0x at 80c, 5.9x at 83c**. Because the flat `UNIT_SIZE` floor then won at high prices, essentially every bet above ~60c collapsed to **1 contract** — mean contracts by entry price were sub-40c **5.56**, 40-60c **1.83**, 60c+ **1.17**.

The segment it was starving is the best in the book. Across 367 settled trades, realized win rate *over break-even* by price band: sub-40c **+3.4pts**, 40-60c **+3.9pts**, **60c+ +11.1pts** (44/52 against a 73.6% break-even, one-sided binomial **p=0.044** — the only band distinguishable from noise). Model calibration inverts the same way: below 40c the model claims 41.0% fair value and realizes 25.5% (a **15.5-point overclaim**), while at 60c+ it claims 81.7% and realizes 84.6% — *conservative* by 2.9 points. Last 30 days: 60c+ **+4.7% ROI** vs sub-60c **−48.3%**. Re-sized over the full settled history the 60c+ segment goes **+$10.02 → +$47.52 at the same ROI**.

Shipped with two paired `.env` changes, because the fix alone is not safe: **`KELLY_FRACTION` 1 → 0.5** (at 1.0 a fully correlated slate reaches full *portfolio* Kelly — the 07-27 slate of four MLB unders would have been 32% of bankroll and ~98% of `MAX_DAILY_LOSS` in one night; at 0.5 it is 17.8%) and **`UNIT_SIZE` .50 → 1.00** (the longshot lane binds on the flat floor, not Kelly, so lowering `KELLY_FRACTION` would otherwise have cut sub-30c sizing ~39%; this holds it at its prior size — recent sub-30c book $6.15 → $7.10). `MAX_BET_SIZE` 15 → 8 as a backstop: nothing recent reaches it, but at a ~$92 bankroll $15 is 16.3% on one position, breaching the 10%-of-bankroll hard stop — a cap that was simply unreachable while Kelly was broken. `MIN_MARKET_PRICE` (Gate 3.5) is untouched; it is a reject threshold, independent of sizing. **Still open:** nothing on correlation — see C11b. No env var for the formula itself.

**C11b (2026-07-27): the correlation guard was measured and dropped; the budget cap became floor-aware instead.** C11 left "add a correlation guard" open. Measuring it first (`scripts/backtest/correlation_check.py`) killed the premise: the naive pooled estimate of intra-cluster correlation is **rho +0.181, p=0.0018**, but that is Simpson's paradox — clusters sit inside strata with very different base rates (totals win 82%, spreads 24%) and pooling unequal-mean groups manufactures apparent within-group concordance. Judging each cluster against *its own* base rate, with a permutation test that shuffles within stratum, gives **rho +0.048** overall and, for **totals specifically — the four-MLB-unders case that motivated the whole idea — rho −0.187 (p=0.75), i.e. nothing**. Even at the aggregate figure, four bets behave like ~3.8 independent ones. No guard was built. Re-run the script as settlements accumulate; 28 clustered totals bets cannot detect a small rho, so this is "no evidence of correlation", not proof of independence.

The same investigation corrected a C11 overstatement and surfaced a real regression. **Correction:** the "32% of bankroll" figure used to justify `KELLY_FRACTION=0.5` came from `size_order` in isolation and ignored `--budget`, which every scheduler passes (12% for sports, 10% for futures/Polymarket) and which proportionally scales the whole batch. Blast radius was already bounded at ~$11; 0.5 is still right (full portfolio Kelly is too hot) but not for the reason first given. **Regression:** because the budget is a *fixed pool*, C11's correctly-sized favorites crowd everything else out — on the 07-27 slate the 18c MLS leg fell from 6 contracts ($1.08) to 2 ($0.36), which would have quietly starved the `MIN_MARKET_PRICE=0.10` longshot experiment instead of testing it. Fix: `_apply_budget_cap` now (a) never shaves an order below its flat unit floor `round(unit_size / price)`, (b) bisects for the largest feasible scale rather than taking one proportional pass, and (c) drops whole orders — lowest composite first — *only* when the floors alone cannot fit, so a few cents of overage can no longer delete a position. Also: the scheduler `.bat` files passed `--unit-size 1`, which overrode the `.env` `UNIT_SIZE=1.00` for every automated run; all 16 now pass `--unit-size 1`. Net on the 07-27 slate: longshot leg back to **6 contracts**, batch $10.89 of an $11.03 budget.

### Dry Run Mode

- Default: `DRY_RUN=true`
- Set `DRY_RUN=false` only for live execution
- Dry-run logs identically to live (for backtesting)

---

## Risk Limits

Defaults — adjust in `.env`:

> **The live `.env` deliberately overrides several of these.** Current operator settings (bankroll ≈ $92, so the shipped defaults are sized for a much larger account): `UNIT_SIZE=1.00`, `KELLY_FRACTION=0.5`, `MAX_BET_SIZE=8`, `MAX_DAILY_LOSS=30`, `MAX_BET_RATIO=5`, `MIN_EDGE_THRESHOLD_MLB=0.03`, plus the longshot change below. Run `python scripts/doctor.py` to see what is actually in force — the values in this block are the code defaults, not the running config.
>
> - **The two sizing lanes are separately controlled, and it matters which knob you reach for.** Below ~30c the flat floor `round(UNIT_SIZE / price)` binds and Kelly never clears it, so **`UNIT_SIZE` alone sets longshot size**. Above ~60c Kelly binds and `UNIT_SIZE` is irrelevant (at 83c it asks for 1 contract), so **`KELLY_FRACTION` is the favorites knob**. They bind at different prices, so they can be tuned independently. `KELLY_FRACTION=1` was originally set on 2026-07-22 to size *longshots* up — the wrong knob; it barely moved them and silently took favorites to full portfolio Kelly.
> - **`KELLY_FRACTION` is effectively a *portfolio* fraction, not a per-bet one.** `kalshi_executor.py` divides it by `batch_size = min(len(opportunities), --max-bets)`. That divisor doubles as a crude correlation guard: a slate whose legs all resolve on one underlying (e.g. four MLB unders on a single night) splits **one** Kelly allocation instead of stacking N of them. The flip side is that at `KELLY_FRACTION=1` such a slate reaches **full Kelly** — the 2026-07-27 slate would have been $29.43, 32% of bankroll and ~98% of `MAX_DAILY_LOSS` in one evening. Keep it **≤ 0.5** unless a real correlation guard lands.
> - **`MIN_MARKET_PRICE=0.10` (2026-07-22, was 0.12).** Intentional re-opening of the longshot lane. Gate 3.5 is a pure *reject* threshold — it decides eligibility only and is independent of all sizing knobs. See the R7 note below for the original rationale and the `.env` comment for the current full-history read (sub-15c: 6W-47L / 53 bets; headline +47.5% ROI is 99% a single trade). **Open experiment — recheck after ~30 more settles.**

```env
UNIT_SIZE=1.00                  # Kelly floor per bet
KELLY_FRACTION=0.25             # Kelly multiplier (divided by batch size)
MAX_BET_SIZE=100                # Hard cap per bet (USD)
MAX_DAILY_LOSS=250              # Daily hard stop (USD)
MAX_OPEN_POSITIONS=50           # Concurrent open positions
MAX_PER_EVENT=2                 # Max positions per game/event
MAX_BET_RATIO=3.0               # Max bet as multiple of batch median
MIN_EDGE_THRESHOLD=0.03         # Minimum 3% edge (global)
MIN_MARKET_PRICE=0.12           # R7: reject bets priced below this (lottery-ticket floor); 0 disables. Raised 0.06->0.12 2026-07-14 (30d: sub-15c bets 0W-21L / -100%)
MIN_EDGE_THRESHOLD_NBA=0.04     # Per-sport override (2026-06-14 — lowered 0.06->0.04 alongside MLB; matching fix de-inflated edges)
MIN_EDGE_THRESHOLD_NCAAB=0.04   # Per-sport override (2026-06-14 — lowered 0.06->0.04 for consistency)
MIN_EDGE_THRESHOLD_MLB=0.04     # Per-sport override (2026-06-14 — lowered 0.06->0.04; the ~15% over-claim that justified the higher floor is now fixed upstream by the edge-matching corrections of 06-03/06-05. 2-4 week experiment, then recalibrate)
MIN_COMPOSITE_SCORE=6.0         # Minimum score (0-10)
MIN_CONFIDENCE=medium           # Reject below this confidence (low|medium|high) — R3
NO_SIDE_FAVORITE_THRESHOLD=0.25 # R1: NO bets below this price need elevated bar
NO_SIDE_MIN_EDGE=0.25           # R1: required edge when NO price < threshold (also needs confidence=high)
NO_SIDE_MIN_EDGE_GLOBAL=0.08    # R28 (2026-06-23): min edge on ANY NO bet (90d review: NO -7% vs YES +48% ROI). Effective NO floor = max(per-sport floor, this); 0 disables
NO_SIDE_KELLY_PRICE_FLOOR=0.35  # R1: below this NO-side price, apply Kelly multiplier
NO_SIDE_KELLY_MULTIPLIER=0.5    # R1: half-Kelly on NO bets below the price floor
NO_SIDE_KELLY_MULTIPLIER_GLOBAL=1.0 # R28: Kelly multiplier on ALL NO bets (default 1.0 = off; lower to shrink NO sizing)
MIN_CONSENSUS_BOOKS_NBA=8       # R29 (2026-06-23): NBA games with <8 agreeing books drop to `low` confidence (Gate 4.5 then rejects); filters stale recreational lines. 0 disables
MAX_LIVE_BOOK_AGE_SECONDS=1200  # L1 Phase 2: drop bookmakers whose in-play line is older than this (20m) from live-game consensus; 0 disables
MIN_LIVE_CONSENSUS_BOOKS=3      # L1 Phase 2: skip an in-progress game whose consensus the stale filter thinned below this many fresh books (fires only when staleness removed books; pre-game unaffected); 0 disables
CALIBRATION_STDEVS_TTL_DAYS=30  # C8 (2026-06-23): max age of auto-recalibrated per-sport stdevs in data/cache/calibration_stdevs.json before falling back to hardcoded defaults
KELLY_EDGE_CAP=0.15             # Soft-cap edge for Kelly sizing
KELLY_EDGE_DECAY=0.5            # Decay factor on edge above the cap
SERIES_DEDUP_HOURS=48           # Reject same-matchup bets within this window (0 disables)
SERIES_DEDUP_HOURS_MLB=72       # R9: MLB series span up to 72h (default 48h leaks the 49h adjacent-day case)
SERIES_DEDUP_HOURS_NHL=72       # R9: NHL series cycle on consecutive days like MLB
CROSS_CATEGORY_DEDUP=false      # R8: when true, collapse ML+Total+Spread on same game to one bet (highest composite). Per-sport overrides via CROSS_CATEGORY_DEDUP_<SPORT>=true|false
RESTING_ORDER_MAX_HOURS=24      # R4: cancel zero-fill resting orders older than this (0 disables)
ALLOW_PREDICTION_BETS=false     # R25 Gate 4.7: true to enable crypto/weather/spx/mentions/companies/politics bets
ALLOW_LIVE_BETS=false           # L1 Gate 4.8: true to enable bets on in-progress games (is_game_started)
ODDS_CACHE_TTL_SECONDS=300      # R24b: file-backed cache for Odds API responses (5 min default; 0 disables)
ODDS_CACHE_ENABLED=true         # R24b: false bypasses the file cache entirely
ODDS_LIVE_TTL_SECONDS=45        # L1: shorter TTL (both cache layers) when a sport response has an in-play event; pre-game keeps 300s
SCAN_CACHE_TTL_SECONDS=600      # R26: cache last preview's row→ticker mapping so `--pick … --execute` replays instead of rescanning (10 min default; 0 disables)
SCAN_CACHE_ENABLED=true         # R26: false forces every --execute call to rescan
```

> **⚠️ Config changes require a restart of any running web app.** `kalshi_executor.py` snapshots every gate threshold into module-level globals **at import time** — a long-running process never re-reads `.env`. The CLI re-imports on each invocation (always fresh), but the **local Streamlit app must be restarted** (`Ctrl+C` → `streamlit run webapp/app.py`) after editing `.env`, and the **Streamlit Cloud app uses Secrets, not `.env`** — update *Settings → Secrets* (saving auto-reboots) or hit *Reboot* at [share.streamlit.io](https://share.streamlit.io). Full procedure: `docs/web-app/LOCAL.md` and `docs/web-app/CLOUD.md`.

---

## MCP Servers

See `docs/setup/mcp-servers.md` for full setup.

| Server | Purpose |
|:-------|:--------|
| `alpaca-mcp` | Stock/options trading (paper + live) |
| `brave-search` / `tavily` | Real-time news & web research |
| `fetch` | HTTP requests to odds/market APIs |
| `filesystem` | Read/write positions, logs, data |
| `sqlite` / `postgres` | Trade history & strategy database |
| `memory` | Cross-session context |
| `ax-gcp` | AX Platform workspace coordination |

---

## Common Commands

```bash
# Setup
pip install -r requirements.txt

# Scan (preview only)
python scripts/scan.py sports --filter mlb --date today --save
python scripts/scan.py sports --filter mlb,nhl --date today --save
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py prediction --filter crypto

# Execute with budget cap
python scripts/scan.py sports --unit-size 1 --max-bets 5 --budget 10% --date today --exclude-open --execute

# Portfolio
python scripts/kalshi/risk_check.py --report positions

# Morning digest (yesterday P&L + open exposure + today pending)
python scripts/kalshi/daily_summary.py --save

# Backtest
python scripts/backtest/backtester.py --simulate --save

# Dashboard (local)
streamlit run webapp/app.py

# Dashboard (live)
# See docs/web-app/LOCAL.md for Cloud deployment instructions

# Automation
python scripts/schedulers/automation/daily_sports_scan.py
python scripts/schedulers/automation/install_windows_task.py install

# Makefile shortcuts
make scan-mlb    make scan-all    make status
make settle      make report      make backtest
make test        make hooks
```

---

## Session Startup Checklist

1. Run `git sync-master` — sync local master with remote (user works on `mike_win-desktop`, pushes to remote master; local master goes stale without this)
2. Read `data/positions/open_positions.json` — current exposure
3. Read `data/history/today_trades.json` — today's P&L
4. Check daily loss limit — if breached, **NO** new positions
5. Confirm `DRY_RUN` setting in `.env`
6. Run `python scripts/shared/check_odds_keys.py` — see cached Odds API quota. Add `--live` to probe each key (costs N requests) and refresh the cache.
7. Pull latest market data before analysis

---

## Output Standards

### Trade Rationale (required before execution)

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

### Research Output

- Lead with the edge/opportunity thesis
- Include data sources with timestamps
- Note contradicting signals
- End with actionable recommendation

---

## Workflow Patterns

### Discovery Loop

```
1. MARKET_RESEARCHER scans configured markets
2. Edge > MIN_EDGE_THRESHOLD → flagged
3. DATA_ANALYST validates with quantitative model
4. RISK_MANAGER checks sizing & portfolio limits
5. Approved → TRADE_EXECUTOR places order
6. PORTFOLIO_MONITOR logs result & tracks position
```

### Daily Cadence

| Time | Action |
|:-----|:-------|
| 4:50 AM PT | `Daily-Summary` — generate morning digest (yesterday P&L + open exposure + today pending + 7d rolling). Email at 5:00 AM PT (U2, 2026-04-30) |
| Morning | Pull overnight news, check positions, reset daily counters |
| Midday | Scan for opportunities, review open positions |
| Evening | Close day trades, log P&L, update strategy performance |

---

## Tech Stack

| Component | Technology |
|:----------|:-----------|
| Language | Python 3.11+ |
| Import Setup | `.venv/Lib/site-packages/edge_radar.pth` auto-adds script dirs |
| Key Libraries | `pandas`, `numpy`, `scipy`, `alpaca-trade-api` |
| Database | SQLite (local), PostgreSQL (production) |
| Scheduling | `APScheduler` / Windows Task Scheduler |
| Notifications | Slack webhook / email |
| Version Control | Git + pre-commit hooks (detect-secrets, black, flake8) |

---

## Hard Stops

Claude must **REFUSE** to execute (regardless of instruction) if:

- Daily loss limit is exceeded
- Single position would exceed 10% of total bankroll
- API credentials not properly loaded from environment
- Market is clearly illiquid (spread > 5%)
- Action would violate a platform's TOS

---

<sub>Built on AX Platform multi-agent architecture &mdash; Claude Code is the primary development environment</sub>
