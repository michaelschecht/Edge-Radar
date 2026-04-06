"""Settle & Report page — settle completed markets and view P&L reports."""

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import get_client, run_settle, run_report
from theme import page_header, section_label, CYAN, GREEN, AMBER


def render():
    page_header("Settle & Report", "Close out completed markets and review performance")

    # ── Settle ──────────────────────────────────────────────────────────
    section_label("Settle Completed Markets")

    st.markdown(f"""
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
        else:
            st.info(f"No new settlements. {still_open} trades still open.")

        if console_out.strip():
            with st.expander("Console output"):
                st.code(console_out)

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
        else:
            st.info("No report data available. Run settle first if you have completed trades.")
