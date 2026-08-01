"""
polymarket_games_edge.py — Polymarket per-game edge detector (PM1d, read-only).

Prices Polymarket's individual game markets (moneyline / run-line spread /
game total) against the SAME sportsbook-consensus model that prices Kalshi
sports bets: `consensus_fair_value`, `consensus_spread_prob`, and
`consensus_total_prob` from `edge_detector` — including their de-vig,
weighted-median sharp-book logic, sport-specific stdevs, and the C8-calibrated
overrides. Only the market side differs (Gamma instead of Kalshi).

Discovery note (2026-07-20): the 07-14 spike concluded Polymarket had no
per-game markets. Wrong — game events exist for every MLB/NFL/NBA/NHL game
but are invisible to title search and default listing order; they surface
only via tag_id + open filtering (`fetch_game_events`). Same failure mode as
the PM1b futures slugs.

Read-only (Phase 1): emits normalized `Opportunity` objects for the dry-run
evidence log; execution is refused until PM2's write half ships.

Scope notes:
  - Pre-game only — a started game (`gameStartTime` past) is skipped,
    mirroring Gate 4.8's default.
  - Core markets only: the exotic derivatives (NRFI, first-five, extra
    innings, player props) have dead 2c/98c books and no consensus source.
  - Book-quality floor: rows with a bid/ask spread wider than
    `MAX_BOOK_SPREAD` are skipped — a quote nobody maintains is not a price.
"""

import re
from datetime import datetime, timezone

from opportunity import Opportunity

# Reuse the calibrated Kalshi sports consensus model unchanged.
from edge_detector import (
    fetch_odds_api,
    consensus_fair_value,
    consensus_spread_prob,
    consensus_total_prob,
    _event_has_matchup,
    _parse_iso_utc,
)

try:
    from logging_setup import setup_logging
    log = setup_logging("polymarket_games_edge")
except Exception:  # pragma: no cover
    import logging
    log = logging.getLogger("polymarket_games_edge")

import polymarket_client as pm

# Sport config. `stdev_ticker` is a synthetic Kalshi-prefixed ticker passed to
# the consensus spread/total models purely so their `_get_margin_stdev` /
# `_get_total_stdev` prefix routing resolves the right sport (and any C8
# calibrated override); it never appears in output.
PM_GAME_SPORTS = {
    "mlb": {"tag_slug": "mlb", "odds_sport_key": "baseball_mlb",
            "stdev_ticker": "KXMLB", "label": "MLB"},
    "nfl": {"tag_slug": "nfl", "odds_sport_key": "americanfootball_nfl",
            "stdev_ticker": "KXNFL", "label": "NFL"},
    "nba": {"tag_slug": "nba", "odds_sport_key": "basketball_nba",
            "stdev_ticker": "KXNBA", "label": "NBA"},
    "nhl": {"tag_slug": "nhl", "odds_sport_key": "icehockey_nhl",
            "stdev_ticker": "KXNHL", "label": "NHL"},
}

# Skip quotes wider than this — dead/unmaintained books, not real prices.
MAX_BOOK_SPREAD = 0.10

# A Polymarket game and an Odds API event are the same game only if their
# start times agree within this window. Team matching alone is NOT enough:
# a 3-game series lists three Polymarket events with identical matchups, and
# without the time check every one of them would price against whichever
# single game the odds feed carries (the 2026-06-03 Kalshi bug class).
MAX_START_DELTA_HOURS = 6.0

_SPREAD_Q_RE = re.compile(r"Spread:\s*(.+?)\s*\(([+-]?\d+(?:\.\d+)?)\)")


def _parse_game_start(value: str) -> datetime | None:
    """Parse Gamma's gameStartTime ('2026-07-21 23:15:00+00')."""
    if not value:
        return None
    try:
        v = value.strip().replace(" ", "T")
        if v.endswith("+00"):
            v += ":00"
        dt = datetime.fromisoformat(v)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _confidence(n_books: int, tight: bool) -> str:
    if n_books >= 8 and tight:
        return "high"
    if n_books >= 4:
        return "medium"
    return "low"


