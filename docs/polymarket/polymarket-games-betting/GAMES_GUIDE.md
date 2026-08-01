# ⚾ Polymarket Games Guide

<p align="center">
  <img src="https://img.shields.io/badge/Surface-Per--Game%20Markets-8b5cf6?style=for-the-badge&labelColor=09090b" alt="Games">
  <img src="https://img.shields.io/badge/Data-International%20Gamma-f59e0b?style=for-the-badge&labelColor=09090b" alt="Gamma">
  <img src="https://img.shields.io/badge/Executable-No%20(Evidence%20Only)-e74c3c?style=for-the-badge&labelColor=09090b" alt="Not executable">
</p>

Per-game moneyline / spread / total edge detection, implemented in `scripts/polymarket/polymarket_games_edge.py` (PM1d).

> [!WARNING]
> **This surface is not executable.** It reads the **international Gamma** API, whose slug namespace is different from Polymarket US. Games opportunities deliberately record **no** `market_slug`, so `create_order` refuses them and the execution pipeline filters them out automatically. They exist purely as dry-run evidence.

---

## Why it exists, and why it can't trade

The PM1d build was correct about Gamma and wrong about US.

**What PM1d got right.** The earlier PM0 spike concluded Polymarket had no per-game markets. That was wrong — Gamma carries ML, run-line spread, and total for every MLB/NFL/NBA/NHL game, with tight 1–4¢ books. They're simply invisible to title search and default listing order; they surface only via `tag_id` + open filtering. (The same discovery failure mode that hid the PM1b futures boards.)

**What changed underneath it.** The 2026-07-20 discovery that the funded account is the **US** product invalidated the execution path for this surface. A 3,000-market catalog sweep found US is not a Gamma mirror:

| | International Gamma | **Polymarket US** |
|:--|:--|:--|
| Per-game moneyline | ✅ every game | ⚠️ seasonal only (NBA/NHL/NFL/CBB/CFB/UFC/soccer) |
| Per-game spread | ✅ run lines | ❌ **none anywhere** |
| Per-game total | ✅ O/U | ❌ **none anywhere** |
| MLB per-game | ✅ full slate | ❌ **none at all** |

So the games repoint is a deferred, **seasonal** follow-on: moneyline-only, wired per-league as seasons start, with spreads/totals/MLB dropped. Nothing is open during the summer offseason, which is why it hasn't been built yet.

---

## The edge model

Games reuse the **same calibrated consensus model that prices Kalshi sports bets**, imported unchanged from `edge_detector`:

| Market | Model function |
|:-------|:---------------|
| Moneyline | `consensus_fair_value` |
| Spread (run line) | `consensus_spread_prob` |
| Total (O/U) | `consensus_total_prob` |

That includes de-vig, weighted-median sharp-book logic, sport-specific stdevs, and the C8-calibrated overrides. Only the market side differs (Gamma instead of Kalshi).

Sport routing passes a synthetic Kalshi-prefixed `stdev_ticker` (e.g. `KXMLB`) purely so the models' prefix-based stdev lookup resolves the right sport; it never appears in output.

| Sport | `--filter` | Gamma tag | Odds API key |
|:------|:-----------|:----------|:-------------|
| MLB | `mlb-games` | `mlb` | `baseball_mlb` |
| NFL | `nfl-games` | `nfl` | `americanfootball_nfl` |
| NBA | `nba-games` | `nba` | `basketball_nba` |
| NHL | `nhl-games` | `nhl` | `icehockey_nhl` |

### Composite scoring (C10b, 2026-07-31)

The composite that feeds Gate 4 is the sports formula, with one deliberate difference:

```
composite = 0.4 * min(edge / 0.01, 10)          # edge, saturating at 10%
          + 0.3 * {high: 9, medium: 6, low: 3}  # confidence
          + 0.2 * max(0, 10 - book_spread*100)  # liquidity — steeper than Kalshi
          + 0.1 * 5                             # time-sensitivity placeholder
```

