---
name: edge-radar-analysis
description: Generate a comprehensive post-hoc betting performance report from local Kalshi settlement data. Trade ledger + slices by sport, category, side (YES/NO), edge bucket, confidence, market price, predicted-probability calibration, longshots, streaks, and daily P&L. Ad-hoc or scheduled.
argument-hint: [days] [--save] [--out PATH] — e.g., "30", "14 --save", "90"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep
---

# Edge-Radar Analysis Skill

You are executing `/edge-radar-analysis`. This skill produces a **comprehensive post-hoc performance report** for a rolling window of settled bets, pulled from local data (`data/history/kalshi_settlements.json` — populated by the nightly `kalshi_settler.py` task at 11 PM).

Use this for weekly reviews, ad-hoc "how am I doing" checks, and calibration attribution after risk-gate changes ship.

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

Accept natural phrasing. "Run the betting analysis for the last 30 days" = `30 --save`.

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
   - Longshot record.
   - Current streak.
5. If the user asks follow-up questions, re-read specific sections rather than regenerating.

## Freshness Awareness

`data/history/kalshi_settlements.json` is populated by `kalshi_settler.py`, scheduled as the Windows task installed via `python scripts/schedulers/automation/install_windows_task.py install settle` (nightly 11 PM).

- If the user asks about "today's" bets and the settler hasn't run since those games ended, the report will be missing them. Suggest manually running the settler (`python scripts/kalshi/kalshi_settler.py settle` or `make settle`) before generating the report.
- **Schema changed 2026-04-27 (R5).** Settlements written from this point carry `composite_score`, `risk_approval`, `bankroll_pct`, `category`, `title`, `closing_price`, `clv`, `edge_source`, `unit_size`, `fill_status` in addition to the legacy fields. Pre-R5 settlements (the historical 178 orphans) only carry the legacy schema — these show as `null` for the new fields and are excluded from any slicing on those dimensions. They still contribute to win rate / Brier / edge-bucket math (which only need `won`, `cost`, `revenue`, `edge_estimated`, `confidence`).
- For an audit of the trade-log/settlement join health and per-field coverage, run `python scripts/kalshi/risk_check.py --report reconciliation`.

## Scheduling

For periodic auto-generated reports, chain this after the nightly settler or run separately via Task Scheduler. The script is side-effect-free (reads JSON, writes markdown). A weekly Sunday-night job is a reasonable starting cadence.

Suggested command for a scheduled task:

```bash
.venv/Scripts/python.exe scripts/kalshi/betting_analysis.py --days 7 --save
.venv/Scripts/python.exe scripts/kalshi/betting_analysis.py --days 30 --save
```

## Related

- **`/edge-radar`** — unified scan/bet/status/settle command.
- **`scripts/kalshi/model_calibration.py`** — complementary calibration-focused report (Brier decomposition, cross-tabs, prescriptive recommendations). `betting_analysis.py` is broader and less prescriptive.
- **Roadmap items this report surfaces evidence for:** R7 (min market price floor — longshot section), R10 (category-weighted composite — by category), R12 (R2 attribution check at 100 trades — headline Brier + calibration section), C6 (totals bias audit — category + sport cross-reference).
