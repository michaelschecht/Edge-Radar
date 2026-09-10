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

## How the two strategies stay separate

Four independent layers, each doing one job. The mechanism is generic — a
second profile would use all four unchanged — but `longshot` is the only one
that exists today.

| Layer | Separated by | Where |
|:--|:--|:--|
| **1. Selection** | `--profile longshot` / `EDGE_RADAR_PROFILE` | `scripts/scan.py`, `app/config.py` |
| **2. Settings** | `.env.longshot` overlaid on the base `.env` | `apply_profile_overlay()` |
| **3. Money** | `KALSHI_SUBACCOUNT=1` — an exchange-enforced wallet | `scripts/kalshi/kalshi_client.py` |
| **4. Data** | `"profile"` tag on every trade row | `scripts/shared/trade_log.py` |

Only layer 3 is real isolation. The other three are bookkeeping that keeps the
two books from confusing *each other*; the exchange is what keeps them from
spending each other's money.

### 1. Selection — how a run picks a strategy

```bash
python scripts/scan.py sports --profile longshot --filter mlb --date today
EDGE_RADAR_PROFILE=longshot python scripts/doctor.py   # non-scan entry points
```

`--profile` is consumed by `scan.py` and **never forwarded** — the scanners
take no such flag. It reaches the child process as `EDGE_RADAR_PROFILE`, and
because `load_dotenv()` does not override variables already set, the overlay
survives the child's own `.env` load.

**It fails closed.** A missing `.env.<name>` raises rather than falling back,
because the base `.env` is the live-money wallet: a typo'd `--profile longshto`
that silently resolved to `main` would run one strategy's intent against the
other's bankroll, live. Same reasoning as S3's venue-eligibility check.

`doctor.py` prints the active profile and its wallet on a dedicated line
whenever it is not `main` — a balance or exposure report read without knowing
the profile is reading the wrong account's numbers.

### 2. Settings — what actually differs

The base `.env` loads first; the overlay is applied on top. **Only the keys the
overlay names differ.** Today that is four:

| Key | `main` | `longshot` | Effect |
|:--|--:|--:|:--|
| `KALSHI_SUBACCOUNT` | `0` | `1` | which wallet |
| `DRY_RUN` | `false` | `true` | longshot places no real orders |
| `MIN_MARKET_PRICE` | `0.10` | `0.08` | Gate 3.5 floor — **the strategy** |
| `MAX_PER_EVENT_FUTURES` | `2` | `3` | Gate 6, futures only |

Everything else is inherited: all nine risk gates, the fee model, calibration,
per-sport edge floors, the NFL freeze, and every future fix — in lockstep,
automatically. **That inheritance is the whole point.** The fork this replaced
ran `MAX_OPEN_EXPOSURE_PCT=0`, `MAX_SEGMENT_EXPOSURE_PCT=0`,
`MAX_DAYS_TO_EVENT_FOR_GAME_MARKETS=0`, `MAX_BET_SIZE=100` and
`MAX_DAILY_LOSS=250` — not by decision, but because nobody re-tightened the
shipped defaults after cloning.

So the comparison measures **the strategies**, not two drifting codebases.

### 3. Money — the only layer that isolates anything

`KALSHI_SUBACCOUNT` is threaded into every balance, position, order, fill,
settlement and cancel call. One client instance is one wallet.

Neither a second API key nor a second checkout of this repo isolates a
bankroll — both still draw on one balance, and each copy's `MAX_DAILY_LOSS`
and exposure gates would see only its own activity, never the combined
draw-down. **Bankroll isolation is an account-level fact, so it never
justified a fork.**

> ⚠️ **`balance_breakdown` on `get_balance()` is ACCOUNT-WIDE and ignores
> `subaccount`.** Only `balance` / `balance_dollars` are scoped. Verified
> 2026-09-08: queried as subaccount 1 (which held $40, all on shard 0) it
> returned `{0: 109.79, 3: 13.76}` — that subaccount's money summed with the
> primary's. Use `get_shard_balance(exchange_index)`, the only
> per-(subaccount, shard) read the v2 API offers.