def _build_opp(slug: str, label: str, bet_type: str, pick: str, side: str,
               price: float, fair: float, confidence: str, row: dict,
               meta: dict, token_index: int) -> Opportunity | None:
    edge = fair - price
    if edge <= 0 or price <= 0 or price >= 1.0:
        return None
    # Liquidity deliberately scales 5x steeper than the Kalshi/futures
    # `spread * 20`: rows wider than MAX_BOOK_SPREAD (0.10) are already
    # dropped upstream, so `* 20` would compress every surviving row into
    # 9.8-10.0 and the term would carry no information. `* 100` spreads the
    # admissible 0-0.10 band across the full 0-10 range. This is a real
    # cross-surface inconsistency when games and futures are merged and
    # ranked together, but it errs strict and is the better-calibrated of
    # the two — leaving it rather than loosening a second term.
    liquidity = max(0.0, 10 - row["book_spread"] * 100)

    # C10 (2026-07-31, extended from the 07-23 futures fix): edge scales as
    # `edge / 0.01`, matching the sports composite in `edge_detector.py`.
    #
    # This file was written 3 days before C10 and copied `edge * 20` from
    # `polymarket_futures_edge`, which had itself copied it from the
    # `liquidity` line above it — the copy-of-a-copy C10 diagnosed. C10 fixed
    # both futures paths but not this one, so games kept the 5x-stricter
    # scale (saturating at 50% edge instead of 10%).
    #
    # Same consequence, independently confirmed: clearing
    # MIN_COMPOSITE_SCORE=6.0 needed ~15% edge at high confidence / 26%
    # medium / 38% low, against game edges that run 1-7% in practice. Across
    # 362 logged Gamma game rows, **not one** ever reached 6.0 (max 5.30) —
    # Gate 4 was structurally unreachable here too.
    #
    # Not a floodgate: replayed over those same 362 rows, only 5 (1.4%) newly
    # clear Gate 4, all marginally (6.02-6.26), and each still faces gates
    # 3.5/4.5/4.6b/5/6/7. The other 330 edge-gated rows never reach Gate 4 at
    # all. Games are not executable today regardless (Gamma rows carry no US
    # market_slug); this matters for when the seasonal US repoint lands, so
    # that surface doesn't inherit the same unreachable gate a third time.
    edge_score = min(edge / 0.01, 10)

    # `high: 9` left uncapped, following C10's own precedent for futures: C4
    # capped high->medium for *Kalshi sports* on 306 settled bets (F49) and
    # scoped everything else out. There is still no settled Polymarket data
    # to justify either choice. Worth revisiting once PM3 settlement lands —
    # this path prices off the same Odds API consensus as sports, so C4's
    # reasoning plausibly transfers even though its evidence doesn't.
    conf_score = {"high": 9, "medium": 6, "low": 3}[confidence]
    composite = 0.4 * edge_score + 0.3 * conf_score + 0.2 * liquidity + 0.1 * 5
    return Opportunity(
        ticker=f"PM-{slug}-{bet_type.lower()}"[:64],
        title=f"{row['question']} — {pick}",
        category={"ML": "game", "Spread": "spread", "Total": "total"}[bet_type],
        side=side,
        market_price=round(price, 4),
        fair_value=round(fair, 4),
        edge=round(edge, 4),
        edge_source="polymarket_vs_consensus",
        confidence=confidence,
        liquidity_score=round(liquidity, 1),
        composite_score=round(composite, 1),
        details={
            "venue": "polymarket",
            "sport": label,
            "bet_type": f"{label} {bet_type}",
            "candidate": pick,
            "n_books": meta.get("n_books", 0),
            "game_start": row["game_start"],
            "condition_id": row["condition_id"],
            "clob_token_ids": row["clob_token_ids"],
            "token_index": token_index,
            "pm_book_spread": row["book_spread"],
        },
    )


