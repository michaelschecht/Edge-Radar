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
    venue_for_market_type, polymarket_order_mode, is_executable,
    SPORT_FILTERS, CATEGORY_OPTIONS, DATE_OPTIONS,
    MIN_EDGE_THRESHOLD, DRY_RUN,
)
from ticker_display import (
    sport_from_ticker, format_bet_label, format_pick_label, parse_game_datetime,
)
from favorites import save_favorite, delete_favorite, load_favorites
from theme import page_header, section_label, CYAN, AMBER, RED, GREEN, DIM

MARKET_TYPES = ["sports", "futures", "prediction", "polymarket"]
DEFAULT_UNIT_SIZE = 1.00  # C11 (2026-07-27): matches live .env / scheduler --unit-size 1

# Category options per market type
CATEGORIES_BY_TYPE = {
    "sports": ["all", "game", "spread", "total", "player_prop", "esports", "other"],
    "futures": [],
    "prediction": ["all", "crypto", "weather", "spx", "mentions", "companies", "politics"],
    # Polymarket routes surfaces through --filter, not a separate category.
    "polymarket": [],
}

# Filter options per market type. The Polymarket list mirrors
# `polymarket_futures_edge._route_filter`: bare sport = that championship
# future, `-games` suffix = that sport's game markets, `all` = both surfaces.
FILTERS_BY_TYPE = {
    "sports": ["(none)"] + SPORT_FILTERS,
    "futures": ["(none)", "nba-futures", "nhl-futures", "mlb-futures", "nfl-futures", "pga-futures"],
    "prediction": ["(none)", "crypto", "weather", "spx", "mentions", "companies", "politics"],
    "polymarket": ["(none)", "futures", "mlb", "nfl", "nba", "nhl",
                   "games", "mlb-games", "nfl-games", "nba-games", "nhl-games"],
}

MIN_EDGE_HELP = (
    "Scan-level minimum edge. The executor enforces more on top of it: "
    "per-sport floors at gate 3 (NBA/NCAAB/MLB 4%, others 3%); a market-price "
    "floor at gate 3.5 (MIN_MARKET_PRICE, currently 0.10 — the re-opened "
    "longshot lane); a medium-confidence floor at gate 4.5; the NO-side "
    "favorite guard at 4.6 plus the global 8% NO floor at 4.6b (R28); a "
    "prediction-market gate at 4.7 (crypto/weather/spx/mentions/companies/"
    "politics blocked unless ALLOW_PREDICTION_BETS=true); an in-progress-game "
    "gate at 4.8 (blocked unless ALLOW_LIVE_BETS=true); and series dedup at "
    "gate 7 (48h default, 72h MLB/NHL). The Gate column on each result row "
    "previews which gate, if any, will reject it."
)


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


def _banner(text: str, color: str, bold: bool = False):
    """Status strip above the controls."""
    rgb = {AMBER: "245,158,11", RED: "239,68,68", CYAN: "0,212,170"}.get(color, "100,116,139")
    st.markdown(f"""
    <div style="background:rgba({rgb},0.08); border:1px solid rgba({rgb},0.25);
                border-radius:6px; padding:0.6rem 1rem; margin-bottom:0.5rem;
                font-family:JetBrains Mono,monospace; font-size:0.78rem;
                color:{color};{' font-weight:600;' if bold else ''}">
        {text}
    </div>
    """, unsafe_allow_html=True)


