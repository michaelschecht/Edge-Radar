"""
kalshi_executor.py
Automated Kalshi wagering pipeline.

Reads scored opportunities from the edge detector, applies risk management
(Kelly sizing, daily loss limits, position limits), and places orders.

Usage:
    # Scan + execute in one shot (default: dry run preview)
    python scripts/kalshi_executor.py run

    # Live execution on demo
    python scripts/kalshi_executor.py run --execute

    # Execute from saved watchlist instead of fresh scan
    python scripts/kalshi_executor.py run --from-file --execute

    # Check current state
    python scripts/kalshi_executor.py status
"""

import os
import sys
import json
import uuid
import logging
import argparse
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dataclasses import dataclass, asdict

# Shared imports
import paths  # noqa: F401 -- path constants -- configures sys.path
from opportunity import Opportunity
from trade_log import load_trade_log, save_trade_log, get_today_pnl

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from kalshi_client import KalshiClient, KalshiAPIError, make_prod_client
from edge_detector import scan_all_markets
from ticker_display import _detect_sport

# ── Setup ─────────────────────────────────────────────────────────────────────
load_dotenv()
from logging_setup import setup_logging
log = setup_logging("kalshi_executor")
console = Console()

TRADE_LOG_PATH = paths.TRADE_LOG_PATH

# ── Risk Parameters ───────────────────────────────────────────────────────────

MAX_BET_SIZE = float(os.getenv("MAX_BET_SIZE", "100"))
UNIT_SIZE = float(os.getenv("UNIT_SIZE", "1.00"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "250"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "10"))
MIN_EDGE_THRESHOLD = float(os.getenv("MIN_EDGE_THRESHOLD", "0.03"))
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))
MAX_PER_EVENT = int(os.getenv("MAX_PER_EVENT", "2"))
MAX_BET_RATIO = float(os.getenv("MAX_BET_RATIO", "3.0"))
MIN_COMPOSITE_SCORE = float(os.getenv("MIN_COMPOSITE_SCORE", "6.0"))
KELLY_EDGE_CAP = float(os.getenv("KELLY_EDGE_CAP", "0.15"))
KELLY_EDGE_DECAY = float(os.getenv("KELLY_EDGE_DECAY", "0.5"))
SERIES_DEDUP_HOURS = int(os.getenv("SERIES_DEDUP_HOURS", "48"))

# R3 (2026-04-21): reject opportunities below this confidence level. Two review
# windows showed low-confidence at 0W-3L / -105% ROI. Values: low|medium|high.
MIN_CONFIDENCE = os.getenv("MIN_CONFIDENCE", "medium").strip().lower()

# R1 (2026-04-21): side-aware penalty for NO bets on heavy favorites. 14-day
# review: all 13 high-edge losers were NO-side; NO at >=20% edge realized 31%
# WR / -33% ROI. Reject NO bets whose market price is below
# NO_SIDE_FAVORITE_THRESHOLD unless edge >= NO_SIDE_MIN_EDGE AND confidence is
# "high". Separately, apply NO_SIDE_KELLY_MULTIPLIER to Kelly sizing for any NO
# bet priced below NO_SIDE_KELLY_PRICE_FLOOR.
NO_SIDE_FAVORITE_THRESHOLD = float(os.getenv("NO_SIDE_FAVORITE_THRESHOLD", "0.25"))
NO_SIDE_MIN_EDGE = float(os.getenv("NO_SIDE_MIN_EDGE", "0.25"))
NO_SIDE_KELLY_PRICE_FLOOR = float(os.getenv("NO_SIDE_KELLY_PRICE_FLOOR", "0.35"))
NO_SIDE_KELLY_MULTIPLIER = float(os.getenv("NO_SIDE_KELLY_MULTIPLIER", "0.5"))

_CONFIDENCE_RANK = {"low": 0, "medium": 1, "high": 2}


def _confidence_rank(level: str | None) -> int:
    """Map confidence string to an ordinal; unknown values rank as medium."""
    if not level:
        return _CONFIDENCE_RANK["medium"]
    return _CONFIDENCE_RANK.get(level.strip().lower(), _CONFIDENCE_RANK["medium"])

# Per-sport edge-threshold overrides. Any sport not listed falls back to
# MIN_EDGE_THRESHOLD. Read at import; tests patch _PER_SPORT_MIN_EDGE directly.
_SUPPORTED_SPORTS = ("mlb", "nba", "nhl", "nfl", "ncaab", "ncaaf", "mls", "soccer")
_PER_SPORT_MIN_EDGE: dict[str, float] = {}
for _sport in _SUPPORTED_SPORTS:
    _val = os.getenv(f"MIN_EDGE_THRESHOLD_{_sport.upper()}")
    if _val:
        try:
            _PER_SPORT_MIN_EDGE[_sport] = float(_val)
        except ValueError:
            pass


def min_edge_for(opp: "Opportunity") -> float:
    """Return the edge threshold for an opportunity's sport, or the global default.

    Per-sport overrides are read from env as `MIN_EDGE_THRESHOLD_<SPORT>` at
    import (e.g., MIN_EDGE_THRESHOLD_NBA=0.08). Calibration (2026-04-18)
    showed NBA and NCAAB losing money at the global 3% floor — raising their
    per-sport floor blocks marginal-edge bets where the model is worst-
    calibrated, without touching sports where it works (e.g., NHL +100% ROI).
    """
    sport = _detect_sport(opp.ticker)
    if sport and sport in _PER_SPORT_MIN_EDGE:
        return _PER_SPORT_MIN_EDGE[sport]
    return MIN_EDGE_THRESHOLD


def trusted_edge(edge: float, cap: float | None = None, decay: float | None = None) -> float:
    """Soft-cap the edge used for Kelly sizing.

    Post-baseline calibration (2026-04-18) showed claimed edges >=25% realize
    -35% ROI while 10-15% claimed edges realize +127%. Large edges are
    systematically overstated, yet Kelly sizes linearly off raw edge — so fakes
    get the biggest bets. This softly compresses the portion above `cap`:

        trusted_edge(edge <= cap) == edge
        trusted_edge(edge >  cap) == cap + (edge - cap) * decay

    Raw edge still flows through gates, reports, and rationale unchanged. Only
    the Kelly sizing calculation sees the trusted value.
    """
    c = KELLY_EDGE_CAP if cap is None else cap
    d = KELLY_EDGE_DECAY if decay is None else decay
    if edge <= c:
        return edge
    return c + (edge - c) * d


