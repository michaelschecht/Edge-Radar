"""S20b — does thin book consensus explain a sport's underperformance?

S20 asked one question about MLB and never answered it: *"log `n_books` on every
MLB edge and check whether the failure days coincide with the losing trades."*
It could not be answered, because `n_books` was computed at scan time — it sets
`confidence` and feeds the composite — and then **thrown away**. Nothing in the
trade log or the settlement log ever carried it.

So this script does two things:

1. **`--proxy`** — the retrospective path. Recovers Odds-API key-exhaustion days
   from the logs and splits a sport's settled bets by whether their game day had
   one. This is a *proxy and a weak one*: an exhaustion line dates the **scan**,
   not the book behind a given edge, and it is scraped from log text that is
   rotated and can be pruned. It is what was available on 2026-09-10.

2. **default** — the direct path, usable once settlements carry `n_books`
   (persisted from 2026-09-10). Splits by actual book width. Prefer it as soon
   as enough rows exist; the proxy exists only to bridge the gap.

Both report **ROI and the model-minus-market Brier gap with bootstrap CIs**,
and both print a per-month breakdown, because the pooled number is exactly
where this repo has been burned before: `correlation_check.py` found a pooled
rho of +0.181 that was Simpson's paradox and inverted per stratum. A pooled
difference whose sign flips month to month is not a finding.

Usage:
    python scripts/backtest/book_width_check.py --proxy --sport mlb
    python scripts/backtest/book_width_check.py --sport mlb --thin 5
    python scripts/backtest/book_width_check.py --proxy --sport mlb --json
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import json
import random
import re
import sys
from pathlib import Path

import paths  # noqa: F401  -- adds scripts/shared to sys.path

from trade_log import load_settlement_log  # noqa: E402

PROJECT_ROOT = Path(paths.PROJECT_ROOT)

# Ticker prefixes per sport shorthand. Deliberately prefix-matched rather than
# routed through `_detect_sport`: this reads historical rows whose tickers may
# predate any given mapping change.
SPORT_PREFIX = {
    "mlb": "KXMLB", "nba": "KXNBA", "nhl": "KXNHL", "nfl": "KXNFL",
    "ncaab": "KXNCAAB", "ncaaf": "KXNCAAF", "mls": "KXMLS",
}

_MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT",
     "NOV", "DEC"])}

_EXHAUSTION = re.compile(r"All \d+ Odds API keys returned 401/429")
_LOG_DATE = re.compile(r"^(\d{4}-\d{2}-\d{2}) ")
_TICKER_DATE = re.compile(r"^KX[A-Z]+-(\d{2})([A-Z]{3})(\d{2})")


def exhaustion_days(log_dir: Path | None = None) -> set[str]:
    """Dates carrying at least one Odds-API key-exhaustion line.

    **Log timestamps are local while log FILENAMES are UTC** (a known trap in
    this repo), so the date is read from the line, never the filename.
    """
    out: set[str] = set()
    d = log_dir or (PROJECT_ROOT / "logs")
    for f in glob.glob(str(d / "*.log")):
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for line in fh:
                    if _EXHAUSTION.search(line):
                        m = _LOG_DATE.match(line)
                        if m:
                            out.add(m.group(1))
        except OSError:
            continue
    return out


def game_date(ticker: str) -> dt.date | None:
    """The event date embedded in a Kalshi game ticker.

    `KXMLBGAME-26MAR282140CLESEA-SEA` -> 2026-03-28. Used as a stand-in for the
    entry date because **the trade log is pruned** — it held 193 rows against
    426 settlements on 2026-09-10, so two thirds of settled rows could not be
    dated through `trade_id` at all. Game markets are scanned same-day or close
    to it, so the game date is the better key; futures have no meaningful one
    and drop out (their `--days-before` window would be meaningless anyway).
    """
    m = _TICKER_DATE.match((ticker or "").upper())
    if not m:
        return None
    yy, mon, dd = m.groups()
    if mon not in _MONTHS:
        return None
    try:
        return dt.date(2000 + int(yy), _MONTHS[mon], int(dd))
    except ValueError:
        return None


def _rows_for(sport: str) -> list[dict]:
    prefix = SPORT_PREFIX.get(sport.lower(), sport.upper())
    out = []
    for r in load_settlement_log():
        if not str(r.get("ticker", "")).upper().startswith(prefix):
            continue
        won = r.get("won")
        out.append({
            "ticker": r.get("ticker"),
            "date": game_date(r.get("ticker")),
            "cost": float(r.get("cost") or 0.0),
            "net": float(r.get("net_pnl") or 0.0),
            "fv": r.get("fair_value"),
            "mp": r.get("market_price_at_entry"),
            "y": (1.0 if won else 0.0) if won is not None else None,
            "n_books": r.get("n_books"),
        })
    return out


# ── statistics ──────────────────────────────────────────────────────────────

def roi(rows: list[dict]) -> float | None:
    staked = sum(r["cost"] for r in rows)
    return (sum(r["net"] for r in rows) / staked) if staked > 0 else None


def brier_gap(rows: list[dict]) -> float | None:
    """model Brier - market Brier. **Positive means the model is worse.**

    Reported as a *pair difference* rather than a bare "Brier", per S18: a bare
    Brier is not a quantity — predicted=market price is the benchmark,
    predicted=fair_value is the thing under test, and printing either alone
    under one label is how 0.169 got reported where the truth was 0.077.
    """
    v = [r for r in rows
         if r["fv"] is not None and r["mp"] is not None and r["y"] is not None]
    if not v:
        return None
    bm = sum((float(r["fv"]) - r["y"]) ** 2 for r in v) / len(v)
    bk = sum((float(r["mp"]) - r["y"]) ** 2 for r in v) / len(v)
    return bm - bk


def bootstrap_diff(a: list[dict], b: list[dict], stat, n: int = 8000,
                   seed: int = 20260910) -> tuple[float, float] | None:
    """95% CI on stat(a) - stat(b), resampling each arm independently."""
    if not a or not b:
        return None
    rng = random.Random(seed)
    diffs = []
    for _ in range(n):
        ra = [rng.choice(a) for _ in a]
        rb = [rng.choice(b) for _ in b]
        x, y = stat(ra), stat(rb)
        if x is not None and y is not None:
            diffs.append(x - y)
    if not diffs:
        return None
    diffs.sort()
    return diffs[int(0.025 * len(diffs))], diffs[int(0.975 * len(diffs))]


def split(rows: list[dict], *, proxy: bool, exh: set[str],
          days_before: int, thin: int) -> tuple[list[dict], list[dict], list[dict]]:
    """-> (suspect, control, undatable/unknown)."""
    lo, hi, skip = [], [], []
    for r in rows:
        if proxy:
            if r["date"] is None:
                skip.append(r)
                continue
            days = [(r["date"] - dt.timedelta(days=k)).isoformat()
                    for k in range(days_before + 1)]
            (lo if any(d in exh for d in days) else hi).append(r)
        else:
            nb = r["n_books"]
            if nb is None:
                skip.append(r)
                continue
            (lo if int(nb) < thin else hi).append(r)
    return lo, hi, skip


def _fmt(rows: list[dict]) -> str:
    n = len(rows)
    if not n:
        return "n=0"
    wins = sum(1 for r in rows if r["y"] == 1.0)
    r_, g = roi(rows), brier_gap(rows)
    return (f"n={n:4} W-L {wins:3}-{n - wins:<3} staked ${sum(x['cost'] for x in rows):7.2f} "
            f"net ${sum(x['net'] for x in rows):+7.2f} "
            f"ROI {(f'{r_:+.1%}' if r_ is not None else 'n/a'):>8} "
            f"model-market Brier {(f'{g:+.4f}' if g is not None else 'n/a'):>8}")


def report(sport: str, *, proxy: bool, days_before: int, thin: int) -> dict:
    rows = _rows_for(sport)
    exh = exhaustion_days() if proxy else set()
    lo, hi, skip = split(rows, proxy=proxy, exh=exh,
                         days_before=days_before, thin=thin)

    lo_name = "EXHAUSTED" if proxy else f"THIN (<{thin})"
    hi_name = "CLEAN" if proxy else f"WIDE (>={thin})"

    print(f"\n=== {sport.upper()} — {'exhaustion-day proxy' if proxy else 'book width'} ===")
    if proxy:
        print(f"exhaustion days on record: {len(exh)}   "
              f"window: game day{f' or up to {days_before}d before' if days_before else ''}")
        print("PROXY, and a weak one: an exhaustion line dates the SCAN, not the "
              "book behind any one edge.")
    print(f"settled {sport.upper()} rows: {len(rows)}")
    print(f"  {lo_name:14} {_fmt(lo)}")
    print(f"  {hi_name:14} {_fmt(hi)}")
    if skip:
        why = "no parseable game date" if proxy else "no n_books recorded"
        print(f"  {'excluded':14} n={len(skip):4} ({why})")

    out = {"sport": sport, "mode": "proxy" if proxy else "n_books",
           "n": len(rows), "n_low": len(lo), "n_high": len(hi),
           "n_excluded": len(skip)}

    if lo and hi:
        print(f"\nDIFFERENCE ({lo_name} - {hi_name}), 95% bootstrap CI:")
        for label, stat, pct in (("ROI", roi, True), ("Brier gap", brier_gap, False)):
            a, b = stat(lo), stat(hi)
            ci = bootstrap_diff(lo, hi, stat)
            if a is None or b is None or ci is None:
                print(f"  {label:10} n/a")
                continue
            d = a - b
            f = (lambda v: f"{v:+.1%}") if pct else (lambda v: f"{v:+.4f}")
            verdict = "EXCLUDES 0" if (ci[0] > 0) == (ci[1] > 0) else "straddles 0"
            print(f"  {label:10} {f(d):>9}   CI [{f(ci[0])}, {f(ci[1])}]   {verdict}")
            out[label.lower().replace(" ", "_")] = {
                "diff": d, "ci": list(ci), "significant": verdict == "EXCLUDES 0"}

    # Per-month, because a pooled difference that flips sign is not a finding.
    bym = collections.defaultdict(lambda: {"lo": [], "hi": []})
    for r in lo + hi:
        if r["date"]:
            bym[r["date"].strftime("%Y-%m")]["lo" if r in lo else "hi"].append(r)
    if bym:
        print(f"\nPER MONTH — does the sign hold? (Simpson's-paradox check)")
        print(f"  {'month':9}{lo_name:>13} n{'':>4}{hi_name:>13} n")
        flips = 0
        for m in sorted(bym):
            a, b = roi(bym[m]["lo"]), roi(bym[m]["hi"])
            if a is not None and b is not None and (a - b > 0):
                flips += 1
            print(f"  {m:9} {(f'{a:+.1%}' if a is not None else '-'):>12} "
                  f"{len(bym[m]['lo']):4} {(f'{b:+.1%}' if b is not None else '-'):>12} "
                  f"{len(bym[m]['hi']):4}")
        both = [m for m in bym if roi(bym[m]["lo"]) is not None
                and roi(bym[m]["hi"]) is not None]
        if both:
            print(f"\n  {lo_name} worse in {len(both) - flips}/{len(both)} months, "
                  f"better in {flips}/{len(both)}.")
            out["months_compared"] = len(both)
            out["months_low_worse"] = len(both) - flips
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S20b book-width / quota-starvation check.")
    ap.add_argument("--sport", default="mlb", help="mlb, nba, nhl, ... (default mlb)")
    ap.add_argument("--proxy", action="store_true",
                    help="Use Odds-API exhaustion days instead of recorded n_books.")
    ap.add_argument("--days-before", type=int, default=1,
                    help="Proxy window: also count exhaustion N days before the game (default 1).")
    ap.add_argument("--thin", type=int, default=5,
                    help="n_books below this counts as thin (default 5).")
    ap.add_argument("--json", action="store_true", help="Emit the summary as JSON.")
    a = ap.parse_args(argv)

    out = report(a.sport, proxy=a.proxy, days_before=a.days_before, thin=a.thin)
    if a.json:
        print("\n" + json.dumps(out, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
