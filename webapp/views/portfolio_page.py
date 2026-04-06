"""Portfolio page — balance, positions, P&L, risk status."""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import get_client, get_portfolio_data, format_positions_for_display
from theme import page_header, metric_row, section_label, CYAN, GREEN, RED, AMBER


def render():
    page_header("Portfolio", "Live positions, balance, and risk status")

    if st.button("REFRESH", type="primary"):
        st.session_state.pop("portfolio_data", None)

    # Fetch or use cached data
    if "portfolio_data" not in st.session_state:
        with st.spinner("Fetching portfolio data..."):
            try:
                client = get_client()
                st.session_state.portfolio_data = get_portfolio_data(client)
            except Exception as e:
                st.error(f"Failed to fetch portfolio: {e}")
                return

    data = st.session_state.portfolio_data
    pnl = data["daily_pnl"]

    # ── Summary metrics ─────────────────────────────────────────────────
    section_label("Account Summary")

    pnl_color = GREEN if pnl >= 0 else RED
    metric_row([
        {"label": "Balance", "value": f"${data['balance']:,.2f}", "color": CYAN},
        {"label": "Portfolio Value", "value": f"${data['portfolio_value']:,.2f}"},
        {"label": "Open Positions", "value": f"{data['open_count']}/{data['max_positions']}"},
        {"label": "Today's P&L", "value": f"${pnl:+,.2f}", "color": pnl_color,
         "delta": f"${pnl:+,.2f}"},
    ])

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Daily loss limit progress ───────────────────────────────────────
    limit = data["daily_limit"]
    loss_used = max(0, -pnl)
    pct = min(loss_used / limit, 1.0) if limit > 0 else 0

    st.progress(pct, text=f"Daily loss: ${loss_used:.2f} / ${limit:.2f}")

    if pnl <= -limit:
        st.markdown(f"""
        <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3);
                    border-radius:6px; padding:0.75rem 1rem; margin:0.5rem 0;
                    font-family:JetBrains Mono,monospace; font-size:0.82rem;
                    color:{RED}; font-weight:600; text-align:center;">
            HARD STOP ACTIVE &mdash; No new positions permitted today
        </div>
        """, unsafe_allow_html=True)

    if data["dry_run"]:
        st.markdown(f"""
        <div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.25);
                    border-radius:6px; padding:0.5rem 1rem; margin:0.5rem 0;
                    font-family:JetBrains Mono,monospace; font-size:0.78rem; color:{AMBER};">
            DRY_RUN=true
        </div>
        """, unsafe_allow_html=True)

    # ── Open positions table ────────────────────────────────────────────
    section_label("Open Positions")

    positions = data["positions"]
    if not positions:
        st.markdown(f"""
        <div style="text-align:center; padding:2rem; color:#475569;
                    font-family:JetBrains Mono,monospace; font-size:0.82rem;">
            No open positions
        </div>
        """, unsafe_allow_html=True)
    else:
        rows = format_positions_for_display(positions)
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

    # ── Resting orders ──────────────────────────────────────────────────
    resting = data["resting_orders"]
    if resting:
        section_label(f"Resting Orders ({len(resting)})")
        resting_rows = []
        for o in resting:
            resting_rows.append({
                "Ticker": o.get("ticker", ""),
                "Side": o.get("side", ""),
                "Contracts": o.get("remaining_count", 0),
                "Price": f"${o.get('yes_price', 0) / 100:.2f}" if o.get("yes_price") else "",
                "Created": o.get("created_time", "")[:16],
            })
        st.dataframe(pd.DataFrame(resting_rows), use_container_width=True, hide_index=True)

    # ── Today's trades ──────────────────────────────────────────────────
    today_trades = data["today_trades"]
    if today_trades:
        section_label(f"Today's Trades ({len(today_trades)})")
        trade_rows = []
        for t in today_trades:
            trade_rows.append({
                "Ticker": t.get("ticker", ""),
                "Side": t.get("side", ""),
                "Contracts": t.get("filled_contracts", t.get("contracts", 0)),
                "Cost": f"${t.get('filled_cost', t.get('cost_dollars', 0)):.2f}",
                "Edge": f"+{t.get('edge_estimated', 0):.1%}" if t.get("edge_estimated") else "",
                "Time": t.get("timestamp", "")[:16],
            })
        st.dataframe(pd.DataFrame(trade_rows), use_container_width=True, hide_index=True)
