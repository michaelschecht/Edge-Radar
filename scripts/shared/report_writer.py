"""
report_writer.py
Generate markdown scan reports from Opportunity lists.

Used by all scanners when --save is passed.
"""

from datetime import datetime, timezone
from pathlib import Path

from ticker_display import parse_game_datetime, format_bet_label, format_pick_label, sport_from_ticker

# Report directories (relative to project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORT_DIRS = {
    "sports": _PROJECT_ROOT / "reports" / "Sports",
    "futures": _PROJECT_ROOT / "reports" / "Futures",
    "prediction": _PROJECT_ROOT / "reports" / "Predictions",
}


def save_scan_report(
    opportunities: list,
    report_type: str = "sports",
    filter_label: str = "",
    min_edge: float = 0.03,
    output_dir: str | Path | None = None,
) -> Path | None:
    """Save a markdown report from a list of Opportunity objects.

    Args:
        opportunities: List of Opportunity objects (or dicts with same keys)
        report_type: "sports", "futures", or "prediction"
        filter_label: Filter used (e.g., "mlb", "crypto") — appears in filename and header
        min_edge: Minimum edge threshold used in the scan
        output_dir: Override the default report directory (optional)

    Returns:
        Path to the saved report, or None if no opportunities.
    """
    if not opportunities:
        return None

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%I:%M %p UTC")

    # Build filename
    label = f"_{filter_label}" if filter_label else ""
    filename = f"{date_str}{label}_{report_type}_scan.md"

    report_dir = Path(output_dir) if output_dir else REPORT_DIRS.get(report_type, REPORT_DIRS["sports"])
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / filename

    lines = []

    # Header
    type_label = report_type.replace("_", " ").title()
    lines.append(f"# {type_label} Edge Scan{f' — {filter_label.upper()}' if filter_label else ''}")
    lines.append("")
    lines.append(f"*{now.strftime('%A, %B %d, %Y')} | {time_str} | "
                 f"{len(opportunities)} opportunities | min edge: {min_edge:.0%}*")
    lines.append("")

    # Summary by category
    cat_counts: dict[str, int] = {}
    for o in opportunities:
        cat = _get_attr(o, "category", "other")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    if len(cat_counts) > 1:
        lines.append("## Summary")
        lines.append("")
        lines.append("| Category | Count |")
        lines.append("|:---------|------:|")
        for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append(f"| {cat} | {count} |")
        lines.append("")

    # Opportunities table
    lines.append("## Opportunities")
    lines.append("")

    if report_type == "futures":
        lines.append("| # | Bet Type | Candidate | Date | Side | Mkt | Fair | Edge | Conf |")
        lines.append("|--:|:---------|:----------|:-----|:-----|----:|-----:|-----:|:-----|")
        for i, o in enumerate(opportunities, 1):
            details = _get_attr(o, "details", {})
            lines.append(
                f"| {i} "
                f"| {details.get('bet_type', '')[:25]} "
                f"| {details.get('candidate', '')[:20]} "
                f"| {parse_game_datetime(_get_attr(o, 'ticker', ''))} "
                f"| {_get_attr(o, 'side', '').upper()} "
                f"| ${_get_attr(o, 'market_price', 0):.2f} "
                f"| ${_get_attr(o, 'fair_value', 0):.3f} "
                f"| {_get_attr(o, 'edge', 0):+.1%} "
                f"| {_get_attr(o, 'confidence', '')[:3].upper()} |"
            )
    else:
        cat_labels = {
            "game": "ML", "spread": "Spread", "total": "Total",
            "player_prop": "Prop", "esports": "Esports",
        }
        lines.append("| # | Sport | Bet | Type | Pick | When | Mkt | Fair | Edge | Conf | Score |")
        lines.append("|--:|:------|:----|:-----|:-----|:-----|----:|-----:|-----:|:-----|------:|")
        for i, o in enumerate(opportunities, 1):
            ticker = _get_attr(o, "ticker", "")
            title = _get_attr(o, "title", "")
            cat = _get_attr(o, "category", "")
            side = _get_attr(o, "side", "")
            bet = format_bet_label(ticker, title)[:35].replace("|", "/")
            pick = format_pick_label(ticker, title, side, cat).replace("|", "/")
            lines.append(
                f"| {i} "
                f"| {sport_from_ticker(ticker)} "
                f"| {bet} "
                f"| {cat_labels.get(cat, cat.title())} "
                f"| {pick} "
                f"| {parse_game_datetime(ticker)} "
                f"| ${_get_attr(o, 'market_price', 0):.2f} "
                f"| ${_get_attr(o, 'fair_value', 0):.2f} "
                f"| {_get_attr(o, 'edge', 0):+.1%} "
                f"| {_get_attr(o, 'confidence', '')[:3].upper()} "
                f"| {_get_attr(o, 'composite_score', 0):.1f} |"
            )

    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by Edge-Radar*")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return report_path


