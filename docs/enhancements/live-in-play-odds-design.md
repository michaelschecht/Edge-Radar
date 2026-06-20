# Design: Live In-Play Odds (real-time edges on in-progress games)

**ID:** L1
**Status:** Scoped — not yet implemented (2026-06-20)
**Related:** F44 (phantom live edges), R27 (the "LIVE" tag), R24b (file odds cache)
**Owner decision pending:** whether to build Phase 1 now or later.

---

## Problem

Edges on **in-progress** games are currently untrustworthy. The scan flags them
with a `LIVE` tag (R27) but still prints an edge computed against **stale
pre-game odds**, producing phantom edges (F44 saw `+50%` "edges" on games already
underway). The user wants edges on live games to reflect **current** book odds so
in-play betting is viable.

## Root cause — it's caching, not missing data

The Odds API **already returns live in-play odds**. The `GET /v4/sports/{sport}/odds`
endpoint returns *"upcoming and live games with recent odds"*; an event is in-play
when `commence_time < now`. So the data is present on every fetch. The staleness
comes from two cache layers in `fetch_odds_api()` (`scripts/kalshi/edge_detector.py`):

1. **In-process cache `_odds_cache` (no TTL)** — the primary F44 culprit. Keyed
   `"{sport_key}:{markets}"`, it returns the first response for the entire process
   lifetime. In the long-running Streamlit app, the pre-game odds fetched once stay
   cached for hours; during the game Kalshi's price moves but the cached odds are
   frozen → phantom edge. (`edge_detector.py` ~L186, ~L207-208.)
2. **File cache (`ODDS_CACHE_TTL_SECONDS=300`)** — adds up to 5 min of staleness on
   top, shared across processes (`scripts/shared/odds_cache.py`, R24b).

The CLI re-imports each run (in-process cache is fresh-ish) but still hits the
5-min file cache; the webapp suffers both layers.

## Goal

When a game is in progress, the edge should be computed against **current** book
odds (seconds-to-~1-minute fresh), not a cached pre-game snapshot — without
blowing up Odds API quota or destabilizing pre-game scanning.

---

## Phased approach

### Phase 1 — Freshness fix (small, highest leverage) — RECOMMENDED FIRST

Make in-progress games bypass the stale caches; leave pre-game behavior unchanged.

- **Add a TTL to the in-process `_odds_cache`** (it currently has none). Store
  `(timestamp, events)` and treat entries older than a small TTL as misses. This
  alone fixes the dominant F44 mechanism in the webapp.
- **Live-aware TTL.** When the *sport response contains at least one in-play event*
  (`commence_time < now`), use a short "live TTL" (e.g. `ODDS_LIVE_TTL_SECONDS`,
  default ~30–60s) for both cache layers instead of the 300s pre-game TTL. Pre-game
  fetches keep the 300s TTL (quota-friendly).
- **Detection reuses existing logic** — `ticker_display.is_game_started()` /
  `commence_time < now`. No new matching code; `find_market_event()` already pairs
  the live game by teams + schedule.

**Effort:** contained to `fetch_odds_api()` + a new config knob in `app/config.py`
(`odds_cache` group). ~Half a day incl. tests.

**Quota impact:** minimal — live games refetch only when a scan actually runs and
only at the shorter TTL. Scans are discrete (scheduled tasks + manual), not
continuous polling. Cost per refresh is unchanged: `markets × regions` = `3 × 1 = 3`
credits per sport response.

### Phase 2 — Targeted live fetch (medium)

Use the per-event endpoint `GET /v4/sports/{sport}/events/{eventId}/odds` to refresh
**only** the in-progress games rather than re-pulling the whole sport.

- Capture the Odds API event `id` (already present in the `/odds` response) when a
  market is matched, then refresh that single event on the live TTL.
- More quota-efficient when many sports are scanned but only a few games are live.
- More code: per-event fetch path, event-id bookkeeping, a second cache namespace.

**Effort:** ~1–2 days. Do this once Phase 1 shows live betting is worth optimizing.

### Phase 3 — Continuous / real-time (large) — probably out of scope

Background polling during games + live edge alerts + optional auto-execution.
High quota, real-time infra, execution-latency engineering. Only if the user wants
to actively day-trade in-play.

---

## Caveats / risks (carry into implementation)

- **Quota:** `cost = markets × regions`. Today `markets="h2h,spreads,totals"` (3) ×
  `regions="us"` (1) = 3 credits/call. Budget is 12 keys × 500 = 6,000/month.
  Short live TTL + many live games + frequent scans can burn this; Phase 2 mitigates.
- **US in-play book coverage is uneven.** Soccer/World Cup in-play h2h is
  well-covered; **MLB in-play h2h is spotty** and some US books *suspend* markets
  during play. When live odds are thin/absent, the system already emits no edge
  (correct/safe) — so some live games simply won't be actionable. Set expectations.
- **Execution lag.** Live lines move fast; by the time scan → risk gates → order
  completes, the line may have moved. In-play is inherently more time-sensitive than
  pre-game. Consider tighter `time_in_force` (IOC/FOK) for live orders later.
- **Edge validity vs. game state.** Even with fresh odds, a mid-game edge reflects a
  point-in-time snapshot; the model has no in-game state (score, inning, red cards).
  Phase 1 makes the *reference odds* honest; it does not add game-state modeling.

## Open questions / decisions for implementation

1. Default `ODDS_LIVE_TTL_SECONDS` value (30s vs 60s) — trade freshness vs quota.
2. Should live TTL apply per-sport-response (any in-play event shortens the whole
   sport's TTL) or be deferred to Phase 2's per-event granularity? (Phase 1 = whole
   sport for simplicity.)
3. Do we want a hard guard that *suppresses* (not just refreshes) edges when the
   matched event's `last_update` is older than N seconds, so a stale/suspended book
   can't resurrect a phantom edge even within TTL?
4. Should live betting get its own gate/flag (e.g. `ALLOW_LIVE_BETS`, off by
   default) so in-play is opt-in until trusted? (Mirrors R25 `ALLOW_PREDICTION_BETS`.)

## Testing approach

- Unit: cache returns fresh on expiry; live TTL chosen when a response contains an
  in-play event; pre-game TTL otherwise; in-process TTL honored.
- Mock Odds API responses with `commence_time` before/after a fixed `now` (pass
  `now` in, mirroring `is_game_started(ticker, now=...)`).
- Live smoke: during an actual game, confirm two scans ~1 min apart return changed
  odds for the in-play event while a pre-game event stays cached.

## Touch points (files)

- `scripts/kalshi/edge_detector.py` — `fetch_odds_api()` (cache logic), `_odds_cache`.
- `scripts/shared/odds_cache.py` — file cache `load`/`save` (R24b); add live TTL path.
- `app/config.py` — `odds_cache` config group; add `ODDS_LIVE_TTL_SECONDS` (+ maybe
  `ALLOW_LIVE_BETS`).
- `scripts/shared/ticker_display.py` — `is_game_started()` / `commence_time` reuse.
- Tests: `tests/test_odds_cache.py`, `tests/test_edge_detection.py`.
