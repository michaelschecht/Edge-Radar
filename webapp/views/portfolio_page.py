"""Portfolio page — balance, positions, P&L, risk status, per venue."""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import (
    get_client, get_portfolio_data, format_positions_for_display,
    format_polymarket_positions_for_display, polymarket_order_mode,
)
from theme import page_header, metric_row, section_label, CYAN, GREEN, RED, AMBER

VENUES = ["kalshi", "polymarket"]


def render():
    page_header("Portfolio", "Live positions, balance, and risk status")

    col1, col2 = st.columns([4, 1])
    with col1:
        auto = st.toggle("Auto-refresh (30s)", value=st.session_state.get("portfolio_auto", False),
                         key="portfolio_auto")
    with col2:
        if st.button("REFRESH", type="primary"):
            for v in VENUES:
                st.session_state.pop(f"portfolio_data_{v}", None)

    if auto:
        _portfolio_content_auto()
    else:
        _portfolio_content()


@st.fragment(run_every=timedelta(seconds=30))
def _portfolio_content_auto():
    """Auto-refreshing portfolio fragment (runs every 30s)."""
    _render_venue_tabs()


def _portfolio_content():
    """Manual-refresh portfolio content."""
    _render_venue_tabs()


def _render_venue_tabs():
    """One tab per execution venue.

    Polymarket gets its own tab rather than a merged view because almost
    nothing lines up: separate balances, separate position shapes, separate
    dry-run flags. The one thing that IS shared — the daily loss budget, which
    Gate 1 reads off the common trade log — is labelled as such in both tabs.
    """
    kalshi_tab, pm_tab = st.tabs(["Kalshi", "Polymarket"])
    with kalshi_tab:
        _fetch_and_render("kalshi")
    with pm_tab:
        _fetch_and_render("polymarket")


def _fetch_and_render(venue: str):
    """Fetch one venue's portfolio data and render all its sections."""
    cache_key = f"portfolio_data_{venue}"
    # Always fetch fresh when auto-refreshing; use cache otherwise
    auto = st.session_state.get("portfolio_auto", False)
    if auto or cache_key not in st.session_state:
        with st.spinner(f"Fetching {venue} portfolio..."):
            try:
                client = get_client(venue)
                st.session_state[cache_key] = get_portfolio_data(client, venue=venue)
            except FileNotFoundError as e:
                # Credentials for this venue aren't configured — an expected
                # state, not an error worth a red banner.
                st.info(f"{venue.title()} is not configured: {e}")
                return
            except Exception as e:
                st.error(f"Failed to fetch {venue} portfolio: {e}")
                return

    data = st.session_state[cache_key]
    pnl = data["daily_pnl"]

    # ── Summary metrics ─────────────────────────────────────────────────
    section_label("Account Summary")

    pnl_color = GREEN if pnl >= 0 else RED
    metrics = [
        {"label": "Balance", "value": f"${data['balance']:,.2f}", "color": CYAN},
        {"label": "Portfolio Value", "value": f"${data['portfolio_value']:,.2f}"},
        {"label": "Open Positions", "value": f"{data['open_count']}/{data['max_positions']}"},
    ]
    if venue == "polymarket":
        # Buying power can differ from balance on the US retail API; showing
        # only balance would misstate what is actually spendable.
        metrics.append({"label": "Buying Power",
                        "value": f"${data.get('buying_power', 0):,.2f}"})
    else:
        metrics.append({"label": "Today's P&L", "value": f"${pnl:+,.2f}",
                        "color": pnl_color, "delta": f"${pnl:+,.2f}"})
    metric_row(metrics)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)

    # ── Daily loss limit progress (shared across venues) ────────────────
    limit = data["daily_limit"]
    loss_used = max(0, -pnl)
    pct = min(loss_used / limit, 1.0) if limit > 0 else 0

    st.progress(pct, text=f"Daily loss (all venues): ${loss_used:.2f} / ${limit:.2f}")
    st.caption(
        "Gate 1 reads the shared trade log, so this budget spans Kalshi and "
        "Polymarket together — one operator, one daily risk budget."
    )

    if pnl <= -limit:
        st.markdown(f"""
        <div style="background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3);
                    border-radius:6px; padding:0.75rem 1rem; margin:0.5rem 0;
                    font-family:JetBrains Mono,monospace; font-size:0.82rem;
                    color:{RED}; font-weight:600; text-align:center;">
            HARD STOP ACTIVE &mdash; No new positions permitted today
        </div>
        """, unsafe_allow_html=True)

    # ── Order-mode banner ───────────────────────────────────────────────
    if venue == "polymarket":
        live, mode = polymarket_order_mode()
        color, rgb = (RED, "239,68,68") if live else (AMBER, "245,158,11")
        text = (f"LIVE ORDERS ARMED &mdash; {mode}" if live
                else f"Orders {mode}")
        st.markdown(f"""
        <div style="background:rgba({rgb},0.08); border:1px solid rgba({rgb},0.25);
                    border-radius:6px; padding:0.5rem 1rem; margin:0.5rem 0;
                    font-family:JetBrains Mono,monospace; font-size:0.78rem;
                    color:{color};">{text}</div>
        """, unsafe_allow_html=True)
    elif data["dry_run"]:
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
        st.markdown("""
        <div style="text-align:center; padding:2rem; color:#475569;
                    font-family:JetBrains Mono,monospace; font-size:0.82rem;">
            No open positions
        </div>
        """, unsafe_allow_html=True)
    elif venue == "polymarket":
        _render_polymarket_positions(data)
    else:
        _render_kalshi_positions(positions)

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
                "Created": str(o.get("created_time", ""))[:16],
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


