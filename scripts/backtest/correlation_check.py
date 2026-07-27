#!/usr/bin/env python3
"""Measure intra-cluster outcome correlation in the settled trade history.

Motivation (2026-07-27): the C11 sizing work raised the question of whether
same-night / same-league / same-direction bets — e.g. four MLB "under 13 runs"
totals on one evening — resolve together often enough to justify damping their
combined size beyond what `batch_size` division already does.

The naive answer is yes and it is wrong. Pooling every cluster against a single
global win rate reports rho ~ +0.18, but clusters live inside strata with very
different base rates (totals win ~82% of the time, spreads ~24%), and pooling
groups with unequal means manufactures apparent within-group concordance. That
is Simpson's paradox, not correlation.

This script reports both numbers so the artifact is visible:

  * POOLED     — every cluster judged against one global win rate (inflated)
  * STRATIFIED — every cluster judged against its own (series, type, side)
                 base rate, with a permutation test that shuffles outcomes
                 *within* stratum so the null preserves those base rates

Use the stratified number. Re-run as settlements accumulate; the 2026-07-27
reading was rho ~ +0.05 (concordance gap +0.024, permutation p = 0.036) over
243 clustered bets, which is too weak to justify correlation-based damping.

Usage:
    python scripts/backtest/correlation_check.py
    python scripts/backtest/correlation_check.py --since 2026-06-01
    python scripts/backtest/correlation_check.py --category total
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
from pathlib import Path

# Kalshi tickers look like KXMLBTOTAL-26JUL271910ATLNYM-13. Group 1 is the
# sport/series stem, group 2 the market type when present, group 3 the date.
_TICKER_RE = re.compile(r"^([A-Z0-9]+?)(GAME|TOTAL|SPREAD)?-(\d{2}[A-Z]{3}\d{2})")

_DEFAULT_PATH = Path("data/history/kalshi_settlements.json")
_PERMUTATIONS = 4000


def _parse(ticker: str) -> tuple[str, str, str] | None:
    m = _TICKER_RE.match(ticker or "")
    if not m:
        return None
    return m.group(1), m.group(2) or "", m.group(3)


def _clusters(rows: list[dict]) -> dict[tuple, list[bool]]:
    """Group settled bets by (series, market type, date, side)."""
    out: dict[tuple, list[bool]] = collections.defaultdict(list)
    for r in rows:
        parsed = _parse(r.get("ticker") or "")
        if not parsed:
            continue
        out[(*parsed, r.get("side"))].append(bool(r.get("won")))
    return {k: v for k, v in out.items() if len(v) >= 2}


def _concordance(groups) -> tuple[int, int]:
    conc = disc = 0
    for v in groups:
        for i in range(len(v)):
            for j in range(i + 1, len(v)):
                if v[i] == v[j]:
                    conc += 1
                else:
                    disc += 1
    return conc, disc


def _rho(observed: float, expected: float, p: float) -> float:
    """Back out the pairwise correlation implied by a concordance gap.

    For two Bernoulli(p) draws with correlation rho,
        P(same) = p^2 + (1-p)^2 + 2*rho*p*(1-p)
    """
    denom = 2 * p * (1 - p)
    return (observed - expected) / denom if denom else 0.0


def analyze(rows: list[dict], seed: int = 11) -> dict:
    rng = random.Random(seed)
    multi = _clusters(rows)
    if not multi:
        return {}

    conc, disc = _concordance(multi.values())
    observed = conc / (conc + disc)

    flat = [b for v in multi.values() for b in v]
    p_global = sum(flat) / len(flat)
    pooled_expected = p_global**2 + (1 - p_global) ** 2

    # Stratum = the thing that owns a base rate: series + market type + side.
    strata: dict[tuple, list[bool]] = collections.defaultdict(list)
    for k, v in multi.items():
        strata[(k[0], k[1], k[3])].extend(v)
    rates = {k: sum(v) / len(v) for k, v in strata.items()}

    exp_sum = 0.0
    n_pairs = 0
    for k, v in multi.items():
        p = rates[(k[0], k[1], k[3])]
        pairs = len(v) * (len(v) - 1) // 2
        exp_sum += pairs * (p**2 + (1 - p) ** 2)
        n_pairs += pairs
    strat_expected = exp_sum / n_pairs if n_pairs else 0.0

    # Permutation null: reshuffle outcomes *inside* each stratum, so the null
    # keeps each stratum's base rate and only destroys cluster membership.
    sizes = [(k, len(v)) for k, v in multi.items()]
    hits = 0
    for _ in range(_PERMUTATIONS):
        pools = {s: rng.sample(v, len(v)) for s, v in strata.items()}
        idx: dict[tuple, int] = collections.defaultdict(int)
        groups = []
        for k, n in sizes:
            s = (k[0], k[1], k[3])
            start = idx[s]
            groups.append(pools[s][start:start + n])
            idx[s] = start + n
        c, d = _concordance(groups)
        if c + d and c / (c + d) >= observed:
            hits += 1

    return {
        "clusters": len(multi),
        "bets": len(flat),
        "win_rate": p_global,
        "observed": observed,
        "pooled_expected": pooled_expected,
        "pooled_rho": _rho(observed, pooled_expected, p_global),
        "strat_expected": strat_expected,
        "strat_rho": _rho(observed, strat_expected, p_global),
        "perm_p": hits / _PERMUTATIONS,
        "sizes": dict(sorted(collections.Counter(len(v) for v in multi.values()).items())),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--path", type=Path, default=_DEFAULT_PATH,
                    help=f"settlements JSON (default {_DEFAULT_PATH})")
    ap.add_argument("--since", help="only settlements on/after this YYYY-MM-DD")
    ap.add_argument("--category", help="restrict to one category (total|spread|game|...)")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()

    if not args.path.exists():
        print(f"No settlements file at {args.path}")
        return 1

    rows = json.loads(args.path.read_text(encoding="utf-8"))
    if args.since:
        rows = [r for r in rows if (r.get("settled_at") or "")[:10] >= args.since]
    if args.category:
        rows = [r for r in rows if r.get("category") == args.category]

    def show(label: str, subset: list[dict]) -> None:
        s = analyze(subset, seed=args.seed)
        if not s:
            print(f"{label:24} no clusters with >= 2 bets")
            return
        print(f"{label:24} clusters={s['clusters']:>3}  bets={s['bets']:>4}  "
              f"WR={s['win_rate']:.3f}  concordance={s['observed']:.3f}")
        print(f"{'':24}   pooled     expected {s['pooled_expected']:.3f}  "
              f"-> rho {s['pooled_rho']:+.3f}   (inflated; ignore)")
        print(f"{'':24}   stratified expected {s['strat_expected']:.3f}  "
              f"-> rho {s['strat_rho']:+.3f}   perm p={s['perm_p']:.4f}")
        print(f"{'':24}   cluster sizes {s['sizes']}")

    print(f"Intra-cluster correlation — {len(rows)} settled bets"
          + (f" since {args.since}" if args.since else ""))
    print("Cluster = same (series, market type, date, side).\n")
    show("ALL", rows)
    if not args.category:
        for cat in ("total", "spread", "game"):
            subset = [r for r in rows if r.get("category") == cat]
            if subset:
                print()
                show(f"  {cat}", subset)
    print("\nUse the STRATIFIED rho. The pooled figure mixes strata with"
          "\ndifferent base rates and reports correlation that isn't there.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
