"""
model_calibration.py — Model feedback loop for Edge-Radar.

Analyzes settled trades to identify calibration issues and generate
actionable recommendations for improving the edge detection model.

Compares predicted probabilities (fair values) against realized win rates
across multiple dimensions to surface systematic biases.

Data source: reads `data/history/kalshi_settlements.json` (populated nightly
by `kalshi_settler.py`), the same source `betting_analysis.py` uses.
Previously read `trade_log`, which only captures bets submitted after the
log was introduced — most historical bets were missing. Switched
2026-04-24 per roadmap item R15.

Usage:
    python scripts/kalshi/model_calibration.py              # Full calibration report
    python scripts/kalshi/model_calibration.py --save       # Save as markdown
    python scripts/kalshi/model_calibration.py --days 14    # Last 14 days only
"""

import argparse
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paths  # noqa: F401
from ticker_display import bet_type_from_ticker, sport_from_ticker
from logging_setup import setup_logging

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import print as rprint

load_dotenv()
log = setup_logging("model_calibration")
console = Console()

# Current model parameters (from edge_detector.py) — used for comparison and calibration baseline
CURRENT_MARGIN_STDEV = {
    "basketball_nba": 13.8,
    "basketball_ncaab": 12.1,
    "americanfootball_nfl": 13.5,
    "americanfootball_ncaaf": 15.0,
    "baseball_mlb": 4.025,
    "icehockey_nhl": 2.5,
    "soccer": 1.8,
    "mma": 5.0,
}
CURRENT_TOTAL_STDEV = {
    "basketball_nba": 20.7,
    "basketball_ncaab": 17.6,
    "americanfootball_nfl": 13.0,
    "americanfootball_ncaaf": 14.0,
    "baseball_mlb": 3.45,
    "icehockey_nhl": 2.2,
    "soccer": 1.5,
}

_PREFIX_TO_SPORT_KEY = {
    "KXNBA": "basketball_nba",
    "KXNCAAMB": "basketball_ncaab",
    "KXNCAABB": "basketball_ncaab",
    "KXNFL": "americanfootball_nfl",
    "KXNCAAF": "americanfootball_ncaaf",
    "KXMLB": "baseball_mlb",
    "KXNHL": "icehockey_nhl",
    "KXSOCCER": "soccer",
    "KXMLS": "soccer",
    "KXWC": "soccer",
    "KXUFC": "mma",
}

def get_sport_key(ticker: str) -> str | None:
    """Resolve the internal sport key from ticker prefix."""
    for prefix, key in _PREFIX_TO_SPORT_KEY.items():
        if ticker.startswith(prefix):
            return key
    return None

