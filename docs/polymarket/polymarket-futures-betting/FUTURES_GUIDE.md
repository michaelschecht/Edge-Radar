# 🏆 Polymarket Futures Guide

<p align="center">
  <img src="https://img.shields.io/badge/Surface-Championship%20Futures-8b5cf6?style=for-the-badge&labelColor=09090b" alt="Futures">
  <img src="https://img.shields.io/badge/Data-Polymarket%20US-0078d4?style=for-the-badge&labelColor=09090b" alt="US data">
  <img src="https://img.shields.io/badge/Executable-Yes-2ea44f?style=for-the-badge&labelColor=09090b" alt="Executable">
</p>

Championship futures are the **only executable surface on Polymarket US** — ~2,500 open markets, always on, and the one place where a scanned opportunity carries a real US `market_slug` that `create_order` can address.

Implemented in `scripts/polymarket/polymarket_futures_edge.py`, sourcing market data through `scripts/polymarket/polymarket_us_data.py`.

---

## How a championship is reconstructed

Polymarket US does **not** publish a championship as one multi-outcome market. Each team is its own independent Yes/No market, and they are grouped only by sharing a `question` string:

```
"Will the San Antonio Spurs win the NBA Championship?"   → one market, slug tec-nba-champ-...-w-sas
"Will the Boston Celtics win the NBA Championship?"      → another market, another slug
```

`fetch_open_futures()` pages the catalog (`GET /v1/markets?closed=false`, 500/page, up to 8 pages) and keeps markets where `sportsMarketType == "futures"`. `championship_candidates()` then groups them by matching the `question`.

### Question matching is whole-word, with exclusions

Naive substring matching produces silent, expensive errors — `"nba champion"` matches **"WNBA Champion"**, and every conference board contains both words. So matching is whole-word over a term's words, with an `exclude` list:

```python
"nba": {
    "terms": ("nba champion",), "league": None,
    "exclude": ("conference", "mvp", "eastern", "western"),
    ...
}
```

Where the venue tags teams with a league, that is used as a second filter (`league: "mlb"`). NBA team markets carry no league tag, which is exactly why the NBA entry leans on `exclude` instead.

### Boards currently wired

| Board | `--filter` | Match terms | Odds API key |
|:------|:-----------|:------------|:-------------|
| MLB World Series Champion | `mlb` | `world series champion` (league `mlb`) | `baseball_mlb_world_series_winner` |
| NFL Champion | `nfl` | `pro football champion` (league `nfl`) | `americanfootball_nfl_super_bowl_winner` |
| NBA Champion | `nba` | `nba champion`, excl. conference/mvp/eastern/western | `basketball_nba_championship_winner` |
| NHL Stanley Cup Champion | `nhl` | `stanley cup champion` | `icehockey_nhl_championship_winner` |

> [!NOTE]
> World Cup was dropped in the US repoint — the 2026 event is over and the US product carries no World Cup futures. Soccer-league titles (EPL, LaLiga, UCL, MLS) exist on US and are candidates for a later add.

---

## Reading the price

The tradeable YES ask is **`bestAskQuote`** (equivalently the `Yes` entry in `marketSides`); `bestBidQuote` is the YES bid.

> [!WARNING]
> Do **not** use the `outcomes` / `outcomePrices` arrays. Their ordering is inconsistent — sometimes Yes-first, sometimes No-first — so index-based reads silently invert the price on an unpredictable subset of markets.

Each candidate extracted also carries `minimumTradeQty` as `min_order_shares`, the exchange-enforced per-order share floor that sizing must respect. See the [Execution Guide](../polymarket-execution/EXECUTION_GUIDE.md#venue-minimum-order-size).

---

## The edge model

Identical in shape to the Kalshi futures path — only the market side differs:

1. **Fair value** comes from The Odds API `outrights` feed, N-way de-vigged and median-aggregated across books (`consensus_outright_fair_values`, reused unchanged from `scripts/kalshi/futures_edge.py`).
2. **Name matching** aligns the Polymarket team name to the sportsbook outcome.
3. **Edge** = `fair_yes − yes_ask`. Non-positive edge is discarded — this path is YES-only.

### Confidence

| Tier | Rule |
|:-----|:-----|
| `high` | ≥ 8 books **and** min/max fair-value spread < 0.05 |
| `medium` | ≥ 4 books |
| `low` | fewer than 4 books |

### Composite score

```python
edge_score = min(edge / 0.01, 10)          # saturates at a 10% edge
conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
liquidity  = max(0, 10 - bid_ask_spread * 20)
composite  = 0.4*edge_score + 0.3*conf_score + 0.2*liquidity + 0.1*5
```

> [!IMPORTANT]
> **C10 (2026-07-23) — the edge term was recalibrated.** It was `min(10, edge * 20)`, saturating at a **50%** edge rather than 10%, which made the futures composite **5× stricter on edge than the sports composite** despite being otherwise identical. Clearing `MIN_COMPOSITE_SCORE=6.0` needed ~**11% edge at high confidence / 23% medium / 34% low**, against real futures edges of **1–4%** — so Gate 4 was unreachable and **no futures bet had ever been placed on either venue** (0 in 85 settled trades). Aligned to the sports scale, the bar is now ~**2.1% / 4.4% / 6.6%** at typical liquidity. The `high: 9` weight is deliberately left alone (C4 capped high→medium for *sports* only, and there is still no futures settlement data either way). Full rationale in [`CLAUDE.md`](../../../CLAUDE.md).

The Kalshi and Polymarket futures composites are intentionally **one calibration, not two** — a cross-venue parity test in `tests/test_polymarket_futures.py` asserts identical inputs score identically on both.

---

## Ticker convention

```
PM-{market_slug}      e.g.  PM-tec-nba-champ-2027-06-18-w-sas
```

Truncated to 64 characters. This is the same convention `get_positions` uses when normalizing open US positions, so a scanner ticker and a held position for the same market match exactly — which is what lets Gate 5 (duplicate ticker) and per-event counting work unchanged across venues.

Every scan records `ticker → market_slug` into `data/polymarket/market_registry.json` (7-day expiry). Without a registry entry, `create_order` refuses.

---

## Usage

```bash
# Preview all four boards
python scripts/scan.py polymarket --filter futures

# A single board, wider net, saved to the evidence log
python scripts/scan.py polymarket --filter nba --min-edge 0.01 --save

# Route through the execution pipeline (orders still held by the venue flag)
python scripts/scan.py polymarket --filter futures --execute
```

The preview's **`US`** column marks which rows are executable, and the **`Gate`** column shows the first gate each row would fail — `ok` means it would pass every per-opportunity risk gate.

---

<p align="center">
  <b><a href="../README.md">← Polymarket Index</a></b> ·
  <b><a href="../polymarket-execution/EXECUTION_GUIDE.md">Execution Guide</a></b> ·
  <b><a href="../polymarket-api/POLYMARKET_API_REFERENCE.md">API Reference</a></b> ·
  <b><a href="../../kalshi/kalshi-futures-betting/FUTURES_GUIDE.md">Kalshi Futures Guide</a></b>
</p>
