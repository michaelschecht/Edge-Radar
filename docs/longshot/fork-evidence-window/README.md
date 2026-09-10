# Fork evidence window — 2026-09-04 → 2026-09-10

The ten scan reports the retired `Edge-Radar-Longshot` fork produced during its
short life, kept because they are the **only** record of that window. Everything
else in that repo was recoverable — the code is in git, the ROADMAP is archived
beside this folder, its `.env` knobs became `.env.longshot`, and its private key
was byte-identical to the main repo's.

From 2026-09-10 the longshot profile writes its reports into the main repo's
`reports/` like any other run, so this folder does not grow.

| | |
|:--|:--|
| `Futures/` | 5 championship-futures scans (09-04, 09-07, 09-08, 09-09, 09-10) |
| `Sports/` | 5 individual-game longshot scans, same dates |

Both legs were preview-only until 2026-09-08, when the fork switched to
`--execute` under `DRY_RUN=true` — a preview writes a candidate list, not a bet,
so nothing before that date could ever settle.

## One row was deliberately not migrated

The fork's `data/history/kalshi_trades.json` held a single row that was **not**
carried into the main trade log:

```
ticker  KXNFLGAME-26SEP21X-A     status  dry_run_blocked
price   30c   contracts 1        edge 0.10   composite 8.50
```

It is a test artifact, not evidence. Real NFL tickers carry team codes
(`KXNFLGAME-26SEP09NESEA-NE`); `26SEP21X-A` is a placeholder, the metrics are
suspiciously round, and no log anywhere references its `trade_id` — a real
`--execute` run would have logged the order. It was written during the
2026-09-08 session that fixed the `dry_run` field, almost certainly by a test
writing to the live log path.

Migrating it would have injected a fabricated NFL row into the settled
population that `nfl_week1_review.py` reads on 2026-09-15 to decide whether to
unfreeze NFL. Losing a fake row costs nothing; adding one to that sample is a
real cost.