def save_calibration_stdevs(settled: list[dict]):
    """Calculate and write calibrated sport standard deviations to data/cache/calibration_stdevs.json."""
    calibrated_margin = {}
    calibrated_total = {}
    
    for sport_key, base_stdev in CURRENT_MARGIN_STDEV.items():
        in_group = [
            t for t in settled
            if get_sport_key(t.get("ticker", "")) == sport_key
            and t.get("category") == "spread"
        ]
        if len(in_group) >= 5:
            pred_avg = sum(t.get("fair_value", 0.5) for t in in_group) / len(in_group)
            real_avg = sum(1.0 if t.get("settlement_won") else 0.0 for t in in_group) / len(in_group)
            gap = pred_avg - real_avg
            # We want to increase stdev if gap is positive (overconfident), and decrease it if negative.
            # Clamp the multiplier to [0.8, 1.5]
            multiplier = max(0.8, min(1.5, 1.0 + gap * 1.5))
            calibrated_margin[sport_key] = round(base_stdev * multiplier, 3)
            log.info("Calibrating margin stdev for %s: base=%.2f, gap=%+.1f%%, new=%.2f (n=%d)",
                     sport_key, base_stdev, gap * 100, calibrated_margin[sport_key], len(in_group))
        else:
            calibrated_margin[sport_key] = base_stdev

    for sport_key, base_stdev in CURRENT_TOTAL_STDEV.items():
        in_group = [
            t for t in settled
            if get_sport_key(t.get("ticker", "")) == sport_key
            and t.get("category") == "total"
        ]
        if len(in_group) >= 5:
            pred_avg = sum(t.get("fair_value", 0.5) for t in in_group) / len(in_group)
            real_avg = sum(1.0 if t.get("settlement_won") else 0.0 for t in in_group) / len(in_group)
            gap = pred_avg - real_avg
            multiplier = max(0.8, min(1.5, 1.0 + gap * 1.5))
            calibrated_total[sport_key] = round(base_stdev * multiplier, 3)
            log.info("Calibrating total stdev for %s: base=%.2f, gap=%+.1f%%, new=%.2f (n=%d)",
                     sport_key, base_stdev, gap * 100, calibrated_total[sport_key], len(in_group))
        else:
            calibrated_total[sport_key] = base_stdev

    output_data = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "margin_stdev": calibrated_margin,
        "total_stdev": calibrated_total
    }
    
    cache_dir = Path(paths.PROJECT_ROOT) / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "calibration_stdevs.json"

    # Atomic write: serialize to a temp file in the same directory, then replace.
    # This calibration job runs nightly via the scheduler while live scans and the
    # Streamlit app may be reading the file; an in-place truncate+stream would let a
    # reader see half-written JSON. Path.replace() is atomic on the same filesystem.
    tmp_file = cache_dir / "calibration_stdevs.json.tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    tmp_file.replace(cache_file)
    rprint(f"[green]Calibrated standard deviations written to {cache_file}[/green]")

# Map sport display names back to sport keys
_SPORT_DISPLAY_TO_KEY = {
    "NBA": "basketball_nba", "NCAAB": "basketball_ncaab",
    "NFL": "americanfootball_nfl", "NCAAF": "americanfootball_ncaaf",
    "MLB": "baseball_mlb", "NHL": "icehockey_nhl",
    "Soccer": "soccer", "MLS": "soccer", "UFC": "mma",
}


# ── Data Loader ──────────────────────────────────────────────────────────────

SETTLEMENTS_PATH = paths.PROJECT_ROOT / "data" / "history" / "kalshi_settlements.json"

# Map bet_type_from_ticker display form → internal lowercase category used by
# downstream cross-tab and recommendation logic. "ML" lands on "game" so the
# existing cat_labels map ({"game": "ML", ...}) still resolves.
_BET_TYPE_TO_CATEGORY = {
    "ML": "game",
    "Spread": "spread",
    "Total": "total",
    "Prop": "player_prop",
}


def _load_settled_trades() -> list[dict]:
    """Load settled bets from `kalshi_settlements.json` and normalize field
    names to the shape the rest of this module expects.

    Normalizations:
        cost            → cost_dollars
        won             → settlement_won
        settled_at      → closed_at
        (derived)       → category (from ticker via bet_type_from_ticker)
    """
    if not SETTLEMENTS_PATH.exists():
        return []
    raw = json.loads(SETTLEMENTS_PATH.read_text(encoding="utf-8"))
    trades: list[dict] = []
    for s in raw:
        ticker = s.get("ticker", "")
        bet_type = bet_type_from_ticker(ticker) or ""
        edge_est = s.get("edge_estimated")
        edge_val = float(edge_est) if edge_est is not None else 0.0
        fv = s.get("fair_value")
        fv_val = float(fv) if fv is not None else 0.5
        trades.append({
            **s,
            "cost_dollars": s.get("cost", 0.0),
            "settlement_won": bool(s.get("won")),
            "closed_at": s.get("settled_at"),
            "category": _BET_TYPE_TO_CATEGORY.get(bet_type, bet_type.lower() or "other"),
            "edge_estimated": edge_val,
            "fair_value": fv_val,
        })
    return trades


# ── Analysis Helpers ─────────────────────────────────────────────────────────

