# ⚙️ Polymarket Execution Guide

<p align="center">
  <img src="https://img.shields.io/badge/Phase-PM2c%20Code%20Complete-2ea44f?style=for-the-badge&labelColor=09090b" alt="PM2c">
  <img src="https://img.shields.io/badge/Orders-Dry--Run%20Blocked-e74c3c?style=for-the-badge&labelColor=09090b" alt="Blocked">
  <img src="https://img.shields.io/badge/Gates-Shared%20with%20Kalshi-0078d4?style=for-the-badge&labelColor=09090b" alt="Shared gates">
</p>

The write half of the Polymarket integration. `scan.py polymarket --execute` routes opportunities through the **same** `execute_pipeline` as Kalshi — same risk gates, same Kelly sizing, same ratio/budget caps — then calls `create_order` on the US API.

Implemented in `scripts/polymarket/polymarket_exec_client.py` (`PolymarketClient`), reached through the venue-neutral `MarketClient` seam.

---

## 🛑 The two-flag dry-run rule

> [!CAUTION]
> A Polymarket order is placed **only** when **both** flags are false:
>
> ```env
> DRY_RUN=false              # global — already false, Kalshi runs live
> POLYMARKET_DRY_RUN=false   # venue-scoped — defaults to TRUE
> ```
>
> Otherwise `create_order` returns `{"status": "dry_run_blocked", ...}` **without touching the network**.

This exists because of a specific hazard: the operator runs Kalshi live, so `DRY_RUN` is already `false`. Without a venue-scoped second flag, the moment the scanner's `--execute` refusal was lifted, Polymarket would have gone live instantly with no deliberate decision. The venue flag is what holds it back while dry-run evidence accumulates.

The default is fail-safe — `getattr(cfg.polymarket, "dry_run", True)` keeps a config that is *missing* the flag on the blocked side. `POLYMARKET_DRY_RUN` is currently **absent from `.env`**, so it resolves to `true` and orders are blocked.

**Flip it deliberately, never as a side effect**, and only after a qualifying edge actually appears in the evidence log.

> [!WARNING]
> `kalshi_executor.py` snapshots every gate threshold into module-level globals **at import time**. The CLI re-imports per invocation (always fresh), but a long-running host must be **restarted** after editing `.env` (or must call `reload_risk_config()`).

---

## Pipeline flow

```
scan.py polymarket --execute
   │
   ├─ scan futures (US data) + games (Gamma)
   ├─ filter to opps carrying a US market_slug     ← games dropped here
   ├─ get_market_client("polymarket")
   │
   └─ execute_pipeline(venue="polymarket")
        ├─ Gates 1–9        (shared with Kalshi)
        ├─ size_order       (Kelly + venue min-share bump)
        ├─ ratio / budget caps
        └─ PolymarketClient.create_order  → blocked unless both flags false
```

### Venue-specific behavior inside the shared pipeline

| Concern | Behavior |
|:--------|:---------|
| **Non-executable rows** | Opportunities without a US `market_slug` (Gamma games) are filtered out before the pipeline, with a count reported. |
| **Resting-order janitor** | Kalshi-only; skipped for other venues. |
| **Daily loss (Gate 1)** | **Intentionally spans venues** — one operator, one risk budget. |
| **Duplicate ticker (Gate 5)** | Works unchanged via normalized positions (below). |
| **Trade log** | Records carry `venue` (`"polymarket"` / `"kalshi"`; absent = kalshi on older records). |
| **Batch resilience** | Placement survives non-Kalshi exceptions without aborting the batch. |

---

## Venue minimum order size

Polymarket US enforces a per-order share minimum (`minimumTradeQty`) that Kalshi has no equivalent for. It is captured **at scan time** into `opp.details["min_order_shares"]` and the registry, then handled in `size_order`:

- If the sized count is below the minimum, it is **bumped up** to it.
- If that bump would breach `MAX_BET_SIZE` or the bankroll, the order is **rejected** with `below_venue_min_shares`.
- The bump runs **after** the ratio/budget caps, so a capped count cannot silently slip back under the minimum.
- Rows that the caps push back below minimum are dropped by the pipeline.

