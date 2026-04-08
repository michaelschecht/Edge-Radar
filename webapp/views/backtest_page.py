"""Backtest page — strategy analysis, signal breakdowns, equity curve, simulation."""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "backtest"))

from backtest.backtester import (
    load_trades, filter_trades, BacktestResult, simulate_strategies,
)
from theme import (
    page_header, section_label, metric_row,
    CYAN, GREEN, RED, AMBER, DIM,
)

SPORT_OPTIONS = ["All", "NBA", "NCAAB", "MLB", "NHL", "NFL"]
CATEGORY_OPTIONS = ["All", "game", "spread", "total"]
CONFIDENCE_OPTIONS = ["All", "low", "medium", "high"]


def _is_cloud() -> bool:
    """Detect Streamlit Cloud environment."""
    import os
    return os.path.exists("/mount/src")


def render():
    page_header("Backtest", "Analyze settled trades and compare strategies")

    # ── Load data ──────────────────────────────────────────────────────
    all_trades = load_trades()
    if not all_trades:
        if _is_cloud():
            st.info(
                "Backtesting requires local trade history which doesn't persist on Streamlit Cloud. "
                "Use the local dashboard or CLI for backtest analysis."
            )
        else:
            st.warning("No settled trades found. Run settle first to populate settlement history.")
        return

    st.markdown(
        f'<p style="color:{DIM}; font-size:0.78rem;">'
        f'{len(all_trades)} settled trades loaded</p>',
        unsafe_allow_html=True,
    )

    # ── Filters ────────────────────────────────────────────────────────
    section_label("Filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        sport = st.selectbox("Sport", SPORT_OPTIONS)
    with col2:
        category = st.selectbox("Category", CATEGORY_OPTIONS)
    with col3:
        confidence = st.selectbox("Confidence", CONFIDENCE_OPTIONS)
    with col4:
        min_edge = st.slider("Min Edge %", 0, 30, 0) / 100

    # Apply filters
    trades = filter_trades(
        all_trades,
        sport=sport if sport != "All" else None,
        category=category if category != "All" else None,
        confidence=confidence if confidence != "All" else None,
        min_edge=min_edge if min_edge > 0 else None,
    )

    if not trades:
        st.warning("No trades match the selected filters.")
        return

    if len(trades) < len(all_trades):
        st.markdown(
            f'<p style="color:{DIM}; font-size:0.78rem;">'
            f'Filtered to {len(trades)} trades</p>',
            unsafe_allow_html=True,
        )

    # ── Export filtered trades ─────────────────────────────────────────
    export_rows = []
    for t in trades:
        export_rows.append({
            "Date": t["settled_at"][:10],
            "Sport": t["sport"],
            "Category": t["category"],
            "Ticker": t["ticker"],
            "Side": t.get("side", ""),
            "Result": "W" if t["won"] else "L",
            "Contracts": t.get("contracts", 0),
            "Cost": round(t["cost"], 2),
            "Revenue": round(t.get("revenue", 0), 2),
            "P&L": round(t["net_pnl"], 2),
            "ROI": round(t["roi"], 4),
            "Edge": round(t["edge_estimated"], 4),
            "Fair Value": round(t["fair_value"], 4),
            "Entry Price": round(t["market_price_at_entry"], 4),
            "Confidence": t["confidence"],
        })
    export_df = pd.DataFrame(export_rows)

    st.download_button(
        f"Export {len(trades)} Filtered Trades (CSV)",
        export_df.to_csv(index=False),
        file_name="edge_radar_backtest_trades.csv",
        mime="text/csv",
    )

    # ── Run analysis ───────────────────────────────────────────────────
    result = BacktestResult(trades=trades, label="Filtered").analyze()

    # ── Summary metrics ────────────────────────────────────────────────
    section_label("Performance Summary")

    pnl_color = GREEN if result.net_pnl >= 0 else RED
    roi_color = GREEN if result.roi >= 0 else RED

    metric_row([
        {"label": "Record", "value": f"{result.wins}W-{result.losses}L"},
        {"label": "Win Rate", "value": f"{result.win_rate:.1%}"},
        {"label": "Net P&L", "value": f"${result.net_pnl:+.2f}", "color": pnl_color},
        {"label": "ROI", "value": f"{result.roi:+.1%}", "color": roi_color},
    ])

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    metric_row([
        {"label": "Profit Factor", "value": f"{result.profit_factor:.2f}"},
        {"label": "Sharpe Ratio", "value": f"{result.sharpe_ratio:.2f}"},
        {"label": "Max Drawdown", "value": f"${result.max_drawdown:.2f}"},
        {"label": "Streaks", "value": f"{result.longest_win_streak}W / {result.longest_lose_streak}L"},
    ])

    # ── Breakdowns ─────────────────────────────────────────────────────
    _render_breakdown("By Sport", result.by_sport)
    _render_breakdown("By Category", result.by_category)
    _render_breakdown("By Confidence", result.by_confidence)
    _render_breakdown("By Edge Bucket", result.by_edge_bucket)

    # ── Calibration Curve ──────────────────────────────────────────────
    if result.calibration:
        section_label("Calibration Curve")

        cal_rows = []
        for row in result.calibration:
            cal_rows.append({
                "Bucket": row["bucket"],
                "Count": row["count"],
                "Predicted": f"{row['avg_predicted']:.1%}",
                "Actual": f"{row['actual_win_rate']:.1%}",
                "Gap": f"{row['gap']:+.1%}",
            })
        st.dataframe(pd.DataFrame(cal_rows), use_container_width=True, hide_index=True)

        # Visual: predicted vs actual as a simple bar comparison
        cal_df = pd.DataFrame(result.calibration)
        if len(cal_df) >= 3:
            chart_df = cal_df[["bucket", "avg_predicted", "actual_win_rate"]].copy()
            chart_df.columns = ["Bucket", "Predicted", "Actual"]
            chart_df = chart_df.set_index("Bucket")
            st.bar_chart(chart_df)

    # ── Equity Curve ───────────────────────────────────────────────────
    if result.equity_curve:
        section_label("Equity Curve")

        # Aggregate by date
        daily = {}
        for point in result.equity_curve:
            d = point["date"]
            if d not in daily:
                daily[d] = {"date": d, "day_pnl": 0, "cumulative": 0}
            daily[d]["day_pnl"] += point["pnl"]

        cum = 0.0
        curve_rows = []
        for d in sorted(daily):
            cum += daily[d]["day_pnl"]
            curve_rows.append({
                "Date": d,
                "Day P&L": f"${daily[d]['day_pnl']:+.2f}",
                "Cumulative": f"${cum:+.2f}",
                "cum_val": cum,
            })

        # Chart
        chart_df = pd.DataFrame(curve_rows)
        st.line_chart(chart_df.set_index("Date")["cum_val"], use_container_width=True)

        # Table
        st.dataframe(
            chart_df.drop(columns=["cum_val"]),
            use_container_width=True,
            hide_index=True,
        )

    # ── Strategy Simulation ────────────────────────────────────────────
    section_label("Strategy Simulation")

    if st.button("RUN SIMULATION", type="primary"):
        with st.spinner("Simulating strategies..."):
            strategies = simulate_strategies(all_trades)
            st.session_state["backtest_strategies"] = strategies

    if "backtest_strategies" in st.session_state:
        strategies = st.session_state["backtest_strategies"]
        sim_rows = []
        for s in strategies:
            sim_rows.append({
                "Strategy": s.label,
                "Trades": s.total_trades,
                "Win %": f"{s.win_rate:.0%}",
                "P&L": f"${s.net_pnl:+.2f}",
                "ROI": f"{s.roi:+.1%}",
                "Sharpe": f"{s.sharpe_ratio:.2f}",
                "Max DD": f"${s.max_drawdown:.2f}",
                "PF": f"{s.profit_factor:.2f}",
            })

        sim_df = pd.DataFrame(sim_rows)
        st.dataframe(sim_df, use_container_width=True, hide_index=True)

        # Best strategy callout
        best = max(strategies, key=lambda s: s.roi)
        if best.label != "Baseline (all trades)":
            st.markdown(
                f'<div style="font-family:JetBrains Mono,monospace; font-size:0.82rem; '
                f'color:{GREEN}; padding:0.5rem 0;">'
                f'Best strategy: <b>{best.label}</b> '
                f'(ROI: {best.roi:+.1%}, Sharpe: {best.sharpe_ratio:.2f})</div>',
                unsafe_allow_html=True,
            )

        st.download_button(
            "Export CSV",
            sim_df.to_csv(index=False),
            file_name="edge_radar_strategy_simulation.csv",
            mime="text/csv",
        )


def _render_breakdown(title: str, data: dict):
    """Render a breakdown section as a styled table."""
    if not data:
        return

    section_label(title)

    rows = []
    for name, stats in data.items():
        rows.append({
            "Group": str(name),
            "Trades": stats["trades"],
            "Record": f"{stats['wins']}W-{stats['losses']}L",
            "Win %": f"{stats['win_rate']:.0%}",
            "P&L": f"${stats['pnl']:+.2f}",
            "ROI": f"{stats['roi']:+.1%}",
            "Avg Edge": f"{stats.get('avg_edge', 0):.1%}",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