def _brier_score(trades: list[dict]) -> float:
    """Brier score: mean squared error of predicted probability vs outcome.

    Lower is better. 0.25 = coin flip baseline.
    """
    if not trades:
        return 0.25
    total = 0.0
    for t in trades:
        predicted = t.get("fair_value", 0.5)
        actual = 1.0 if t.get("settlement_won") else 0.0
        total += (predicted - actual) ** 2
    return total / len(trades)


def _calibration_buckets(trades: list[dict]) -> list[dict]:
    """Group trades by predicted probability and compare to realized win rate.

    Returns list of buckets with predicted range, count, predicted avg, realized avg.
    """
    # Use fair_value as the predicted probability for the chosen side
    # For NO bets, fair_value should already be the NO side probability
    bucket_edges = [0.0, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 1.01]
    buckets = []

    for i in range(len(bucket_edges) - 1):
        lo, hi = bucket_edges[i], bucket_edges[i + 1]
        in_bucket = [t for t in trades if lo <= t.get("fair_value", 0) < hi]
        if not in_bucket:
            continue
        predicted_avg = sum(t.get("fair_value", 0) for t in in_bucket) / len(in_bucket)
        realized_avg = sum(1 for t in in_bucket if t.get("settlement_won")) / len(in_bucket)
        buckets.append({
            "range": f"{lo:.0%}-{hi:.0%}",
            "count": len(in_bucket),
            "predicted": round(predicted_avg, 3),
            "realized": round(realized_avg, 3),
            "gap": round(predicted_avg - realized_avg, 3),
        })
    return buckets


def _edge_bucket_stats(trades: list[dict]) -> list[dict]:
    """Win rate and P&L by estimated edge bucket."""
    bucket_defs = [
        ("3-5%", 0.03, 0.05),
        ("5-10%", 0.05, 0.10),
        ("10-15%", 0.10, 0.15),
        ("15-25%", 0.15, 0.25),
        ("25%+", 0.25, 1.0),
    ]
    results = []
    for name, lo, hi in bucket_defs:
        in_bucket = [t for t in trades if lo <= t.get("edge_estimated", 0) < hi]
        if not in_bucket:
            continue
        wins = sum(1 for t in in_bucket if t.get("settlement_won"))
        pnl = sum(t.get("net_pnl", 0) for t in in_bucket)
        wagered = sum(t.get("cost_dollars", 0) for t in in_bucket)
        avg_edge = sum(t.get("edge_estimated", 0) for t in in_bucket) / len(in_bucket)
        results.append({
            "bucket": name,
            "count": len(in_bucket),
            "wins": wins,
            "wr": round(wins / len(in_bucket), 3),
            "pnl": round(pnl, 2),
            "roi": round(pnl / wagered, 3) if wagered > 0 else 0,
            "avg_edge": round(avg_edge, 3),
        })
    return results


def _dimension_stats(trades: list[dict], key_fn, label: str) -> list[dict]:
    """Generic dimension breakdown: win rate, P&L, avg edge, Brier score."""
    groups: dict[str, list] = {}
    for t in trades:
        k = key_fn(t)
        groups.setdefault(k, []).append(t)

    results = []
    for name, group in sorted(groups.items(), key=lambda x: -len(x[1])):
        wins = sum(1 for t in group if t.get("settlement_won"))
        pnl = sum(t.get("net_pnl", 0) for t in group)
        wagered = sum(t.get("cost_dollars", 0) for t in group)
        avg_edge = sum(t.get("edge_estimated", 0) for t in group) / len(group)
        brier = _brier_score(group)
        results.append({
            "name": name,
            "count": len(group),
            "wins": wins,
            "wr": round(wins / len(group), 3),
            "pnl": round(pnl, 2),
            "roi": round(pnl / wagered, 3) if wagered > 0 else 0,
            "avg_edge": round(avg_edge, 3),
            "brier": round(brier, 4),
        })
    return results


# ── Recommendation Engine ────────────────────────────────────────────────────