The edge term **was** `min(10, edge * 20)`, saturating at a 50% edge instead of 10%. This file was written three days before C10 and copied that expression from `polymarket_futures_edge.py`, which had itself copied it from its own `liquidity` line — a copy of a copy of the bug C10 diagnosed, so it had no independent rationale either.

The consequence was the same, and the evidence log proves it: clearing `MIN_COMPOSITE_SCORE=6.0` needed roughly **15% edge at high confidence, 26% at medium, 38% at low**, against game edges that run **1–7%** in practice. Across **362 logged Gamma game rows, not one ever reached 6.0** — the maximum observed was **5.30**. Gate 4 was structurally unreachable.

Aligning it is **not a floodgate**: replayed through the shipped code over those same 362 rows, only **5 (1.4%)** newly clear Gate 4, all marginally (6.02–6.26), and each still faces gates 3.5 / 4.5 / 4.6b / 5 / 6 / 7. The other **330** are stopped at Gate 3 (edge) and never reach Gate 4 at all. Nothing here is executable today regardless — the point is that the seasonal US repoint doesn't inherit an unreachable gate.

Two divergences from the sports composite are intentional:

- **Liquidity scales `* 100`, not `* 20`.** Rows wider than `MAX_BOOK_SPREAD` (0.10) are already dropped by the guard rail below, so `* 20` would compress every surviving row into 9.8–10.0 and the term would carry no information. `* 100` spreads the admissible band across the full range. The cost is that games and futures composites are not directly comparable when merged and ranked together.
- **`high` is weighted 9, not capped to 6.** C4 capped high→medium for *Kalshi sports* on 306 settled bets and scoped everything else out; there is still no settled Polymarket data. Worth revisiting when PM3 settlement lands — this path prices against the same Odds API consensus as sports, so C4's reasoning plausibly transfers even though its evidence doesn't.

---

## Guard rails

Three filters, each added in response to a specific failure:

**Pre-game only.** A game whose `gameStartTime` has passed is skipped, mirroring Gate 4.8's default posture. In-progress games otherwise keep producing edges against stale pre-game fair values until the odds feed drops them (finding F44).

**Book-quality floor.** Rows with a bid/ask spread wider than `MAX_BOOK_SPREAD` (0.10) are skipped — a quote nobody maintains is not a price. This also removes the exotic derivatives (NRFI, first-five, extra innings, player props), whose 2¢/98¢ books have no consensus source anyway.

**Start-time matching (±6h).** The one that caught a real bug. Team-name matching alone priced later games in a series against the *wrong* game's odds — it surfaced 3 phantom Twins edges live before the guard was added. This is the same bug class as the 2026-06-03 Kalshi incident, so the Polymarket game and the odds event must agree on start time, not just on teams.

---

## Reading the evidence

Games rows dominate the dry-run log by volume while contributing nothing executable — in the first four days, **66 of 79 logged rows were Gamma games**. Each logged row therefore carries an `executable` flag and each run an `executable_count`, and the preview shows a `US` column.

> [!TIP]
> When judging whether Polymarket edge is proving out, read `executable_count`, never `count`. The headline row count is mostly a surface you cannot trade.

---

## Usage

```bash
# All game sports (evidence only)
python scripts/scan.py polymarket --filter games

# One sport
python scripts/scan.py polymarket --filter mlb-games --min-edge 0.01 --save
```

`--execute` on a games-only scan will report that nothing is executable and place no orders.

---

<p align="center">
  <b><a href="../README.md">← Polymarket Index</a></b> ·
  <b><a href="../polymarket-futures-betting/FUTURES_GUIDE.md">Futures Guide</a></b> ·
  <b><a href="../polymarket-execution/EXECUTION_GUIDE.md">Execution Guide</a></b> ·
  <b><a href="../../kalshi/kalshi-sports-betting/SPORTS_GUIDE.md">Kalshi Sports Guide</a></b>
</p>