def render():
    page_header("Scan & Execute", "Find edge, size positions, place orders")

    defaults = _get_defaults()

    # Reserved for the mode banners — they depend on the market type chosen
    # below, but belong visually above the controls.
    banner_slot = st.container()

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

    # ── Mode banners (rendered into the slot reserved above) ────────────
    venue = venue_for_market_type(market_type)
    with banner_slot:
        if DRY_RUN:
            _banner("DRY_RUN=true &mdash; no real orders will be placed on any venue", AMBER)

        if venue == "polymarket":
            pm_live, pm_mode = polymarket_order_mode()
            if pm_live:
                # Both flags are false: --execute here spends real money.
                _banner(
                    "POLYMARKET LIVE ORDERS ARMED &mdash; "
                    f"{pm_mode}. Executing places REAL orders on any row that "
                    "clears the gates. Set POLYMARKET_DRY_RUN=true to halt "
                    "this venue without touching Kalshi.",
                    RED, bold=True,
                )
            else:
                _banner(f"Polymarket orders {pm_mode}", AMBER)
            _banner(
                "Only Polymarket <b>US futures</b> are orderable. Game rows come "
                "from international Gamma, carry no US market_slug, and are "
                "excluded from execution automatically &mdash; they are dry-run "
                "evidence only (see the Exec column).",
                DIM,
            )
        elif not DRY_RUN:
            _banner("DRY_RUN=false &mdash; Kalshi orders are LIVE", RED, bold=True)

    # ── Execution Parameters ────────────────────────────────────────────
    section_label("Execution Parameters")

    # Row 1: universal params
    col5, col6, col7, col8 = st.columns(4)

    with col5:
        min_edge = st.slider(
            "Min Edge %", 1, 20, defaults["min_edge"], help=MIN_EDGE_HELP,
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

    # Budget applies to every market type — the executor's cap is venue- and
    # type-neutral, and the schedulers pass --budget on futures and Polymarket
    # runs too (10%). It used to be hidden outside sports, which meant a
    # dashboard futures run was the only path with no batch cap at all.
    with col11:
        budget_pct = st.number_input(
            "Budget %", min_value=0, max_value=100, value=defaults["budget_pct"],
            help="Percent of bankroll as a cap on total batch cost. 0 = no cap. "
                 "C11b: the cap never shaves an order below its flat unit floor; "
                 "if the floors alone don't fit it drops whole orders, lowest "
                 "composite first.",
        )

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # ── Scan + Clear buttons ────────────────────────────────────────────
    btn_col1, btn_col2 = st.columns([4, 1])

    with btn_col2:
        if st.button("CLEAR", use_container_width=True,
                     help="Clear displayed results AND drop the scan-result cache "
                          "so the next scan fetches fresh data from the Odds API."):
            for key in ["scan_results", "scan_console", "scan_market_type", "exec_params",
                        "preview_orders", "preview_console", "execute_orders", "execute_console"]:
                st.session_state.pop(key, None)
            # Also wipe the 60s scan cache so the user can force a refresh
            # (R24a). Otherwise an immediately-following scan would return
            # the same cached rows even though the user asked for a clear.
            run_scan.clear()
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
                client = get_client(venue)
                opps, console_out = run_scan(
                    _client=client,
                    market_type=market_type,
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
                    # Pinned to the scan, not re-read at execute time: the
                    # results in session state belong to the venue that
                    # produced them, even if the selectbox has moved since.
                    "venue": venue,
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

    # ── Scan log (reads from session state so it survives reruns) ────────
    console_saved = st.session_state.get("scan_console", "")
    opps_saved = st.session_state.get("scan_results", [])
    if console_saved.strip():
        clean = _strip_ansi(console_saved)
        # Auto-expand when the scan returned nothing — that's when you need it most
        auto_expand = bool(st.session_state.get("scan_results") is not None and not opps_saved)
        with st.expander("Scan log", expanded=auto_expand):
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
            "Started": st.column_config.TextColumn(width="small"),
            "Price": st.column_config.TextColumn(width="small"),
            "Fair": st.column_config.TextColumn(width="small"),
            "Edge": st.column_config.TextColumn(width="small"),
            "Conf": st.column_config.TextColumn(width="small"),
            "Score": st.column_config.TextColumn(width="small"),
            "Gate": st.column_config.TextColumn(
                width="small",
                help="Risk-gate preflight: 'ok' would pass, otherwise the "
                     "gate that rejects this row. Portfolio-state gates "
                     "(daily loss, position count) are evaluated at execute "
                     "time, so 'ok' is necessary, not sufficient.",
            ),
            "Exec": st.column_config.TextColumn(
                width="small",
                help="Orderable on Polymarket US (has a US market_slug). "
                     "'—' rows are Gamma-sourced games — dry-run evidence "
                     "only, excluded from execution automatically.",
            ),
        }
    )

    n_blocked = sum(1 for o in opps if not is_executable(o))
    if n_blocked:
        st.caption(
            f"{n_blocked} of {len(opps)} rows are not orderable on Polymarket US "
            f"and will be dropped before execution."
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

    params = st.session_state.get("exec_params", {})
    max_bets = params.get("max_bets", 5)
    unit_size = params.get("unit_size", DEFAULT_UNIT_SIZE)
    budget = params.get("budget")
    venue = params.get("venue", "kalshi")

    selected = ([opps[i] for i in pick_indices if i < len(opps)]
                if pick_indices else list(opps))

    # PM2c: state the real orderable count, not the selected count. Selecting
    # five Gamma game rows on Polymarket sends zero orders — a dialog that
    # said "up to 5" would be actively misleading right before a confirm.
    orderable = [o for o in selected if is_executable(o)]
    n_excluded = len(selected) - len(orderable)
    n_orders = min(len(orderable), max_bets)

    # Live means: this confirm spends real money on THIS venue.
    if venue == "polymarket":
        live, mode_detail = polymarket_order_mode()
    else:
        live, mode_detail = (not DRY_RUN), ("DRY_RUN=true" if DRY_RUN else "DRY_RUN=false")

    mode_color = RED if live else AMBER
    mode_label = f"{venue.upper()} — {'LIVE' if live else 'DRY RUN'}"

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
            <b>Venue:</b> {venue} ({mode_detail})<br>
            <b>Opportunities:</b> {len(selected)} selected{
                f' ({n_excluded} not orderable on this venue)' if n_excluded else ''}<br>
            <b>Max orders:</b> {max_bets}<br>
            <b>Unit size:</b> ${unit_size:.2f}<br>
            <b>Budget cap:</b> {f'{budget}% of bankroll' if budget else 'none'}<br>
            <b>Orders to place:</b> up to {n_orders}
        </div>""",
        unsafe_allow_html=True,
    )

    if live:
        st.markdown(
            f'<p style="font-family:JetBrains Mono,monospace; font-size:0.78rem; '
            f'color:{RED};">This will place real orders with real money on '
            f'{venue}.</p>',
            unsafe_allow_html=True,
        )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.pop("_confirm_opps", None)
            st.session_state.pop("_confirm_picks", None)
            st.rerun()
    with col2:
        label = "Confirm & Place Orders" if live else "Confirm (Dry Run)"
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

    venue = params.get("venue", "kalshi")

    with st.spinner(label):
        try:
            client = get_client(venue)
            sized_orders, console_out = run_execute(
                client=client,
                opportunities=opps,
                unit_size=params.get("unit_size", DEFAULT_UNIT_SIZE),
                max_bets=params.get("max_bets", 5),
                min_bets=params.get("min_bets"),
                budget=params.get("budget"),
                pick_indices=pick_indices,
                execute=execute,
                venue=venue,
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
        # Mirror the column set used by the scan-results table
        # (services.opportunities_to_rows) so the user can see matchup names,
        # picks, and game times alongside the sized order — not just the raw
        # ticker. Same helpers as the scan table for label parity.
        cat_labels = {
            "game": "ML", "spread": "Spread", "total": "Total",
            "player_prop": "Prop", "esports": "Esports", "futures": "Futures",
        }
        order_rows = []
        for s in sized_orders:
            opp = s.opportunity if hasattr(s, "opportunity") else s.get("opportunity", {})
            if hasattr(s, "contracts"):
                ticker = opp.ticker if hasattr(opp, "ticker") else opp.get("ticker", "")
                title = opp.title if hasattr(opp, "title") else opp.get("title", "")
                category = opp.category if hasattr(opp, "category") else opp.get("category", "")
                side = opp.side if hasattr(opp, "side") else opp.get("side", "")
                details = (getattr(opp, "details", None)
                           or (opp.get("details") if isinstance(opp, dict) else None) or {})
                # Same split as the scan table: `PM-{slug}` has no Kalshi
                # ticker grammar, so read the labels off `details` instead of
                # parsing noise out of the ticker.
                if details.get("venue") == "polymarket":
                    sport_lbl = details.get("sport") or details.get("bet_type", "Futures")
                    bet_lbl = details.get("bet_type", title)
                    pick_lbl = details.get("candidate", side.upper())
                    when_lbl = (details.get("game_start") or "")[:16]
                else:
                    sport_lbl = sport_from_ticker(ticker)
                    bet_lbl = format_bet_label(ticker, title)
                    pick_lbl = format_pick_label(ticker, title, side, category)
                    when_lbl = parse_game_datetime(ticker)
                order_rows.append({
                    "Ticker": ticker,
                    "Sport": sport_lbl,
                    "Bet": bet_lbl,
                    "Type": cat_labels.get(category, category.title()),
                    "Pick": pick_lbl,
                    "When": when_lbl,
                    "Side": side,
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
