"""
Edge-Radar Web Dashboard — Streamlit entry point.

Launch:  streamlit run webapp/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Edge-Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject theme CSS before anything else renders
from theme import inject_css, section_label, CYAN, DIM
inject_css()

from favorites import load_favorites


def check_password() -> bool:
    """Simple password gate using st.secrets."""
    try:
        correct_pw = st.secrets["passwords"]["user"]
    except (KeyError, FileNotFoundError):
        return True

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("""
    <div style="display:flex; justify-content:center; align-items:center;
                min-height:60vh; flex-direction:column;">
        <div style="font-family:Outfit,sans-serif; font-size:2rem; font-weight:700;
                    color:#00d4aa; margin-bottom:0.25rem; letter-spacing:-0.02em;">
            EDGE-RADAR
        </div>
        <div style="font-family:JetBrains Mono,monospace; font-size:0.78rem;
                    color:#64748b; margin-bottom:2rem;">
            Authenticate to continue
        </div>
    </div>
    """, unsafe_allow_html=True)

    pw = st.text_input("Password", type="password", label_visibility="collapsed",
                       placeholder="Enter password...")
    if pw:
        if pw == correct_pw:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    return False


QUICK_SCANS = {
    "Sports": "sports",
    "Futures": "futures",
    "Prediction": "prediction",
    "Polymarket": "polymarket",
}


def main():
    if not check_password():
        st.stop()

    # ── Sidebar ─────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("""
        <div style="padding: 0.5rem 0 1rem 0;">
            <div style="font-family:Outfit,sans-serif; font-weight:700;
                        font-size:1.3rem; color:#00d4aa; letter-spacing:-0.02em;">
                EDGE-RADAR
            </div>
            <div style="font-family:JetBrains Mono,monospace; font-size:0.65rem;
                        color:#475569; margin-top:2px; letter-spacing:0.04em;">
                PREDICTION MARKET INTELLIGENCE
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Main navigation ─────────────────────────────────────────
        page = st.radio(
            "NAV",
            ["Scan & Execute", "Portfolio", "Settle & Report", "Backtest"],
            index=0,
            label_visibility="collapsed",
        )

        # ── Quick scan buttons ──────────────────────────────────────
        section_label("Quick Scan")

        for label, market_type in QUICK_SCANS.items():
            if st.button(label, key=f"qs_{market_type}", use_container_width=True):
                st.session_state.quick_scan_market = market_type
                # Force nav to scan page
                st.session_state["nav_radio"] = "Scan & Execute"
                st.rerun()

        # ── Favorite scans ──────────────────────────────────────────
        favs = load_favorites()
        if favs:
            section_label("Favorites")
            for fav in favs:
                fav_label = fav.get("name", "Unnamed")
                if st.button(fav_label, key=f"fav_{fav_label}", use_container_width=True):
                    st.session_state.quick_scan_market = fav.get("market_type", "sports")
                    st.session_state.favorite_params = fav
                    st.rerun()

        # Sidebar footer
        st.markdown("""
        <div style="position:fixed; bottom:1rem; font-family:JetBrains Mono,monospace;
                    font-size:0.6rem; color:#334155; letter-spacing:0.05em;">
            v1.0 &middot; KALSHI
        </div>
        """, unsafe_allow_html=True)

    # ── Page routing ────────────────────────────────────────────────────
    if page == "Scan & Execute":
        from views import scan_page
        scan_page.render()
    elif page == "Portfolio":
        from views import portfolio_page
        portfolio_page.render()
    elif page == "Settle & Report":
        from views import settle_page
        settle_page.render()
    elif page == "Backtest":
        from views import backtest_page
        backtest_page.render()


if __name__ == "__main__":
    main()
