"""Settle & Report page — settle completed markets and view P&L reports."""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import get_client, run_settle, run_report, get_settlement_history
from theme import page_header, section_label, CYAN, GREEN, RED, AMBER


_CLOUD_NOTICE = """
<div style="background:rgba(100,116,139,0.08); border:1px solid rgba(100,116,139,0.2);
            border-radius:6px; padding:0.8rem 1rem; margin-bottom:1rem;
            font-family:JetBrains Mono,monospace; font-size:0.78rem; color:#94a3b8;">
    <b>Cloud note:</b> Settlement history and P&amp;L reports rely on local trade logs
    that don&rsquo;t persist on Streamlit Cloud. Settle will run against the Kalshi API,
    but history resets on app reboot. For full reporting, use the local dashboard or CLI.
</div>
"""


def _is_cloud() -> bool:
    """Detect Streamlit Cloud environment."""
    import os
    return os.path.exists("/mount/src")


def render():
    page_header("Settle & Report", "Close out completed markets and review performance")

    if _is_cloud():
        st.markdown(_CLOUD_NOTICE, unsafe_allow_html=True)

    # ── Settle ──────────────────────────────────────────────────────────
    section_label("Settle Completed Markets")

    st.markdown("""
    <p style="color:#64748b; font-size:0.78rem; margin-bottom:1rem;">
        Polls the Kalshi API for settled markets and updates the trade log with outcomes and realized P&amp;L.
    </p>
    """, unsafe_allow_html=True)

    if st.button("SETTLE", type="primary"):
        with st.spinner("Settling trades..."):
            try:
                client = get_client()
                result, console_out = run_settle(client)
            except Exception as e:
                st.error(f"Settlement failed: {e}")
                return

        settled = result.get("settled", 0)
        still_open = result.get("still_open", 0)

        if settled > 0:
            st.success(f"Settled {settled} trades. {still_open} still open.")
            st.toast(f"Settled {settled} trades", icon="\u2705")
        else:
            st.info(f"No new settlements. {still_open} trades still open.")
            st.toast("No new settlements", icon="\u2139\ufe0f")

        if console_out.strip():
            if st.button("Show settle log", key="toggle_settle_log"):
                import re
                clean = re.sub(r'\x1b\[[0-9;]*m', '', console_out)
                st.code(clean)

    # ── Settlement History ──────────────────────────────────────────────
    section_label("Settlement History")

    settlements = get_settlement_history(limit=50)

    if not settlements:
        st.markdown("""
        <div style="text-align:center; padding:2rem; color:#475569;
                    font-family:JetBrains Mono,monospace; font-size:0.82rem;">
            No settlements yet. Run settle after markets close.
        </div>
        """, unsafe_allow_html=True)
    else:
        rows = []
        for s in settlements:
            ticker = s.get("ticker", "")
            won = s.get("won", False)
            net_pnl = s.get("net_pnl", 0)
            rows.append({
                "Result": "W" if won else "L",
                "Ticker": ticker,
                "Side": (s.get("side") or "").upper(),
                "Contracts": s.get("contracts", 0),
                "Cost": f"${s.get('cost', 0):.2f}",
                "Revenue": f"${s.get('revenue', 0):.2f}",
                "P&L": f"${net_pnl:+.2f}",
                "ROI": f"{s.get('roi', 0):+.0%}" if s.get("roi") is not None else "",
                "Edge": f"+{s.get('edge_estimated', 0):.1%}" if s.get("edge_estimated") else "",
                "Settled": (s.get("settled_at") or "")[:10],
            })

        df = pd.DataFrame(rows)

        st.dataframe(df, use_container_width=True, hide_index=True)

        # Summary line
        total_pnl = sum(s.get("net_pnl", 0) for s in settlements)
        wins = sum(1 for s in settlements if s.get("won"))
        losses = len(settlements) - wins
        pnl_color = GREEN if total_pnl >= 0 else RED

        scol1, scol2 = st.columns([4, 1])
        with scol1:
            st.markdown(
                f'<div style="font-family:JetBrains Mono,monospace; font-size:0.78rem; '
                f'padding:0.25rem 0.5rem;">'
                f'{len(settlements)} settled · '
                f'<span style="color:{GREEN};">{wins}W</span> · '
                f'<span style="color:{RED};">{losses}L</span> · '
                f'<span style="color:{pnl_color}; font-weight:600;">'
                f'${total_pnl:+,.2f}</span></div>',
                unsafe_allow_html=True,
            )
        with scol2:
            st.download_button(
                "Export CSV",
                df.to_csv(index=False),
                file_name="edge_radar_settlements.csv",
                mime="text/csv",
            )

    # ── Report ──────────────────────────────────────────────────────────
    section_label("P&L Report")

    rcol1, rcol2 = st.columns(2)
    with rcol1:
        days_option = st.selectbox("Time Range", ["All time", "Last 7 days", "Last 30 days"])
    with rcol2:
        detail = st.checkbox("Show per-trade detail", value=False)

    days_map = {"All time": None, "Last 7 days": 7, "Last 30 days": 30}
    days = days_map[days_option]

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    if st.button("GENERATE REPORT", use_container_width=True):
        with st.spinner("Generating report..."):
            try:
                md_content, console_out = run_report(detail=detail, days=days)
            except Exception as e:
                st.error(f"Report failed: {e}")
                return

        if md_content.strip():
            st.markdown(md_content)
            st.download_button(
                "Export Report",
                md_content,
                file_name="edge_radar_pnl_report.md",
                mime="text/markdown",
            )
        else:
            st.info("No report data available. Run settle first if you have completed trades.")
