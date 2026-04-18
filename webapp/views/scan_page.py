"""Scan & Execute page — all controls up front, scan to find, preview to size, execute to place."""

import re
import streamlit as st
import pandas as pd
import sys
from pathlib import Path

# Ensure webapp/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import (
    get_client, run_scan, run_execute, opportunities_to_rows,
    SPORT_FILTERS, CATEGORY_OPTIONS, DATE_OPTIONS,
    MIN_EDGE_THRESHOLD, DRY_RUN,
)
from favorites import save_favorite, delete_favorite, load_favorites
from theme import page_header, section_label, CYAN, AMBER, RED, GREEN, DIM

MARKET_TYPES = ["sports", "futures", "prediction", "polymarket"]
DEFAULT_UNIT_SIZE = 0.50

# Category options per market type
CATEGORIES_BY_TYPE = {
    "sports": ["all", "game", "spread", "total", "player_prop", "esports", "other"],
    "futures": [],
    "prediction": ["all", "crypto", "weather", "spx", "mentions", "companies", "politics"],
    "polymarket": ["all", "crypto", "weather", "spx", "politics", "companies"],
}

# Filter options per market type
FILTERS_BY_TYPE = {
    "sports": ["(none)"] + SPORT_FILTERS,
    "futures": ["(none)", "nba-futures", "nhl-futures", "mlb-futures", "nfl-futures", "pga-futures"],
    "prediction": ["(none)", "crypto", "weather", "spx", "mentions", "companies", "politics"],
    "polymarket": ["(none)", "crypto", "weather", "spx", "politics", "companies"],
}


