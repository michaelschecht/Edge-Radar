# kalshi_executor.py — Portfolio Status & Execution Library

**Location:** `scripts/kalshi/kalshi_executor.py`

**Role:** Two purposes:
1. **`status` subcommand** -- Quick portfolio dashboard (balance, positions, P&L)
2. **Internal execution library** -- All scanners call `execute_pipeline()` from this module when `--execute` is passed to `scan.py`

> **Note:** The `run` subcommand is a deprecated legacy entry point that predates `scan.py`. Use `scan.py` for all scanning and execution.

---

## `status` -- Portfolio Dashboard

```bash
python scripts/kalshi/kalshi_executor.py status [flags]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--save` | off | Save status report as markdown to `reports/Accounts/Kalshi/kalshi_status_YYYY-MM-DD.md` |

Shows: balance, portfolio value, open positions table (Bet, Type, Pick, When, Qty, Cost, P&L), today's P&L, resting orders.

### Examples

```bash
# Console only
python scripts/kalshi/kalshi_executor.py status

# Console + save markdown report
python scripts/kalshi/kalshi_executor.py status --save
```

---

## Execution Pipeline (Library)

When any scanner is called with `--execute`, it imports `execute_pipeline()` from this module. The pipeline:

1. **Portfolio state** -- fetches balance, open positions, today's P&L
2. **Correlated bracket dedup** -- collapses multiple totals/spread lines on the same game into the single best-scoring pick (e.g., Over 221.5, Over 224.5, Over 228.5 on BOS@MIL → keeps only the highest composite score)
3. **Risk check** -- validates daily loss limit, max open positions, per-trade sizing
4. **Min-bets gate** -- if `--min-bets N` is set and fewer than N bets passed risk checks, abort to avoid over-concentrating the budget into too few positions
5. **Sizing** -- calculates contract count based on `--unit-size` and market price
6. **Preview table** -- shows all approved orders with Bet, Type, Pick, When, Qty, Price, Cost, Edge
7. **Execution** (if `--execute` is passed) -- places limit orders via Kalshi API
8. **Trade logging** -- records each trade to `data/history/`

### Risk Gates (16 gates)

Gates 1-7 reject. Gates 8-9 downsize and approve. **Gate 2b does both** — it rejects when a
ceiling is already breached and trims the order otherwise.

| # | Gate | Rule |
|---|------|------|
| 1 | Daily loss limit | Today's losses must be under `MAX_DAILY_LOSS` ($250 default) |
| 2 | Max open positions | Must be under `MAX_OPEN_POSITIONS` (50) |
| 2b | **Cumulative exposure (S4, 2026-08-26)** | Total open at-risk must be under `MAX_OPEN_EXPOSURE_PCT` of equity, and the row's own sport under `MAX_SEGMENT_EXPOSURE_PCT` (live 0.50 / 0.33; both ship at 0 = off). **The only gate that measures a standing total** — gate 2 counts rows, gate 6 binds one event, gates 8/9 and `--budget` bind a single batch, and all of them passed while 26 NFL positions reached 31% of bankroll over three months. Denominated in **equity** (cash + position value), not cash. Rejects at/over a ceiling; otherwise trims the order to the smaller remaining headroom (`APPROVED_CAPPED_EXPOSURE`). Fails open on unknown equity. |
| 3 | Edge threshold | Must meet the per-sport floor or `MIN_EDGE_THRESHOLD` global (3% default; MLB/NBA/NCAAB 4% [2026-06-14, lowered from 0.06]). **The exchange fee is added to the floor** (F1, 2026-08-25), so the effective bar is ~4.8% at 50c. A floor >= 1.0 is unreachable and means the sport is **off** — the rejection reads `sport_disabled`. |
| 3.5 | Market-price floor (R7) | Reject below `MIN_MARKET_PRICE` (0.12 default, live 0.10). Lottery-ticket filter; 0 disables. |
| 3.6 | Liquidity floor (L2, 2026-08-18) | Bid/ask spread must be <= `MAX_BID_ASK_SPREAD` ($0.05) and 24h volume >= `MIN_MARKET_VOLUME_24H` (0 = off). Implements the CLAUDE.md "spread > 5%" Hard Stop, which was documented from launch but unenforced for five months. Fails open on a missing book. |
| 3.7 | **Time-to-event cap (S5, 2026-08-26)** | Game markets only: days from now to the event must be <= `MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS` (0 = off, live 14). **Futures are exempt by category**, not ticker prefix — `KXMLB-26-LAD` and `KXMLBGAME-26AUG26...` share a prefix and only the scanner's `category` separates them. Caps lead time, not sports: near-dated college football is untouched. Fails open on an unparseable date. |
| 4 | Composite score | Must meet `MIN_COMPOSITE_SCORE` (6.0) — confidence is factored into composite |
| 4.5 | Min confidence (R3) | Confidence label must be >= `MIN_CONFIDENCE` (default `medium`). Added 2026-04-21 after low-confidence bets showed 0W-3L / -105% ROI across two review windows. |
| 4.6 | NO-side favorite guard (R1) | NO bets whose market price < `NO_SIDE_FAVORITE_THRESHOLD` (0.25) need edge >= `NO_SIDE_MIN_EDGE` (0.25) AND confidence=high. Added 2026-04-21 after all 13 high-edge losers in the 14-day window were NO-side bets on heavy favorites. |
| 4.6b | NO-side global floor (R28) | Effective floor on **any** NO bet = max(per-sport floor, `NO_SIDE_MIN_EDGE_GLOBAL` = 0.08). |
| 4.7 | Prediction-market safety (R25) | Rejects `opp.category` in `crypto` / `weather` / `spx` / `mentions` / `companies` / `politics` unless `ALLOW_PREDICTION_BETS=true`. Added 2026-04-24 after an audit found all 6 modules cache stale data with no TTL, have zero settlements, and produce nonsense fair values (Miami weather at $1.00 fair on a 1F window). |
| 4.8 | Live/in-play safety (L1) | Rejects games already started (`is_game_started`) unless `ALLOW_LIVE_BETS=true`. |
| 5 | Duplicate ticker | Can't already hold a position in this market |
| 6 | Per-event cap | Max `MAX_PER_EVENT` (2) positions on the same game |
| 7 | Series dedup | Same matchup (sport + team pair, date-agnostic) can't have been bet within `SERIES_DEDUP_HOURS` (48h global). Per-sport overrides via `SERIES_DEDUP_HOURS_<SPORT>` (R9, 2026-04-27): MLB=72h, NHL=72h to cover 3-game series cycles after F12 (NYM/LAD pair @ 49h slipped the global, both lost). Added 2026-04-18 (C5) after calibration showed consecutive-night bleeds. |
| 8 | Max bet size | Cost can't exceed `MAX_BET_SIZE` ($100 default, live $8) — sizing cap |
| 9 | Bet ratio cap | Single bet can't exceed `MAX_BET_RATIO` (3.0) times the batch median cost — sizing cap |

