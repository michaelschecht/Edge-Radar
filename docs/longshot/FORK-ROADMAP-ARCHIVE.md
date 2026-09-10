# Edge-Radar-Longshot — setup roadmap

*Last updated: 2026-09-08 — **Section 5's operator action is DONE: subaccount 1 is funded**
($40, all on exchange shard 0; sub 0 restored by a $40 deposit; verified against the exchange).
Four things shipped alongside it, three of them fixes to things that were quietly not working.
**(1)** `shard_balances()` read `balance_breakdown`, which **ignores the `subaccount` param** — so
this fork's wallet saw the *primary's* cash on a shard it holds $0 on, found no shortfall, and
would have approved an order the venue rejects `404 user_not_found`; the guard failed **open** in
exactly its own case. Fixed with `KalshiClient.get_shard_balance()`, and caught a real MLB total on
the first run after. **(2) The dry-run evidence window was recording nothing** — the scheduled task
was preview-only, and a preview writes a candidate list, not a bet, so `data/history/` held only a
README four days in. Now runs `--execute` under `DRY_RUN=true`, daily instead of weekly, with
explicit `--max-bets`/`--budget`. **(3)** But dry-run rows **still cannot settle** (blocked before
the venue ⇒ `fill_count: 0`/`resting`, which `settle_trades()` excludes), so forward-testing can
never answer a strategy question; a fill simulator was considered and rejected as assumption-laden,
and the question was answered by backtesting instead. **(4) Price band set to 8c-75c** — and the
backtest **contradicts the 0.08 floor**: the 8-12c band it newly admits is **0W-36L (-103.3% ROI)**
across all six months, while the 0-8c band it still excludes holds the book's two biggest winners.
Left at 0.08 pending the operator's call. **🔴 NEXT UP:** decide the floor (0.12 or 0.06, not 0.08),
and consider `spread`-as-category (**23% win, +31.7% ROI, n=111**) as the better-evidenced route to
the same longshot profile. Previous header follows.*

