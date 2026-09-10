"""S8 — capture the closing book for open positions, for CLV.

CLV (closing line value) is the entry price measured against the market's price
at the moment the pre-game line closes. It is the strongest short-horizon
read on whether a model has edge, and at this book's sample size the ROADMAP's
Priority 0a rests on it: *"CLV and Brier are the only readable signals."*

**It has never once been computed.** `kalshi_settler.py` derived `closing_price`
from the settlement-time market snapshot — but a settled Kalshi market returns
nothing meaningful for `last_price`, so it read `0.0`, `0.0` is falsy, and the
guard `if closing_price and entry_price` short-circuited `clv` to `None`.
Silently, on every settle, for five months: **426 settlements, 0 CLV**, with
`closing_price` split `{None: 259, 0.0: 167}` (D1/S8).

The fix is not a better sum at settlement time. The closing book **does not
exist any more** by then — it has to be sampled before the event starts, which
is what this job does.

## How it runs

Idempotent, cheap, and safe to run often. Each pass:

1. loads open trades that have an `event_start_time` and no capture yet;
2. keeps those whose start is inside the capture window;
3. reads each ticker's book once from Kalshi;
4. writes the **whole book**, not one scalar.

Run it every few minutes from the scheduler. A pass with nothing due costs one
trade-log read and no API calls at all.

## Why the whole book

`close_yes_bid` / `close_yes_ask` / `close_no_bid` / `close_no_ask` are all
persisted alongside `close_mid_bet_side`. Storing only a midpoint makes the S14
maker/taker A/B unreadable — you cannot tell maker CLV genuinely improving from
the close being sampled on the other side of a wide book.

## Why `missed` is NULL and never 0.0

A capture that could not get a book writes `close_capture_reason="missed"` with
**null prices**. A falsy sentinel absorbed by a truthiness guard is precisely
how D1 went unnoticed for five months, and a zero close would additionally drag
every mean CLV toward a fictitious `-entry_price`. Absent, missed, and captured
are three different facts and stay distinguishable.

Usage:
    python scripts/kalshi/clv_capture.py                 # capture what is due
    python scripts/kalshi/clv_capture.py --dry-run       # show, write nothing
    python scripts/kalshi/clv_capture.py --window 10     # widen the window
    python scripts/kalshi/clv_capture.py --report        # coverage so far
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

import paths  # noqa: F401  -- adds scripts/shared to sys.path

from dotenv import load_dotenv

from trade_log import load_trade_log, save_trade_log, trade_log_lock  # noqa: E402

load_dotenv()
log = logging.getLogger("clv_capture")

# Capture opens this many minutes before the scheduled start and closes at the
# start itself. Five minutes is late enough that the line has stopped drifting
# and early enough to beat first pitch; the T-0 fallback exists because a job
# that runs every 5 minutes cannot guarantee it lands inside a 5-minute slot.
DEFAULT_WINDOW_MINUTES = 5

# How far past the start a T-0 fallback may still fire. Beyond this the book is
# in-play and is no longer a *closing* line -- capturing it would quietly
# redefine CLV to mean something else for the rows that were late.
FALLBACK_GRACE_MINUTES = 10

REASON_T_MINUS = "t_minus_5"
REASON_T_ZERO = "t_zero_fallback"
REASON_MISSED = "missed"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_open(trade: dict) -> bool:
    """Unsettled, real, and actually filled.

    Dry-run rows are excluded: they never reached the venue, so there is no
    position whose line can close. Zero-fill rows are excluded for the same
    reason -- a resting order that never filled has no entry price to measure
    against.
    """
    if trade.get("closed_at"):
        return False
    if trade.get("dry_run"):
        return False
    try:
        return float(trade.get("filled_contracts")
                     or trade.get("fill_count") or 0) > 0
    except (TypeError, ValueError):
        return False


def needs_capture(trade: dict) -> bool:
    """No capture attempt has been recorded yet.

    A recorded `missed` counts as done. Re-trying it later would sample an
    in-play book and label it a close, which is worse than a recorded gap --
    S9 prints `n_captured / n_settled` precisely so gaps stay visible.
    """
    return not trade.get("close_capture_reason")


def capture_due(trade: dict, now: datetime, window_minutes: int,
                grace_minutes: int = FALLBACK_GRACE_MINUTES) -> str | None:
    """Which capture reason applies right now, or None if not due yet.

    Returns `t_minus_5` inside the pre-start window, `t_zero_fallback` in the
    grace period just after the start, and `missed` once the book has been
    in-play too long to call a close. None means "too early, look again later".
    """
    start = _parse_iso(trade.get("event_start_time"))
    if start is None:
        return None
    delta_minutes = (start - now).total_seconds() / 60.0
    if delta_minutes > window_minutes:
        return None
    if delta_minutes >= 0:
        return REASON_T_MINUS
    if -delta_minutes <= grace_minutes:
        return REASON_T_ZERO
    return REASON_MISSED


def _price(raw) -> float | None:
    """A Kalshi dollar price as a float, or None. **Never 0.0 for missing.**"""
    if raw is None or raw == "":
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def closing_book(market: dict, side: str) -> dict:
    """The full closing book plus the bet-side midpoint.

    `side` is the side actually bought. The midpoint is expressed in **bet-side
    probability space** so that CLV means one thing across YES and NO: for a NO
    bet, a *rising* NO price is line movement in the bettor's favour, exactly as
    a rising YES price is for a YES bet. Mixing the two frames is the S18
    mistake, and it silently inverts the sign on a third of the book.
    """
    yes_bid = _price(market.get("yes_bid_dollars"))
    yes_ask = _price(market.get("yes_ask_dollars"))
    no_bid = _price(market.get("no_bid_dollars"))
    no_ask = _price(market.get("no_ask_dollars"))

    if no_bid is None and yes_ask is not None:
        no_bid = round(1.0 - yes_ask, 4)
    if no_ask is None and yes_bid is not None:
        no_ask = round(1.0 - yes_bid, 4)

    bid, ask = (yes_bid, yes_ask) if side == "yes" else (no_bid, no_ask)
    mid = round((bid + ask) / 2.0, 4) if bid is not None and ask is not None else None

    return {
        "close_yes_bid": yes_bid, "close_yes_ask": yes_ask,
        "close_no_bid": no_bid, "close_no_ask": no_ask,
        "close_mid_bet_side": mid,
    }


def compute_clv(entry_price_bet_side, close_mid_bet_side) -> float | None:
    """`close - entry`, both bet-side. None if either leg is missing.

    Uses an explicit `is None` test, never truthiness. An entry price of 0.0 is
    not a real Kalshi fill, but a *close* of 0.0 is entirely possible on a
    market that has collapsed, and `if close and entry` would silently discard
    it -- the same shape of bug as D1, one level down.
    """
    if entry_price_bet_side is None or close_mid_bet_side is None:
        return None
    try:
        return round(float(close_mid_bet_side) - float(entry_price_bet_side), 4)
    except (TypeError, ValueError):
        return None


def run(client=None, *, now: datetime | None = None,
        window_minutes: int = DEFAULT_WINDOW_MINUTES,
        dry_run: bool = False) -> dict:
    """One capture pass. Returns a summary dict."""
    now = now or datetime.now(timezone.utc)
    trades = load_trade_log()

    due: list[tuple[dict, str]] = []
    for t in trades:
        if not (is_open(t) and needs_capture(t)):
            continue
        reason = capture_due(t, now, window_minutes)
        if reason:
            due.append((t, reason))

    summary = {"scanned": len(trades), "due": len(due),
               "captured": 0, "missed": 0, "errors": 0}
    if not due:
        log.info("CLV capture: nothing due (%d trades scanned)", len(trades))
        return summary

    if client is None:
        from kalshi_client import KalshiClient
        client = KalshiClient()

    for trade, reason in due:
        ticker = trade.get("ticker", "")
        if reason == REASON_MISSED:
            book = {k: None for k in
                    ("close_yes_bid", "close_yes_ask", "close_no_bid",
                     "close_no_ask", "close_mid_bet_side")}
            summary["missed"] += 1
        else:
            try:
                market = (client.get_market(ticker) or {}).get("market", {})
                book = closing_book(market, trade.get("side", "yes"))
            except Exception as e:                            # noqa: BLE001
                # A venue error is a miss, not a crash: one unreachable ticker
                # must not abandon the rest of the window, which will not come
                # round again.
                log.warning("CLV capture failed for %s: %s", ticker, e)
                book = {k: None for k in
                        ("close_yes_bid", "close_yes_ask", "close_no_bid",
                         "close_no_ask", "close_mid_bet_side")}
                reason = REASON_MISSED
                summary["errors"] += 1
            else:
                if book["close_mid_bet_side"] is None:
                    reason = REASON_MISSED
                    summary["missed"] += 1
                else:
                    summary["captured"] += 1

        trade.update(book)
        trade["close_capture_reason"] = reason
        trade["close_capture_at"] = now.isoformat()
        trade["clv"] = compute_clv(
            trade.get("entry_price_bet_side", trade.get("market_price_at_entry")),
            book["close_mid_bet_side"])
        log.info("CLV %s %s: close=%s entry=%s clv=%s", reason, ticker,
                 book["close_mid_bet_side"],
                 trade.get("entry_price_bet_side"), trade.get("clv"))

    if dry_run:
        log.info("CLV capture: --dry-run, %d rows NOT written", len(due))
        return summary

    # M2: `save_trade_log` overwrites the WHOLE file, so a bare
    # load -> mutate -> save loses any row another process appended in between.
    # This job runs every few minutes alongside ~10 scheduled execute tasks, so
    # that window is real and what it would lose is a live position record.
    # Re-read inside the lock and re-apply the captures by `trade_id`, which is
    # the idiom `append_trades` and the settler already use.
    #
    # The venue reads above are deliberately OUTSIDE the lock: holding a
    # cross-process lock across N network calls would block execution writes for
    # as long as Kalshi takes to answer.
    captured_by_id = {t.get("trade_id"): t for t, _ in due if t.get("trade_id")}
    fields = ("close_yes_bid", "close_yes_ask", "close_no_bid", "close_no_ask",
              "close_mid_bet_side", "close_capture_at", "close_capture_reason",
              "clv")
    with trade_log_lock():
        fresh = load_trade_log()
        applied = 0
        for row in fresh:
            src = captured_by_id.get(row.get("trade_id"))
            if src is None:
                continue
            for f in fields:
                row[f] = src.get(f)
            applied += 1
        save_trade_log(fresh)
    if applied != len(captured_by_id):
        log.warning("CLV capture: %d/%d captured rows found on re-read; the "
                    "rest were removed or rewritten concurrently",
                    applied, len(captured_by_id))
    summary["written"] = applied
    return summary


def report() -> dict:
    """Coverage so far. Prints `n_captured / n_settled`, per S9."""
    trades = load_trade_log()
    settled = [t for t in trades if t.get("closed_at") and not t.get("dry_run")]
    captured = [t for t in settled if t.get("clv") is not None]
    reasons: dict[str, int] = {}
    for t in settled:
        r = t.get("close_capture_reason") or "absent"
        reasons[r] = reasons.get(r, 0) + 1

    n_s, n_c = len(settled), len(captured)
    print(f"CLV coverage: {n_c}/{n_s} settled rows carry a CLV "
          f"({(n_c / n_s * 100) if n_s else 0:.0f}%)")
    for r, n in sorted(reasons.items()):
        print(f"  {r:16} {n}")
    if captured:
        vals = sorted(t["clv"] for t in captured)
        mean = sum(vals) / len(vals)
        print(f"  mean CLV {mean:+.4f}   median {vals[len(vals) // 2]:+.4f}")
        print("  (coverage below ~90% biases this optimistic — misses "
              "concentrate in thin markets, which is where the bad bets live)")
    else:
        print("  no CLV yet — capture accrues from the day it ships; "
              "there is nothing to backfill.")
    return {"settled": n_s, "captured": n_c, "reasons": reasons}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S8 CLV closing-book capture.")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW_MINUTES,
                    help=f"Minutes before start to capture (default {DEFAULT_WINDOW_MINUTES}).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show what would be captured; write nothing.")
    ap.add_argument("--report", action="store_true", help="Print coverage and exit.")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if a.report:
        report()
        return 0

    s = run(window_minutes=a.window, dry_run=a.dry_run)
    print(f"scanned {s['scanned']}  due {s['due']}  captured {s['captured']}  "
          f"missed {s['missed']}  errors {s['errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