def save_execution_report(
    sized_orders: list,
    report_type: str = "sports",
    filter_label: str = "",
    min_edge: float = 0.03,
    output_dir: str | None = None,
) -> str | None:
    """Save a markdown report with sized execution data (Sport, Bet, Type, Pick, Qty, Price, Cost, Edge).

    Args:
        sized_orders: List of SizedOrder objects from execute_pipeline.
        report_type: 'sports', 'futures', or 'prediction'.
        filter_label: Sport or category filter used.
        min_edge: Minimum edge threshold used.
        output_dir: Override output directory.
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")

    base_dir = Path(output_dir) if output_dir else REPORT_DIRS.get(report_type, REPORT_DIRS["sports"])
    base_dir.mkdir(parents=True, exist_ok=True)

    label = f"_{filter_label}" if filter_label else ""
    filename = f"{date_str}{label}_{report_type}_execution.md"
    report_path = base_dir / filename

    total_cost = sum(s.cost_dollars for s in sized_orders) if sized_orders else 0

    lines = [
        f"# {report_type.title()} Execution Report",
        "",
        f"*{now.strftime('%A, %B %d, %Y | %I:%M %p UTC')} | {len(sized_orders)} orders | "
        f"total cost: ${total_cost:.2f} | min edge: {min_edge:.0%}*",
        "",
        "## Orders",
        "",
        "| # | Sport | Bet | Type | Pick | When | Qty | Price | Cost | Edge |",
        "|--:|:------|:----|:-----|:-----|:-----|----:|------:|-----:|-----:|",
    ]

    cat_labels = {
        "game": "ML", "spread": "Spread", "total": "Total",
        "player_prop": "Prop", "esports": "Esports",
    }

    for i, s in enumerate(sized_orders, 1):
        opp = s.opportunity
        bet = format_bet_label(opp.ticker, opp.title)[:35].replace("|", "/")
        pick = format_pick_label(opp.ticker, opp.title, opp.side, opp.category).replace("|", "/")
        lines.append(
            f"| {i} "
            f"| {sport_from_ticker(opp.ticker)} "
            f"| {bet} "
            f"| {cat_labels.get(opp.category, opp.category.title())} "
            f"| {pick} "
            f"| {parse_game_datetime(opp.ticker)} "
            f"| {s.contracts} "
            f"| ${s.price_cents / 100:.2f} "
            f"| ${s.cost_dollars:.2f} "
            f"| {opp.edge:+.1%} |"
        )

    lines.append("")
    lines.append(f"**Total cost: ${total_cost:.2f}**")
    lines.append("")
    lines.append("---")
    lines.append(f"*Generated by Edge-Radar*")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return report_path


def _get_attr(obj, key: str, default=None):
    """Get attribute from Opportunity object or dict."""
    if hasattr(obj, key):
        return getattr(obj, key)
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default