**Preflight preview.** `preflight_gate_status()` predicts the per-opportunity gates for a scan
table (`off` / `edge` / `price` / `illiq` / `far` / `score` / `conf` / `no-fav` / `pred-off` /
`live-off`). It is **static only** — gates 1, 2, 2b, 5, 6 and 7 all need live portfolio state,
so an `ok` verdict means the row itself has no blockers, not that execution will succeed.

### Sizing

Uses **Kelly with flat unit floor**: `bet = max(unit_size, kelly_fraction * trusted_edge(edge) / (1 - market_price) * bankroll) / market_price` contracts. Kelly scales up high-edge bets; low-edge bets stay at the flat unit minimum. The result is capped by gates 8-9 above, and by gate 2b's exposure headroom.

**Kelly price complement (C11, 2026-07-27).** The `/ (1 - market_price)` term is the actual Kelly formula for a binary contract — `f* = (q - p) / (1 - p)`, i.e. `edge / (1 - price)`. It was missing until 2026-07-27: the even-money (`b=1`) approximation, exact only at 50¢ and increasingly wrong toward either extreme. Favorites were under-sized by `1/(1-p)` — 2.5x at 60¢, 5.0x at 80¢, 5.9x at 83¢ — and because the flat unit floor then won at high prices, nearly every bet above ~60¢ collapsed to a single contract (mean contracts by entry price: sub-40¢ 5.56, 40-60¢ 1.83, 60¢+ 1.17). That starved the best-calibrated band in the book: 60¢+ beats break-even by +11.1 points (44/52 vs a 73.6% break-even, one-sided binomial p=0.044), the only price band distinguishable from noise.

**Which knob moves what.** Below ~30¢ the flat floor `round(unit_size / price)` binds and Kelly never clears it, so `UNIT_SIZE` alone sets longshot size. Above ~60¢ Kelly binds and `UNIT_SIZE` is irrelevant (at 83¢ it asks for 1 contract), so `KELLY_FRACTION` is the favorites knob. They bind at different prices and are independently tunable.

**`KELLY_FRACTION` is a *portfolio* fraction.** It is divided by `batch_size = min(len(opportunities), --max-bets)`, and that divisor doubles as a crude correlation guard — a slate whose legs share an underlying splits one Kelly allocation instead of stacking N. The consequence is that at `KELLY_FRACTION=1` a fully correlated slate reaches **full Kelly**. Keep it at or below 0.5.

`trusted_edge()` soft-caps the edge used in the Kelly calculation at `KELLY_EDGE_CAP` (default 0.15). Excess is multiplied by `KELLY_EDGE_DECAY` (default 0.5) — so a 25% claimed edge sizes like 20%, a 35% like 25%. Raw edge is unchanged in gate 3, composite score, reports, and the trade journal. Introduced 2026-04-18 after calibration showed claimed edges ≥25% realize -35% ROI.

**NO-side Kelly dampener (R1, 2026-04-21).** NO bets priced below `NO_SIDE_KELLY_PRICE_FLOOR` (default $0.35) are sized at `NO_SIDE_KELLY_MULTIPLIER` (default 0.5 = half-Kelly) of normal Kelly. Complements gate 4.6 — bets that clear the reject gate but are still on relatively heavy favorites get downsized rather than taken at full confidence.

---

## `run` -- Legacy Scan & Execute (Deprecated)

Use `scan.py` instead. See [scan.py flags](../SCRIPTS_REFERENCE.md#scanpy--unified-scanner).

```bash
# OLD (deprecated):
python scripts/kalshi/kalshi_executor.py run --filter nba --execute --unit-size 2

# NEW (use this instead):
python scripts/scan.py sports --filter nba --execute --unit-size 2
```
