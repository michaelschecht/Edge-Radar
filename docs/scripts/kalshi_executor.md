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

### Risk Gates (11 gates)

The pipeline rejects opportunities that fail any of gates 1-7 (including 4.5 and 4.6). Gates 8-9 downsize and approve.

| # | Gate | Rule |
|---|------|------|
| 1 | Daily loss limit | Today's losses must be under `MAX_DAILY_LOSS` ($250) |
| 2 | Max open positions | Must be under `MAX_OPEN_POSITIONS` (50) |
| 3 | Edge threshold | Must meet per-sport floor or `MIN_EDGE_THRESHOLD` global (3% default; NBA 12% [R14, 2026-04-24], NCAAB 10% [2026-04-18]). Rejection message shows the floor in use. |
| 4 | Composite score | Must meet `MIN_COMPOSITE_SCORE` (6.0) — confidence is factored into composite |
| 4.5 | Min confidence (R3) | Confidence label must be ≥ `MIN_CONFIDENCE` (default `medium`). Added 2026-04-21 after low-confidence bets showed 0W-3L / -105% ROI across two review windows. |
| 4.6 | NO-side favorite guard (R1) | NO bets whose market price < `NO_SIDE_FAVORITE_THRESHOLD` (0.25) need edge ≥ `NO_SIDE_MIN_EDGE` (0.25) AND confidence=high. Added 2026-04-21 after all 13 high-edge losers in the 14-day window were NO-side bets on heavy favorites. |
| 5 | Duplicate ticker | Can't already hold a position in this market |
| 6 | Per-event cap | Max `MAX_PER_EVENT` (2) positions on the same game |
| 7 | Series dedup | Same matchup (sport + team pair, date-agnostic) can't have been bet within `SERIES_DEDUP_HOURS` (48h). Added 2026-04-18 after calibration showed consecutive-night series bleeds. |
| 8 | Max bet size | Cost can't exceed `MAX_BET_SIZE` ($100) — sizing cap |
| 9 | Bet ratio cap | Single bet can't exceed `MAX_BET_RATIO` (3.0) times the batch median cost — sizing cap |

### Sizing

Uses **Kelly with flat unit floor**: `bet = max(unit_size, kelly_fraction * trusted_edge(edge) * bankroll) / market_price` contracts. Kelly scales up high-edge bets; low-edge bets stay at the flat unit minimum. The result is capped by gates 7-8 above.

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
