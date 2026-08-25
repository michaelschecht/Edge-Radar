"""
calibration_study.py -- does the model know anything the market doesn't?

Every risk knob in this repo (per-sport edge floors, R7, R28, C11, the sport
stdevs) tunes *how much* to bet on the model's claimed edge. None of them ask the
prior question: **is the claimed edge real?** This script asks it directly, against
settled outcomes.

The core comparison, per settled bet, all in *bet-side* probability space:

    p_model   -- what the edge detector said (`fair_value`)
    p_market  -- what Kalshi charged        (`market_price_at_entry`, the ask)
    y         -- what happened              (`won`)

If the model carries information the price does not, it should beat the price on
Brier score, and its claimed edge should predict outcomes *within* a market-price
band. If it does not, the "edge" is estimation noise and the gates are selecting
the upper tail of the model's own error distribution -- a winner's curse, where
realised outcomes land near the market price no matter what the model claimed.

**The selection caveat, stated once and never forgotten:** we only observe bets the
gates approved, i.e. where `p_model > p_market + floor`. That truncation biases
*both* series high, so the absolute errors below overstate how wrong each source
is on the full market population. It does NOT bias the *comparison* between them,
nor the within-band test (`information_test`), which is the load-bearing result.

Usage:
    python scripts/backtest/calibration_study.py
    python scripts/backtest/calibration_study.py --category spread --min-n 20
    python scripts/backtest/calibration_study.py --save
"""

from __future__ import annotations

import argparse
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import paths  # noqa: F401 -- configures sys.path
from trade_log import load_settlement_log

# ── Ticker -> sport / category, for the pre-R5 cohort ────────────────────────
# 178 of 390 settled rows predate R5 and carry no `category` field, so derive it
# from the ticker rather than dropping 45% of the sample.

_SPORTS = ("NFL", "NBA", "NHL", "MLB", "MLS", "WC", "NCAAMB", "NCAAF",
           "ATP", "WTA", "UFC", "SOCCER", "EPL", "UCL")
_BET_TYPES = ("SPREAD", "TOTAL", "GAME")


def parse_ticker(ticker: str) -> tuple[str, str]:
    """(sport, category) from a Kalshi ticker prefix. ('other', 'other') if unknown."""
    head = (ticker or "").split("-", 1)[0].upper()
    if not head.startswith("KX"):
        return "other", "other"
    body = head[2:]
    sport = next((s for s in sorted(_SPORTS, key=len, reverse=True)
                  if body.startswith(s)), "other")
    bet = next((b for b in _BET_TYPES if body.endswith(b)), None)
    category = {"GAME": "game", "SPREAD": "spread", "TOTAL": "total"}.get(bet, "other")
    return sport.lower(), category


def load_rows(settlements: list[dict] | None = None) -> list[dict]:
    """Settled bets with both a model probability and a market price, bet-side."""
    if settlements is None:
        settlements = load_settlement_log()
    out = []
    for s in settlements:
        fv, mp = s.get("fair_value"), s.get("market_price_at_entry")
        if fv is None or mp is None:
            continue
        try:
            p_model, p_market = float(fv), float(mp)
        except (TypeError, ValueError):
            continue
        if not (0.0 < p_model < 1.0 and 0.0 < p_market < 1.0):
            continue
        sport, cat_from_ticker = parse_ticker(s.get("ticker", ""))
        out.append({
            "ticker": s.get("ticker", ""),
            "sport": sport,
            # `category` is absent on the pre-R5 cohort; fall back to the ticker.
            "category": s.get("category") or cat_from_ticker,
            "side": s.get("side"),
            "confidence": s.get("confidence"),
            "p_model": p_model,
            "p_market": p_market,
            "edge": p_model - p_market,
            "y": 1.0 if s.get("won") else 0.0,
            "settled_at": s.get("settled_at", ""),
        })
    return out


# ── Scoring ──────────────────────────────────────────────────────────────────

def brier(ps: list[float], ys: list[float]) -> float:
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ps)


def log_loss(ps: list[float], ys: list[float], eps: float = 1e-6) -> float:
    import math
    total = 0.0
    for p, y in zip(ps, ys):
        p = min(1 - eps, max(eps, p))
        total -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return total / len(ps)


