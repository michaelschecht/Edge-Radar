"""Scan & Execute page — all controls up front, scan to find, preview to size, execute to place."""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Ensure webapp/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import (
    get_client, run_scan, run_execute, opportunities_to_rows,
    SPORT_FILTERS, CATEGORY_OPTIONS, DATE_OPTIONS,
    MIN_EDGE_THRESHOLD, UNIT_SIZE, MAX_PER_EVENT, DRY_RUN,
)
from theme import page_header, section_label, CYAN, AMBER, RED, GREEN, DIM


def render():
    page_header("Scan & Execute", "Find edge, size positions, place orders")

    if DRY_RUN:
        st.markdown(f"""
        <div style="background:rgba(245,158,11,0.08); border:1px solid rgba(245,158,11,0.25);
                    border-radius:6px; padding:0.6rem 1rem; margin-bottom:1rem;
                    font-family:JetBrains Mono,monospace; font-size:0.78rem; color:{AMBER};">
            DRY_RUN=true &mdash; no real orders will be placed
        </div>
        """, unsafe_allow_html=True)

    # ── Scan Filters ────────────────────────────────────────────────────
    section_label("Filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        market_type = st.selectbox("Market Type", ["sports", "futures", "prediction", "polymarket"])
    with col2:
        sport_filter = st.selectbox("Sport Filter", ["(none)"] + SPORT_FILTERS)
    with col3:
        category = st.selectbox("Category", CATEGORY_OPTIONS)
    with col4:
        date = st.selectbox("Date", DATE_OPTIONS)

    # ── Execution Parameters ────────────────────────────────────────────
    section_label("Execution Parameters")

    col5, col6, col7, col8 = st.columns(4)

    with col5:
        min_edge = st.slider("Min Edge %", 1, 20, int(MIN_EDGE_THRESHOLD * 100)) / 100
    with col6:
        top_n = st.number_input("Top N", min_value=1, max_value=50, value=20)
    with col7:
        unit_size = st.number_input("Unit Size ($)", min_value=0.1, value=float(UNIT_SIZE), step=0.5)
    with col8:
        budget_pct = st.number_input("Budget %", min_value=0, max_value=100, value=10,
                                     help="0 = no budget cap")

    col9, col10, col11, col12 = st.columns(4)

    with col9:
        max_bets = st.number_input("Max Bets", min_value=1, max_value=20, value=6)
    with col10:
        min_bets = st.number_input("Min Bets", min_value=0, max_value=20, value=0,
                                   help="0 = no minimum")
    with col11:
        max_per_game = st.number_input("Max Per Game", min_value=1, max_value=5,
                                       value=int(MAX_PER_EVENT))
    with col12:
        exclude_open = st.checkbox("Exclude Open Positions", value=True)

    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)

    # ── Scan button ─────────────────────────────────────────────────────
    if st.button("SCAN MARKETS", type="primary", use_container_width=True):
        with st.spinner("Scanning markets..."):
            try:
                client = get_client()
                opps, console_out = run_scan(
                    client=client,
                    ticker_filter=sport_filter if sport_filter != "(none)" else None,
                    category_filter=category if category != "all" else None,
                    date_filter=date if date != "all dates" else None,
                    min_edge=min_edge,
                    top_n=top_n,
                    exclude_open=exclude_open,
                )
                st.session_state.scan_results = opps
                st.session_state.scan_console = console_out
                st.session_state.scan_market_type = market_type
                st.session_state.exec_params = {
                    "unit_size": unit_size,
                    "max_bets": max_bets,
                    "min_bets": min_bets if min_bets > 0 else None,
                    "budget": budget_pct if budget_pct > 0 else None,
                    "max_per_game": max_per_game,
                }
                st.session_state.pop("preview_orders", None)
                st.session_state.pop("preview_console", None)
                st.session_state.pop("execute_orders", None)
                st.session_state.pop("execute_console", None)
            except Exception as e:
                st.error(f"Scan failed: {e}")
                return

        if not opps:
            st.warning("No opportunities found above edge threshold.")
        else:
            st.success(f"Found {len(opps)} opportunities")

        if console_out.strip():
            with st.expander("Raw console output"):
                st.code(console_out)

    # ── Results table ───────────────────────────────────────────────────
    opps = st.session_state.get("scan_results", [])
    if not opps:
        return

    section_label(f"Results &mdash; {len(opps)} opportunities")

    rows = opportunities_to_rows(opps)
    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "#": st.column_config.NumberColumn(width="small"),
            "Sport": st.column_config.TextColumn(width="small"),
            "Type": st.column_config.TextColumn(width="small"),
            "Price": st.column_config.TextColumn(width="small"),
            "Fair": st.column_config.TextColumn(width="small"),
            "Edge": st.column_config.TextColumn(width="small"),
            "Conf": st.column_config.TextColumn(width="small"),
            "Score": st.column_config.TextColumn(width="small"),
        }
    )

    # ── Pick rows + Preview/Execute ─────────────────────────────────────
    section_label("Order Selection")

    pick_options = [f"{r['#']}. {r['Sport']} — {r['Bet']} ({r['Edge']})" for r in rows]
    selected = st.multiselect("Select picks (leave empty for auto-ranked top N)", pick_options)

    pick_indices = None
    if selected:
        pick_indices = [pick_options.index(s) for s in selected]

    bcol1, bcol2 = st.columns(2)

    with bcol1:
        if st.button("PREVIEW", use_container_width=True):
            _run_pipeline(opps, pick_indices, execute=False)

    with bcol2:
        if st.button("EXECUTE", type="primary", use_container_width=True):
            _run_pipeline(opps, pick_indices, execute=True)

    # ── Show results ────────────────────────────────────────────────────
    if "preview_orders" in st.session_state:
        _display_orders(st.session_state["preview_orders"],
                        st.session_state.get("preview_console", ""),
                        is_preview=True)

    if "execute_orders" in st.session_state:
        _display_orders(st.session_state["execute_orders"],
                        st.session_state.get("execute_console", ""),
                        is_preview=False)