The client falls back to a conservative `MIN_ORDER_SHARES = 5` when a market reports no minimum, and logs a warning if a sub-minimum order still reaches it.

---

## Ticker → slug resolution

Polymarket US addresses markets by **`marketSlug`**, not by ticker. YES/NO is chosen at order time via `outcomeSide`, so **one slug covers both sides** — no per-token bookkeeping.

The scanners are the only components that know a ticker's market, so every scan records the mapping to `data/polymarket/market_registry.json`:

```json
"PM-tec-nba-champ-2027-06-18-w-sas": {
  "market_slug": "tec-nba-champ-2027-06-18-w-sas",
  "title": "NBA Champion: San Antonio Spurs",
  "min_order_shares": 5,
  "recorded_at": "2026-07-23T16:40:15+00:00"
}
```

Entries **expire after 7 days** and are pruned on every write, so the file can't grow unbounded and a stale mapping can't place an order on a long-gone market. A registry miss makes `create_order` **refuse** rather than guess.

---

## Position normalization

`get_positions` returns the raw venue shape under `positions` (an object keyed by `marketSlug`) **plus** a Kalshi-shaped `market_positions` list with `PM-{marketSlug}` tickers — the same convention the scanners mint.

That single normalization is what lets Gate 5 (duplicate ticker), per-event counts, and `kalshi_executor.py status --venue polymarket` consume Polymarket positions with no venue-specific code.

---

## Order mapping

Edge-Radar's legacy Kalshi-shaped order translates to the US body as:

| Edge-Radar | Polymarket US |
|:-----------|:--------------|
| `ticker` | `marketSlug` (via registry) |
| `side` yes/no | `outcomeSide`: `OUTCOME_SIDE_YES` / `OUTCOME_SIDE_NO` |
| `action` buy/sell | `action`: `ORDER_ACTION_BUY` / `ORDER_ACTION_SELL` |
| `*_price_cents` | `price`: `{"value": "0.20", "currency": "USD"}` |
| `count` | `quantity` (float) |
| `time_in_force` | `tif`: `TIME_IN_FORCE_*` |

> [!NOTE]
> A NO price is used **directly** — it is already the NO outcome's price, so there is no `1 − p` translation.

---

## Gate reachability (C10)

Until 2026-07-23 the pipeline was correct but **unreachable**. The futures composite scaled edge 5× more strictly than sports, so clearing `MIN_COMPOSITE_SCORE=6.0` required ~11% edge at high confidence against real futures edges of 1–4%. Since futures are the only executable Polymarket surface, no order could ever pass Gate 4.

Fixed in C10 — see the [Futures Guide](../polymarket-futures-betting/FUTURES_GUIDE.md#composite-score) and [`CLAUDE.md`](../../../CLAUDE.md). The gate is now reachable; nothing in the observed evidence newly qualifies on its own.

---

## Verification status

Live-verified 2026-07-20 in preview mode against the funded account:

- Balance read: **$60.12** buying power
- **2** real US positions counted through the normalized shape
- All four championship boards priced
- The one live edge (Spurs) correctly **gate-rejected** on composite score

Re-verified 2026-07-23 after C10: scores rose as expected (NHL 4.36 → 4.8, Spurs 3.57 → 4.4) and all rows still correctly gated on `edge`.

**No live order has been placed on Polymarket.**

---

## Not yet built (PM3)

`get_settlements` returns an empty page. Settlement and ops work still to come:

- Polymarket settler — US resolution / redemption → venue-tagged `trade_log`
- Venue surfacing in daily-summary, portfolio, and `betting_analysis`
- **Venue-aware series/event dedup** — the same game on both venues is double exposure
- Schedulers

---

<p align="center">
  <b><a href="../README.md">← Polymarket Index</a></b> ·
  <b><a href="../polymarket-futures-betting/FUTURES_GUIDE.md">Futures Guide</a></b> ·
  <b><a href="../polymarket-api/POLYMARKET_API_REFERENCE.md">API Reference</a></b> ·
  <b><a href="../../setup/ARCHITECTURE.md">Architecture</a></b>
</p>