def best_lambda(rows: list[dict], grid: int = 101) -> tuple[float, float]:
    """Shrinkage weight on the model, fitted by Brier score.

        p_blend = p_market + lam * (p_model - p_market)

    lam=0 ignores the model entirely and just trusts the price; lam=1 is the
    model as shipped. The Brier-minimising lam is how much of the claimed edge
    the settled outcomes actually support. Values below ~0.3 mean most of the
    claimed edge is noise; a negative lam means the edge points the wrong way.
    """
    ys = [r["y"] for r in rows]
    best, best_score = 0.0, None
    for i in range(grid):
        lam = -0.5 + 2.0 * i / (grid - 1)          # scan [-0.5, 1.5]
        ps = [r["p_market"] + lam * r["edge"] for r in rows]
        ps = [min(0.999, max(0.001, p)) for p in ps]
        sc = brier(ps, ys)
        if best_score is None or sc < best_score:
            best, best_score = lam, sc
    return best, best_score


def bootstrap_ci(rows: list[dict], stat, n_boot: int = 2000,
                 seed: int = 12345) -> tuple[float, float]:
    """Percentile bootstrap 95% CI. n is small here -- always report the interval,
    never the point estimate alone."""
    rng = random.Random(seed)
    vals = []
    for _ in range(n_boot):
        sample = [rows[rng.randrange(len(rows))] for _ in range(len(rows))]
        try:
            vals.append(stat(sample))
        except (ZeroDivisionError, ValueError):
            continue
    if not vals:
        return float("nan"), float("nan")
    vals.sort()
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]