def _get_defaults() -> dict:
    """Get default values, overridden by quick-scan or favorite if set."""
    defaults = {
        "market_type": "sports",
        "sport_filter": "(none)",
        "category": "all",
        "date": "all dates",
        "min_edge": int(MIN_EDGE_THRESHOLD * 100),
        "top_n": 20,
        "unit_size": DEFAULT_UNIT_SIZE,
        "budget_pct": 10,
        "max_bets": 6,
        "min_bets": 0,
        "exclude_open": True,
        "cross_ref": False,
    }

    # Quick-scan button sets market type
    if "quick_scan_market" in st.session_state:
        defaults["market_type"] = st.session_state.pop("quick_scan_market")

    # Favorite loads all params
    if "favorite_params" in st.session_state:
        fav = st.session_state.pop("favorite_params")
        for key in defaults:
            if key in fav:
                defaults[key] = fav[key]

    return defaults


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

    defaults = _get_defaults()

    # ── Scan Filters ────────────────────────────────────────────────────
    section_label("Filters")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        mt_index = MARKET_TYPES.index(defaults["market_type"]) if defaults["market_type"] in MARKET_TYPES else 0
        market_type = st.selectbox("Market Type", MARKET_TYPES, index=mt_index)

    # Dynamic filter and category options based on market type
    filter_options = FILTERS_BY_TYPE.get(market_type, ["(none)"])
    category_options = CATEGORIES_BY_TYPE.get(market_type, [])

    with col2:
        sf_index = filter_options.index(defaults["sport_filter"]) if defaults["sport_filter"] in filter_options else 0
        sport_filter = st.selectbox("Filter", filter_options, index=sf_index)

    with col3:
        if category_options:
            cat_index = category_options.index(defaults["category"]) if defaults["category"] in category_options else 0
            category = st.selectbox("Category", category_options, index=cat_index)
        else:
            st.selectbox("Category", ["n/a"], disabled=True)
            category = None

    with col4:
        date_index = DATE_OPTIONS.index(defaults["date"]) if defaults["date"] in DATE_OPTIONS else 0
        date = st.selectbox("Date", DATE_OPTIONS, index=date_index)

    # ── Execution Parameters ────────────────────────────────────────────
    section_label("Execution Parameters")

    # Row 1: universal params
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        min_edge = st.slider(
            "Min Edge %", 1, 20, defaults["min_edge"],
            help="Scan-level minimum edge. The executor additionally enforces per-sport floors at gate 3 (NBA 8%, NCAAB 10%) and a 48h series-dedup at gate 7 — bets may be rejected on execute even if they pass this scan filter.",
        ) / 100
    with col6:
        top_n = st.number_input("Top N", min_value=1, max_value=50, value=defaults["top_n"])
    with col7:
        unit_size = st.number_input("Unit Size ($)", min_value=0.1, value=float(defaults["unit_size"]), step=0.5)
    with col8:
        exclude_open = st.checkbox("Exclude Open Positions", value=defaults["exclude_open"])

    # Row 2: conditional params based on market type
    col9, col10, col11, col12 = st.columns(4)

    with col9:
        max_bets = st.number_input("Max Bets", min_value=1, max_value=20, value=defaults["max_bets"])
    with col10:
        min_bets = st.number_input("Min Bets", min_value=0, max_value=20, value=defaults["min_bets"],
                                   help="0 = no minimum")

    # Sports-only params
    if market_type == "sports":
        with col11:
            budget_pct = st.number_input("Budget %", min_value=0, max_value=100, value=defaults["budget_pct"],
                                         help="0 = no budget cap")
    else:
        budget_pct = 0

    # Prediction-only params
    cross_ref = False
    if market_type == "prediction":
        with col11:
            cross_ref = st.checkbox("Cross-Ref Polymarket", value=defaults.get("cross_ref", False))

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Scan + Clear buttons ────────────────────────────────────────────
    btn_col1, btn_col2 = st.columns([4, 1])

    with btn_col2:
        if st.button("CLEAR", use_container_width=True):
            for key in ["scan_results", "scan_console", "scan_market_type", "exec_params",
                        "preview_orders", "preview_console", "execute_orders", "execute_console"]:
                st.session_state.pop(key, None)
            st.rerun()

    with btn_col1:
        scan_clicked = st.button("SCAN MARKETS", type="primary", use_container_width=True)

    # ── Save as favorite (toggle section, no expander) ────────────────
    if "show_favorites" not in st.session_state:
        st.session_state.show_favorites = False

    if st.button("MANAGE FAVORITES", use_container_width=True):
        st.session_state.show_favorites = not st.session_state.show_favorites
        st.rerun()

    if st.session_state.show_favorites:
        section_label("Save Current Config")
        fcol1, fcol2 = st.columns([3, 1])
        with fcol1:
            fav_name = st.text_input("Favorite name", placeholder="e.g. MLB Today", label_visibility="collapsed")
        with fcol2:
            if st.button("Save", use_container_width=True):
                if fav_name.strip():
                    fav_data = {
                        "name": fav_name.strip(),
                        "market_type": market_type,
                        "sport_filter": sport_filter,
                        "category": category or "all",
                        "date": date,
                        "min_edge": int(min_edge * 100),
                        "top_n": top_n,
                        "unit_size": unit_size,
                        "budget_pct": budget_pct,
                        "max_bets": max_bets,
                        "min_bets": min_bets,
                        "exclude_open": exclude_open,
                        "cross_ref": cross_ref,
                    }
                    save_favorite(fav_data)
                    st.success(f"Saved '{fav_name.strip()}'")
                    st.rerun()
                else:
                    st.warning("Enter a name")

        # List existing favorites with delete buttons
        favs = load_favorites()
        if favs:
            section_label("Saved Favorites")
            for fav in favs:
                dcol1, dcol2 = st.columns([4, 1])
                with dcol1:
                    params_str = f"{fav.get('market_type', '')} | {fav.get('sport_filter', '')} | {fav.get('date', '')}"
                    st.caption(f"**{fav['name']}** — {params_str}")
                with dcol2:
                    if st.button("Del", key=f"del_{fav['name']}", use_container_width=True):
                        delete_favorite(fav["name"])
                        st.rerun()

    # ── Run scan ────────────────────────────────────────────────────────
    if scan_clicked:
        with st.spinner("Scanning markets..."):
            try:
                client = get_client()
                opps, console_out = run_scan(
                    client=client,
                    ticker_filter=sport_filter if sport_filter != "(none)" else None,
                    category_filter=category if category and category != "all" else None,
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
            clean = _strip_ansi(console_out)
            if st.button("Show scan log", key="toggle_scan_log"):
                st.code(clean)

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

    st.download_button(
        "Export CSV",
        df.to_csv(index=False),
        file_name="edge_radar_scan.csv",
        mime="text/csv",
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
            # Store what we need in session state so the dialog can access it
            st.session_state["_confirm_opps"] = opps
            st.session_state["_confirm_picks"] = pick_indices
            _show_execute_confirmation()

    # ── Run confirmed execution (after dialog rerun) ─────────────────
    if st.session_state.get("_execute_confirmed"):
        confirmed_opps = st.session_state.pop("_execute_confirmed_opps", [])
        confirmed_picks = st.session_state.pop("_execute_confirmed_picks", None)
        st.session_state.pop("_execute_confirmed", None)
        _run_pipeline(confirmed_opps, confirmed_picks, execute=True)

    # ── Show results ────────────────────────────────────────────────────
    if "preview_orders" in st.session_state:
        _display_orders(st.session_state["preview_orders"],
                        st.session_state.get("preview_console", ""),
                        is_preview=True)

    if "execute_orders" in st.session_state:
        _display_orders(st.session_state["execute_orders"],
                        st.session_state.get("execute_console", ""),
                        is_preview=False)


@st.dialog("Confirm Execution")
def _show_execute_confirmation():
    """Show a confirmation dialog before placing real orders."""
    opps = st.session_state.get("_confirm_opps", [])
    pick_indices = st.session_state.get("_confirm_picks")

    n_picks = len(pick_indices) if pick_indices else len(opps)
    params = st.session_state.get("exec_params", {})
    max_bets = params.get("max_bets", 5)
    unit_size = params.get("unit_size", DEFAULT_UNIT_SIZE)
    n_orders = min(n_picks, max_bets)

    mode_color = AMBER if DRY_RUN else RED
    mode_label = "DRY RUN" if DRY_RUN else "LIVE"

    st.markdown(
        f'<p style="font-family:JetBrains Mono,monospace; font-size:0.95rem; '
        f'color:{mode_color}; font-weight:600; text-align:center; margin-bottom:0.5rem;">'
        f'{mode_label} MODE</p>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""<div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08);
                border-radius:6px; padding:0.8rem 1rem; margin-bottom:1rem;
                font-family:JetBrains Mono,monospace; font-size:0.82rem; color:#e2e8f0;">
            <b>Opportunities:</b> {n_picks} selected<br>
            <b>Max orders:</b> {max_bets}<br>
            <b>Unit size:</b> ${unit_size:.2f}<br>
            <b>Orders to place:</b> up to {n_orders}
        </div>""",
        unsafe_allow_html=True,
    )

    if not DRY_RUN:
        st.markdown(
            f'<p style="font-family:JetBrains Mono,monospace; font-size:0.78rem; '
            f'color:{RED};">This will place real orders with real money.</p>',
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("_confirm_opps", None)
            st.session_state.pop("_confirm_picks", None)
            st.rerun()
    with col2:
        label = "Confirm (Dry Run)" if DRY_RUN else "Confirm & Place Orders"
        if st.button(label, type="primary", use_container_width=True):
            # Set flag so the main page runs the pipeline after rerun
            st.session_state["_execute_confirmed"] = True
            st.session_state["_execute_confirmed_opps"] = opps
            st.session_state["_execute_confirmed_picks"] = pick_indices
            st.session_state.pop("_confirm_opps", None)
            st.session_state.pop("_confirm_picks", None)
            st.rerun()


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
                unit_size=params.get("unit_size", DEFAULT_UNIT_SIZE),
                max_bets=params.get("max_bets", 5),
                min_bets=params.get("min_bets"),
                budget=params.get("budget"),
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
        n = len(sized_orders) if sized_orders else 0
        if n > 0:
            total = sum(s.cost_dollars for s in sized_orders if hasattr(s, "cost_dollars"))
            st.toast(f"Placed {n} orders (${total:.2f})", icon="\u2705")
        else:
            st.toast("No orders passed risk checks", icon="\u26a0\ufe0f")
    else:
        st.session_state["preview_orders"] = sized_orders or []
        st.session_state["preview_console"] = console_out


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes and rich markup from console output."""
    # Remove ANSI escape sequences
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    # Remove rich markup like [bold], [green], [/green], [dim], etc.
    text = re.sub(r'\[/?[a-z0-9; ]+\]', '', text)
    return text


def _extract_pipeline_summary(console_out: str) -> str:
    """Extract the useful summary lines from pipeline console output, skip the table."""
    clean = _strip_ansi(console_out)
    summary_lines = []
    skip = False
    for line in clean.split('\n'):
        stripped = line.strip()
        # Skip the rich table (box-drawing characters)
        if any(c in stripped for c in ['┏', '┃', '┡', '│', '├', '└', '━', '─']):
            skip = True
            continue
        if skip and not stripped:
            skip = False
            continue
        if skip:
            continue
        # Skip lines that are just the table footer hints
        if 'Tip: use --pick' in stripped or 'DRY RUN -- pass --execute' in stripped:
            continue
        if stripped:
            summary_lines.append(stripped)
    return '\n'.join(summary_lines)


def _display_orders(sized_orders, console_out, is_preview):
    """Display sized order results."""
    color = CYAN if is_preview else GREEN
    label = "PREVIEW" if is_preview else "EXECUTION RESULT"

    section_label(label)

    # Show clean pipeline summary (portfolio state, risk checks, budget cap)
    if console_out.strip():
        summary = _extract_pipeline_summary(console_out)
        if summary.strip():
            st.code(summary)

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
