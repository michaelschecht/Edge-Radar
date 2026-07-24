---
name: edge-radar-analysis
description: Generate a comprehensive post-hoc betting performance report from local Kalshi settlement data. Trade ledger + slices by sport, category, side (YES/NO), edge bucket, confidence, market price, predicted-probability calibration, longshots, streaks, and daily P&L. Ad-hoc or scheduled. Also handles snapshot mode — interactive Plotly account-growth chart at docs/my-documents/account-graph/<M-D-YY>/ — triggered by "snapshot the account", "regenerate the account graph", "build the account chart" or after a Kalshi balance pull.
argument-hint: [days] [--save] [--out PATH] — or "snapshot --cash X --portfolio Y --positions N"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep
---

# Edge-Radar Analysis Skill

You are executing `/edge-radar-analysis`. This skill produces a **comprehensive post-hoc performance report** for a rolling window of settled bets, pulled from local data (`data/history/kalshi_settlements.json` — populated by `kalshi_settler.py`, which runs **hourly at :35** (U1, 2026-07-20) plus the 11 PM `NightlySettle` backstop).

Use this for weekly reviews, ad-hoc "how am I doing" checks, and calibration attribution after risk-gate changes ship.

> **Scope: Kalshi only.** Settlement records carry no `venue` field — all 354 are Kalshi. Polymarket execution went live 2026-07-23 but **no Polymarket order has ever filled** (every candidate is still stopped by the 3% edge gate), so nothing from that venue reaches this report yet. If Polymarket starts filling, check whether `betting_analysis.py` needs a venue split before quoting blended ROI.

## Parse Arguments

Arguments: `$ARGUMENTS`

| Input form | Meaning |
|---|---|
| *(empty)* | 30-day window, print to stdout |
| `30` / `14` / `90` | Window in days, print to stdout |
| `30 --save` | Save to `reports/Performance/betting_analysis_YYYY-MM-DD_30d.md` |
| `--save` | 30 days + save (default window) |
| `--out PATH` | Write to a specific path |
| `last week` / `last month` | Interpret as 7 / 30 days |
| `snapshot` / `chart` / `graph` | Generate the **interactive account-growth HTML chart** instead of the markdown report. See "Account Snapshot Chart" below. |

Accept natural phrasing. "Run the betting analysis for the last 30 days" = `30 --save`. "Snapshot the account" / "regenerate the account graph" / "build the account chart" → snapshot mode.

## What The Report Contains

The script renders in this order. Reference the user to specific sections when answering follow-ups:

1. **Headline** — bet count, W-L, win rate, total cost, P&L, ROI, Brier, avg claimed edge, avg predicted probability, pace.
2. **By Sport** — count, W-L, WR%, cost, P&L, ROI per sport (NHL, MLB, NBA, NCAAB, MLS, etc.).
3. **By Category** — ML / Spread / Total / Prop.
4. **By Side** — YES vs NO. The F1 story in a row.
5. **By Claimed Edge Bucket** — 5-10%, 10-15%, 15-20%, 20-25%, ≥25%. Watch for inversion (high edges ≠ high ROI).
6. **By Confidence** — High / Medium / Low. R3 monitoring.
7. **By Market Price at Entry** — including longshot buckets (< 5¢, 5-10¢ = 9:1+, 10-15¢ = 5.67:1+).
8. **Calibration** — predicted probability bucket vs realized win rate + gap. R2 monitoring.
9. **Longshots** — every bet priced < 15¢ (≈ 5.67:1 or longer), with fair-value, edge, result.
10. **Streaks** — current streak, longest win, longest loss.
11. **Daily P&L** — running daily rollup with cumulative verification.
12. **Trade Ledger** — every bet row-by-row (date, sport, type, matchup, side, cost, price, edge, confidence, result, P&L, ROI).

## How To Run

The script is `scripts/kalshi/betting_analysis.py`. Always invoke via the project Python (`.venv/Scripts/python.exe` on Windows). Default settlement source is `data/history/kalshi_settlements.json`.

