# 🎯 Kalshi Betting Guides & Coverage

<p align="center">
  <img src="https://img.shields.io/badge/Domain-Kalshi-e74c3c?style=for-the-badge&labelColor=09090b" alt="Kalshi">
  <img src="https://img.shields.io/badge/Edge%20Detection-18%20Sports-2ea44f?style=for-the-badge&labelColor=09090b" alt="Sports">
  <img src="https://img.shields.io/badge/Bet%20Types-ML%20%7C%20Spread%20%7C%20Total%20%7C%20Futures-8b5cf6?style=for-the-badge&labelColor=09090b" alt="Bet Types">
</p>

Domain guides for every Kalshi market Edge-Radar trades, plus the authoritative **coverage matrix** below — exactly which sports have live edge detection, which are scan-only, and what bet types each supports. Coverage is sourced from `KALSHI_TO_ODDS_SPORT`, `CATEGORY_MAP`, and `FILTER_SHORTCUTS` in `scripts/kalshi/edge_detector.py`.

---

## 📚 Guides in this folder

| Guide | What it covers |
|:------|:---------------|
| **[Sports Betting Guide](./kalshi-sports-betting/SPORTS_GUIDE.md)** | The core edge model: weighted de-vig consensus, normal-CDF spreads/totals, sportsbook weighting tiers. |
| **[MLB Filtering Guide](./kalshi-sports-betting/MLB_FILTERING_GUIDE.md)** | Pitcher/matchup and weather filtering for baseball. |
| **[Kalshi API Reference](./kalshi-sports-betting/KALSHI_API_REFERENCE.md)** | REST endpoints, RSA-signed auth, v2 order placement. |
| **[Futures Guide](./kalshi-futures-betting/FUTURES_GUIDE.md)** | Championship/division futures de-vigging and PGA majors. |
| **[Prediction Markets Guide](./kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md)** | Crypto, weather, and S&P 500 scanners (execution gated off — see below). |

---

## ✅ Sports with live edge detection

These sports have a matching key in The Odds API, so Edge-Radar prices them against a sharp-book consensus. The columns show which **bet types** are wired (game = moneyline / winner, plus spread and total where Kalshi lists them).

| Sport | `--filter` | Game (ML) | Spread | Total | Odds source |
|:------|:-----------|:---------:|:------:|:-----:|:------------|
| MLB | `mlb` | ✅ | — | — | `baseball_mlb` |
| NBA | `nba` | ✅ | ✅ | ✅ | `basketball_nba` |
| NHL | `nhl` | ✅ | ✅ | ✅ | `icehockey_nhl` |
| NFL | `nfl` | ✅ | ✅ | ✅ | `americanfootball_nfl` |
| NCAA Men's Basketball | `ncaamb` | ✅ | ✅ | ✅ | `basketball_ncaab` |
| NCAA Football | `ncaafb` | ✅ | — | — | `americanfootball_ncaaf` |
| NCAA Women's Basketball | `ncaawb` | ✅ | — | — | `basketball_wncaab` |
| MLS | `mls` | ✅ | ✅ | ✅ | `soccer_usa_mls` |
| World Cup | `worldcup` / `wc` | ✅ | ✅ | ✅ | `soccer_fifa_world_cup` |
| Champions League | `ucl` | ✅ | — | — | `soccer_uefa_champs_league` |
| Premier League | `epl` | ✅ | — | — | `soccer_epl` |
| La Liga | `laliga` | ✅ | — | — | `soccer_spain_la_liga` |
| Serie A | `seriea` | ✅ | — | — | `soccer_italy_serie_a` |
| Bundesliga | `bundesliga` | ✅ | — | — | `soccer_germany_bundesliga` |
| Ligue 1 | `ligue1` | ✅ | — | — | `soccer_france_ligue_one` |
| UFC / MMA | `ufc` | ✅ (fight winner) | — | — | `mma_mixed_martial_arts` |
| Boxing | `boxing` | ✅ (fight winner) | — | — | `boxing_boxing` |
| Cricket (IPL) | `ipl` | ✅ | — | — | `cricket_ipl` |

> [!NOTE]
> An additional NCAA basketball game prefix (`KXNCAABB`, filter `ncaabb`) also maps to `basketball_ncaab` (game only). Use the `soccer` filter to scan all six European leagues + MLS + World Cup at once.

---

## ⚠️ Scanned but NOT edge-detected

These markets are reachable by `--filter` but have **no external odds feed**, so Edge-Radar cannot compute a sharp-book edge. They are scanned (and may appear in raw output) but produce no executable edge through the sports pipeline.

| Market | `--filter` | Why no edge | Where it's handled |
|:-------|:-----------|:------------|:-------------------|
| Formula 1 | `f1` | No Odds API race-winner key | Scan only |
| NASCAR | `nascar` | No Odds API race-winner key | Scan only |
| PGA Tour | `pga` | No game-level h2h odds | **Futures** (4 majors, via outrights) |
| Player props (NBA/NHL) | (within `nba`/`nhl`) | No props odds feed | Scan only |
| Esports (CS2, LoL) | `cs2` / `lol` / `esports` | No odds feed | Scan only |
| Mentions | (prediction) | Not a sports market | Prediction scanner |

---

## 🏆 Futures

Championship and season-long outrights, priced by `futures_edge.py` against The Odds API `outrights` market. See the **[Futures Guide](./kalshi-futures-betting/FUTURES_GUIDE.md)**.

| Market | `--filter` |
|:-------|:-----------|
| NFL / Super Bowl champion | `nfl-futures` / `superbowl` |
| NBA champion | `nba-futures` |
| NHL / Stanley Cup champion | `nhl-futures` |
| MLB / World Series champion | `mlb-futures` |
| NCAAB tournament (MOP) | `ncaab-futures` |
| PGA majors (US Open, PGA Championship, Masters, The Open) | `golf-futures` / `pga` |
| All of the above | `futures` |

---

## 🔮 Prediction Markets

Crypto (BTC, ETH, XRP, DOGE, SOL), weather (13 cities), S&P 500, mentions, companies, and politics — scanned by `prediction_scanner.py`. See the **[Prediction Markets Guide](./kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md)**.

> [!IMPORTANT]
> Prediction-market **execution is disabled by default** (Risk Gate 4.7, `ALLOW_PREDICTION_BETS=false`). The 2026-04-24 audit (R20) found the fair-value models unreliable and parked them pending a rebuild; scanning works, but these markets will not place bets until `ALLOW_PREDICTION_BETS=true` and the models are rebuilt.

---

<p align="center">
  <b><a href="../README.md">← Docs Index</a></b> ·
  <b><a href="../polymarket/README.md">Polymarket Guides</a></b> ·
  <b><a href="../scripts/SCRIPTS_REFERENCE.md">Scripts Reference</a></b> ·
  <b><a href="../setup/ARCHITECTURE.md">Architecture</a></b>
</p>
