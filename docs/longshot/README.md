# Longshot profile

The longshot/futures strategy, run as a **profile** of this repo since
2026-09-10 (P1): `--profile longshot` overlays `.env.longshot` on the base
`.env` and routes every Kalshi call to **subaccount 1** (~$40, `DRY_RUN=true`).

Rules and usage: **[CLAUDE.md → Strategy Profiles](../../CLAUDE.md)**.
Full reasoning for the merge: **[CHANGELOG 2026-09-10 (P1)](../CHANGELOG.md)**.

| | |
|:--|:--|
| Overlay template | [`.env.longshot.example`](../../.env.longshot.example) |
| Scheduled tasks | `Longshot-Scan` 08:00, `Email-Longshot-Scan` 08:20 (see [task-schedules](../task-schedules/README.md)) |
| Trade rows | tagged `"profile": "longshot"` in the shared `data/history/kalshi_trades.json` |

---

## History

It began on 2026-09-04 as `Repos/Other_Apps/Edge-Radar-Longshot`, a second
checkout of this repo, so the two strategies' results could be compared over
time. It was folded back in on 2026-09-10.

The fork was buying bankroll isolation, and a fork cannot provide that — the
money is in the Kalshi account, not the repo, so two checkouts on one API key
share one balance. What isolates it is a **subaccount**, which the fork itself
discovered and shipped on 2026-09-07. That is an account-level fact, and one
codebase addresses it fine.

Measured before merging, the fork's real code delta was ~74 lines across three
concerns, none of them strategy, and its strategy delta was two env vars. In six
days it had already drifted into a live defect in each direction: it scanned
zero college football all September on a stale `KXNCAAFBGAME` prefix and was
missing S26/S27, while this side was missing its `dry_run` trade-row fix.

The fork was fully retired on 2026-09-10: the local checkout is deleted and the
GitHub remote (`michaelschecht/Edge-Radar-Longshot`, private, 22 commits) is
**archived, not deleted** — read-only and unarchivable at any time.

Two things were carried across because they existed nowhere else:

- **[FORK-ROADMAP-ARCHIVE.md](FORK-ROADMAP-ARCHIVE.md)** — the fork's own
  ROADMAP, verbatim, for the evidence in it: the subaccount/Advanced-tier
  sequence, the `balance_breakdown` discovery, and the price-band backtest.
- **[fork-evidence-window/](fork-evidence-window/)** — the ten scan reports it
  produced between 09-04 and 09-10, plus a note on the one trade row that was
  deliberately *not* migrated (a synthetic test artifact that would have
  injected a fake NFL row into the sample `nfl_week1_review.py` reads on 09-15).

Nothing else was lost: the code is in the archived remote, the `.env` knobs
became `.env.longshot`, and its private key was byte-identical to this repo's.

---

## Open question, carried forward and not decided by the merge

`MIN_MARKET_PRICE=0.08` **is contradicted by our own backtest.** The 8-12c band
it admits went **0W-36L (-103.3% ROI)** across all six settled months, while the
0-8c band it still excludes holds the book's two biggest winners. The standing
recommendation on record is **0.12 or 0.06, not 0.08**, and `spread`-as-category
(23% win, +31.7% ROI, n=111) as the better-evidenced route to a longshot
profile. It was carried over as-is so the merge changed no strategy.

**Resolve this before the profile ever runs with `DRY_RUN=false`.**