def _event_key(ticker: str) -> str:
    """Extract the event (game) portion from a Kalshi ticker.

    KXNBAGAME-26APR02SASLAC-SAS -> KXNBAGAME-26APR02SASLAC
    """
    parts = ticker.rsplit("-", 1)
    return parts[0] if len(parts) > 1 else ticker


# Matches the leading YY-MMM-DD date and optional 4-digit HHMM game time that
# Kalshi embeds in the event-descriptor portion of a ticker (e.g. "26APR14" or
# "26APR011940"). Stripping it leaves just the team abbreviations, so the same
# matchup on consecutive days produces the same key.
_DATE_PREFIX_RE = re.compile(r"^\d{2}[A-Z]{3}\d{2}\d{0,4}")


def matchup_key(ticker: str) -> tuple[str, str] | None:
    """Extract a series-invariant matchup identifier from a Kalshi ticker.

    Same matchup on different dates yields the same key — lets C5 detect when
    we're about to bet the same series back-to-back. Returns ``None`` for
    tickers that don't match the expected sport-game pattern (futures,
    prediction markets, malformed tickers).

    Examples:
        KXMLBGAME-26APR14LAAANYY-NYY  -> ('mlb', 'LAAANYY')
        KXMLBGAME-26APR15LAAANYY-NYY  -> ('mlb', 'LAAANYY')
        KXMLBGAME-26APR011940MINKC-MIN -> ('mlb', 'MINKC')
    """
    sport = _detect_sport(ticker)
    if not sport:
        return None
    parts = ticker.split("-")
    if len(parts) < 2:
        return None
    middle = parts[1]
    m = _DATE_PREFIX_RE.match(middle)
    if not m:
        return None
    teams = middle[m.end():]
    if not teams:
        return None
    return (sport, teams)


def recent_matchups_from_log(
    trade_log: list[dict],
    hours: int | None = None,
    now: datetime | None = None,
) -> set[tuple[str, str]]:
    """Matchup keys that had a bet placed in the last ``hours`` window.

    Used by Gate 7 (series dedup) to reject a new bet on a matchup we already
    bet on a recent day. Observed bleed pattern (2026-04-18): the same MLB
    matchup was bet on 2-3 consecutive days with compounding losses
    (LA Angels @ NY Yankees ML NO Apr 13, 14, 15; NY Mets @ LA Dodgers Apr 13,
    15). `dedup_correlated_brackets` handles within-day correlation but can't
    see across days.

    Any entry in the trade log counts as a placed order — dry-run runs don't
    write to the log, so no extra filtering is needed.
    """
    if hours is None:
        hours = SERIES_DEDUP_HOURS
    if hours <= 0:
        return set()
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(hours=hours)
    keys: set[tuple[str, str]] = set()
    for trade in trade_log:
        ts = trade.get("timestamp")
        if not ts:
            continue
        try:
            placed_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if placed_at.tzinfo is None:
            placed_at = placed_at.replace(tzinfo=timezone.utc)
        if placed_at < cutoff:
            continue
        key = matchup_key(trade.get("ticker", ""))
        if key:
            keys.add(key)
    return keys


def dedup_correlated_brackets(opportunities: list[Opportunity]) -> list[Opportunity]:
    """Remove correlated bracket bets from the same game, keeping the best one.

    Multiple totals/spread lines on the same game (e.g., Over 221.5, Over 224.5,
    Over 228.5) are highly correlated — they win or lose together. Stacking them
    gives concentration risk, not diversification.

    Groups opportunities by (event_key, category) and keeps only the highest
    composite_score from each group. Different categories on the same game
    (e.g., ML + totals) are kept since they're less correlated.
    """
    best: dict[tuple[str, str], Opportunity] = {}
    for opp in opportunities:
        key = (_event_key(opp.ticker), opp.category)
        existing = best.get(key)
        if existing is None or opp.composite_score > existing.composite_score:
            best[key] = opp
    # Preserve original sort order (by composite_score descending from scanner)
    deduped_set = set(id(o) for o in best.values())
    return [o for o in opportunities if id(o) in deduped_set]


# ── Position Sizing ──────────────────────────────────────────────────────────

@dataclass
class SizedOrder:
    """An opportunity that has passed risk checks and been sized."""
    opportunity: Opportunity
    contracts: int
    price_cents: int
    cost_dollars: float
    bankroll_pct: float
    risk_approval: str  # approved / rejected + reason


def unit_size_contracts(market_price: float, unit: float | None = None) -> int:
    """
    Calculate number of contracts to buy for a fixed dollar unit size.

    Examples (unit=$1.00):
        price $0.02 -> 50 contracts ($1.00)
        price $0.50 ->  2 contracts ($1.00)
        price $0.03 -> 33 contracts ($0.99)
        price $0.07 -> 14 contracts ($0.98)
    """
    if unit is None:
        unit = UNIT_SIZE
    if market_price <= 0 or market_price >= 1:
        return 0
    return max(1, round(unit / market_price))


