"""
betting_analysis.py — Comprehensive post-hoc betting performance report.

Reads `data/history/kalshi_settlements.json` and produces a detailed markdown
report of every settled bet in a rolling window, plus slice-by-slice breakdowns
(sport, category, side, edge bucket, confidence, price bucket, calibration,
streaks, volume).

Usage:
    python scripts/kalshi/betting_analysis.py                       # 30d to stdout
    python scripts/kalshi/betting_analysis.py --days 14             # 14d to stdout
    python scripts/kalshi/betting_analysis.py --days 30 --save      # write to reports/Performance/
    python scripts/kalshi/betting_analysis.py --days 30 --out path  # write to specific path
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import paths  # noqa: F401
from dotenv import load_dotenv
from ticker_display import bet_type_from_ticker, parse_matchup, sport_from_ticker

load_dotenv()


SETTLEMENTS_PATH = Path("data/history/kalshi_settlements.json")
DEFAULT_OUT_DIR = Path("reports/Performance")


# ── Data loading ─────────────────────────────────────────────────────────────

def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def load_settlements(path: Path, days: int, now: datetime | None = None) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Settlements file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    out = []
    for row in data:
        ts_raw = row.get("settled_at")
        if not ts_raw:
            continue
        ts = _parse_iso(ts_raw)
        if ts >= cutoff:
            enriched = dict(row)
            enriched["_ts"] = ts
            out.append(enriched)
    out.sort(key=lambda r: r["_ts"])
    return out


# ── Helpers ──────────────────────────────────────────────────────────────────

def _pct(n: float, d: float) -> float:
    return (n / d * 100.0) if d else 0.0


def _fmt_pct(n: float, d: float, decimals: int = 1) -> str:
    if not d:
        return "—"
    return f"{n / d * 100.0:.{decimals}f}%"


def _fmt_money(x: float) -> str:
    sign = "-" if x < 0 else ""
    return f"{sign}${abs(x):.2f}"


def _fmt_roi(pnl: float, cost: float) -> str:
    if not cost:
        return "—"
    return f"{pnl / cost * 100:+.1f}%"


def _edge_bucket(edge: float | None) -> str:
    if edge is None:
        return "n/a"
    if edge < 0.05:
        return "< 5%"
    if edge < 0.10:
        return "5–10%"
    if edge < 0.15:
        return "10–15%"
    if edge < 0.20:
        return "15–20%"
    if edge < 0.25:
        return "20–25%"
    return "≥ 25%"


_EDGE_BUCKET_ORDER = ["< 5%", "5–10%", "10–15%", "15–20%", "20–25%", "≥ 25%", "n/a"]


def _price_bucket(price: float | None) -> str:
    """Buckets on market price at entry (cost side).

    Longshot shorthand: 15¢ ≈ 5.67:1, 10¢ = 9:1, 5¢ = 19:1.
    """
    if price is None:
        return "n/a"
    if price < 0.05:
        return "< 5¢ (≥ 19:1)"
    if price < 0.10:
        return "5–10¢ (9:1–19:1)"
    if price < 0.15:
        return "10–15¢ (5.67:1–9:1)"
    if price < 0.25:
        return "15–25¢ (3:1–5.67:1)"
    if price < 0.40:
        return "25–40¢"
    if price < 0.60:
        return "40–60¢ (coinflip)"
    if price < 0.75:
        return "60–75¢ (favorite)"
    if price < 0.90:
        return "75–90¢ (heavy fav)"
    return "≥ 90¢ (locks)"


_PRICE_BUCKET_ORDER = [
    "< 5¢ (≥ 19:1)",
    "5–10¢ (9:1–19:1)",
    "10–15¢ (5.67:1–9:1)",
    "15–25¢ (3:1–5.67:1)",
    "25–40¢",
    "40–60¢ (coinflip)",
    "60–75¢ (favorite)",
    "75–90¢ (heavy fav)",
    "≥ 90¢ (locks)",
    "n/a",
]


def _fv_bucket(fv: float | None) -> str:
    """Predicted-probability buckets for calibration curve."""
    if fv is None:
        return "n/a"
    if fv < 0.10:
        return "0–10%"
    if fv < 0.20:
        return "10–20%"
    if fv < 0.30:
        return "20–30%"
    if fv < 0.40:
        return "30–40%"
    if fv < 0.50:
        return "40–50%"
    if fv < 0.60:
        return "50–60%"
    if fv < 0.70:
        return "60–70%"
    if fv < 0.80:
        return "70–80%"
    if fv < 0.90:
        return "80–90%"
    return "90–100%"


_FV_BUCKET_ORDER = [
    "0–10%", "10–20%", "20–30%", "30–40%", "40–50%",
    "50–60%", "60–70%", "70–80%", "80–90%", "90–100%", "n/a",
]


def _confidence_rank(c: str | None) -> int:
    return {"low": 0, "medium": 1, "high": 2}.get((c or "").lower(), -1)


# ── Metric aggregation ───────────────────────────────────────────────────────

@dataclass
class SliceStats:
    count: int = 0
    wins: int = 0
    losses: int = 0
    cost: float = 0.0
    pnl: float = 0.0
    edges: list[float] = None  # type: ignore[assignment]
    fvs: list[float] = None  # type: ignore[assignment]
    outcomes: list[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.edges is None:
            self.edges = []
        if self.fvs is None:
            self.fvs = []
        if self.outcomes is None:
            self.outcomes = []

    def add(self, row: dict) -> None:
        self.count += 1
        won = bool(row.get("won"))
        if won:
            self.wins += 1
        else:
            self.losses += 1
        self.cost += float(row.get("cost") or 0.0)
        self.pnl += float(row.get("net_pnl") or 0.0)
        if row.get("edge_estimated") is not None:
            self.edges.append(float(row["edge_estimated"]))
        if row.get("fair_value") is not None:
            self.fvs.append(float(row["fair_value"]))
            self.outcomes.append(1 if won else 0)

    @property
    def win_rate(self) -> float:
        return _pct(self.wins, self.count)

    @property
    def roi(self) -> float:
        return _pct(self.pnl, self.cost)

    @property
    def avg_edge(self) -> float | None:
        return statistics.mean(self.edges) if self.edges else None

    @property
    def avg_fv(self) -> float | None:
        return statistics.mean(self.fvs) if self.fvs else None

    @property
    def brier(self) -> float | None:
        if not self.outcomes:
            return None
        return sum((p - o) ** 2 for p, o in zip(self.fvs, self.outcomes)) / len(self.outcomes)


def _bucket(rows: Iterable[dict], key_fn) -> dict[str, SliceStats]:
    out: dict[str, SliceStats] = defaultdict(SliceStats)
    for r in rows:
        out[key_fn(r)].add(r)
    return out


# ── Streak math ──────────────────────────────────────────────────────────────

def _streaks(rows: list[dict]) -> tuple[str, int, int, int]:
    """Return (current_streak_str, current_len, longest_win, longest_loss)."""
    if not rows:
        return ("—", 0, 0, 0)
    ordered = sorted(rows, key=lambda r: r["_ts"])
    longest_w = longest_l = 0
    cur_w = cur_l = 0
    for r in ordered:
        if r.get("won"):
            cur_w += 1
            cur_l = 0
            longest_w = max(longest_w, cur_w)
        else:
            cur_l += 1
            cur_w = 0
            longest_l = max(longest_l, cur_l)
    last = ordered[-1]
    if last.get("won"):
        current = f"W{cur_w}"
        cur_len = cur_w
    else:
        current = f"L{cur_l}"
        cur_len = cur_l
    return current, cur_len, longest_w, longest_l


# ── Report rendering ─────────────────────────────────────────────────────────

def _write(lines: list[str], s: str = "") -> None:
    lines.append(s)


def _render_headline(rows: list[dict], days: int, now: datetime) -> list[str]:
    lines: list[str] = []
    total = SliceStats()
    for r in rows:
        total.add(r)
    bets_per_day = total.count / days if days else 0
    _write(lines, f"# Betting Analysis — Last {days} Days")
    _write(lines)
    _write(lines, f"*Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}*")
    _write(lines, f"*Window: {(now - timedelta(days=days)).strftime('%Y-%m-%d')} → {now.strftime('%Y-%m-%d')}*")
    _write(lines, f"*Source: `{SETTLEMENTS_PATH}` ({total.count} settled bets)*")
    _write(lines)
    _write(lines, "## Headline")
    _write(lines)
    _write(lines, "| Metric | Value |")
    _write(lines, "|---|---|")
    _write(lines, f"| Bets settled | {total.count} |")
    _write(lines, f"| Record | {total.wins}W–{total.losses}L |")
    _write(lines, f"| Win rate | {total.win_rate:.1f}% |")
    _write(lines, f"| Total cost | {_fmt_money(total.cost)} |")
    _write(lines, f"| Net P&L | {_fmt_money(total.pnl)} |")
    _write(lines, f"| ROI | {total.roi:+.1f}% |")
    _write(lines, f"| Avg bet size | {_fmt_money(total.cost / total.count) if total.count else '—'} |")
    _write(lines, f"| Pace | {bets_per_day:.1f} bets/day |")
    if total.brier is not None:
        _write(lines, f"| Brier score | {total.brier:.4f} *(0.25 = coin-flip; lower is better)* |")
    if total.avg_edge is not None:
        _write(lines, f"| Avg claimed edge | {total.avg_edge * 100:.1f}% |")
    if total.avg_fv is not None:
        _write(lines, f"| Avg predicted prob | {total.avg_fv * 100:.1f}% |")
    _write(lines)
    return lines


def _render_slice_table(title: str, buckets: dict[str, SliceStats], order: list[str] | None = None,
                        extra_cols: bool = False) -> list[str]:
    lines: list[str] = []
    _write(lines, f"## {title}")
    _write(lines)
    header = "| Slice | N | W–L | WR% | Cost | P&L | ROI |"
    sep = "|---|---:|---|---:|---:|---:|---:|"
    if extra_cols:
        header = "| Slice | N | W–L | WR% | Claimed WR% | Gap | Cost | P&L | ROI |"
        sep = "|---|---:|---|---:|---:|---:|---:|---:|---:|"
    _write(lines, header)
    _write(lines, sep)
    keys = order if order is not None else sorted(buckets.keys(), key=lambda k: -buckets[k].pnl)
    for k in keys:
        s = buckets.get(k)
        if not s or s.count == 0:
            continue
        row = f"| {k} | {s.count} | {s.wins}–{s.losses} | {s.win_rate:.1f}% |"
        if extra_cols:
            if s.avg_fv is not None:
                claimed = s.avg_fv * 100
                gap = s.win_rate - claimed
                row += f" {claimed:.1f}% | {gap:+.1f} |"
            else:
                row += " — | — |"
        row += f" {_fmt_money(s.cost)} | {_fmt_money(s.pnl)} | {s.roi:+.1f}% |"
        _write(lines, row)
    _write(lines)
    return lines


def _render_ledger(rows: list[dict]) -> list[str]:
    lines: list[str] = []
    _write(lines, "## Trade Ledger")
    _write(lines)
    _write(lines,
           "| Date | Sport | Type | Matchup | Side | N | Cost | Price | Edge | Conf | Result | P&L | ROI |")
    _write(lines,
           "|---|---|---|---|---|---:|---:|---:|---:|---|---|---:|---:|")
    for r in rows:
        date = r["_ts"].strftime("%m-%d")
        sport = sport_from_ticker(r.get("ticker", "")) or "—"
        btype = bet_type_from_ticker(r.get("ticker", "")) or "—"
        matchup = parse_matchup(r.get("ticker", "")) or r.get("ticker", "")[:20]
        side = (r.get("side") or "").upper()
        n = r.get("contracts") or 0
        cost = float(r.get("cost") or 0.0)
        price = r.get("market_price_at_entry")
        edge = r.get("edge_estimated")
        conf = (r.get("confidence") or "—").title()
        result = "WIN" if r.get("won") else "LOSS"
        pnl = float(r.get("net_pnl") or 0.0)
        price_str = f"{price * 100:.0f}¢" if price is not None else "—"
        edge_str = f"{edge * 100:+.1f}%" if edge is not None else "—"
        _write(lines,
               f"| {date} | {sport} | {btype} | {matchup} | {side} | {n} | "
               f"{_fmt_money(cost)} | {price_str} | {edge_str} | {conf} | "
               f"{result} | {_fmt_money(pnl)} | {_fmt_roi(pnl, cost)} |")
    _write(lines)
    return lines


def _render_longshot(rows: list[dict]) -> list[str]:
    """Longshot detail — market price < 15¢ (≈ 5.67:1 or longer)."""
    lines: list[str] = []
    longshots = [r for r in rows
                 if r.get("market_price_at_entry") is not None
                 and float(r["market_price_at_entry"]) < 0.15]
    _write(lines, "## Longshots (Market Price < 15¢, ≈ 5.67:1+)")
    _write(lines)
    if not longshots:
        _write(lines, "*No longshot bets in window.*")
        _write(lines)
        return lines
    agg = SliceStats()
    for r in longshots:
        agg.add(r)
    _write(lines, f"*{agg.count} bets · {agg.wins}W–{agg.losses}L · "
                  f"WR {agg.win_rate:.1f}% · P&L {_fmt_money(agg.pnl)} · ROI {agg.roi:+.1f}%*")
    _write(lines)
    _write(lines, "| Date | Sport | Matchup | Side | Price | Edge | Fair | Result | P&L |")
    _write(lines, "|---|---|---|---|---:|---:|---:|---|---:|")
    for r in sorted(longshots, key=lambda x: x["_ts"]):
        date = r["_ts"].strftime("%m-%d")
        sport = sport_from_ticker(r.get("ticker", "")) or "—"
        matchup = parse_matchup(r.get("ticker", "")) or r.get("ticker", "")[:20]
        side = (r.get("side") or "").upper()
        price = r.get("market_price_at_entry")
        edge = r.get("edge_estimated")
        fv = r.get("fair_value")
        result = "WIN" if r.get("won") else "LOSS"
        pnl = float(r.get("net_pnl") or 0.0)
        _write(lines,
               f"| {date} | {sport} | {matchup} | {side} | "
               f"{price * 100:.0f}¢ | "
               f"{edge * 100:+.1f}% | {fv * 100:.0f}% | "
               f"{result} | {_fmt_money(pnl)} |")
    _write(lines)
    return lines


def _render_streaks(rows: list[dict]) -> list[str]:
    lines: list[str] = []
    current, cur_len, lw, ll = _streaks(rows)
    _write(lines, "## Streaks")
    _write(lines)
    _write(lines, "| Metric | Value |")
    _write(lines, "|---|---|")
    _write(lines, f"| Current streak | {current} |")
    _write(lines, f"| Longest win streak | {lw} |")
    _write(lines, f"| Longest loss streak | {ll} |")
    _write(lines)
    return lines


def _render_daily_pnl(rows: list[dict]) -> list[str]:
    lines: list[str] = []
    by_day: dict[str, SliceStats] = defaultdict(SliceStats)
    for r in rows:
        key = r["_ts"].strftime("%Y-%m-%d")
        by_day[key].add(r)
    _write(lines, "## Daily P&L")
    _write(lines)
    _write(lines, "| Date | N | W–L | WR% | Cost | P&L | ROI |")
    _write(lines, "|---|---:|---|---:|---:|---:|---:|")
    running = 0.0
    for day in sorted(by_day.keys()):
        s = by_day[day]
        running += s.pnl
        _write(lines,
               f"| {day} | {s.count} | {s.wins}–{s.losses} | {s.win_rate:.1f}% | "
               f"{_fmt_money(s.cost)} | {_fmt_money(s.pnl)} | {s.roi:+.1f}% |")
    _write(lines)
    _write(lines, f"*Running total matches headline P&L: {_fmt_money(running)}*")
    _write(lines)
    return lines


# ── Main renderer ────────────────────────────────────────────────────────────

def build_report(rows: list[dict], days: int, now: datetime) -> str:
    if not rows:
        return (f"# Betting Analysis — Last {days} Days\n\n"
                f"*No settled bets in the last {days} days.*\n")

    sections: list[str] = []

    sections.append("\n".join(_render_headline(rows, days, now)))

    by_sport = _bucket(rows, lambda r: sport_from_ticker(r.get("ticker", "")) or "Unknown")
    sections.append("\n".join(_render_slice_table("By Sport", by_sport)))

    by_cat = _bucket(rows, lambda r: bet_type_from_ticker(r.get("ticker", "")) or "Unknown")
    sections.append("\n".join(_render_slice_table("By Category", by_cat)))

    by_side = _bucket(rows, lambda r: (r.get("side") or "unknown").upper())
    sections.append("\n".join(_render_slice_table("By Side (YES vs NO)", by_side)))

    by_edge = _bucket(rows, lambda r: _edge_bucket(r.get("edge_estimated")))
    sections.append("\n".join(_render_slice_table(
        "By Claimed Edge Bucket", by_edge, order=_EDGE_BUCKET_ORDER)))

    by_conf = _bucket(rows, lambda r: (r.get("confidence") or "n/a").title())
    sections.append("\n".join(_render_slice_table(
        "By Confidence", by_conf, order=["High", "Medium", "Low", "N/A"])))

    by_price = _bucket(rows, lambda r: _price_bucket(r.get("market_price_at_entry")))
    sections.append("\n".join(_render_slice_table(
        "By Market Price at Entry", by_price, order=_PRICE_BUCKET_ORDER)))

    by_fv = _bucket(rows, lambda r: _fv_bucket(r.get("fair_value")))
    sections.append("\n".join(_render_slice_table(
        "Calibration (Predicted Probability vs Realized Win Rate)",
        by_fv, order=_FV_BUCKET_ORDER, extra_cols=True)))

    sections.append("\n".join(_render_longshot(rows)))
    sections.append("\n".join(_render_streaks(rows)))
    sections.append("\n".join(_render_daily_pnl(rows)))
    sections.append("\n".join(_render_ledger(rows)))

    return "\n".join(sections) + "\n"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=30,
                    help="Lookback window in days (default: 30)")
    ap.add_argument("--save", action="store_true",
                    help=f"Save to {DEFAULT_OUT_DIR}/betting_analysis_YYYY-MM-DD_Nd.md")
    ap.add_argument("--out", type=Path, default=None,
                    help="Explicit output path (overrides --save default)")
    ap.add_argument("--settlements", type=Path, default=SETTLEMENTS_PATH,
                    help=f"Path to settlements JSON (default: {SETTLEMENTS_PATH})")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    now = datetime.now(timezone.utc)
    rows = load_settlements(args.settlements, args.days, now=now)
    report = build_report(rows, args.days, now)

    out_path: Path | None = args.out
    if args.save and not out_path:
        DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = DEFAULT_OUT_DIR / f"betting_analysis_{now.strftime('%Y-%m-%d')}_{args.days}d.md"

    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"Wrote {out_path}")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