### 4. Data — one trade log, two books

Every trade row carries `"profile"`, mirroring PM2c's `"venue"` one level up.
**Rows written before P1 have no key, and readers must default to `"main"`.**

One shared log is *better* evidence than two logs gave, because both books run
identical code, odds cache, fees and calibration. But it means any gate reading
**history** rather than the venue must be scoped, or it measures the wrong
book. Two do, and `for_profile()` scopes both:

| Gate | Reads | Scoped by |
|:--|:--|:--|
| **1** — daily loss limit | trade log | `for_profile()` |
| **7** — series dedup | trade log | `for_profile()` |
| 5 — already holding | live venue positions | Kalshi (subaccount) |
| 6 — per-event cap | live venue positions | Kalshi (subaccount) |

Unscoped, this is not cosmetic: a bad day on `main` would halt `longshot`, and
a matchup one profile bet would block the other — **across two genuinely
separate wallets.** This was live for one run after the merge; longshot's
banner reported `Today P&L: $-2.40` and `Series dedup: 2 active`, both of them
`main`'s.

**Settlement, CLV capture and reconciliation deliberately do *not* scope.**
They act on a row by `trade_id` or ticker, and a row is a row regardless of
which strategy opened it.

### Telling them apart in practice

```bash
# Which profile/wallet am I about to run as?
EDGE_RADAR_PROFILE=longshot python scripts/doctor.py

# Split the trade log by book
python -c "import json,collections; print(collections.Counter(t.get('profile','main') for t in json.load(open('data/history/kalshi_trades.json'))))"
```

Scan reports separate only by **convention**: every `main` scheduled task pins
an explicit `--report-dir` under `reports/*/schedulers/`, and `longshot_scan.bat`
pins none, so it lands in the default `reports/Sports/` and `reports/Futures/`.
Filenames carry the date, filter and type — **not the profile.** Two profiles
scanning the same filter on the same day into the same directory would
overwrite each other silently.

### Known soft spots

- **Reporting is pooled, not split.** `daily_summary.py`, `risk_check.py` and
  `betting_analysis.py` read the whole trade log. This is currently harmless
  only because `longshot` is `DRY_RUN=true`: a dry run returns
  `{"status": "dry_run_blocked"}` with no fill, so its rows are zero-fill,
  excluded from open positions and `$ at risk`, and never settle. **The day
  `DRY_RUN=false` is set on this profile, those surfaces start blending two
  books** and need `for_profile()` or a per-profile split first.
- **Settlement and reconciliation only ever see subaccount 0.** `KalshiClient()`
  takes its subaccount from the *active* profile, and every settle/reconcile
  task (`Hourly-Settle`, `NightlySettle`, `Reconcile`) runs unprofiled — so
  they run as `main`. Harmless today: longshot is `DRY_RUN=true`, never fills,
  and so has nothing to settle. **The day `DRY_RUN=false` is set, subaccount 1
  needs its own settle + reconcile tasks** (`EDGE_RADAR_PROFILE=longshot`) or
  its fills are never settled and its P&L never lands. `CLV-Capture` needs
  nothing — it reads the unfiltered trade log and calls `get_market()`, which
  is public market data, not portfolio-scoped, so it already covers both books.
- **Scan report filenames carry no profile tag** (above).
- **`MIN_MARKET_PRICE=0.08` is unresolved** — see the open question below.

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

## When to enable live

**Not on a date.** The pre-declared criterion is **[ROADMAP → P1b](../ROADMAP.md)**,
written 2026-09-10 while nothing was at stake (the S1b precedent).

The short version: seven days of scans have produced **one** trade row, and the
09-10 run approved **0 of 7** candidates — every rejection on *edge*, not price.
So `MIN_MARKET_PRICE=0.08` is barely binding, and flipping the flag today would
change nothing except downside. Resolve the price floor first, then read **CLV**
rather than ROI (S8/S9 — this profile will never accumulate enough settles for
ROI), then go to **pilot**, not straight to normal sizing.