def _generate_recommendations(
    settled: list[dict],
    by_category: list[dict],
    by_confidence: list[dict],
    by_sport: list[dict],
    by_edge: list[dict],
    calibration: list[dict],
    by_side: list[dict] | None = None,
) -> list[dict]:
    """Generate prioritized recommendations from the analysis.

    Each recommendation has: priority (1-3), area, finding, action.
    """
    recs = []

    # 1. Confidence inversion check
    conf_map = {c["name"]: c for c in by_confidence}
    if "high" in conf_map and "medium" in conf_map:
        hi = conf_map["high"]
        med = conf_map["medium"]
        if hi["wr"] < med["wr"] and hi["count"] >= 10 and med["count"] >= 10:
            diff = med["wr"] - hi["wr"]
            recs.append({
                "priority": 1,
                "area": "Confidence Signals",
                "finding": (
                    f"High confidence ({hi['wr']:.0%} WR, ${hi['pnl']:+.2f}) "
                    f"underperforms medium ({med['wr']:.0%} WR, ${med['pnl']:+.2f}). "
                    f"R13 (2026-04-24) already made the team-stats/rest/sharp-money "
                    f"bumps one-way (drop on contradicts, no-op on supports), so the "
                    f"bolt-on bumps are no longer inflating this tier — the base "
                    f"'high' rule itself is the remaining suspect."
                ),
                "action": (
                    "Bump removal already shipped as R13 — do NOT re-recommend it. "
                    "The base 'high' tier is now set directly by the >=8 sharp-books + "
                    "tight-consensus rule in edge_detector.py. Investigate that rule: "
                    "Option A: tighten it (require more sharp books or a tighter "
                    "consensus band before granting 'high'). "
                    "Option B: down-rank base-'high' to 'medium' for Kelly sizing so "
                    "the inflated tier no longer draws larger stakes. "
                    "Option C: confirm the gap persists across two more 30-day windows "
                    "before changing anything (small-sample inversions are common)."
                ),
            })

    # 2. Category calibration
    for cat in by_category:
        if cat["count"] < 10:
            continue
        # If claimed edge is way above realized ROI, model is overestimating
        if cat["avg_edge"] > 0.15 and cat["roi"] < 0.05:
            severity = "severely " if cat["avg_edge"] > 0.25 else ""
            recs.append({
                "priority": 1 if cat["roi"] < 0 else 2,
                "area": f"{cat['name']} Model",
                "finding": (
                    f"{cat['name']} claims {cat['avg_edge']:.0%} avg edge but "
                    f"realizes {cat['roi']:+.0%} ROI ({cat['wr']:.0%} WR over {cat['count']} trades). "
                    f"Model is {severity}overestimating edge."
                ),
                "action": _stdev_recommendation(cat["name"], cat["avg_edge"], cat["wr"]),
            })

    # 3. Calibration curve gaps
    for bucket in calibration:
        if bucket["count"] < 5:
            continue
        gap = bucket["gap"]
        if abs(gap) > 0.10:
            direction = "overconfident" if gap > 0 else "underconfident"
            recs.append({
                "priority": 2,
                "area": "Calibration",
                "finding": (
                    f"Predicted {bucket['range']} bucket: model says {bucket['predicted']:.0%}, "
                    f"realized {bucket['realized']:.0%} ({bucket['count']} trades). "
                    f"Model is {direction} by {abs(gap):.0%}."
                ),
                "action": (
                    f"{'Increase' if gap > 0 else 'Decrease'} stdev parameters for markets "
                    f"in this probability range to pull predictions toward 50%."
                ),
            })

    # 4. Edge bucket analysis — are high-edge bets actually better?
    if len(by_edge) >= 2:
        best_bucket = max(by_edge, key=lambda b: b["roi"])
        worst_bucket = min(by_edge, key=lambda b: b["roi"])
        if worst_bucket["avg_edge"] > best_bucket["avg_edge"] and worst_bucket["count"] >= 10:
            recs.append({
                "priority": 2,
                "area": "Edge Estimation",
                "finding": (
                    f"Highest-edge bucket ({worst_bucket['bucket']}, avg {worst_bucket['avg_edge']:.0%}) "
                    f"has worst ROI ({worst_bucket['roi']:+.0%}), while {best_bucket['bucket']} "
                    f"(avg {best_bucket['avg_edge']:.0%}) has best ROI ({best_bucket['roi']:+.0%}). "
                    f"Large edges are systematically overestimated."
                ),
                "action": (
                    "Consider capping maximum trusted edge at 15-20% (soft cap via composite score "
                    "penalty for extreme edges), or increase stdevs to compress edge estimates."
                ),
            })

    # 5. Sport-specific issues
    for sport in by_sport:
        if sport["count"] < 10:
            continue
        if sport["roi"] < -0.10:
            recs.append({
                "priority": 2,
                "area": f"{sport['name']} Performance",
                "finding": (
                    f"{sport['name']}: {sport['count']} trades, {sport['wr']:.0%} WR, "
                    f"{sport['roi']:+.0%} ROI. Losing sport."
                ),
                "action": (
                    f"Review {sport['name']} stdev parameters. Consider raising minimum edge "
                    f"threshold for this sport or reducing its weight in composite score."
                ),
            })

    # 6. YES/NO side asymmetry — analogous trigger to the R1 NO-side guard
    if by_side:
        side_map = {s["name"]: s for s in by_side}
        yes = side_map.get("YES")
        no = side_map.get("NO")
        if yes and no and yes["count"] >= 20 and no["count"] >= 20:
            wr_gap = no["wr"] - yes["wr"]
            roi_gap = no["roi"] - yes["roi"]
            # Flag when one side is winning ≥15pts more often AND the loser has negative ROI
            if abs(wr_gap) >= 0.15 and (yes["roi"] < 0 or no["roi"] < 0):
                worse, better = (yes, no) if wr_gap > 0 else (no, yes)
                recs.append({
                    "priority": 1,
                    "area": "Side Asymmetry (YES vs NO)",
                    "finding": (
                        f"{better['name']} side: {better['count']} bets, {better['wr']:.0%} WR, "
                        f"{better['roi']:+.0%} ROI. {worse['name']} side: {worse['count']} bets, "
                        f"{worse['wr']:.0%} WR, {worse['roi']:+.0%} ROI. "
                        f"{abs(wr_gap):.0%}-pt WR gap, {abs(roi_gap):.0%}-pt ROI gap."
                    ),
                    "action": (
                        f"Investigate why {worse['name']}-side selection is unprofitable. "
                        f"Consider adding a {worse['name']}-side gate analogous to R1's NO-side guard "
                        f"(elevated edge/confidence floor for {worse['name']} bets), or audit the model "
                        f"for systematic bias toward overpriced {worse['name']} contracts."
                    ),
                })

    # 7. Brier score baseline check
    overall_brier = _brier_score(settled)
    if overall_brier > 0.25:
        recs.append({
            "priority": 1,
            "area": "Overall Calibration",
            "finding": (
                f"Overall Brier score {overall_brier:.4f} is worse than coin-flip baseline (0.2500). "
                f"The model's probability estimates are adding noise, not signal."
            ),
            "action": (
                "This suggests stdevs are too low (probabilities too extreme). "
                "Increase all stdev parameters by 10-20% as a starting point."
            ),
        })

    # Sort by priority
    recs.sort(key=lambda r: r["priority"])
    return recs


