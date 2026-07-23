# 🟣 Polymarket Betting Guides & Coverage

<p align="center">
  <img src="https://img.shields.io/badge/Domain-Polymarket%20US-8b5cf6?style=for-the-badge&labelColor=09090b" alt="Polymarket US">
  <img src="https://img.shields.io/badge/Auth-Ed25519%20Retail%20API-0078d4?style=for-the-badge&labelColor=09090b" alt="Auth">
  <img src="https://img.shields.io/badge/Orders-Dry--Run%20Blocked-e74c3c?style=for-the-badge&labelColor=09090b" alt="Orders blocked">
  <img src="https://img.shields.io/badge/Executable-Futures%20Only-f59e0b?style=for-the-badge&labelColor=09090b" alt="Futures only">
</p>

Domain guides for the **Polymarket** integration — the second venue Edge-Radar trades, alongside [Kalshi](../kalshi/README.md). This folder is the authoritative record of what is wired, what is executable, and what is deliberately still read-only.

---

> [!IMPORTANT]
> **Two facts shape everything in this folder.**
>
> 1. **The funded account is Polymarket *US*** — the CFTC-regulated product (iOS-app only), which uses an **Ed25519 retail API** at `api.polymarket.us`. It is **not** the international EIP-712 / `py-clob-client` exchange most documentation describes. See the [API Reference](./polymarket-api/POLYMARKET_API_REFERENCE.md).
> 2. **Orders are blocked by a two-flag rule.** A Polymarket order is placed only when **both** `DRY_RUN=false` **and** `POLYMARKET_DRY_RUN=false`. The venue flag defaults to `true` and is absent from `.env`, so Kalshi runs live while Polymarket accumulates dry-run evidence. Flip it deliberately — never as a side effect.

---

## 📚 Guides in this folder

| Guide | What it covers |
|:------|:---------------|
| **[Futures Guide](./polymarket-futures-betting/FUTURES_GUIDE.md)** | The **only executable surface**. Championship boards priced on US quotes vs sportsbook outright consensus. |
| **[Games Guide](./polymarket-games-betting/GAMES_GUIDE.md)** | Per-game ML/spread/total edge detection via international Gamma — **dry-run evidence only**, not orderable on US. |
| **[Execution Guide](./polymarket-execution/EXECUTION_GUIDE.md)** | The write half: two-flag dry-run, risk gates, Kelly sizing, venue minimum shares, the slug registry, position normalization. |
| **[API Reference](./polymarket-api/POLYMARKET_API_REFERENCE.md)** | Ed25519 signing scheme, endpoints, response shapes, and the failure modes that cost real debugging time. |
| **[Setup Guide](../setup/polymarket-us-setup.md)** | Generating API keys and putting them in `.env` (lives with the other setup docs). |

---

## 📊 Coverage matrix

What Edge-Radar actually does with each Polymarket market type today.

| Surface | `--filter` | Data source | Edge model | Executable | Notes |
|:--------|:-----------|:------------|:-----------|:----------:|:------|
| **Championship futures** | `futures`, `mlb`, `nfl`, `nba`, `nhl` | **Polymarket US** (`api.polymarket.us`) | Odds API outright consensus | ✅ **Yes** | The only orderable surface. Records a real US `market_slug`. |
| Per-game moneyline | `games`, `<sport>-games` | International **Gamma** | Kalshi sports consensus model | ❌ No | No US slug → `create_order` refuses. Evidence only. |
| Per-game spread (run line) | `<sport>-games` | International **Gamma** | `consensus_spread_prob` | ❌ No | US carries **no spreads at all**. |
| Per-game total (O/U) | `<sport>-games` | International **Gamma** | `consensus_total_prob` | ❌ No | US carries **no totals at all**. |

### Why futures are the only executable surface

A full 3,000-market catalog sweep found **Polymarket US is not a mirror of international Gamma**:

- **Futures are the deep, always-on surface** — ~2,500 open markets (every league champion, division, awards, plus soccer leagues, F1, NASCAR, golf, tennis).
- **US game markets are moneyline-only and seasonal** (NBA/NHL/NFL/CBB/CFB/UFC/soccer) — **zero open during the summer offseason**.
- **No spreads or totals anywhere**, and **no MLB per-game markets at all**.

So the games scanner (PM1d), which was built against Gamma's rich ML/spread/total inventory, does **not** map onto US. Execution went futures-first; the games repoint is a deferred, seasonal follow-on — moneyline-only, wired per-league as seasons start, with spreads/totals/MLB dropped.

---

## 🏆 Championship futures wired

Each board is identified by the `question` its per-team markets share, then priced against the same Odds API outright feed the Kalshi futures scanner uses. See the **[Futures Guide](./polymarket-futures-betting/FUTURES_GUIDE.md)**.

| Board | `--filter` | Odds API key |
|:------|:-----------|:-------------|
| MLB World Series Champion | `mlb` | `baseball_mlb_world_series_winner` |
| NFL Champion | `nfl` | `americanfootball_nfl_super_bowl_winner` |
| NBA Champion | `nba` | `basketball_nba_championship_winner` |
| NHL Stanley Cup Champion | `nhl` | `icehockey_nhl_championship_winner` |
| All of the above | `futures` | — |