def detect_game_market_edges(row: dict, scoped_events: list, label: str,
                             slug: str, stdev_ticker: str) -> list[Opportunity]:
    """Price one Polymarket game sub-market against the scoped consensus.

    `scoped_events` must be pre-scoped to the single matching Odds API event
    (the consensus functions refuse multi-event pools by design).
    Moneyline and totals are priced on BOTH sides (the second outcome's
    effective ask is 1 - best bid on the first token); spreads are YES-only
    (each team's line is its own market).
    """
    opps: list[Opportunity] = []
    mtype = row["market_type"]

    if mtype == "moneyline":
        team_a, team_b = row["outcomes"]
        fv_a = consensus_fair_value(scoped_events, team_a)
        if fv_a:
            fair, meta = fv_a
            tight = (meta["max_fair"] - meta["min_fair"]) < 0.05
            conf = _confidence(meta["n_books"], tight)
            opps.append(_build_opp(slug, label, "ML", team_a, "yes",
                                   row["yes_price"], fair, conf, row, meta, 0))
        if row["yes_bid"] > 0:
            fv_b = consensus_fair_value(scoped_events, team_b)
            if fv_b:
                fair, meta = fv_b
                tight = (meta["max_fair"] - meta["min_fair"]) < 0.05
                conf = _confidence(meta["n_books"], tight)
                opps.append(_build_opp(slug, label, "ML", team_b, "no",
                                       1 - row["yes_bid"], fair, conf, row, meta, 1))

    elif mtype == "spreads" and row["line"] is not None:
        m = _SPREAD_Q_RE.search(row["question"])
        if not m:
            return []
        team, line = m.group(1), float(m.group(2))
        # YES = team covers `line`; covering means final margin > -line
        # (line=-1.5 → wins by 2+; line=+1.5 → wins or loses by ≤1).
        sp = consensus_spread_prob(scoped_events, team, -line, ticker=stdev_ticker)
        if sp:
            fair, meta = sp
            tight = meta.get("book_spread_range", 99) <= 0.5
            conf = _confidence(meta["n_books"], tight)
            opps.append(_build_opp(slug, label, "Spread", f"{team} {line:+g}",
                                   "yes", row["yes_price"], fair, conf, row, meta, 0))

    elif mtype == "totals" and row["line"] is not None:
        tp = consensus_total_prob(scoped_events, row["line"], ticker=stdev_ticker)
        if tp:
            fair_over, meta = tp
            conf = _confidence(meta["n_books"], False)
            opps.append(_build_opp(slug, label, "Total", f"Over {row['line']:g}",
                                   "yes", row["yes_price"], fair_over, conf, row, meta, 0))
            if row["yes_bid"] > 0:
                opps.append(_build_opp(slug, label, "Total", f"Under {row['line']:g}",
                                       "no", 1 - row["yes_bid"], 1 - fair_over,
                                       conf, row, meta, 1))

    return [o for o in opps if o is not None]


def scan_polymarket_games(min_edge: float = 0.03,
                          sports: list[str] | None = None,
                          top_n: int = 20) -> list[Opportunity]:
    """Scan Polymarket per-game markets for the given sports (default: all)."""
    from rich import print as rprint

    keys = [k for k in (sports or PM_GAME_SPORTS) if k in PM_GAME_SPORTS]
    now = datetime.now(timezone.utc)
    opps: list[Opportunity] = []

    for key in keys:
        cfg = PM_GAME_SPORTS[key]
        tag_id = pm.get_tag_id(cfg["tag_slug"])
        if not tag_id:
            rprint(f"  [dim]{cfg['label']} games: tag lookup failed — skipping.[/dim]")
            continue
        events = pm.fetch_game_events(tag_id)
        game_rows = []  # (event, [rows])
        for ev in events:
            rows = [r for r in pm.iter_game_rows(ev)
                    if r["book_spread"] <= MAX_BOOK_SPREAD]
            # Pre-game only (Gate 4.8 default posture).
            rows = [r for r in rows
                    if (start := _parse_game_start(r["game_start"])) and start > now]
            if rows and " vs. " in (ev.get("title") or ""):
                game_rows.append((ev, rows))
        if not game_rows:
            rprint(f"  [dim]{cfg['label']} games: no open pre-game markets with "
                   f"live books.[/dim]")
            continue

        odds_events = fetch_odds_api(cfg["odds_sport_key"], markets="h2h,spreads,totals")
        if not odds_events:
            rprint(f"  [dim]{cfg['label']} games: no Odds API feed "
                   f"({cfg['odds_sport_key']}) — can't price.[/dim]")
            continue

        found = 0
        for ev, rows in game_rows:
            team_a, team_b = [t.strip() for t in ev["title"].split(" vs. ", 1)]
            game_start = _parse_game_start(rows[0]["game_start"])
            scoped = [
                e for e in odds_events
                if _event_has_matchup(e, team_a, team_b)
                and (commence := _parse_iso_utc(e.get("commence_time", "")))
                and game_start
                and abs((commence - game_start).total_seconds()) <= MAX_START_DELTA_HOURS * 3600
            ]
            if len(scoped) != 1:
                # 0 = no odds coverage for THIS game (later series games have
                # no posted lines yet); >1 = still ambiguous (true same-day
                # doubleheader) — refuse rather than price the wrong game.
                continue
            for row in rows:
                for opp in detect_game_market_edges(
                        row, scoped, cfg["label"], ev.get("slug", ""),
                        cfg["stdev_ticker"]):
                    if opp.edge >= min_edge:
                        opps.append(opp)
                        found += 1
        rprint(f"  {cfg['label']} games: {len(game_rows)} games with live books "
               f"→ [green]{found}[/green] edge(s)")

    opps.sort(key=lambda o: o.composite_score, reverse=True)
    opps = opps[:top_n]
    # Record ticker → CLOB token mappings so the PM2 execution client can
    # resolve orders for these opportunities later.
    import market_registry
    market_registry.record_opportunities(opps)
    return opps