def _stdev_recommendation(category: str, avg_edge: float, win_rate: float) -> str:
    """Generate a specific stdev recommendation for a category."""
    cat_lower = category.lower()

    if "spread" in cat_lower:
        param = "SPORT_MARGIN_STDEV"
        desc = "spread model"
    elif "total" in cat_lower:
        param = "SPORT_TOTAL_STDEV"
        desc = "total model"
    else:
        param = "fair value consensus"
        desc = "game model"

    # If win rate is well below predicted, stdev is too low
    if win_rate < 0.40 and avg_edge > 0.15:
        pct = "20-30%"
    elif win_rate < 0.45 and avg_edge > 0.10:
        pct = "10-20%"
    else:
        pct = "5-10%"

    return (
        f"Increase {param} values by {pct} for the {desc}. "
        f"This compresses probability estimates toward 50%, reducing phantom edge. "
        f"Current values are in edge_detector.py."
    )


# ── Report Generation ────────────────────────────────────────────────────────

def _parse_iso(ts: str | None) -> datetime | None:
    """Parse an ISO timestamp, tolerating trailing 'Z'."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def generate_calibration_report(days: int | None = None, save: bool = False):
    """Run the full calibration analysis and print recommendations."""
    settled = [t for t in _load_settled_trades() if t.get("closed_at")]

    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        settled = [
            t for t in settled
            if (_parse_iso(t.get("closed_at")) or datetime.min.replace(tzinfo=timezone.utc)) >= cutoff
        ]

    if len(settled) < 10:
        rprint(f"[yellow]Only {len(settled)} settled trades — need at least 10 for calibration.[/yellow]")
        return

    period = f"last {days} days" if days else "all time"
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md: list[str] = []

    rprint(f"\n[bold]Model Calibration Report ({period})[/bold]")
    rprint(f"  Generated: {generated_at}")
    rprint(f"  Settled trades: {len(settled)}")

    md.append(f"# Model Calibration Report ({period})")
    md.append(f"")
    md.append(f"*Generated: {generated_at} | {len(settled)} settled trades*")

    # ── Overall metrics
    wins = sum(1 for t in settled if t.get("settlement_won"))
    total_pnl = sum(t.get("net_pnl", 0) for t in settled)
    total_wagered = sum(t.get("cost_dollars", 0) for t in settled)
    roi = total_pnl / total_wagered if total_wagered > 0 else 0
    avg_edge = sum(t.get("edge_estimated", 0) for t in settled) / len(settled)
    brier = _brier_score(settled)

    rprint(f"\n[bold]Overall[/bold]")
    rprint(f"  Win rate:     {wins}/{len(settled)} ({wins/len(settled):.0%})")
    rprint(f"  ROI:          {roi:+.1%}")
    rprint(f"  Avg est edge: {avg_edge:.1%}")
    rprint(f"  Brier score:  {brier:.4f} ({'better' if brier < 0.25 else 'worse'} than coin flip 0.2500)")

    md.append(f"")
    md.append(f"## Overall")
    md.append(f"")
    md.append(f"| Metric | Value |")
    md.append(f"|--------|-------|")
    md.append(f"| Win rate | {wins}/{len(settled)} ({wins/len(settled):.0%}) |")
    md.append(f"| ROI | {roi:+.1%} |")
    md.append(f"| Avg estimated edge | {avg_edge:.1%} |")
    md.append(f"| Brier score | {brier:.4f} ({'better' if brier < 0.25 else 'worse'} than 0.2500 baseline) |")

    # ── Calibration curve
    calibration = _calibration_buckets(settled)
    if calibration:
        rprint(f"\n[bold]Calibration Curve[/bold]")
        rprint(f"  {'Predicted':>12} {'Count':>6} {'Predicted':>10} {'Realized':>10} {'Gap':>8}")
        md.append(f"")
        md.append(f"## Calibration Curve")
        md.append(f"")
        md.append(f"| Predicted Range | Count | Predicted | Realized | Gap |")
        md.append(f"|-----------------|-------|-----------|----------|-----|")
        for b in calibration:
            gap_color = "red" if abs(b["gap"]) > 0.10 else "dim"
            rprint(f"  {b['range']:>12} {b['count']:>6} {b['predicted']:>10.0%} {b['realized']:>10.0%} [{gap_color}]{b['gap']:>+8.0%}[/{gap_color}]")
            md.append(f"| {b['range']} | {b['count']} | {b['predicted']:.0%} | {b['realized']:.0%} | {b['gap']:+.0%} |")

    # ── By category
    cat_labels = {"game": "ML", "spread": "Spread", "total": "Total", "player_prop": "Prop"}
    by_category = _dimension_stats(
        settled, lambda t: cat_labels.get(t.get("category", ""), t.get("category", "Other")), "Category"
    )
    _print_dimension_table("By Category", by_category, md)

    # ── By confidence
    by_confidence = _dimension_stats(
        settled, lambda t: t.get("confidence", "unknown"), "Confidence"
    )
    _print_dimension_table("By Confidence", by_confidence, md)

    # ── By sport
    by_sport = _dimension_stats(
        settled, lambda t: sport_from_ticker(t.get("ticker", "")) or "Other", "Sport"
    )
    _print_dimension_table("By Sport", by_sport, md)

    # ── By side (YES vs NO)
    by_side = _dimension_stats(
        settled, lambda t: (t.get("side") or "unknown").upper(), "Side"
    )
    _print_dimension_table("By Side", by_side, md)

    # ── By edge bucket
    by_edge = _edge_bucket_stats(settled)
    if by_edge:
        rprint(f"\n[bold]By Edge Bucket[/bold]")
        md.append(f"")
        md.append(f"## By Edge Bucket")
        md.append(f"")
        md.append(f"| Bucket | Trades | WR | P&L | ROI | Avg Edge |")
        md.append(f"|--------|--------|----|-----|-----|----------|")
        for b in by_edge:
            pnl_color = "green" if b["pnl"] >= 0 else "red"
            rprint(
                f"  {b['bucket']:>8}: {b['count']:>3} trades, {b['wr']:.0%} WR, "
                f"[{pnl_color}]${b['pnl']:+.2f}[/{pnl_color}], ROI {b['roi']:+.0%}, avg edge {b['avg_edge']:.0%}"
            )
            md.append(f"| {b['bucket']} | {b['count']} | {b['wr']:.0%} | ${b['pnl']:+.2f} | {b['roi']:+.0%} | {b['avg_edge']:.0%} |")

    # ── Confidence x Category cross-tab
    _print_cross_tab(settled, md)

    # ── Recommendations
    recs = _generate_recommendations(
        settled, by_category, by_confidence, by_sport, by_edge, calibration, by_side
    )
    if recs:
        rprint(f"\n[bold]{'='*60}[/bold]")
        rprint(f"[bold]RECOMMENDATIONS ({len(recs)})[/bold]")
        rprint(f"[bold]{'='*60}[/bold]")
        md.append(f"")
        md.append(f"## Recommendations")
        md.append(f"")

        for i, r in enumerate(recs, 1):
            priority_label = {1: "HIGH", 2: "MEDIUM", 3: "LOW"}[r["priority"]]
            priority_color = {1: "red", 2: "yellow", 3: "dim"}[r["priority"]]
            rprint(f"\n  [{priority_color}][{priority_label}][/{priority_color}] {r['area']}")
            rprint(f"  [dim]Finding:[/dim] {r['finding']}")
            rprint(f"  [bold]Action:[/bold] {r['action']}")

            md.append(f"### {i}. [{priority_label}] {r['area']}")
            md.append(f"")
            md.append(f"**Finding:** {r['finding']}")
            md.append(f"")
            md.append(f"**Action:** {r['action']}")
            md.append(f"")
    else:
        rprint(f"\n[green]No calibration issues detected.[/green]")
        md.append(f"")
        md.append(f"## Recommendations")
        md.append(f"")
        md.append(f"No calibration issues detected.")

    # ── Current model parameters (for reference)
    md.append(f"")
    md.append(f"## Current Model Parameters")
    md.append(f"")
    md.append(f"### Spread Stdev (SPORT_MARGIN_STDEV)")
    md.append(f"")
    md.append(f"| Sport | Current |")
    md.append(f"|-------|---------|")
    for sport, val in sorted(CURRENT_MARGIN_STDEV.items()):
        md.append(f"| {sport} | {val} |")
    md.append(f"")
    md.append(f"### Total Stdev (SPORT_TOTAL_STDEV)")
    md.append(f"")
    md.append(f"| Sport | Current |")
    md.append(f"|-------|---------|")
    for sport, val in sorted(CURRENT_TOTAL_STDEV.items()):
        md.append(f"| {sport} | {val} |")

    md.append(f"")
    md.append(f"---")
    md.append(f"*Generated by Edge-Radar model_calibration.py*")

    if save:
        report_dir = Path(paths.PROJECT_ROOT) / "reports" / "Calibration"
        report_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_path = report_dir / f"{today}_calibration_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md) + "\n")
        rprint(f"\n[dim]Report saved to {report_path}[/dim]")

    # Auto-calibrate standard deviations and save to cache (C8)
    save_calibration_stdevs(settled)


def _print_dimension_table(title: str, data: list[dict], md: list[str]):
    """Print a dimension breakdown table to console and markdown."""
    if not data:
        return
    rprint(f"\n[bold]{title}[/bold]")
    md.append(f"")
    md.append(f"## {title}")
    md.append(f"")
    md.append(f"| {title} | Trades | WR | P&L | ROI | Avg Edge | Brier |")
    md.append(f"|{'-'*len(title)}--|--------|----|----|-----|----------|-------|")

    for d in data:
        pnl_color = "green" if d["pnl"] >= 0 else "red"
        brier_note = " *" if d["brier"] > 0.25 else ""
        rprint(
            f"  {d['name']:>12}: {d['count']:>3} trades, {d['wr']:.0%} WR, "
            f"[{pnl_color}]${d['pnl']:+.2f}[/{pnl_color}], ROI {d['roi']:+.0%}, "
            f"edge {d['avg_edge']:.0%}, Brier {d['brier']:.4f}{brier_note}"
        )
        md.append(
            f"| {d['name']} | {d['count']} | {d['wr']:.0%} | ${d['pnl']:+.2f} | "
            f"{d['roi']:+.0%} | {d['avg_edge']:.0%} | {d['brier']:.4f}{brier_note} |"
        )

    if any(d["brier"] > 0.25 for d in data):
        rprint(f"  [dim]* Brier > 0.2500 = worse than coin flip[/dim]")


def _print_cross_tab(settled: list[dict], md: list[str]):
    """Print confidence x category cross-tab to find where bumps help/hurt."""
    cat_labels = {"game": "ML", "spread": "Spread", "total": "Total"}
    confs = ["medium", "high"]
    cats = ["ML", "Spread", "Total"]

    groups: dict[tuple[str, str], list] = {}
    for t in settled:
        conf = t.get("confidence", "unknown")
        cat = cat_labels.get(t.get("category", ""), "Other")
        if conf in confs and cat in cats:
            groups.setdefault((conf, cat), []).append(t)

    if not groups:
        return

    rprint(f"\n[bold]Confidence x Category[/bold]")
    md.append(f"")
    md.append(f"## Confidence x Category")
    md.append(f"")
    md.append(f"| Confidence | Category | Trades | WR | P&L | ROI |")
    md.append(f"|------------|----------|--------|----|-----|-----|")

    for conf in confs:
        for cat in cats:
            group = groups.get((conf, cat), [])
            if len(group) < 3:
                continue
            wins = sum(1 for t in group if t.get("settlement_won"))
            pnl = sum(t.get("net_pnl", 0) for t in group)
            wagered = sum(t.get("cost_dollars", 0) for t in group)
            roi = pnl / wagered if wagered > 0 else 0
            wr = wins / len(group)
            pnl_color = "green" if pnl >= 0 else "red"
            rprint(
                f"  {conf:>8} x {cat:<8}: {len(group):>3} trades, {wr:.0%} WR, "
                f"[{pnl_color}]${pnl:+.2f}[/{pnl_color}], ROI {roi:+.0%}"
            )
            md.append(
                f"| {conf} | {cat} | {len(group)} | {wr:.0%} | ${pnl:+.2f} | {roi:+.0%} |"
            )


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Model calibration and feedback loop")
    parser.add_argument("--save", action="store_true", help="Save report to reports/Calibration/")
    parser.add_argument("--days", type=int, default=None, help="Only include last N days")
    args = parser.parse_args()

    generate_calibration_report(days=args.days, save=args.save)


if __name__ == "__main__":
    main()