```bash
# Preview to stdout (30 days)
.venv/Scripts/python.exe scripts/kalshi/betting_analysis.py

# Specific window
.venv/Scripts/python.exe scripts/kalshi/betting_analysis.py --days 14

# Save with default filename
.venv/Scripts/python.exe scripts/kalshi/betting_analysis.py --days 30 --save
# -> reports/Performance/betting_analysis_YYYY-MM-DD_30d.md

# Custom path
.venv/Scripts/python.exe scripts/kalshi/betting_analysis.py --days 30 --out reports/custom/april.md
```

Full CLI flags:

| Flag | Default | Description |
|---|---|---|
| `--days N` | `30` | Lookback window in days |
| `--save` | off | Write to `reports/Performance/betting_analysis_YYYY-MM-DD_<N>d.md` |
| `--out PATH` | *(none)* | Explicit output path; overrides `--save` default |
| `--settlements PATH` | `data/history/kalshi_settlements.json` | Override source file |

## Execution Steps

1. Parse `$ARGUMENTS` for a day count and save/output flags.
2. Run the script via Bash with the resolved args.
3. If `--save` or `--out` was used, confirm the output path. Otherwise surface the rendered markdown directly.
4. **After the report is generated**, read it back and surface the highlights the user most often cares about:
   - Headline line (N bets, W-L, WR%, ROI, Brier).
   - Top and bottom sport by ROI.
   - YES vs NO divergence.
   - Any edge-bucket inversion (≥25% claimed edge with poor ROI).
   - Longshot record — **always with and without its top winner** (see Freshness Awareness).
   - Current streak.
5. If the user asks follow-up questions, re-read specific sections rather than regenerating.

## Freshness Awareness

`data/history/kalshi_settlements.json` is populated by `kalshi_settler.py`. Two Windows tasks write it:

| Task | Cadence | Note |
|---|---|---|
| `Hourly-Settle` | every hour at **:35** | U1 (2026-07-20). Enabled by M2's cross-process trade-log lock, which made concurrent settle+execute merge-safe. Sharpens Gate 1 daily-loss accuracy intraday. |
| `NightlySettle` | 11:00 PM | Original backstop (`install_windows_task.py install settle`). Was slated for retirement ~1 week after U1; still live as of 2026-07-23. |

- Freshness is now much better than it used to be — worst case the data is ~1 hour stale, not ~24. If the user asks about games that finished within the hour, suggest `make settle` (or `python scripts/kalshi/kalshi_settler.py settle`) before generating.
- **Schema changed 2026-04-27 (R5).** Settlements written from this point carry `composite_score`, `risk_approval`, `bankroll_pct`, `category`, `title`, `closing_price`, `clv`, `edge_source`, `unit_size`, `fill_status` in addition to the legacy fields. Pre-R5 settlements (**190 of the current 354** — recount before quoting, it only grows as a share denominator) carry only the legacy schema, show as `null` for the new fields, and are excluded from any slicing on those dimensions. They still contribute to win rate / Brier / edge-bucket math (which only need `won`, `cost`, `revenue`, `edge_estimated`, `confidence`).
- **Beware single-trade artifacts in thin slices.** Several buckets are small enough that one outlier drives the headline — as of 2026-07-23 the sub-15¢ longshot bucket shows +47.5% ROI over 53 bets, but 99% of that P&L is one trade. When reporting any slice under ~50 bets, state the record **with and without its top winner**.
- For an audit of the trade-log/settlement join health and per-field coverage, run `python scripts/kalshi/risk_check.py --report reconciliation`.

## Scheduling

For periodic auto-generated reports, chain this after the nightly settler or run separately via Task Scheduler. The script is side-effect-free (reads JSON, writes markdown). A weekly Sunday-night job is a reasonable starting cadence.

Suggested command for a scheduled task:

```bash
.venv/Scripts/python.exe scripts/kalshi/betting_analysis.py --days 7 --save
.venv/Scripts/python.exe scripts/kalshi/betting_analysis.py --days 30 --save
```

## Account Snapshot Chart

