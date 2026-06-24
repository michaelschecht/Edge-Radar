# Edge-Radar Prompt Library

Ready-to-use natural-language prompts for driving Edge-Radar through Claude Code. Each file is a self-contained prompt: a short brief, the exact CLI commands to run, and what to surface in the response. Paste one into a session, or just describe what you want and Claude will pick the right scan/execute flow.

**Research-first, execute-second.** Most prompts preview (scan) by default. Anything that places real bets uses `--execute`, requires `DRY_RUN=false`, and passes every risk gate in `CLAUDE.md`.

> **Related, but not here:** the `/edge-radar` skill is the unified scan/bet/status/settle/risk command center, and `/edge-radar-analysis` produces performance reports. These prompts are lightweight, copy-pasteable recipes; the skills are richer interactive tools.

---

## Folders

| Folder | What it covers |
|:-------|:---------------|
| [`sports-betting/`](#sports-betting) | NBA/NHL/MLB/NFL/NCAA/soccer/combat/motorsport game, spread, total & prop scans and execution |
| [`predictions/`](#prediction-markets) | Crypto, weather, S&P 500, TV mentions, companies & politics binary markets |
| [`futures/`](#championship-futures) | Championship & season-long outright (futures) markets |
| [`portfolio/`](#portfolio--risk) | Daily routines, status, risk audits, settlement & reviews |
| [`analysis/`](#analysis--diagnostics) | Backtesting, calibration, environment health & quota checks |

---

## sports-betting

The largest category. Sport filters: `nba`, `nhl`, `mlb`, `nfl`, `ncaamb`, `ncaawb`, `ncaafb`, `ncaabb`, `soccer` (+ `mls`, `epl`, `ucl`, `laliga`, `seriea`, `bundesliga`, `ligue1`, `worldcup`), `ufc`, `boxing`, `f1`, `nascar`, `ipl`, `esports` (`cs2`/`lol`). (`pga` routes to the futures scanner.)

| Prompt | Use it to… |
|:-------|:-----------|
| [daily-scan](sports-betting/daily-scan.md) | Preview the top edges across all active sports |
| [sport-specific-scan](sports-betting/sport-specific-scan.md) | Deep-scan a single sport (with the full filter roster) |
| [mlb-daily](sports-betting/mlb-daily.md) | Full-context MLB scan (our highest-volume sport) |
| [tomorrow-preview](sports-betting/tomorrow-preview.md) | Get ahead of tomorrow's lines before they move |
| [high-conviction-only](sports-betting/high-conviction-only.md) | Only the strongest edges (5%+, high confidence) |
| [spreads-only](sports-betting/spreads-only.md) | Point-spread edges only |
| [totals-only](sports-betting/totals-only.md) | Over/under edges only |
| [player-props](sports-betting/player-props.md) | Player-prop markets (PTS/REB/AST, goals, etc.) |
| [live-betting](sports-betting/live-betting.md) | In-progress games (`ALLOW_LIVE_BETS` opt-in, Gate 4.8) |
| [compare-two-sports](sports-betting/compare-two-sports.md) | Decide which of two sports has better value tonight |
| [execute-top-picks](sports-betting/execute-top-picks.md) | Scan one sport and execute the top picks |
| [multi-sport-execute](sports-betting/multi-sport-execute.md) | Full scan-and-execute session across all sports |
| [settle-and-review](sports-betting/settle-and-review.md) | Settle bets and review performance + CLV |

## prediction-markets

> **Execution is gated off by default (Gate 4.7 / R25).** Scans always preview; placing prediction bets requires `ALLOW_PREDICTION_BETS=true`. Filters: `crypto` (+ `btc`/`eth`/`xrp`/`doge`/`sol`), `weather`, `spx`, `mentions`, `companies`, `politics`.

| Prompt | Use it to… |
|:-------|:-----------|
| [scan-all-predictions](predictions/scan-all-predictions.md) | One scan across every prediction category |
| [morning-prediction-brief](predictions/morning-prediction-brief.md) | Quick morning overview of all prediction markets |
| [crypto-edge-scan](predictions/crypto-edge-scan.md) | BTC/ETH/XRP/DOGE/SOL binary mispricing |
| [weather-betting](predictions/weather-betting.md) | Temperature-threshold markets (13 cities) |
| [spx-daily-scan](predictions/spx-daily-scan.md) | S&P 500 binary options using SPX + VIX |
| [mention-markets](predictions/mention-markets.md) | TV mention / word-count markets |
| [execute-predictions](predictions/execute-predictions.md) | Scan one category and execute (opt-in gate) |
| [full-prediction-execute](predictions/full-prediction-execute.md) | Full scan-and-execute session across categories |

## championship-futures

Outright/futures markets priced via N-way de-vigging. Edges are small (0.5–2% normal) and capital locks up until resolution. Filters: `nfl-futures` (`superbowl`), `nba-futures`, `nhl-futures`, `mlb-futures`, `ncaab-futures`, `golf-futures`.

| Prompt | Use it to… |
|:-------|:-----------|
| [championship-scan](futures/championship-scan.md) | Scan all futures markets for the best edges |
| [best-value-across-sports](futures/best-value-across-sports.md) | Find the single best futures bet right now |
| [sport-futures-report](futures/sport-futures-report.md) | Detailed report for one sport's futures |
| [build-futures-portfolio](futures/build-futures-portfolio.md) | Allocate $10–$20 across a diversified futures basket |
| [weekly-futures-tracker](futures/weekly-futures-tracker.md) | Week-over-week tracking of how edges move |
| [execute-futures](futures/execute-futures.md) | Execute futures picks with a tight budget cap |

## portfolio & risk

| Prompt | Use it to… |
|:-------|:-----------|
| [morning-routine](portfolio/morning-routine.md) | Full morning startup: digest → settle → risk → scan |
| [status-check](portfolio/status-check.md) | Complete portfolio + risk-exposure snapshot |
| [risk-audit](portfolio/risk-audit.md) | Deep dive on concentration & limit utilization |
| [end-of-day](portfolio/end-of-day.md) | Close out the day: settle, review, preview tomorrow |
| [weekly-review](portfolio/weekly-review.md) | End-of-week performance breakdown & strategy plan |

## analysis & diagnostics

| Prompt | Use it to… |
|:-------|:-----------|
| [backtest](analysis/backtest.md) | Backtest settled trades & run strategy what-ifs |
| [performance-report](analysis/performance-report.md) | Calibration / Brier / CLV report on closed positions |
| [health-check](analysis/health-check.md) | Validate `.env`, keys & imports; check Odds API quota |

---

## Conventions

- **Preview before execute.** Scan prompts stop at a table; execute prompts show the preview, wait for confirmation, then place orders.
- **`--exclude-open`** skips markets where you already hold a position (avoids doubling up).
- **`--save`** writes a markdown report under `reports/` (Sports/, Futures/, etc.).
- **`--date today|tomorrow|YYYY-MM-DD`** scopes sports scans to a slate.
- **Opt-in gates:** prediction execution needs `ALLOW_PREDICTION_BETS=true`; in-progress games need `ALLOW_LIVE_BETS=true`.
- **Config changes need a restart** of any running Streamlit app — gate thresholds snapshot at import time. The CLI always re-reads `.env`.

See `CLAUDE.md` for the full gate list, risk limits, and `.env` reference.