> [!NOTE]
> World Cup was dropped in the US repoint — the 2026 event is over and the US product carries no World Cup futures. Soccer-league titles (EPL, LaLiga, UCL, MLS) exist on US and are candidates for a later add.

---

## 🚦 Integration status

| Phase | What it delivered | Status |
|:------|:------------------|:-------|
| **PM0** | Spike — restored API references, smoke-tested Gamma live | ✅ Done |
| **PM1** | Read-only futures edge detection (dry-run) | ✅ Done |
| **PM1b** | Event discovery for NFL/MLB/NBA/NHL boards (search fallback) | ✅ Done |
| **PM1c** | Dry-run evidence log + daily scheduled scan | ✅ Done |
| **PM1d** | Per-game ML/spread/total edge detection (Gamma) | ✅ Done |
| **PM2a** | `MarketClient` seam + `get_market_client(venue)` factory | ✅ Done |
| **PM2c-0** | Rebuilt on the US retail API; futures repointed to US data | ✅ Done |
| **PM2c** | Execution pipeline wired end-to-end | ✅ Code-complete |
| **C10** | Futures composite unblocked — Gate 4 was arithmetically unreachable | ✅ Done |
| **PM2 (live)** | First live orders after a qualifying edge appears | ⏸️ Awaiting edge |
| **PM3** | Settlement & ops — settler, venue surfacing, venue-aware dedup | 📋 Planned |

### The C10 finding (2026-07-23) — why nothing had cleared

Four days of scheduled dry-run evidence (8 runs, 79 rows) produced **zero** gate-passing opportunities. The cause was not market conditions but **gate arithmetic**: the futures composite scaled edge as `min(10, edge * 20)` (saturating at a **50%** edge) while the sports composite uses `min(edge / 0.01, 10)` (saturating at **10%**) — the same weights and structure otherwise, one term **5× stricter**, dating to the launch-day commit with no recorded rationale.

Clearing `MIN_COMPOSITE_SCORE=6.0` therefore required roughly **11% edge at high confidence / 23% medium / 34% low**, against championship-futures edges that run **1–4%** in practice. Since futures are the *only* executable surface on Polymarket US, **no Polymarket order could ever clear Gate 4** — the "prove edge in dry-run, then flip the flag" plan could not terminate. The same bug explains **0 futures bets across 85 settled Kalshi trades**.

Fixed by aligning both futures paths to the sports scale. It is **not a floodgate**: replayed against the four days of evidence it approves none of the 9 observed US candidates on its own — each stays blocked by Gate 3 (edge), Gate 3.5 (price floor), or Gate 4.5 (confidence). Full rationale in [`CLAUDE.md`](../../CLAUDE.md) (C10) and [ROADMAP](../ROADMAP.md) (C10).

---

## 🔍 Dry-run evidence

The Phase 1 → Phase 2 gate is *"prove edge in dry-run."* A scheduled task (`Daily-Polymarket-DryRun`, 9:40 AM) runs a read-only scan and appends every run to an append-only evidence log.

| Artifact | Path |
|:---------|:-----|
| Evidence log (JSONL, append-only) | `data/polymarket/dryrun_log.jsonl` |
| Markdown reports | `reports/Polymarket/` |
| Slug registry (7-day expiry) | `data/polymarket/market_registry.json` |
| Scan log | `logs/polymarket_dryrun_scan.log` |

Each run record carries `generated_at`, `filter`, `min_edge`, `count`, **`executable_count`**, and every opportunity with its **gate verdict** and an **`executable`** flag. Zero-opportunity runs are logged too — *"how often does edge appear at all"* is part of the evidence.

> [!TIP]
> The `executable` / `executable_count` split matters. Most logged rows are Gamma-sourced games that can never be ordered on US — in the first four days, **66 of 79 rows were non-executable**, making the log read far busier than the 13-row tradable universe actually was. Always read the evidence against `executable_count`, not `count`.

---

## ⚡ Common commands

```bash
# Preview the executable surface (futures only)
python scripts/scan.py polymarket --filter futures

# Full funnel incl. non-executable Gamma games, saved as evidence
python scripts/scan.py polymarket --filter all --min-edge 0.01 --top 40 --save

# Route through the execution pipeline (orders still blocked by the venue flag)
python scripts/scan.py polymarket --filter futures --execute

# Portfolio status for this venue
python scripts/kalshi/kalshi_executor.py status --venue polymarket
```

Aliases for the scanner: `polymarket`, `poly`, `pm`.

---

<p align="center">
  <b><a href="../README.md">← Docs Index</a></b> ·
  <b><a href="../kalshi/README.md">Kalshi Guides</a></b> ·
  <b><a href="../setup/polymarket-us-setup.md">Polymarket Setup</a></b> ·
  <b><a href="../ROADMAP.md">Roadmap</a></b> ·
  <b><a href="../scripts/SCRIPTS_REFERENCE.md">Scripts Reference</a></b>
</p>