def _run_pipeline(opps, pick_indices, execute):
    """Run the execution pipeline in preview or live mode."""
    params = st.session_state.get("exec_params", {})
    label = "Executing orders..." if execute else "Running preview..."

    with st.spinner(label):
        try:
            client = get_client()
            sized_orders, console_out = run_execute(
                client=client,
                opportunities=opps,
                unit_size=params.get("unit_size", UNIT_SIZE),
                max_bets=params.get("max_bets", 5),
                min_bets=params.get("min_bets"),
                budget=params.get("budget"),
                max_per_game=params.get("max_per_game"),
                pick_indices=pick_indices,
                execute=execute,
            )
        except Exception as e:
            st.error(f"{'Execution' if execute else 'Preview'} failed: {e}")
            return

    if execute:
        st.session_state["execute_orders"] = sized_orders or []
        st.session_state["execute_console"] = console_out
        st.session_state.pop("preview_orders", None)
    else:
        st.session_state["preview_orders"] = sized_orders or []
        st.session_state["preview_console"] = console_out


def _display_orders(sized_orders, console_out, is_preview):
    """Display sized order results."""
    color = CYAN if is_preview else GREEN
    label = "PREVIEW" if is_preview else "EXECUTION RESULT"

    section_label(label)

    if console_out.strip():
        with st.expander("Pipeline output", expanded=True):
            st.code(console_out)

    if sized_orders:
        order_rows = []
        for s in sized_orders:
            opp = s.opportunity if hasattr(s, "opportunity") else s.get("opportunity", {})
            if hasattr(s, "contracts"):
                order_rows.append({
                    "Ticker": opp.ticker if hasattr(opp, "ticker") else opp.get("ticker", ""),
                    "Side": opp.side if hasattr(opp, "side") else opp.get("side", ""),
                    "Contracts": s.contracts,
                    "Price": f"${s.price_cents / 100:.2f}",
                    "Cost": f"${s.cost_dollars:.2f}",
                    "Edge": f"+{opp.edge:.1%}" if hasattr(opp, "edge") else "",
                    "Status": s.risk_approval,
                })
        if order_rows:
            total_cost = sum(s.cost_dollars for s in sized_orders if hasattr(s, "cost_dollars"))
            st.dataframe(pd.DataFrame(order_rows), use_container_width=True, hide_index=True)
            st.markdown(
                f'<p style="font-family:JetBrains Mono,monospace; font-size:0.82rem; '
                f'color:{color}; text-align:right;">Total cost: ${total_cost:.2f}</p>',
                unsafe_allow_html=True
            )
    else:
        st.warning("No orders passed risk checks.")
