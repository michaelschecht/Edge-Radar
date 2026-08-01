#!/usr/bin/env python3
"""Measure whether totals-bet performance depends on extrapolation distance.

Motivation (2026-07-31, T1): the operator noticed MLB "under ~13 runs" bets
being placed far more than anything else. They were 69% of everything bet after
MLB totals coverage landed on 07-20, and the model over-claimed their win rate
by ~26 points (claimed 89.7%, realized 64.3%).

The proposed fix was a **cap on extrapolation distance** — reject a totals bet
whose Kalshi strike sits more than N stdevs from the model's inferred mean, on
the reasoning that past some distance the answer comes from SPORT_TOTAL_STDEV
rather than from anything a sportsbook actually quoted.

This script exists because that fix did not survive measurement, and the result
should stay reproducible rather than live only in a changelog entry. Over 136
settled totals bets the 1.0-1.5 sigma band -- exactly where the MLB bets sit --
was the ONLY profitable bucket (+5.8%), while 0.5-1.0 sigma lost 29.5%. A cap
at 1 sigma would have deleted the best band and kept the worst.

What the data does show is a **uniform over-claim at every distance** (+9 to
+32 points, claimed vs realized), which points at stdev calibration rather than
at distance. That is C8's job, not a new gate.

Extrapolation distance is recovered by inverting the normal CDF from the stored
`fair_value`, since z = (strike - inferred_mean) / stdev is exactly what the
model applied:

    NO  bet: fair_value = Phi(z)      -> z = Phi^-1(fair_value)
    YES bet: fair_value = 1 - Phi(z)  -> z = Phi^-1(1 - fair_value)

Caveat: for MLB/NFL a post-CDF weather adjustment can shift `fair_value` after
the CDF is applied, so z is approximate on those rows. It is exact everywhere
else. Re-run as settlements accumulate.

Usage:
    python scripts/backtest/totals_distance_check.py
    python scripts/backtest/totals_distance_check.py --sport MLB
    python scripts/backtest/totals_distance_check.py --since 2026-07-01
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from scipy.stats import norm, beta
except ImportError:  # pragma: no cover
    print("scipy is required: pip install scipy", file=sys.stderr)
    raise SystemExit(1)

_DEFAULT_PATH = Path("data/history/kalshi_settlements.json")

# Buckets in |z| = stdevs between the Kalshi strike and the inferred mean.
_BUCKETS = [
    (0.0, 0.5, "< 0.5"),
    (0.5, 1.0, "0.5 - 1.0"),
    (1.0, 1.5, "1.0 - 1.5"),
    (1.5, 2.0, "1.5 - 2.0"),
    (2.0, 99.0, "> 2.0"),
]

_SPORTS = ("NCAAB", "NCAAF", "MLB", "NBA", "NHL", "NFL", "MLS", "SOCCER")


def sport_of(ticker: str) -> str:
    up = (ticker or "").upper()
    for s in _SPORTS:
        if s in up:
            return s
    return "other"


def z_of(row: dict) -> float | None:
    """Stdevs between the Kalshi strike and the model's inferred mean."""
    fair = row.get("fair_value")
    if not fair or not 0.0 < fair < 1.0:
        return None
    # fair_value is always the probability of the side actually bet.
    return norm.ppf(fair) if row.get("side") == "no" else norm.ppf(1.0 - fair)


def load(path: Path, since: str | None, sport: str | None) -> list[dict]:
    if not path.exists():
        print(f"No settlement log at {path}", file=sys.stderr)
        raise SystemExit(1)
    rows = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        ticker = r.get("ticker") or ""
        is_total = r.get("category") == "total" or "TOTAL" in ticker.upper()
        if not is_total or not (r.get("cost") or 0) > 0:
            continue
        if since and (r.get("settled_at") or "")[:10] < since:
            continue
        if sport and sport_of(ticker) != sport.upper():
            continue
        if z_of(r) is None:
            continue
        out.append(r)
    return out


def summarize(group: list[dict]) -> dict:
    n = len(group)
    wins = sum(1 for r in group if r.get("won"))
    cost = sum(r.get("cost") or 0.0 for r in group)
    pnl = sum(r.get("net_pnl") or 0.0 for r in group)
    claimed = sum(r.get("fair_value") or 0.0 for r in group) / n
    # Jeffreys-style interval; the point of showing it is that these samples
    # are small enough that most buckets cannot distinguish anything.
    lo = beta.ppf(0.025, wins, n - wins + 1) if wins else 0.0
    hi = beta.ppf(0.975, wins + 1, n - wins) if n - wins else 1.0
    return {
        "n": n, "wins": wins, "wr": wins / n, "ci": (lo, hi),
        "claimed": claimed, "roi": (pnl / cost if cost else 0.0), "pnl": pnl,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--path", default=str(_DEFAULT_PATH))
    ap.add_argument("--since", default=None, help="YYYY-MM-DD settled_at floor")
    ap.add_argument("--sport", default=None, help="e.g. MLB, NHL, SOCCER")
    args = ap.parse_args()

    rows = load(Path(args.path), args.since, args.sport)
    if not rows:
        print("No settled totals bets matched.")
        return 0

    scope = args.sport or "all sports"
    print(f"{len(rows)} settled totals bets ({scope}"
          f"{', since ' + args.since if args.since else ''})")
    print("|z| = stdevs between the Kalshi strike and the model's inferred mean.\n")

    hdr = f"  {'|z| bucket':<12} {'n':>4} {'W-L':>9} {'WR':>5} {'95% CI':>13} {'claimed':>8} {'ROI':>8} {'P&L':>8}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for lo, hi, label in _BUCKETS:
        g = [r for r in rows if lo <= abs(z_of(r)) < hi]
        if not g:
            continue
        s = summarize(g)
        print(f"  {label:<12} {s['n']:>4} {s['wins']:>4}W-{s['n']-s['wins']:<4}"
              f" {s['wr']:>4.0%} [{s['ci'][0]:>4.0%},{s['ci'][1]:>4.0%}]"
              f" {s['claimed']:>8.0%} {s['roi']:>+8.1%} {s['pnl']:>+8.2f}")

    overall = summarize(rows)
    print(f"\n  overall: {overall['wins']}W-{overall['n']-overall['wins']}L  "
          f"claimed {overall['claimed']:.0%} vs realized {overall['wr']:.0%} "
          f"(over-claim {overall['claimed']-overall['wr']:+.0%})  "
          f"ROI {overall['roi']:+.1%}")
    print("\n  A uniform over-claim across ALL buckets is a stdev-calibration")
    print("  signal (C8's job), not a distance signal. Only trust a bucket whose")
    print("  95% CI is narrow enough to exclude the overall rate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