<sub>Previous header — Last updated: 2026-09-07 (retry, later same day) — **Section 0 bankroll isolation is DONE.**
The Advanced-tier grant that looked blocked earlier that day propagated a few hours later
(`usage_tier` flipped `basic` -> `advanced`, rate limits jumped 200/100 -> 300/300);
`create_subaccount()` then succeeded (`subaccount_number: 1`), verified genuinely isolated
($0.00 balance, no positions, vs. the primary account's real $85.86/$34.42 at the same moment),
and `.env` now sets `KALSHI_SUBACCOUNT=1` — `doctor.py` and a live dry-run scan both confirmed
clean against it. This fork's bankroll is now a real, exchange-enforced separate wallet under the
same Kalshi login, not a shared-balance soft limit. Earlier the same day: **Gate 6 split shipped**
(`MAX_PER_EVENT_FUTURES=3`, games stay at 2, +3 tests) and **confirmed** individual-game longshots
were already in scope/live alongside futures. **🔴 NEXT UP — OPERATOR ACTION:** subaccount 1 is
$0. Fund it (Section 5) before anything else here can move — this is the one step in this whole
doc that needs the operator, not the agent. After that: keep accumulating dry-run evidence and
settle Section 4's bet-sizing question before ever flipping `DRY_RUN=false`. Previous header
follows.</sub>

<sub>Previous header — Last updated: 2026-09-07 (earlier same day) — three operator decisions made
and (mostly) shipped: **Section 0 bankroll isolation moved to Option B** (real Kalshi subaccount,
not the shared-balance Option A) — client code done and tested (`KALSHI_SUBACCOUNT`, threaded
through every balance/position/order call), but subaccount creation was **blocked on Kalshi's
side** at the time: the self-serve Advanced-tier upgrade call succeeded and showed a grant, yet
the account's effective tier still read `basic` and creation still 403'd on the same requirement
— resolved a few hours later, see the current header above. **Gate 6 split shipped**:
`MAX_PER_EVENT_FUTURES=3` (individual games stay at 2), +3 tests. **Confirmed, no change
needed:** individual-game longshots were already in scope and live alongside futures — nothing
was futures-only. Previous header follows.</sub>

<sub>Previous header — Last updated: 2026-09-07 — repaired the dry-run scheduled-task paths after the
repo move: both tasks still referenced the retired `Repos/Draft/` location and
were failing with Task Scheduler result `1`. The portable batch scripts are now
tracked with the installer and the tasks were re-registered against this repo.
**Verified same day:** both `Longshot-Scan` and `Email-Longshot-Scan` manually
triggered post-repair and returned `LastTaskResult 0` (success), confirming the
fix holds rather than just looking right. The evidence window remains
dry-run-only. Previous update follows.</sub>

<sub>Previous header — Last updated: 2026-09-04 — repo graduated to its own remote (Section 6): moved
`Repos/Draft/` → `Repos/Other_Apps/`, pushed to a new **private** GitHub repo
(`michaelschecht/Edge-Radar-Longshot`), history squashed to one initial commit, Edge-Radar's
public-site artifacts (`.claude/html/`, `.claude/backup/`, Pages deploy workflow) dropped as
not-applicable. **🔴 NEXT UP:** unchanged from before — let the dry-run evidence window
accumulate, then the still-open Gate 6 `MAX_PER_EVENT` diversification question (Section 4).</sub>

<sub>Previous header — Last updated: 2026-09-04 — session paused here. **Done that session:** repo forked (local clone, not
pushed anywhere — see "how does forking work" note in Section 0-adjacent history), venv/deps
installed, baseline pytest run explained (1019 pass/10 fail, expected on a fresh `.env.example`
clone — not a defect), full evidence review of `docs/CHANGELOG.md` for prior longshot/futures
results (Section 3), Gates 6/7 checked against futures tickers (Section 4, no bugs found), CLV
report gap confirmed (Section 4), scope decided — **sports only: championship futures +
individual-game longshots (moneylines + alt-spreads), no crypto/politics** — and risk posture
decided — **conservative, matches main repo, `.env` already correct, no change needed**.
Cosmetic rename done (Section 6). `CLAUDE.md` rescoped to this fork's actual requirements — "What's
Live" now marks sports+futures in scope and crypto/politics/Polymarket out of scope, the
Polymarket-US Priority-0 section is quarantined as main-repo-only (it described a funded live
account, not this fork's), the Risk Limits block is flagged as main-repo `.env` evidence rather
than this fork's state, and the branch/sync notes no longer assume a pushed `origin`/`master`.
`ODDS_API_KEYS` filled in (reused main repo's 14 free-tier keys) and the missing
`.venv/Lib/site-packages/edge_radar.pth` recreated (fresh venv never got it — mechanical, same
`sys.prefix`-relative one-liner as main). **Found + corrected a wrong assumption in this doc:**
`KalshiClient()` requires `KALSHI_API_KEY`/`KALSHI_PRIVATE_KEY_PATH` just to **read** market data,
so Section 0 (bankroll isolation) blocks even a dry-run scan, not only going live. **Section 0
decided (2026-09-04, operator call): Option A** — this fork's `.env` now points at the same
Kalshi API key/private key as main Edge-Radar (`DRY_RUN=true`, so no orders place either way;
the shared-balance risk in Option A only applies once `DRY_RUN=false`). `scan --filter
nba-futures` and `scan sports --filter mlb --date today` both ran end-to-end with real output
(Section 5, first item). **Dry-run evidence window now runs itself**: two scheduled tasks
installed under a new `\Edge-Radar-Longshot\` Task Scheduler folder (`Longshot-Scan` 08:00 daily,
`Email-Longshot-Scan` 08:20 daily, reports to `mikeschecht+longshot@gmail.com`) — separate folder
and separate email address from main Edge-Radar's fleet, both verified live. **🔴 NEXT UP:** let
the window accumulate (nothing to do here but wait/check in), then the still-open Gate 6
`MAX_PER_EVENT` diversification question (Section 4).</sub>

---

Forked from `Live_Apps/Edge-Radar` (local `git clone`, `mike_desktop` branch, remote renamed
`upstream` — points at the local Edge-Radar path for pulling in future fixes, not GitHub; this
repo is un-pushed per `Repos/Draft/` convention). Goal: a strategy focused on longshot/futures
bets (low-price, high-payoff outcomes and season-long championship markets) instead of
Edge-Radar's current individual-game, short-horizon focus.

**This doc tracks fork-specific setup and strategy work only.** `docs/ROADMAP.md` came along with
the clone and is Edge-Radar's own history — it's stale for this repo's purpose, left as reference,
not maintained here.

---

## 0. Answered: does forking the repo also isolate the money?

**No.** The repo is just code. The bankroll lives in the Kalshi **account** (and, if you use one,
the **subaccount**) tied to whatever `KALSHI_API_KEY` / private key sits in this repo's `.env`.

- If this fork's `.env` points at the **same API key as the main Edge-Radar**, both codebases draw
  from and report against **one shared balance** — a bad day in one strategy reduces capital
  available to the other, and each repo's own `MAX_DAILY_LOSS`/exposure gates only see their own
  activity, not the combined draw-down.
- A **second API key on the same Kalshi account** doesn't fix this either — same account, same
  balance, still shared.
- The only thing that gives you an exchange-enforced separate wallet under one Kalshi login is a
  **subaccount** (`subaccount` index 1+, separate `get_balance`, separate positions — see the prior
  analysis at `Agents/Claude/.claude/temp/edge-radar-longshot-fork-analysis.md`), gated behind the
  self-serve Advanced API tier upgrade.

**Decision needed before going live:**
- [x] ~~Option A~~ — superseded 2026-09-07, see Option B below.
- [x] **Option B — real subaccount isolation — chosen 2026-09-07.** Code is done and tested;
      the live account isn't ready yet:
      - `scripts/kalshi/kalshi_client.py`: `KalshiClient(subaccount=...)` (defaults to
        `cfg.kalshi.subaccount`, i.e. `KALSHI_SUBACCOUNT` in `.env`, itself defaulting to `0` =
        primary). Threaded through `get_balance`, `get_positions`, `get_fills`,
        `get_settlements`, `get_orders`, `create_order` (body field), `cancel_order` (query
        param) — every call site in the codebase constructs `KalshiClient()` with no args, so
        one env var routes everything without touching call sites. New
        `get_account_limits()` / `upgrade_to_advanced_tier()` / `create_subaccount()` methods.
        `app/config.py` validates `KALSHI_SUBACCOUNT` is 0-63. +2 tests
        (`tests/test_kalshi_client_order.py`) pinning the order-body field, since a
        wrong/omitted value here would silently route an order back onto the shared primary
        balance instead of the isolated one.
      - **DONE 2026-09-07 (same day, later retry).** The Basic->Advanced grant from earlier that
        day was real but hadn't propagated yet — `GET /account/limits` initially still reported
        `usage_tier: basic` right after the upgrade call, and `POST /portfolio/subaccounts` 403'd
        with `subaccount_creation_requires_advanced_api_usage_level` even though the `advanced`
        grant for `event_contract` was already listed. A few hours later `usage_tier` read
        `advanced` (rate limits also jumped 200/100 -> 300/300, confirming it wasn't cosmetic),
        and `create_subaccount()` succeeded: **`subaccount_number: 1`**. Confirmed a real
        isolated wallet before wiring anything to it — `KalshiClient(subaccount=1).get_balance_dollars()`
        returned `$0.00 / $0.00` and `get_positions()` returned empty, against the primary
        account's real `$85.86 / $34.42` at the same moment.
      - `.env`: `KALSHI_SUBACCOUNT=1` is now set (was the commented placeholder). `doctor.py`
        confirms it: `Kalshi API connected (balance: $0.00)`, `DRY_RUN = true` unchanged. Ran a
        live dry-run scan (`scan.py sports --filter mlb --date today`) end-to-end against the
        subaccount with no errors.
      - **Section 0 is now fully resolved.** This fork's bankroll is a real, exchange-enforced
        separate wallet under the same Kalshi login — a bad day in main Edge-Radar's strategy
        cannot touch it, and vice versa. `DRY_RUN=true` still gates real orders regardless.
      - **Still open, deliberately deferred:** `shard_funding.py`'s `intra_exchange_transfer` /
        `ensure_shard_funded()` is not subaccount-aware. Irrelevant for now —
        `AUTO_SHARD_TRANSFER=false` in this fork — but revisit before ever turning shard
        auto-funding on for this subaccount. Also note: subaccount 1 needs its own deposit
        before any live order could actually fill there once `DRY_RUN=false` — it's currently
        unfunded by design.

~~Dry-run development doesn't need this decided — only matters before `DRY_RUN=false`.~~
**Corrected 2026-09-04: wrong.** `KalshiClient()` requires `KALSHI_API_KEY`/
`KALSHI_PRIVATE_KEY_PATH` just to read market data — a dry-run scan fails at client init without
them. This decision gates dry-run scanning too, not only live orders.

---

## 1. Local environment (mechanical — in progress)

- [x] Clone Edge-Radar locally into this path, `mike_desktop` checked out, `upstream` remote set
- [x] `.venv` created, `pip install -r requirements.txt` — clean install, no errors
- [x] Verify install: `./.venv/Scripts/python.exe -m pytest -q` → **1019 passed, 10 failed, 3
      skipped**. Confirmed **not a fork defect** — same 10 fail against a bare `.env.example`
      copy on upstream too; they pass once `MAX_OPEN_EXPOSURE_PCT`/`MAX_SEGMENT_EXPOSURE_PCT`/
      `AUTO_SHARD_TRANSFER` are tuned on, which `.env.example` ships *off* on purpose ("never move
      money unattended on a fresh clone"). Re-run once Section 4's config is set — expect green
      then; don't flip those on just to satisfy tests before you mean to.
- [x] Copy `.env.example` → `.env` (done); `ODDS_API_KEYS` filled with the main repo's free-tier
      keys (2026-09-04, read-only, no bankroll implication) — confirmed via `doctor.py`
      (`Odds API keys loaded: 14`)
- [x] Recreated `.venv/Lib/site-packages/edge_radar.pth` (2026-09-04) — a fresh venv doesn't get
      this file from `requirements.txt` alone; without it every script-level import
      (`from opportunity import Opportunity`, etc.) fails. Copied verbatim from main — it's a
      `sys.prefix`-relative one-liner, not repo-path-hardcoded, so it works unmodified in any venv.
- [ ] `KALSHI_API_KEY`/`KALSHI_PRIVATE_KEY_PATH` — **decide Section 0 first**. Confirmed
      2026-09-04: `KalshiClient()` requires these just to construct, so even a dry-run
      `scan --filter futures` is blocked until this is filled in.
- [ ] Keep `DRY_RUN=true` until Section 0 is resolved and the strategy has real dry-run evidence

---

## 2. What already exists for longshot/futures — don't rebuild this

The original repo turned out to have most of the futures-scanning infrastructure already:

- **`scripts/kalshi/futures_edge.py`** — dedicated futures scanner with **N-way de-vig**,
  covering NFL Super Bowl, NBA/NHL/MLB/NCAAB championships, golf majors, World Cup, and 6 soccer
  league winners. Routes via `edge_detector.py`'s `__FUTURES__` filters (`superbowl`,
  `nba-futures`, `golf-futures`, etc.). This is the "N-way de-vig pricing model" the earlier
  analysis flagged as needed — it's built.
- **Gate thresholds are `.env`-only knobs**, not code: `MIN_MARKET_PRICE` (lottery-ticket floor),
  `KELLY_EDGE_CAP`/`KELLY_EDGE_DECAY` (Kelly damping above a soft edge cap), and per-sport
  `MIN_EDGE_THRESHOLD_*` all live in config, not hardcoded logic. Retuning for longshots is a
  config change in this fork's `.env`, not a code fork of the gate logic.
- **Per-event cap (Gate 6) has already been debugged against futures scans** — a 2026-04-24 fix
  in `kalshi_executor.py` (search `MAX_PER_EVENT`) exists specifically because a 20-opportunity
  futures scan exposed a bug there. Not virgin territory.

## 3. Important prior evidence — read before loosening the price floor

**Done — read `docs/CHANGELOG.md` in full for this.** The real history is messier and more
interesting than "low price = bad":

- **`MIN_MARKET_PRICE` has been tuned back and forth at least 4 times, not set once.** Timeline:
  started at **$0.10** in April, chosen in an explicit operator preference ("I kind of like the
  long shots... I like .10"); drifted to **$0.06** in production without docs catching up; raised
  **0.06 → 0.12 on 2026-07-14** after a 30-day review found sub-15¢ bets at **0W–21L (-100%)**;
  deliberately **lowered 0.12 → 0.10 again on 2026-07-22** ("re-opening the longshot lane") once
  `KELLY_FRACTION` was fixed to actually size longshots instead of flat-unit-sizing them; sits at
  **$0.12** in the current `.env`/`.env.example`.
- **The 07-22 reopening's own audit (2026-07-23) found the "longshot edge" claim weaker than it
  looked:** sub-15¢ was 6W–47L over 53 bets at **+47.5% ROI**, but **99% of that P&L was one
  trade** (`KXMLSSPREAD-26MAY16SEALAG-LAG1`, +$20.59) — ex that trade the bucket is roughly
  breakeven, and it was **-100% in June, -33% in July** on its own. **The 15–25¢ bucket — not the
  cheapest one — was the actual worst performer on the board at -19.2% ROI.** Read as: price alone
  isn't the load-bearing variable here; a handful of settled bets at any price band is dominated by
  variance, and the real signal (if any) is somewhere in edge quality / confidence / market
  microstructure, not the price tag itself. Don't anchor this fork's floor decision on "price
  bucket X was profitable" from a small sample — check sample size and outlier concentration
  first.
- **`MIN_EDGE_THRESHOLD_WORLDCUP` was set to 1.0 (effectively off) after 43 bets at -43.2% ROI** —
  a tournament-outright soccer model 9 points overconfident on favorites (model 22.9%, Kalshi
  16.3%, reality 13.9%). Different root cause (soccer margin model, not price-floor), but the same
  lesson: outright/futures markets self-select for exactly the situations where a fair-value
  model's edge is most likely to be noise rather than signal.

**Takeaway for this fork:** treat "lower the price floor" and "trust the futures fair-value model"
as two separate, individually-risky decisions, not one. Both have direct, recent, real-money
evidence against them in this exact codebase — and both also have a plausible bull case (the
07-22 reopening wasn't irrational, the sample was just too thin to prove it). Whatever this fork
lands on, size small and prove it in dry-run/live-small before trusting it with real capital.

---

## 4. Strategy design work (the actual "different strategy")

- [x] **Scope decided (2026-09-04):** sports only — championship futures **and** individual-game
      longshots (long-odds moneylines, alt-spread bets like a team to win/cover by a large
      margin). **Not** in scope: crypto/political/non-sports prediction markets.
      **This lands mostly on existing infrastructure, not new code:**
      - Championship futures: `futures_edge.py`, already built (Section 2).
      - Individual-game moneyline longshots: the standard game scanner
        (`edge_detector.py`) already prices every side including heavy underdogs — they're
        just currently filtered out by `MIN_MARKET_PRICE`/`MIN_EDGE_THRESHOLD`, not unscanned.
      - **Alt-spread longshots: also already built.** `edge_detector.py` has a dedicated
        normal-CDF spread/cover-probability model (`consensus_spread_prob`) that explicitly
        "correctly handles alternate spreads: the probability of covering a large spread drops
        off following the bell curve, not linearly" — i.e. it's already designed for exactly the
        "win by a lot" longshot case, across MLB/NBA/NHL/NCAAB/NFL/MLS/World Cup spreads.
      - **Caution found while checking this (important, read before trusting spread edges):** a
        comment in that same model **was retracted on 2026-08-25**. It used to claim a real
        exploitable edge on soccer spreads ("placed spreads hit 31% vs 19% paid"); once the
        sample grew to 53 settled soccer-family spreads, the realized hit rate was **15.1%
        against a 15.5% market price — the market was almost exactly right, and the model had
        claimed 21.7%.** Conclusion in the code itself: "the always-YES lean is a MODEL error,
        not a market inefficiency." This is the same overconfidence pattern as the World Cup
        futures finding (Section 3), now showing up on spreads too — both are soccer-specific so
        far (likely the discrete, skewed goal-margin distribution breaking the normal
        approximation), not yet shown to generalize to NFL/NBA/MLB spreads, but it's the closest
        existing analog to "alt-spread longshot" in this codebase and it went the wrong way twice.
        Worth specifically checking calibration on non-soccer spread longshots before trusting
        them, rather than assuming the model's confidence is honest.
- [x] **Risk posture decided (2026-09-04): conservative, match the main repo.** No `.env` change
      needed — `.env.example`/this fork's `.env` already ship `MIN_MARKET_PRICE=0.12` and
      `KELLY_EDGE_CAP=0.15`, which *are* the main repo's live values. Revisit once dry-run data
      from this fork's own scans exists — not before.
- [x] Reviewed Gate 7 (series dedup) and Gate 6 (per-event cap) against season-long futures —
      **Gate 7 is already a safe no-op for futures**: `matchup_key()` in `kalshi_executor.py`
      explicitly returns `None` for futures/prediction tickers (only matches the
      `SPORT-YYMMMDD-TEAMS` game-ticker pattern), and the gate skips entirely when `mkey` is
      `None`. No fix needed. **Gate 6 (`MAX_PER_EVENT`, default 2) does work correctly** —
      `_event_key()` strips the ticker's outcome suffix (`KXSB-26-KC` → `KXSB-26`), so it caps how
      many *different outcomes within the same futures market* you can hold (e.g. 2 different
      teams to win the same championship) — but **the default of 2 was tuned for individual games
      (rarely bet >2 sides of one game), and may be too tight if the strategy wants a
      diversified-longshot-portfolio approach** (small stakes across many underdogs in the same
      futures market). This is a real design decision, not a bug — see the scope/sizing decisions
      below.
- [x] **Gate 6 split — decided 2026-09-07: futures cap = 3, individual games stay at 2.**
      New `MAX_PER_EVENT_FUTURES` (`app/config.py`, `RiskLimits.max_per_event_futures`), live
      `.env` value `3`, code default `2` (== `MAX_PER_EVENT`, so an unset config is unchanged
      behavior). Gate 6 in `kalshi_executor.py::size_order` now checks
      `opp.category == "futures"` and applies the futures cap only to futures rows — a game
      ticker held at 2 is never affected by the wider futures cap. All three call sites (the
      main batch loop, the R26 cached-preview replay path, and the preview display line) updated
      together. `doctor.py` prints both values. +3 tests in `tests/test_exposure_gate.py`
      (`TestPerEventCapFutures`) covering: futures under its cap approves, futures at its cap
      rejects with the right numbers in the message, and a game row at the game cap still
      rejects even though the futures cap is wider (the case that would have silently broken
      the game-side limit).
- [x] **Confirmed scope: individual-game longshots are already live, not futures-only.** Per the
      2026-09-04 scope decision above, this fork bets both championship futures **and**
      individual-game longshots (long-odds moneylines + alt-spreads) — the standard game scanner
      already prices every side including heavy underdogs, gated only by `MIN_MARKET_PRICE`
      (0.12) / per-sport `MIN_EDGE_THRESHOLD_*`, same as futures. No code or config change was
      needed to "turn on" individual games; they were never off.
- [x] **Price band set to 8c-75c — operator's call 2026-09-08.** `.env` is gitignored, so this is
      the only tracked record of it. Prompted by noticing the scheduled scan was surfacing 80-90c
      Unders — favorites, the opposite of this fork's thesis — because the fork had inherited a
      *looser* band than the repo it forked from: floor 0.12 (vs main's 0.10) clipped the cheap
      tail while ceiling 1.0 (OFF, vs main's 0.75) admitted the expensive one. Both knobs pointed
      away from longshots.
      - `MIN_MARKET_PRICE` 0.12 -> **0.08**. **Deliberately against prior evidence**: this floor
        was raised 0.06 -> 0.12 on 2026-07-14 because sub-15c bets went **0W-21L**, and main's
        0.10 is itself still an open experiment re-opening that lane ("recheck after ~30 more
        settles"). 0.08 sits *below* main's experiment, inside the losing band. That is the
        fork's thesis, not an oversight — but it is a bet, so it is the **first knob to revisit**
        once longshot settlements exist.
      - `MAX_MARKET_PRICE` 1.0 (off) -> **0.75**, matching main. Tighter ceilings (0.40 / 0.50)
        were considered and rejected: a narrow band starves the evidence window this fork still
        needs. Revisit toward 0.50 if settled results show the 50-75c end carrying the losses.
      - Verified live via `doctor.py`: `Gate 3.5 = $0.08`, `Gate 3.55 = $0.75`.
- [ ] **🔴 DECIDE THE PRICE FLOOR — 0.12 or 0.06, but not 0.08.** The 2026-09-08 backtest over
      main's 422 settlements contradicts the floor set the same day. The **8-12c band that 0.08
      newly admits is 0W-36L, -103.3% ROI** — spread across all six months (Mar 7 / Apr 3 / May 5 /
      Jun 7 / Jul 12 / Aug 2), 33 of 36 YES, both confidence tiers, average *claimed* edge +17.4%;
      at the cohort's own 9.6c average price, P(0 wins | market fair) = **2.7%**. Meanwhile sub-15c
      *overall* is **+38.7% ROI**, carried entirely by the **0-8c** band 0.08 still excludes (n=10,
      3W, +484.7%) — and the book's two largest winners sit at **6c and 7c**, both MLS spreads. So
      0.08 opens the never-won band while excluding the winners. **Caveat: 0-8c is n=10 with two
      bets carrying it** — too thin to lower the floor onto. Left at 0.08 pending this call, since
      reversing a deliberate thesis decision is the operator's, not an agent's.
- [ ] **Consider `spread`-as-category as the better-evidenced route to the same thesis.** From the
      same run: `spread` is **23% win rate at +31.7% ROI over n=111** — the longshot payoff profile
      (low win rate, high payoff) at ten times the sample of the 0-8c price band, and the most
      profitable category in the book. `game` +8.2% (n=130), `total` +4.4% (n=176). Sport-level for
      context: MLS +64.5%, NHL +62.1%, NCAAB +21.7%; MLB -4.5%, NBA -23.3%, World Cup -43.2% (off).
      All of this is main's book under main's gates — suggestive for this fork, not decisive.
- [ ] Decide bet-sizing philosophy for high-variance/low-probability payouts specifically —
      whether the existing Kelly formula's assumptions (payoff ≈ 1/price, roughly) hold as well at
      the tails as they do for coin-flip-priced game lines. **Cannot be answered by waiting**
      (2026-09-08): dry-run rows never settle, so the forward-test produces nothing a settlement
      report will read. Answer it by backtesting `kalshi_settlements.json`, as the price-band
      question above was.
- [x] Calibration/CLV tracking checked — **confirmed real gap, but narrower than expected**:
      `betting_analysis.py` (the CLV/calibration report) only reads `settled_at` within a rolling
      day window and reports *settled* bets only — a Super Bowl future placed in September and
      resolving in February will be **invisible in that report for ~5 months**, and the "no
      settled bets in the last N days" message will fire constantly for a futures-heavy strategy.
      **Open positions aren't a total blind spot though** — `daily_summary.py` and `risk_check.py`
      already read live open positions/balance separately. The gap is specific to the
      calibration/CLV report, not the whole reporting stack. Low priority to fix; just know the
      calibration report will look quiet by design while futures are in flight.

---

## 5. Validation before going live

- [x] Ran `scan --filter futures` (2026-09-04): pipeline works end-to-end — fetched 30 Kalshi
      NBA futures markets + Odds API outrights, correctly found **0 opportunities >= 3% edge**
      right now (not an error — the market is efficient today). Also ran `scan sports --filter
      mlb --date today`: real MLB game-longshot rows scored and gated, current config (0.12 price
      floor / per-sport edge thresholds) working as configured.
- [x] Confirmed the Gate column output against a fresh scheduled scan (2026-09-07): rows that
      cleared the raw edge threshold were correctly blocked by the remaining configured gates --
      `price` below the 12c floor, `no-fav` for the NO-side favorite guard, `live-off`, `illiq`,
      and fee-adjusted `edge`. A 3.4% MLB World Series model edge was likewise rejected at the
      composite-score/fee-aware edge gate. The scan was preview-only; no orders were submitted.
- [x] Scheduled tasks installed (2026-09-04) to accumulate the dry-run evidence window
      automatically — same pattern the main repo used for Polymarket (`DRY_RUN=true` for a
      proving period before flipping live), no fixed length prescribed, don't skip it given
      Section 3's evidence:
      - **New Task Scheduler folder `\Edge-Radar-Longshot\`** (deliberately separate from main's
        `\Edge-Radar-MikesAILab\`, per `scripts/schedulers/automation/install_windows_task.py`'s
        own folder-conflict check) — `Longshot-Scan` (futures + individual-game longshots, preview
        only, never `--execute`) and `Email-Longshot-Scan` 20 min later.
      - **Throttled DAILY -> WEEKLY (Sun 8:00/8:20 AM) on 2026-09-04** to conserve Odds API quota
        while this fork is only accumulating evidence, not yet time-sensitive. **Set back to daily
        once live/validated** — edit `TASK_PROFILES` in `install_windows_task.py` and re-run
        `install all`.
      - **Email routed separately from main**: `mikeschecht+longshot@gmail.com` (Gmail
        plus-address) with sender display name `Edge-Radar-Longshot <fleet@send.mikesailab.com>`
        (same verified domain, distinct name). Gmail label **`Edge Radar Longshot`** created and a
        filter wired (`to:mikeschecht+longshot@gmail.com` -> add that label, archive out of
        inbox) — mirrors main's existing `Edge Radar` filter pattern
        (`from:send.mikesailab.com subject:"edge radar"` -> same actions).
      - **Confirmed + fixed a real overlap (2026-09-04):** the original subject
        (`Edge-Radar-Longshot | Daily Dry-Run Scan`) DID phrase-match main's
        `subject:"edge radar"` filter — the live scheduled-task test came through double-labeled
        (`Edge Radar` + `Edge Radar Longshot`). Retroactively fixed both existing test messages
        (removed `Edge Radar`, kept only `Edge Radar Longshot`) and changed the subject to
        **`Longshot | Daily Dry-Run Scan`** (`email_longshot_scan.bat`) — no "edge"/"radar" words
        left in it, so it can no longer match main's filter. Main's filter was left untouched.
      - Rebuilt `scripts/custom/Python/send_report_email.py` for this fork (gitignored upstream
        too, so copied rather than shared) — also fixed a stale `CANONICAL_SENDER` path: the
        shared Resend sender moved to
        `Documents/My-Documents/My-AI-Tools/MCP-and-APIs/Resend-API/send_email.py` (was
        `.../My-AI-Tools/Resend-API/...`) since main's copy of this file was written. **Main
        Edge-Radar's own copy of this file was NOT touched and still has the stale path** — flag
        for a separate fix there if its scheduled emails are silently failing.
      - `scripts/schedulers/automation/install_windows_task.py`'s `TASK_FOLDER`/`TASK_PROFILES`
        repointed at this fork's own two profiles (`scan`, `email`) — main's original profiles
        referenced gitignored `.bat` files this fork never had.
      - Rich-table output was truncating to unreadable `...` when redirected to a log file (rich
        defaults to 80 cols off a TTY) — fixed with `set COLUMNS=220` in `longshot_scan.bat`.
      - Verified live: both `.bat` files run clean (exit 0), the scan log is readable, and a real
        test email sent successfully (Resend id `b7a35489-...`).
- [x] Resolve Section 0's bankroll-isolation decision — **DONE 2026-09-07**: real Kalshi
      subaccount (1), verified isolated ($0/no positions vs. primary's live balance).
- [x] **OPERATOR ACTION — fund Kalshi subaccount 1 — DONE 2026-09-08.** $40 moved sub 0 -> sub 1
      via the web UI (Account -> Sub accounts -> Transfer; instant, no fees), and $40 deposited to
      restore sub 0. Verified on the exchange, not just in the UI: sub 1 = **$40.00 cash, $0
      positions**; sub 0 = $83.55 / $35.29. The web UI does expose subaccounts and an internal
      transfer — the API-only assumption in the 09-07 entry was wrong.
      - **All $40 sits on exchange shard 0.** Sub 1 holds **$0 on shard 3 (Tennis & Baseball)**,
        so MLB game longshots cannot fill from this wallet even once live; shard-0 futures can.
        A second per-shard transfer is needed before MLB is orderable here.
- [x] **BUG — `shard_balances()` read account-wide, not per-subaccount — FIXED 2026-09-08.** Found while
      verifying the funding above. `get_balance()`'s `balance_breakdown` **ignores the
      `subaccount` param** — querying as subaccount 1 returned `{0: $109.79, 3: $13.76}`, the
      whole-account totals including main's money, while `balance_dollars` correctly returned
      `$40.00`. `scripts/shared/shard_funding.py:47` reads exactly that field, and
      `kalshi_executor.py:1558` calls it before every live order. So sub 1 asking about shard 3
      sees main's $13.76, finds no shortfall, approves — and the venue rejects `404
      user_not_found`. **The guard fails OPEN in precisely the case it exists for**, and
      `AUTO_SHARD_TRANSFER=false` does not protect against it: the disabled branch only refuses
      when it already *sees* a shortfall. This sharpens the 09-07 "not subaccount-aware" note —
      the defect is in the **read**, not only the missing subaccount field on the transfer.
      - **Fix:** there *is* a correct read — `GET /portfolio/balance?subaccount=N&exchange_index=S`
        scopes `balance_dollars` to both axes. Verified against the web UI's own panel row for
        row (sub 0 `{0: 69.79, 3: 13.76}`, sub 1 `{0: 40.00, 3: 0.00}`), where the breakdown
        matched neither. New `KalshiClient.get_shard_balance()`; `shard_balances()` now takes the
        shards it needs and asks per shard, never touching `balance_breakdown`. Returns `{}` (fail
        open, pre-sharding behaviour) if the client cannot answer — returning nothing is safe,
        returning another wallet's balance is not.
      - Both fakes now report a deliberately wrong uniform `$999` breakdown so any future reader
        of that field fails loudly, plus a regression case asserting the shortfall is seen anyway.
      - **Also fixed two dead tests** in `tests/test_shard_funding.py`: the call site reads
        `dry_run` from the live config rather than a module global, so on any clone whose `.env`
        has `DRY_RUN=true` (this fork's does) both transfer tests silently took the
        `[dry-run] would move` branch and asserted nothing. The fixture now pins `dry_run=False`
        via `dataclasses.replace` (the config is frozen). Suite: **10 failed/1025 passed ->
        8 failed/1027 passed**; the remaining 8 are the documented `.env`-dependent baseline.
- [x] **Scheduled task now generates rows — `--execute` under `DRY_RUN=true`, daily (2026-09-08).**
      It was preview-only, and a preview writes a *candidate list*, not a bet: nothing entered
      `data/history/`, so nothing could ever settle. Four days in, the directory held only its
      README. Now `--unit-size 1 --max-bets 5 --budget 10% --execute` (args passed explicitly —
      CLAUDE.md warns scheduler `.bat` args never see `.env` changes), cadence weekly -> daily.
      Also corrected the installed **task folder**: the tasks actually live under
      `\AI-Projects\Edge-Radar-Longshot\`, not the `\Edge-Radar-Longshot\` the installer defaults
      to and the 09-07 entry recorded — the installer's own conflict guard caught it rather than
      registering a second copy of each. Both verified `MSFT_TaskDailyTrigger daysInterval=1`,
      no duplicates.
- [ ] **KNOWN LIMIT — a dry-run row can never settle, so this window is not strategy evidence.**
      The order is blocked before the venue, so it records `fill_count: 0` / `fill_status:
      "resting"`, and `settle_trades()` excludes exactly those. CLAUDE.md's "dry runs log
      identically to live" holds for the **pre-trade** fields only. A fill simulator was
      **considered and rejected** — its fill/slippage assumptions would decide the answer it was
      built to measure. Strategy questions go to the backtester against
      `kalshi_settlements.json`. What this window *is* good for: proving the pipeline end to end
      (gates, sizing, shard routing, logging) without risking money.
- [ ] **Unresolved — MLB game longshots and tennis are unreachable from this wallet.** Subaccount 1
      exists only on exchange shard 0, and **subaccounts are per-shard entities**: Kalshi's UI
      greys out a shard-3 transfer with *"No other subaccounts on this shard"*. Extending it needs
      `create_subaccount(exchange_index=3)`, and it is **not established** whether that returns
      subaccount 1 again or allocates a new number — `KALSHI_SUBACCOUNT` is a single int, so a
      per-shard-different number has nowhere to live, and creation looks one-way (no delete in the
      client). **Ask the venue before running it.** Everything else is funded: all 124 futures
      markets (`KXMLB`, `KXNBA`, `KXNHL`, `KXSB`) plus NFL and NBA game markets are on shard 0.
      Note `KXMLB` (World Series futures, shard 0) and `KXMLBGAME` (shard 3) split despite the
      shared prefix.
- [ ] Only then flip `DRY_RUN=false` — and only once Section 4's price-floor and bet-sizing
      questions are settled, not immediately on funding.

---

## 6. Housekeeping (low priority, do later)

- [x] Cosmetic: `pyproject.toml` renamed to `edge-radar-longshot`; `README.md` and `CLAUDE.md`
      each got a short banner at the top identifying this as the longshot fork and pointing at
      this `ROADMAP.md`, without rewriting the (still largely accurate, shared-infra) content
      below it
- [x] `CLAUDE.md` rescoped (2026-09-04): "What's Live" table now marks sports/futures in-scope and
      crypto/politics/Polymarket out-of-scope for this fork; the inherited Polymarket-US Priority-0
      section (main repo's funded live account) is clearly quarantined as not-this-fork; the Risk
      Limits block's "live `.env`" narrative is flagged as main-repo evidence, not this fork's
      state; branch/sync notes no longer assume a pushed `origin`/`master`. `docs/README.md` left
      as-is (accurate index of shared infra). `docs/ROADMAP.md` and `docs/CHANGELOG.md` — upstream
      Edge-Radar's own history/priorities, not this fork's — each got a short banner marking them
      stale/reference-only and pointing back at this file.
- [x] **Graduated (2026-09-04):** moved `Repos/Draft/` → `Repos/Other_Apps/`, remote created at
      `github.com/michaelschecht/Edge-Radar-Longshot` (**private** — personal trading tool, no
      landing-page tile or subdomain). History **squashed to a fresh initial commit** (operator
      call) rather than kept as a lineage of Edge-Radar's own commits; the local `upstream` remote
      (pointed at the local Edge-Radar clone) was removed since it no longer shares history to
      merge from. Also dropped Edge-Radar's public GitHub Pages site artifacts
      (`.claude/html/`, `.claude/backup/`, `.github/workflows/deploy.yml`) — this fork has no site
      to deploy.