def size_order(opp: Opportunity, bankroll: float, open_positions: int,
               daily_pnl: float, unit_size: float = UNIT_SIZE,
               open_tickers: set[str] | None = None,
               event_counts: dict[str, int] | None = None,
               max_per_event: int = MAX_PER_EVENT,
               batch_size: int = 1,
               recent_matchups: set[tuple[str, str]] | None = None) -> SizedOrder:
    """
    Apply all risk checks and size the order.

    Uses Kelly sizing divided by batch_size when placing multiple
    simultaneous bets. This prevents over-committing bankroll when
    placing N bets at once (each gets kelly_fraction/N instead of
    the full fraction). Falls back to flat unit sizing if Kelly
    produces fewer contracts than the flat unit.

    Risk gates enforced:
        1.   Daily loss limit                             (reject)
        2.   Max open positions                           (reject)
        3.   Minimum edge threshold (global + per-sport)  (reject)
        4.   Minimum composite score                      (reject)
        4.5  Minimum confidence level (R3)                (reject)
        4.6  NO-side favorite guard (R1)                  (reject)
        5.   Duplicate ticker (already holding this market) (reject)
        6.   Per-event cap (max positions on same game)   (reject)
        7.   Series dedup (same matchup within last Nh)   (reject)
        8.   Max bet size                                 (sizing cap)
        9.   Bet ratio cap                                (sizing cap)

    NO-side Kelly multiplier (R1): NO bets priced below
    NO_SIDE_KELLY_PRICE_FLOOR are sized at NO_SIDE_KELLY_MULTIPLIER of normal
    Kelly (half-Kelly by default).
    """
    rejection = None
    edge_floor = min_edge_for(opp)

    # ── Risk Gate 1: Daily loss limit
    if daily_pnl <= -MAX_DAILY_LOSS:
        rejection = f"daily_loss_limit_breached (P&L: ${daily_pnl:.2f})"

    # ── Risk Gate 2: Max open positions
    elif open_positions >= MAX_OPEN_POSITIONS:
        rejection = f"max_positions_reached ({open_positions}/{MAX_OPEN_POSITIONS})"

    # ── Risk Gate 3: Minimum edge (per-sport override, global fallback)
    elif opp.edge < edge_floor:
        rejection = f"edge_below_threshold ({opp.edge:.1%} < {edge_floor:.1%})"

    # ── Risk Gate 4: Minimum composite score
    elif opp.composite_score < MIN_COMPOSITE_SCORE:
        rejection = f"score_below_minimum ({opp.composite_score:.1f} < {MIN_COMPOSITE_SCORE:.1f})"

    # ── Risk Gate 4.5: Minimum confidence level (R3)
    elif _confidence_rank(opp.confidence) < _confidence_rank(MIN_CONFIDENCE):
        rejection = (
            f"confidence_below_minimum ({opp.confidence or 'unknown'} < {MIN_CONFIDENCE})"
        )

    # ── Risk Gate 4.6: NO-side favorite guard (R1)
    #   Reject NO bets on heavy favorites unless both edge and confidence clear
    #   the higher bar. Observed 2026-04-21: all 13 high-edge losers in the
    #   14-day window were NO-side; NO at >=20% edge realized -33% ROI.
    elif (
        opp.side and opp.side.strip().lower() == "no"
        and opp.market_price < NO_SIDE_FAVORITE_THRESHOLD
        and (opp.edge < NO_SIDE_MIN_EDGE
             or _confidence_rank(opp.confidence) < _confidence_rank("high"))
    ):
        rejection = (
            f"no_side_favorite (price ${opp.market_price:.2f} < "
            f"${NO_SIDE_FAVORITE_THRESHOLD:.2f}; needs edge >= "
            f"{NO_SIDE_MIN_EDGE:.0%} and confidence=high)"
        )

    # ── Risk Gate 5: Duplicate ticker
    elif open_tickers and opp.ticker in open_tickers:
        rejection = f"duplicate_ticker (already holding {opp.ticker})"

    # ── Risk Gate 6: Per-event cap
    elif event_counts:
        evt = _event_key(opp.ticker)
        if event_counts.get(evt, 0) >= max_per_event:
            rejection = f"per_event_cap ({event_counts[evt]}/{max_per_event} on {evt[:30]})"

    # ── Risk Gate 7: Series dedup (C5) -- same matchup bet in last SERIES_DEDUP_HOURS
    if rejection is None and recent_matchups and SERIES_DEDUP_HOURS > 0:
        mkey = matchup_key(opp.ticker)
        if mkey and mkey in recent_matchups:
            rejection = f"series_dedup (matchup {mkey[1]} bet within {SERIES_DEDUP_HOURS}h)"

    if rejection:
        return SizedOrder(
            opportunity=opp, contracts=0, price_cents=0,
            cost_dollars=0, bankroll_pct=0,
            risk_approval=f"REJECTED: {rejection}",
        )

    # ── Size: quarter-Kelly with flat unit as floor
    price_cents = int(opp.market_price * 100)
    if price_cents <= 0:
        price_cents = 1
    if price_cents >= 100:
        price_cents = 99

    # Flat unit sizing (baseline)
    flat_contracts = unit_size_contracts(opp.market_price, unit_size)

    # Kelly sizing divided by batch size: bet = (fraction / N) * edge * bankroll
    # This ensures total batch exposure stays proportional to what single-bet
    # Kelly would allocate, preventing over-commitment on simultaneous bets.
    effective_kelly = KELLY_FRACTION / max(1, batch_size)

    # R1: dampen Kelly on NO bets priced below the floor. These are bets against
    # market-priced favorites, where the model has historically overstated edge.
    is_no_side = bool(opp.side and opp.side.strip().lower() == "no")
    if is_no_side and opp.market_price < NO_SIDE_KELLY_PRICE_FLOOR:
        effective_kelly *= NO_SIDE_KELLY_MULTIPLIER

    kelly_bet = effective_kelly * trusted_edge(opp.edge) * bankroll
    kelly_contracts = max(1, int(kelly_bet / opp.market_price)) if kelly_bet > 0 else flat_contracts

    # Use the larger of flat and Kelly (Kelly scales up for high-edge bets)
    contracts = max(flat_contracts, kelly_contracts)
    actual_cost = contracts * opp.market_price

    approval = "APPROVED"
    bankroll_pct = actual_cost / bankroll if bankroll > 0 else 0

    # ── Risk Gate 7: Max bet size cap (sizing cap, not reject)
    if actual_cost > MAX_BET_SIZE:
        contracts = max(1, int(MAX_BET_SIZE / opp.market_price))
        actual_cost = contracts * opp.market_price
        bankroll_pct = actual_cost / bankroll if bankroll > 0 else 0
        approval = "APPROVED_CAPPED_MAX_BET"

    # Final check: don't exceed bankroll
    if actual_cost > bankroll:
        contracts = max(1, int(bankroll / opp.market_price))
        actual_cost = contracts * opp.market_price
        bankroll_pct = actual_cost / bankroll if bankroll > 0 else 0

    return SizedOrder(
        opportunity=opp,
        contracts=contracts,
        price_cents=price_cents,
        cost_dollars=round(actual_cost, 2),
        bankroll_pct=round(bankroll_pct, 4),
        risk_approval=approval,
    )