def _render_kalshi_positions(positions: list[dict]):
    rows = format_positions_for_display(positions)
    df = pd.DataFrame(rows)

    # Numeric P&L for summary stats
    df["pnl_num"] = df["P&L"].apply(lambda x: float(x.replace("$", "").replace("+", "")))

    st.dataframe(
        df.drop(columns=["pnl_num"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "P&L": st.column_config.TextColumn("P&L", width="small"),
        },
    )
    _pnl_summary(df["pnl_num"], df.drop(columns=["pnl_num"]), "edge_radar_positions.csv")


def _render_polymarket_positions(data: dict):
    rows = format_polymarket_positions_for_display(
        data["positions"], data.get("raw_positions"))
    df = pd.DataFrame(rows)

    st.dataframe(df, use_container_width=True, hide_index=True)

    # Unrealized is blank when the venue didn't return `cashValue`; only
    # summarize the rows that actually have a number.
    def _num(v):
        try:
            return float(str(v).replace("$", "").replace("+", ""))
        except ValueError:
            return None

    vals = [n for n in (_num(v) for v in df["Unrealized"]) if n is not None]
    if vals:
        _pnl_summary(pd.Series(vals), df, "edge_radar_polymarket_positions.csv")
    else:
        st.caption("Mark-to-market values unavailable — showing cost basis only.")
        st.download_button("Export CSV", df.to_csv(index=False),
                           file_name="edge_radar_polymarket_positions.csv",
                           mime="text/csv")


def _pnl_summary(pnl_series, export_df, filename: str):
    """W/L counts + total unrealized P&L, with a CSV export beside it."""
    total_pnl = pnl_series.sum()
    pnl_color = GREEN if total_pnl >= 0 else RED
    winning = (pnl_series > 0).sum()
    losing = (pnl_series < 0).sum()
    flat = (pnl_series == 0).sum()

    pcol1, pcol2 = st.columns([4, 1])
    with pcol1:
        st.markdown(
            f'<div style="font-family:JetBrains Mono,monospace; font-size:0.78rem; '
            f'padding:0.25rem 0.5rem;">'
            f'<span style="color:{GREEN};">{winning}W</span> · '
            f'<span style="color:{RED};">{losing}L</span>'
            f'{f" · {flat}F" if flat else ""} · '
            f'Unrealized: <span style="color:{pnl_color}; font-weight:600;">'
            f'${total_pnl:+,.2f}</span></div>',
            unsafe_allow_html=True,
        )
    with pcol2:
        st.download_button("Export CSV", export_df.to_csv(index=False),
                           file_name=filename, mime="text/csv")