def information_test(rows: list[dict], n_bands: int = 3) -> list[dict]:
    """**The load-bearing test.** Within a narrow market-price band, does a bigger
    claimed edge predict a higher win rate?

    Selection can't explain a positive result here: holding the price roughly
    fixed, the only thing varying is the model's claim. If high-edge bets beat
    low-edge bets at the same price, the model has information. If they don't --
    or if the relationship inverts -- the claimed edge is noise.
    """
    ordered = sorted(rows, key=lambda r: r["p_market"])
    per = max(1, len(ordered) // n_bands)
    out = []
    for b in range(n_bands):
        band = ordered[b * per: (b + 1) * per] if b < n_bands - 1 else ordered[b * per:]
        if len(band) < 8:
            continue
        # Capture the price range BEFORE re-sorting by edge -- otherwise the
        # reported range is whichever rows happen to sit at the ends of the
        # edge-sorted list, which prints nonsense like "0.82-0.57".
        price_range = (band[0]["p_market"], band[-1]["p_market"])
        band = sorted(band, key=lambda r: r["edge"])
        half = len(band) // 2
        lo, hi = band[:half], band[half:]
        out.append({
            "price_range": price_range,
            "n": len(band),
            "lo_edge_mean": statistics.mean(r["edge"] for r in lo),
            "lo_win": statistics.mean(r["y"] for r in lo),
            "hi_edge_mean": statistics.mean(r["edge"] for r in hi),
            "hi_win": statistics.mean(r["y"] for r in hi),
        })
    return out


def summarize(rows: list[dict]) -> dict:
    ys = [r["y"] for r in rows]
    pm = [r["p_model"] for r in rows]
    pk = [r["p_market"] for r in rows]
    lam, lam_brier = best_lambda(rows)
    return {
        "n": len(rows),
        "model_mean": statistics.mean(pm),
        "market_mean": statistics.mean(pk),
        "realised": statistics.mean(ys),
        "model_err": statistics.mean(pm) - statistics.mean(ys),
        "market_err": statistics.mean(pk) - statistics.mean(ys),
        "brier_model": brier(pm, ys),
        "brier_market": brier(pk, ys),
        "logloss_model": log_loss(pm, ys),
        "logloss_market": log_loss(pk, ys),
        "lambda": lam,
        "brier_blend": lam_brier,
    }


# ── Reporting ────────────────────────────────────────────────────────────────

def _fmt_block(label: str, s: dict) -> str:
    verdict = "model better" if s["brier_model"] < s["brier_market"] else "MARKET better"
    return (f"{label:16s} {s['n']:4d} "
            f"{s['model_mean']:7.1%} {s['market_mean']:7.1%} {s['realised']:8.1%} "
            f"{s['model_err']:+8.1%} {s['market_err']:+8.1%} "
            f"{s['brier_model']:7.4f} {s['brier_market']:7.4f} "
            f"{s['lambda']:+6.2f}  {verdict}")


HEADER = (f"{'bucket':16s} {'n':>4} {'model':>7} {'market':>7} {'realised':>8} "
          f"{'mdlErr':>8} {'mktErr':>8} {'BrierM':>7} {'BrierK':>7} {'lambda':>6}")


def render(rows: list[dict], min_n: int = 15) -> str:
    lines: list[str] = []
    add = lines.append
    add("# Edge-Radar Calibration Study")
    add("")
    add(f"{len(rows)} settled bets with both a model probability and a market price, "
        f"{rows[0]['settled_at'][:10]} -> {rows[-1]['settled_at'][:10]}.")
    add("")
    add("All probabilities are bet-side: `p_model` = the detector's fair value for the")
    add("side actually taken, `p_market` = what Kalshi charged for it, `realised` = how")
    add("often that side won. Lower Brier is better. `lambda` is the Brier-optimal")
    add("weight on the model's claimed edge (0 = ignore the model, 1 = the model as")
    add("shipped).")
    add("")
    add("```")
    add(HEADER)
    add("-" * len(HEADER) + "------------------")
    add(_fmt_block("ALL", summarize(rows)))
    add("")
    for cat in ("game", "spread", "total"):
        sub = [r for r in rows if r["category"] == cat]
        if len(sub) >= min_n:
            add(_fmt_block(cat, summarize(sub)))
    add("")
    by_sport: dict[str, list] = defaultdict(list)
    for r in rows:
        by_sport[r["sport"]].append(r)
    for sport, sub in sorted(by_sport.items(), key=lambda kv: -len(kv[1])):
        if len(sub) >= min_n:
            add(_fmt_block(sport, summarize(sub)))
    add("")
    for conf in ("low", "medium", "high"):
        sub = [r for r in rows if (r["confidence"] or "").lower() == conf]
        if len(sub) >= min_n:
            add(_fmt_block("conf=" + conf, summarize(sub)))
    add("```")
    add("")

    # Information test
    add("## Does the claimed edge predict anything, holding price fixed?")
    add("")
    add("Bets split into market-price bands, then each band split at its median")
    add("claimed edge. If the model has information, the high-edge half wins more.")
    add("")
    add("```")
    add(f"{'price band':>16} {'n':>4} {'lo-edge':>9} {'lo win%':>8} "
        f"{'hi-edge':>9} {'hi win%':>8} {'lift':>7}")
    for b in information_test(rows):
        lift = b["hi_win"] - b["lo_win"]
        add(f"{b['price_range'][0]:.2f}-{b['price_range'][1]:.2f}".rjust(16)
            + f" {b['n']:4d} {b['lo_edge_mean']:+9.1%} {b['lo_win']:8.1%} "
              f"{b['hi_edge_mean']:+9.1%} {b['hi_win']:8.1%} {lift:+7.1%}")
    add("```")
    add("")

    # Regime split -- a single pooled number hides a composition change
    add("## By month")
    add("")
    add("A pooled figure hides sports entering and leaving season. Watch for a")
    add("profitable sport's season ending rather than assuming the model decayed.")
    add("")
    add("```")
    add(f"{'month':9s} {'n':>4} {'model':>7} {'market':>7} "
        f"{'realised':>8} {'BrierM':>7} {'BrierK':>7}")
    by_month: dict[str, list] = defaultdict(list)
    for r in rows:
        by_month[r["settled_at"][:7]].append(r)
    for month, sub in sorted(by_month.items()):
        if len(sub) < 5:
            continue
        s = summarize(sub)
        add(f"{month:9s} {s['n']:4d} {s['model_mean']:7.1%} {s['market_mean']:7.1%} "
            f"{s['realised']:8.1%} {s['brier_model']:7.4f} {s['brier_market']:7.4f}")
    add("```")
    add("")

    # Bootstrap on the headline numbers
    lam_ci = bootstrap_ci(rows, lambda rs: best_lambda(rs)[0], n_boot=400)
    diff_ci = bootstrap_ci(
        rows,
        lambda rs: brier([r["p_market"] for r in rs], [r["y"] for r in rs])
        - brier([r["p_model"] for r in rs], [r["y"] for r in rs]),
        n_boot=2000,
    )
    add("## Uncertainty")
    add("")
    add(f"- Brier(market) - Brier(model), 95% CI: "
        f"**[{diff_ci[0]:+.4f}, {diff_ci[1]:+.4f}]** "
        f"(positive = the model is better; an interval spanning 0 means "
        f"the sample cannot tell them apart)")
    add(f"- Optimal lambda, 95% CI: **[{lam_ci[0]:+.2f}, {lam_ci[1]:+.2f}]**")
    add("")
    add("**Selection caveat:** these are only bets the gates approved, i.e. where the")
    add("model already disagreed with the price by more than the edge floor. That")
    add("truncation inflates the absolute error of *both* series, so `mdlErr` and")
    add("`mktErr` overstate how wrong each source is on the full market population.")
    add("It does not bias the model-vs-market comparison, nor the price-band test.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--category", help="restrict to one category")
    ap.add_argument("--sport", help="restrict to one sport")
    ap.add_argument("--min-n", type=int, default=15,
                    help="suppress breakdown rows thinner than this (default 15)")
    ap.add_argument("--save", action="store_true",
                    help="write to reports/Performance/calibration_study_<date>.md")
    args = ap.parse_args(argv)

    rows = load_rows()
    if args.category:
        rows = [r for r in rows if r["category"] == args.category]
    if args.sport:
        rows = [r for r in rows if r["sport"] == args.sport.lower()]
    if len(rows) < 10:
        print(f"Only {len(rows)} usable settled bets -- not enough to calibrate.")
        return 1
    rows.sort(key=lambda r: r["settled_at"])

    out = render(rows, min_n=args.min_n)
    print(out)
    if args.save:
        from datetime import datetime, timezone
        d = Path("reports/Performance")
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"calibration_study_{datetime.now(timezone.utc):%Y-%m-%d}.md"
        p.write_text(out, encoding="utf-8")
        print(f"\nSaved to {p}")
    return 0


def _demo() -> None:
    """Self-check: `python scripts/backtest/calibration_study.py --self-check`."""
    # A model that is exactly right must beat a market that is not, and must
    # earn lambda = 1.
    truth = [0.2, 0.4, 0.6, 0.8] * 25
    rows = [{"p_model": p, "p_market": 0.5, "edge": p - 0.5,
             "y": 1.0 if i % 100 < int(p * 100) else 0.0,
             "category": "game", "sport": "nfl", "confidence": "medium",
             "side": "yes", "ticker": "", "settled_at": ""}
            for i, p in enumerate(truth)]
    s = summarize(rows)
    assert s["brier_model"] < s["brier_market"], s
    assert s["lambda"] > 0.5, s["lambda"]

    # A model that is pure noise around the market must buy no real improvement.
    #
    # Note what is asserted here: NOT that the fitted lambda is near zero. The
    # Brier curve in lambda is very flat when claimed edges are small -- its
    # curvature goes as E[edge^2], which is ~0.013 for +/-20% edges -- so on a
    # few hundred samples the argmin wanders widely (this seed lands at -0.46)
    # purely on sampling noise in the cross term. That is a property of the
    # estimator, not a bug, and it is exactly why `render()` bootstraps a CI
    # around lambda instead of quoting the point estimate. What must hold is
    # that the *gain* from blending is negligible.
    rng = random.Random(7)
    noise = []
    for _ in range(400):
        mk = 0.5
        noise.append({"p_model": mk + rng.uniform(-0.2, 0.2), "p_market": mk,
                      "y": float(rng.random() < mk), "category": "game",
                      "sport": "nfl", "confidence": "medium", "side": "yes",
                      "ticker": "", "settled_at": ""})
    for r in noise:
        r["edge"] = r["p_model"] - r["p_market"]
    ys = [r["y"] for r in noise]
    lam, blended = best_lambda(noise)
    at_zero = brier([r["p_market"] for r in noise], ys)
    assert at_zero - blended < 0.01, (lam, at_zero, blended)
    # ...and the noisy model must not beat the market outright.
    assert brier([r["p_model"] for r in noise], ys) > at_zero

    assert parse_ticker("KXNFLSPREAD-26SEP13BALIND-IND5") == ("nfl", "spread")
    assert parse_ticker("KXMLBGAME-26APR14LAAANYY-NYY") == ("mlb", "game")
    assert parse_ticker("KXWCTOTAL-26JUN10ARGBRA-3") == ("wc", "total")
    assert parse_ticker("garbage") == ("other", "other")
    assert brier([1.0, 0.0], [1.0, 0.0]) == 0.0
    print("calibration_study self-check passed")


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        _demo()
    else:
        raise SystemExit(main())