# ── Trade Logging ─────────────────────────────────────────────────────────────
# load_trade_log, save_trade_log, get_today_pnl imported from scripts.shared.trade_log


def log_trade(order_response: dict, sized: SizedOrder, trade_log: list) -> dict:
    """Log an executed trade with fill-accurate accounting.

    Records both *requested* values (what we asked for) and *filled* values
    (what Kalshi actually executed).  The primary accounting fields
    ``filled_contracts`` / ``filled_cost`` reflect reality — resting or
    partially-filled orders will show lower filled values than requested.
    """
    order = order_response.get("order", order_response)
    opp = sized.opportunity

    # Parse fill info from Kalshi API response
    fill_count = int(float(order.get("fill_count_fp", "0") or "0"))
    remaining = int(float(order.get("remaining_count_fp", "0") or "0"))
    filled_cost = round(fill_count * opp.market_price, 4) if fill_count else 0.0

    # Determine order status category
    api_status = order.get("status", "unknown")
    if fill_count == 0:
        fill_status = "resting"
    elif remaining > 0:
        fill_status = "partial"
    else:
        fill_status = "filled"

    trade_record = {
        "trade_id": str(uuid.uuid4()),
        "order_id": order.get("order_id", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ticker": opp.ticker,
        "title": opp.title,
        "category": opp.category,
        "side": opp.side,
        "action": "buy",
        # Requested values (what we asked for)
        "requested_contracts": sized.contracts,
        "requested_cost": sized.cost_dollars,
        # Filled values (what actually executed) — primary accounting fields
        "filled_contracts": fill_count,
        "filled_cost": filled_cost,
        # Legacy fields kept for backward compatibility
        "contracts": fill_count,
        "cost_dollars": filled_cost,
        "fill_count": fill_count,
        "remaining_count": remaining,
        "price_cents": sized.price_cents,
        "taker_fees": order.get("taker_fees_dollars", "0"),
        "maker_fees": order.get("maker_fees_dollars", "0"),
        "status": api_status,
        "fill_status": fill_status,  # resting | partial | filled
        "edge_estimated": opp.edge,
        "fair_value": opp.fair_value,
        "market_price_at_entry": opp.market_price,
        "confidence": opp.confidence,
        "composite_score": opp.composite_score,
        "edge_source": opp.edge_source,
        "unit_size": UNIT_SIZE,
        "bankroll_pct": sized.bankroll_pct,
        "risk_approval": sized.risk_approval,
        "net_pnl": 0,  # updated on settlement
        "closed_at": None,
        "dry_run": False,
    }

    trade_log.append(trade_record)
    save_trade_log(trade_log)
    return trade_record


# ── Execution Pipeline ────────────────────────────────────────────────────────

def load_opportunities_from_file(prediction: bool = False) -> list[Opportunity]:
    """Load opportunities from saved watchlist file(s).

    Args:
        prediction: If True, load prediction market opportunities.
                    If False, load sports opportunities.
    """
    file_path = paths.PREDICTION_OPPORTUNITIES_PATH if prediction else paths.SPORTS_OPPORTUNITIES_PATH
    if not file_path.exists():
        return []
    with open(file_path) as f:
        data = json.load(f)
    return [
        Opportunity(**{k: v for k, v in o.items()})
        for o in data.get("opportunities", [])
    ]


def _parse_pick_rows(pick_str: str, total: int) -> list[int]:
    """Parse --pick argument into 0-based indices. Supports '1,3,5' and '1-3'."""
    indices = []
    for part in pick_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            for i in range(int(start), int(end) + 1):
                if 1 <= i <= total:
                    indices.append(i - 1)
        else:
            i = int(part)
            if 1 <= i <= total:
                indices.append(i - 1)
    return sorted(set(indices))


def _apply_budget_cap(orders: list[SizedOrder], budget: float) -> list[SizedOrder]:
    """Proportionally scale down contracts so total cost stays within budget.

    Preserves Kelly's edge-based weighting — higher-edge bets keep more
    capital — while enforcing the total ceiling.  Each bet keeps at least
    1 contract, so the actual total may slightly undershoot the budget due
    to contract rounding.
    """
    total = sum(s.cost_dollars for s in orders)
    if total <= budget or total <= 0:
        return orders

    scale = budget / total
    bankroll = budget / 0.10 if budget else 1  # rough; recalc'd below

    capped: list[SizedOrder] = []
    for s in orders:
        new_contracts = max(1, int(s.contracts * scale))
        new_cost = round(new_contracts * s.opportunity.market_price, 2)
        capped.append(SizedOrder(
            opportunity=s.opportunity,
            contracts=new_contracts,
            price_cents=s.price_cents,
            cost_dollars=new_cost,
            bankroll_pct=s.bankroll_pct * scale,
            risk_approval=s.risk_approval,
        ))

    return capped


def _apply_bet_ratio_cap(orders: list[SizedOrder], ratio: float = MAX_BET_RATIO) -> list[SizedOrder]:
    """Cap any single bet that exceeds ratio × the median batch cost.

    Prevents one high-edge, low-price bet from dominating a batch.
    Only scales down outliers — other bets are untouched.
    """
    if len(orders) < 2 or ratio <= 0:
        return orders

    costs = sorted(s.cost_dollars for s in orders)
    median_cost = costs[len(costs) // 2]
    cap = median_cost * ratio

    if cap <= 0:
        return orders

    capped: list[SizedOrder] = []
    for s in orders:
        if s.cost_dollars > cap:
            new_contracts = max(1, int(cap / s.opportunity.market_price))
            new_cost = round(new_contracts * s.opportunity.market_price, 2)
            bankroll_pct = s.bankroll_pct * (new_cost / s.cost_dollars) if s.cost_dollars > 0 else s.bankroll_pct
            capped.append(SizedOrder(
                opportunity=s.opportunity,
                contracts=new_contracts,
                price_cents=s.price_cents,
                cost_dollars=new_cost,
                bankroll_pct=round(bankroll_pct, 4),
                risk_approval="APPROVED_CAPPED_BET_RATIO",
            ))
        else:
            capped.append(s)

    return capped


def execute_pipeline(
    client: KalshiClient,
    opportunities: list[Opportunity],
    execute: bool = False,
    max_bets: int = 5,
    unit_size: float = UNIT_SIZE,
    pick_rows: str | None = None,
    pick_tickers: list[str] | None = None,
    budget: float | None = None,
    min_bets: int | None = None,
) -> list[dict]:
    """
    Run the full pipeline: risk-check, size, and optionally execute.

    Args:
        client: Authenticated KalshiClient
        opportunities: Scored opportunities from edge detector
        execute: If True, actually place orders. If False, preview only.
        max_bets: Maximum number of bets to place in one run
        min_bets: Minimum approved bets required to proceed. If fewer pass
                  risk checks, abort execution to avoid over-concentrating
                  the budget into too few positions.
    """
    # ── Gather portfolio state
    bal = client.get_balance_dollars()
    bankroll = bal["balance"]
    rprint(f"\n[bold]Portfolio State[/bold]")
    rprint(f"  Balance:    [green]${bankroll:,.2f}[/green]")
    rprint(f"  Portfolio:  [green]${bal['portfolio_value']:,.2f}[/green]")

    positions = client.get_positions(limit=200, count_filter="position")
    market_positions = positions.get("market_positions", [])
    open_count = len(market_positions)
    rprint(f"  Positions:  {open_count}/{MAX_OPEN_POSITIONS}")

    # Build open ticker set and per-event counts for risk gates
    open_tickers = {p.get("ticker", "") for p in market_positions}
    event_counts: dict[str, int] = {}
    for t in open_tickers:
        evt = _event_key(t)
        event_counts[evt] = event_counts.get(evt, 0) + 1

    trade_log = load_trade_log()
    daily_pnl = get_today_pnl(trade_log)
    recent_matchups = recent_matchups_from_log(trade_log)
    rprint(f"  Today P&L:  ${daily_pnl:,.2f} (limit: -${MAX_DAILY_LOSS:,.2f})")
    rprint(f"  Unit size:  ${unit_size:.2f}")
    rprint(f"  Per-game:   {MAX_PER_EVENT} max")
    if SERIES_DEDUP_HOURS > 0:
        rprint(f"  Series dedup: blocking matchups bet within last {SERIES_DEDUP_HOURS}h ({len(recent_matchups)} active)")

    if daily_pnl <= -MAX_DAILY_LOSS:
        rprint("[red bold]DAILY LOSS LIMIT HIT -- no new bets allowed today[/red bold]")
        return []

    # ── Deduplicate correlated brackets (e.g., multiple totals lines on same game)
    before_dedup = len(opportunities)
    opportunities = dedup_correlated_brackets(opportunities)
    if len(opportunities) < before_dedup:
        rprint(f"[dim]Deduped correlated brackets: {before_dedup} -> {len(opportunities)} opportunities[/dim]")

    # ── Size all opportunities
    # Divide Kelly fraction by batch size so total exposure stays proportional
    batch_sz = min(len(opportunities), max_bets)
    rprint(f"\n[bold]Risk-checking {len(opportunities)} opportunities (batch={batch_sz})...[/bold]")
    sized_orders: list[SizedOrder] = []
    for opp in opportunities:
        sized = size_order(
            opp, bankroll, open_count + len([s for s in sized_orders if s.risk_approval.startswith("APPROVED")]),
            daily_pnl, unit_size, open_tickers, event_counts, MAX_PER_EVENT,
            batch_size=batch_sz,
            recent_matchups=recent_matchups,
        )
        sized_orders.append(sized)
        # Track newly approved positions for subsequent gate checks
        if sized.risk_approval.startswith("APPROVED"):
            open_tickers.add(opp.ticker)
            evt = _event_key(opp.ticker)
            event_counts[evt] = event_counts.get(evt, 0) + 1
            mkey = matchup_key(opp.ticker)
            if mkey:
                recent_matchups.add(mkey)

    approved = [s for s in sized_orders if s.risk_approval.startswith("APPROVED")]
    rejected = [s for s in sized_orders if not s.risk_approval.startswith("APPROVED")]

    rprint(f"  Approved: [green]{len(approved)}[/green]  Rejected: [red]{len(rejected)}[/red]")

    # Show rejections
    if rejected:
        for s in rejected[:5]:
            rprint(f"  [dim]SKIP {s.opportunity.ticker}: {s.risk_approval}[/dim]")
        if len(rejected) > 5:
            rprint(f"  [dim]... and {len(rejected) - 5} more[/dim]")

    if not approved:
        rprint("[yellow]No opportunities passed risk checks.[/yellow]")
        return []

    # ── Min-bets gate: abort if too few approved to avoid over-concentration
    if min_bets is not None and len(approved) < min_bets:
        rprint(f"[yellow bold]MIN-BETS GATE: only {len(approved)} approved but "
               f"--min-bets requires {min_bets}. Skipping execution to avoid "
               f"over-concentrating budget into too few positions.[/yellow bold]")
        return []

    # ── Preview table
    to_execute = approved[:max_bets]

    # ── Bet ratio cap: prevent one bet from dominating the batch
    pre_ratio_cost = sum(s.cost_dollars for s in to_execute)
    to_execute = _apply_bet_ratio_cap(to_execute)
    post_ratio_cost = sum(s.cost_dollars for s in to_execute)
    if post_ratio_cost < pre_ratio_cost:
        rprint(f"  Bet ratio cap: [yellow]${pre_ratio_cost:.2f} -> ${post_ratio_cost:.2f}[/yellow] (max {MAX_BET_RATIO:.1f}x median)")

    # ── Budget cap: proportionally scale if total exceeds budget
    if budget is not None:
        budget_dollars = budget * bankroll if budget <= 1 else budget
        pre_budget_cost = sum(s.cost_dollars for s in to_execute)
        if pre_budget_cost > budget_dollars:
            to_execute = _apply_budget_cap(to_execute, budget_dollars)
            post_budget_cost = sum(s.cost_dollars for s in to_execute)
            rprint(f"  Budget cap: [yellow]${pre_budget_cost:.2f} -> ${post_budget_cost:.2f}[/yellow] (limit ${budget_dollars:.2f})")
        else:
            rprint(f"  Budget cap: [green]${pre_budget_cost:.2f} within ${budget_dollars:.2f} limit[/green]")

    from ticker_display import (
        parse_game_datetime, format_bet_label, format_pick_label, sport_from_ticker,
    )

    dry_run = os.getenv("DRY_RUN", "true").lower() == "true"
    if execute and dry_run:
        table_title = f"DRY RUN -- {len(to_execute)} orders (DRY_RUN=true, no real orders placed)"
    elif execute:
        table_title = f"EXECUTING -- {len(to_execute)} orders"
    else:
        table_title = f"PREVIEW -- {len(to_execute)} orders"
    table = Table(title=table_title, show_lines=True)
    cat_labels = {
        "game": "ML", "spread": "Spread", "total": "Total",
        "player_prop": "Prop", "esports": "Esports",
    }

    table.add_column("#", justify="right", style="dim")
    table.add_column("Sport", style="yellow")
    table.add_column("Bet", style="cyan", max_width=45)
    table.add_column("Type", style="magenta")
    table.add_column("Pick", style="bold white", max_width=22)
    table.add_column("When", style="dim")
    table.add_column("Qty", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Cost", justify="right", style="green")
    table.add_column("Edge", justify="right", style="bold green")

    total_cost = 0
    for i, s in enumerate(to_execute, 1):
        total_cost += s.cost_dollars
        opp = s.opportunity

        table.add_row(
            str(i),
            sport_from_ticker(opp.ticker),
            format_bet_label(opp.ticker, opp.title),
            cat_labels.get(opp.category, opp.category.title()),
            format_pick_label(opp.ticker, opp.title, opp.side, opp.category),
            parse_game_datetime(opp.ticker),
            str(s.contracts),
            f"${s.price_cents / 100:.2f}",
            f"${s.cost_dollars:.2f}",
            f"+{opp.edge:.1%}",
        )
    console.print(table)
    rprint(f"  Total cost: [bold]${total_cost:.2f}[/bold] of ${bankroll:.2f} available")
    if not execute:
        rprint("[dim]  Tip: use --pick '1,3' --execute to bet on specific rows[/dim]")
        rprint("\n[yellow]DRY RUN -- pass --execute to place these orders[/yellow]")
        return to_execute  # Return sized orders for reporting

    # ── Filter by --pick or --ticker if specified
    if pick_rows is not None:
        selected = _parse_pick_rows(pick_rows, len(to_execute))
        to_execute = [to_execute[i] for i in selected]
        rprint(f"\n[bold]Picked {len(to_execute)} of {len(approved)} approved orders[/bold]")
    if pick_tickers is not None:
        pick_set = {t.upper() for t in pick_tickers}
        to_execute = [s for s in to_execute if s.opportunity.ticker.upper() in pick_set]
        rprint(f"\n[bold]Matched {len(to_execute)} orders by ticker[/bold]")

    if not to_execute:
        rprint("[yellow]No orders matched your --pick or --ticker selection.[/yellow]")
        return []

    # ── Execute
    rprint(f"\n[bold]Placing {len(to_execute)} orders...[/bold]")
    results = []

    for s in to_execute:
        opp = s.opportunity
        try:
            # Determine price based on side
            kwargs = {
                "ticker": opp.ticker,
                "side": opp.side,
                "action": "buy",
                "count": s.contracts,
                "time_in_force": "good_till_canceled",
            }
            if opp.side == "yes":
                kwargs["yes_price_cents"] = s.price_cents
            else:
                kwargs["no_price_cents"] = s.price_cents

            order_resp = client.create_order(**kwargs)
            order = order_resp.get("order", order_resp)
            status = order.get("status", "unknown")

            record = log_trade(order_resp, s, trade_log)
            results.append(record)

            fill = int(float(order.get("fill_count_fp", "0") or "0"))
            fees = order.get("taker_fees_dollars", "0")
            fill_tag = ""
            if fill == 0:
                fill_tag = " [yellow](RESTING — no fills yet)[/yellow]"
            elif fill < s.contracts:
                fill_tag = f" [yellow](PARTIAL — {fill}/{s.contracts} filled)[/yellow]"
            rprint(
                f"  [green]OK[/green] {opp.ticker} "
                f"{opp.side.upper()} x{s.contracts} @ ${s.price_cents/100:.2f} "
                f"-- status={status} filled={fill}/{s.contracts} fees=${fees}"
                f"{fill_tag}"
            )

        except KalshiAPIError as e:
            rprint(f"  [red]FAIL[/red] {opp.ticker}: {e.message[:80]}")
            # Log the failure
            trade_log.append({
                "trade_id": str(uuid.uuid4()),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ticker": opp.ticker,
                "side": opp.side,
                "status": "error",
                "error": str(e.message)[:200],
                "net_pnl": 0,
                "closed_at": None,
            })
            save_trade_log(trade_log)

    # ── Post-execution summary
    rprint(f"\n[bold]Execution complete[/bold]")
    new_bal = client.get_balance_dollars()
    rprint(f"  Balance: ${bankroll:.2f} -> ${new_bal['balance']:.2f}")
    rprint(f"  Orders placed: {len(results)}")
    rprint(f"  Trade log: {TRADE_LOG_PATH}")

    return to_execute  # Return SizedOrder objects for report writer


# ── Status Command ────────────────────────────────────────────────────────────

def show_status(client: KalshiClient, save: bool = False):
    """Show current portfolio status, positions, and today's activity."""
    from ticker_display import parse_game_datetime, parse_matchup, parse_pick_team

    bal = client.get_balance_dollars()
    env = "DEMO" if client.is_demo else "LIVE"
    now = datetime.now(timezone.utc)

    rprint(f"\n[bold]-- Kalshi Portfolio Status --[/bold]")
    rprint(f"  Environment:  {env}")
    rprint(f"  Balance:      [green]${bal['balance']:,.2f}[/green]")
    rprint(f"  Portfolio:    [green]${bal['portfolio_value']:,.2f}[/green]")

    # Positions
    positions = client.get_positions(limit=100, count_filter="position")
    market_pos = positions.get("market_positions", [])
    rprint(f"  Positions:    {len(market_pos)}/{MAX_OPEN_POSITIONS}")

    if market_pos:
        from ticker_display import bet_type_from_ticker

        table = Table(title="Open Positions", show_lines=True)
        table.add_column("Bet", style="cyan", max_width=32)
        table.add_column("Type", style="magenta")
        table.add_column("When", style="dim")
        table.add_column("Pick", justify="center")
        table.add_column("Qty", justify="right")
        table.add_column("Cost", justify="right", style="green")
        table.add_column("P&L", justify="right")

        for p in market_pos:
            ticker = p.get("ticker", "")
            pnl = float(p.get("realized_pnl_dollars", "0"))
            exposure = float(p.get("market_exposure_dollars", "0"))
            pnl_style = "green" if pnl >= 0 else "red"

            yes_qty = float(p.get("position_fp", "0"))
            side = "YES" if yes_qty > 0 else "NO"
            pick_name = parse_pick_team(ticker) or side

            table.add_row(
                parse_matchup(ticker) or ticker[:32],
                bet_type_from_ticker(ticker),
                parse_game_datetime(ticker),
                f"{side} {pick_name}",
                str(int(abs(yes_qty))),
                f"${exposure:.2f}",
                f"[{pnl_style}]${pnl:+.2f}[/{pnl_style}]",
            )
        console.print(table)

    # Today's trades
    trade_log = load_trade_log()
    today = now.strftime("%Y-%m-%d")
    today_trades = [t for t in trade_log if t.get("timestamp", "").startswith(today)]
    daily_pnl = get_today_pnl(trade_log)
    from trade_log import get_filled_cost
    total_wagered = sum(get_filled_cost(t) for t in today_trades)

    if today_trades:
        rprint(f"\n  [bold]Today's Activity: {len(today_trades)} trades[/bold]")
        rprint(f"  Wagered:      ${total_wagered:,.2f}")
        rprint(f"  Realized P&L: ${daily_pnl:,.2f}")
        rprint(f"  Loss limit:   ${daily_pnl:,.2f} / -${MAX_DAILY_LOSS:,.2f}")
    else:
        rprint(f"\n  [dim]No trades today[/dim]")

    # Resting orders
    resting = []
    try:
        orders = client.get_orders(limit=50, status="resting")
        resting = orders.get("orders", [])
        if resting:
            rprint(f"\n  [bold]Resting Orders: {len(resting)}[/bold]")
            for o in resting[:5]:
                rprint(
                    f"    {o['ticker'][:30]} {o['side'].upper()} "
                    f"x{o.get('remaining_count_fp', '?')} @ {o.get('yes_price_dollars', '?')}"
                )
    except Exception:
        pass

    # Save markdown report
    if save:
        md = []
        md.append(f"# Kalshi Portfolio Status")
        md.append(f"")
        md.append(f"*{now.strftime('%A, %B %d, %Y')} | {now.strftime('%I:%M %p UTC')} | {env}*")
        md.append(f"")
        md.append(f"| Metric | Value |")
        md.append(f"|--------|-------|")
        md.append(f"| Cash Balance | ${bal['balance']:,.2f} |")
        md.append(f"| Portfolio Value | ${bal['portfolio_value']:,.2f} |")
        md.append(f"| Open Positions | {len(market_pos)}/{MAX_OPEN_POSITIONS} |")
        md.append(f"| Today's P&L | ${daily_pnl:+,.2f} |")
        md.append(f"| Today's Wagered | ${total_wagered:,.2f} |")
        md.append(f"| Trades Today | {len(today_trades)} |")

        if market_pos:
            total_exposure = 0.0
            total_pnl = 0.0
            md.append(f"")
            md.append(f"## Open Positions ({len(market_pos)})")
            md.append(f"")
            md.append(f"| Bet | When | Pick | Qty | Cost | P&L |")
            md.append(f"|-----|------|------|-----|------|-----|")
            for p in market_pos:
                ticker = p.get("ticker", "")
                pnl = float(p.get("realized_pnl_dollars", "0"))
                exposure = float(p.get("market_exposure_dollars", "0"))
                total_exposure += exposure
                total_pnl += pnl
                yes_qty = float(p.get("position_fp", "0"))
                side = "YES" if yes_qty > 0 else "NO"
                pick_name = parse_pick_team(ticker) or side
                md.append(
                    f"| {parse_matchup(ticker) or ticker[:30]} "
                    f"| {parse_game_datetime(ticker)} "
                    f"| {side} {pick_name} "
                    f"| {int(abs(yes_qty))} "
                    f"| ${exposure:.2f} "
                    f"| ${pnl:+.2f} |"
                )
            md.append(f"| **TOTAL** | | | | **${total_exposure:.2f}** | **${total_pnl:+.2f}** |")

        if resting:
            md.append(f"")
            md.append(f"## Resting Orders ({len(resting)})")
            md.append(f"")
            md.append(f"| Ticker | Side | Remaining | Price |")
            md.append(f"|--------|------|-----------|-------|")
            for o in resting:
                price = o.get("yes_price_dollars") or o.get("no_price_dollars") or "?"
                md.append(f"| {o.get('ticker', '')[:35]} | {o.get('side', '').upper()} | {o.get('remaining_count_fp', '?')} | ${price} |")

        md.append(f"")
        md.append(f"---")
        md.append(f"*Generated by Edge-Radar*")

        from pathlib import Path
        report_dir = Path(paths.PROJECT_ROOT) / "reports" / "Accounts" / "Kalshi"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"kalshi_status_{today}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        rprint(f"\n[dim]Report saved to {report_path}[/dim]")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Kalshi automated executor")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="Scan markets and execute bets")
    run_p.add_argument("--execute", action="store_true",
                       help="Actually place orders (default: preview only)")
    run_p.add_argument("--from-file", action="store_true",
                       help="Use saved watchlist instead of fresh scan")
    run_p.add_argument("--prediction", action="store_true",
                       help="Use prediction market scanner (crypto, weather, S&P 500) instead of sports")
    run_p.add_argument("--filter", dest="ticker_filter",
                       help="Filter: ncaamb, nba, nhl, ... (sports) or crypto, btc, weather, spx (prediction)")
    run_p.add_argument("--min-edge", type=float, default=MIN_EDGE_THRESHOLD,
                       help="Minimum edge threshold")
    run_p.add_argument("--unit-size", type=float, default=UNIT_SIZE,
                       help=f"Dollar amount per bet (default ${UNIT_SIZE:.2f})")
    run_p.add_argument("--max-bets", type=int, default=5,
                       help="Max bets per run (default 5)")
    run_p.add_argument("--top", type=int, default=20,
                       help="Number of opportunities to scan")
    run_p.add_argument("--pick", type=str, default=None,
                       help="Execute only specific rows from preview (e.g., '1,3,5' or '1-3')")
    run_p.add_argument("--ticker", type=str, nargs="+", default=None,
                       help="Execute specific market ticker(s) from the scan results")
    run_p.add_argument("--cross-ref", action="store_true",
                       help="Cross-reference Kalshi prices against Polymarket (prediction markets only)")
    run_p.add_argument("--date", type=str, default=None,
                       help="Only show games on this date (today, tomorrow, YYYY-MM-DD, mar31)")
    run_p.add_argument("--budget", type=str, default=None,
                       help="Max total cost for the batch. Percentage of bankroll (e.g. '10%%') "
                            "or dollar amount (e.g. '15'). Bets are proportionally scaled down "
                            "to stay within budget while preserving Kelly edge-weighting.")
    run_p.add_argument("--exclude-open", action="store_true",
                       help="Exclude markets where you already have an open position")

    status_p = sub.add_parser("status", help="Show portfolio status")
    status_p.add_argument("--save", action="store_true",
                          help="Save status report to reports/Accounts/Kalshi/")

    args = parser.parse_args()

    # Client for execution and portfolio queries
    client = KalshiClient()

    # Production client for market data (if configured)
    prod_client = make_prod_client()
    if prod_client:
        rprint("[bold]Using PRODUCTION market data for scanning[/bold]")
        scan_client = prod_client
    else:
        scan_client = client

    if args.command == "status":
        show_status(client, save=args.save)

    elif args.command == "run":
        # Get opportunities
        if args.from_file:
            rprint(f"[bold]Loading {'prediction' if args.prediction else 'sports'} opportunities from file...[/bold]")
            opportunities = load_opportunities_from_file(prediction=args.prediction)
            src = paths.PREDICTION_OPPORTUNITIES_PATH if args.prediction else paths.SPORTS_OPPORTUNITIES_PATH
            rprint(f"  Loaded {len(opportunities)} from {src}")

        elif args.prediction:
            # Use prediction market scanner
            rprint("[bold]Running prediction market scan...[/bold]")
            from prediction_scanner import scan_prediction_markets
            is_poly_filter = args.ticker_filter and args.ticker_filter.lower() in ("polymarket", "poly", "xref")
            use_cross_ref = args.cross_ref or is_poly_filter
            opportunities = scan_prediction_markets(
                scan_client,
                min_edge=args.min_edge,
                ticker_filter=args.ticker_filter,
                top_n=args.top,
                cross_ref=use_cross_ref,
            )

        else:
            # Use sports edge detector
            rprint("[bold]Running fresh sports market scan...[/bold]")
            # Resolve date early so scan_all_markets can pre-filter before Odds API calls
            resolved_date = None
            if args.date:
                from ticker_display import resolve_date_arg
                resolved_date = resolve_date_arg(args.date)
            opportunities = scan_all_markets(
                scan_client,
                min_edge=args.min_edge,
                ticker_filter=args.ticker_filter,
                top_n=args.top,
                date_filter=resolved_date,
            )

        if not opportunities:
            rprint("[yellow]No opportunities found.[/yellow]")
            return

        # Apply date filter on opportunities (catches any edge cases the early filter missed)
        if args.date:
            from ticker_display import filter_by_date, resolve_date_arg
            target = resolve_date_arg(args.date)
            before = len(opportunities)
            opportunities = filter_by_date(opportunities, target)
            if len(opportunities) < before:
                rprint(f"[dim]Date filter ({target}): {before} -> {len(opportunities)} opportunities[/dim]")
        if args.exclude_open:
            from ticker_display import filter_exclude_tickers
            positions = client.get_positions(limit=200, count_filter="position")
            open_tickers = {p.get("ticker", "") for p in positions.get("market_positions", [])}
            before = len(opportunities)
            opportunities = filter_exclude_tickers(opportunities, open_tickers)
            rprint(f"[dim]Excluded open positions: {before} -> {len(opportunities)} opportunities[/dim]")

        if not opportunities:
            rprint("[yellow]No opportunities after filtering.[/yellow]")
            return

        # Parse --budget: "15%" or "15" -> 0.15 (fraction of bankroll)
        # Values <= 1 treated as fractions, 1-100 as percentages, >100 as dollars
        budget_val = None
        if args.budget is not None:
            raw = args.budget.strip().rstrip("%")
            num = float(raw)
            if num <= 1:
                budget_val = num
            elif num <= 100:
                budget_val = num / 100
            else:
                budget_val = num

        execute_pipeline(
            client=client,
            opportunities=opportunities,
            execute=args.execute,
            max_bets=args.max_bets,
            unit_size=args.unit_size,
            pick_rows=args.pick,
            pick_tickers=args.ticker,
            budget=budget_val,
        )


if __name__ == "__main__":
    main()