Snapshot mode produces the interactive Plotly HTML at `docs/my-documents/account-graph/<M-D-YY>/account_graph.html` — a visual companion to the markdown report. Use it when the user asks to **"snapshot the account"**, **"regenerate the account graph"**, **"build the account chart"**, or after a new Kalshi deposit / balance pull. Each run lands in its own dated subfolder so historical snapshots are preserved.

### Required inputs

The script reads settled bets from `data/history/kalshi_settlements.json` automatically, but the **live snapshot must come from the user**:

| Value | Source |
|---|---|
| `--cash` | Kalshi cash balance (USD) |
| `--portfolio` | Kalshi portfolio value — open-position market value (USD) |
| `--positions` | Open-position count |

If the user hasn't provided these, ask them to run `python scripts/kalshi/risk_check.py --report positions` (or paste the Kalshi UI's Portfolio Status block) and surface those three numbers.

### How to run

```bash
.venv/Scripts/python.exe docs/my-documents/account-graph/Script/build_account_graph.py \
  --cash 65.88 --portfolio 27.54 --positions 23
```

`--as-of` defaults to today; the output folder is named `<M-D-YY>` based on it. The builder also writes a `snapshot.json` capturing every input + summary stats, so the chart is reproducible.

### Optional flags

| Flag | Default | When to use |
|---|---|---|
| `--as-of YYYY-MM-DD` | today | Backfill or post-date a snapshot |
| `--deposit USD` | `45.50` | New deposits to Kalshi land here |
| `--deposit-date YYYY-MM-DD` | `2026-03-22` | Update if deposits start before/after |
| `--out-dir PATH` | `<M-D-YY>/` | Override the dated subfolder |
| `--settlements PATH` | `data/history/kalshi_settlements.json` | Use a different settlements source |

### Execution steps

1. Confirm the user has provided cash + portfolio + positions. If not, prompt for them.
2. Run the builder via Bash with the resolved args.
3. Print the output path and the three key numbers from stdout: settled-only balance, live total, open-position drift.
4. If the open-position drift looks wrong (e.g., negative when the user is up overall), suggest re-pulling settlements (`make settle`) — the local ledger may be stale.

## Related

- **`/edge-radar`** — unified scan/bet/status/settle command.
- **`scripts/kalshi/daily_summary.py`** (U2, 2026-04-30) — daily morning digest. Different scope: 24h rolling window + open exposure + today-pending events + live balance, designed as a quick wake-up signal. Use this skill for retrospective / weekly+ analysis; `daily_summary.py` for the single-morning view. Both pull from `data/history/kalshi_settlements.json` so freshness caveats are identical.
- **`scripts/kalshi/model_calibration.py`** — complementary calibration-focused report (Brier decomposition, cross-tabs, prescriptive recommendations). `betting_analysis.py` is broader and less prescriptive.
- **Roadmap items this report surfaces evidence for:**
  - **R7** (min market price floor) — longshot section. Live floor has moved twice: 0.06 → 0.12 (2026-07-14) → **0.10** (2026-07-22, deliberate re-opening of the longshot lane). This is the report's most-watched open experiment; recheck the sub-15¢ bucket after ~30 more settles past 2026-07-22.
  - **C4** (2026-06-24, high→medium composite cap) — the By Confidence section is the scoreboard. C4 fired because High showed 41.5% WR / +13.5% ROI vs Medium 53.2% / +44.4%, and lost to Medium even at equal claimed edge. Confirm High hasn't re-inflated.
  - **C10** (2026-07-23, futures composite edge scale) — futures were structurally unreachable at Gate 4, which is why **0 of the 85 logged trades are futures**. Any futures row appearing in By Category is the first evidence the fix works.
  - **R28** (NO-side global 8% edge floor) — By Side. Fired on a 90d read of NO at −7% vs YES +48% ROI.
  - **R10** (category-weighted composite) — by category. Resolved 2026-07-20 without re-weighting; the April premise had inverted.
  - **R12** (R2 attribution check at 100 trades) — headline Brier + calibration section.
  - **C6** (totals bias audit) — category + sport cross-reference. Measured 2026-07-20, no tuning applied.
