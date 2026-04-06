"""
theme.py — Edge-Radar dark terminal aesthetic.

Injects custom CSS and provides styled component helpers.
"""

import streamlit as st

# ── Color palette ───────────────────────────────────────────────────────────
CYAN = "#00d4aa"
AMBER = "#f59e0b"
RED = "#ef4444"
GREEN = "#22c55e"
DIM = "#64748b"
SURFACE = "#111827"
DEEP = "#0a0e17"
BORDER = "#1e293b"
TEXT = "#e2e8f0"
TEXT_DIM = "#94a3b8"


def inject_css():
    """Inject the full custom stylesheet."""
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Outfit:wght@300;400;500;600;700&display=swap');

    /* ── Global ─────────────────────────────────────────────────── */
    .stApp {
        background: linear-gradient(180deg, #0a0e17 0%, #0d1220 100%);
    }

    /* Subtle grid pattern overlay */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        background-image:
            linear-gradient(rgba(0, 212, 170, 0.015) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0, 212, 170, 0.015) 1px, transparent 1px);
        background-size: 40px 40px;
        pointer-events: none;
        z-index: 0;
    }

    .main .block-container {
        padding-top: 2rem;
        max-width: 1400px;
    }

    /* ── Hide sidebar toggle buttons entirely ────────────────────── */
    [data-testid="stSidebarCollapseButton"],
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    /* ── Typography ─────────────────────────────────────────────── */
    h1, h2, h3, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em;
    }

    h1, .stMarkdown h1 {
        color: #00d4aa !important;
        font-size: 1.75rem !important;
        border-bottom: 1px solid #1e293b;
        padding-bottom: 0.75rem;
        margin-bottom: 1.5rem;
    }

    h2, .stMarkdown h2 {
        color: #e2e8f0 !important;
        font-size: 1.25rem !important;
        margin-top: 1.5rem;
    }

    h3, .stMarkdown h3 {
        color: #94a3b8 !important;
        font-size: 1rem !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        font-weight: 500 !important;
    }

    p, .stMarkdown p {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem;
    }

    span:not([data-icon]):not(.material-symbols-rounded),
    label {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem;
    }

    /* ── Sidebar ────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1220 0%, #0a0e17 100%);
        border-right: 1px solid #1e293b;
    }

    section[data-testid="stSidebar"] .stRadio > label {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 500;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
    }

    section[data-testid="stSidebar"] .stRadio > div > label {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 400;
        padding: 0.6rem 0.75rem;
        border-radius: 6px;
        transition: all 0.15s ease;
        border: 1px solid transparent;
        text-transform: none;
        letter-spacing: 0;
    }

    section[data-testid="stSidebar"] .stRadio > div > label:hover {
        background: rgba(0, 212, 170, 0.06);
        border-color: rgba(0, 212, 170, 0.15);
    }

    section[data-testid="stSidebar"] .stRadio > div > label[data-checked="true"],
    section[data-testid="stSidebar"] .stRadio > div > label[aria-checked="true"] {
        background: rgba(0, 212, 170, 0.08);
        border-color: rgba(0, 212, 170, 0.25);
        color: #00d4aa;
    }

    /* ── Metric cards ───────────────────────────────────────────── */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #111827 0%, #0d1220 100%);
        border: 1px solid #1e293b;
        border-radius: 8px;
        padding: 1rem 1.25rem;
        transition: border-color 0.2s ease;
    }

    div[data-testid="stMetric"]:hover {
        border-color: rgba(0, 212, 170, 0.3);
    }

    div[data-testid="stMetric"] label {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 500;
        font-size: 0.7rem !important;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #64748b !important;
    }

    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600;
        font-size: 1.5rem !important;
        color: #e2e8f0 !important;
    }

    div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.75rem !important;
    }

    /* ── Buttons ────────────────────────────────────────────────── */
    .stButton > button {
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 500;
        font-size: 0.82rem;
        letter-spacing: 0.04em;
        border-radius: 6px;
        padding: 0.5rem 1.5rem;
        transition: all 0.2s ease;
        border: 1px solid #1e293b;
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #00d4aa 0%, #00b894 100%) !important;
        color: #0a0e17 !important;
        font-weight: 600;
        border: none;
        text-shadow: 0 1px 0 rgba(0,0,0,0.1);
    }

    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #00e6b8 0%, #00d4aa 100%) !important;
        box-shadow: 0 0 20px rgba(0, 212, 170, 0.25);
        transform: translateY(-1px);
    }

    .stButton > button:not([kind="primary"]) {
        background: transparent !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
    }

    .stButton > button:not([kind="primary"]):hover {
        border-color: #00d4aa !important;
        color: #00d4aa !important;
        background: rgba(0, 212, 170, 0.05) !important;
    }

    /* ── Inputs & Selects ───────────────────────────────────────── */
    .stSelectbox > div > div,
    .stNumberInput > div > div > input,
    .stTextInput > div > div > input {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem;
        background: #0d1220 !important;
        border: 1px solid #1e293b !important;
        border-radius: 6px;
        color: #e2e8f0;
    }

    .stSelectbox > div > div:focus-within,
    .stNumberInput > div > div > input:focus,
    .stTextInput > div > div > input:focus {
        border-color: #00d4aa !important;
        box-shadow: 0 0 0 1px rgba(0, 212, 170, 0.2) !important;
    }

    .stSelectbox label,
    .stNumberInput label,
    .stTextInput label,
    .stSlider label,
    .stCheckbox label,
    .stMultiSelect label {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 500;
        font-size: 0.72rem !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #64748b !important;
    }

    /* ── Slider ─────────────────────────────────────────────────── */
    .stSlider > div > div > div > div {
        background: #00d4aa !important;
    }

    /* ── Dataframes ─────────────────────────────────────────────── */
    .stDataFrame {
        border: 1px solid #1e293b;
        border-radius: 8px;
        overflow: hidden;
    }

    /* ── Progress bar ───────────────────────────────────────────── */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #22c55e 0%, #f59e0b 60%, #ef4444 100%) !important;
        border-radius: 4px;
    }

    .stProgress > div > div {
        background: #1e293b !important;
        border-radius: 4px;
    }

    /* ── Expanders ──────────────────────────────────────────────── */
    .streamlit-expanderHeader {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem;
        background: #111827 !important;
        border: 1px solid #1e293b !important;
        border-radius: 6px;
        color: #94a3b8 !important;
    }

    .streamlit-expanderContent {
        border: 1px solid #1e293b;
        border-top: none;
        border-radius: 0 0 6px 6px;
    }

    /* ── Code blocks ────────────────────────────────────────────── */
    .stCodeBlock {
        border: 1px solid #1e293b;
        border-radius: 6px;
    }

    code {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.78rem;
    }

    /* ── Alerts ─────────────────────────────────────────────────── */
    .stAlert {
        border-radius: 6px;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.82rem;
    }

    /* ── Divider ────────────────────────────────────────────────── */
    hr {
        border-color: #1e293b !important;
        margin: 1.5rem 0 !important;
    }

    /* ── Multiselect chips ──────────────────────────────────────── */
    .stMultiSelect span[data-baseweb="tag"] {
        background: rgba(0, 212, 170, 0.12) !important;
        border: 1px solid rgba(0, 212, 170, 0.3) !important;
        color: #00d4aa !important;
        border-radius: 4px;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.75rem;
    }

    /* ── Caption ────────────────────────────────────────────────── */
    .stCaption, .stMarkdown small {
        color: #64748b !important;
        font-family: 'JetBrains Mono', monospace !important;
    }

    /* ── Checkbox ───────────────────────────────────────────────── */
    .stCheckbox {
        padding-top: 0.5rem;
    }

    /* ── Spinner ────────────────────────────────────────────────── */
    .stSpinner > div {
        border-top-color: #00d4aa !important;
    }

    /* ── Toast / Success / Warning styling ──────────────────────── */
    div[data-testid="stNotification"] {
        font-family: 'JetBrains Mono', monospace !important;
        border-radius: 6px;
    }

    </style>
    """, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    """Render a styled page header."""
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(f'<p style="color: #64748b; margin-top: -1rem; font-size: 0.78rem;">{subtitle}</p>',
                    unsafe_allow_html=True)


def status_badge(text: str, color: str = CYAN) -> str:
    """Return HTML for an inline status badge."""
    return (f'<span style="display:inline-block; padding:2px 10px; border-radius:4px; '
            f'font-family:JetBrains Mono,monospace; font-size:0.72rem; font-weight:500; '
            f'background:rgba({_hex_to_rgb(color)},0.12); '
            f'border:1px solid rgba({_hex_to_rgb(color)},0.3); '
            f'color:{color};">{text}</span>')


def metric_row(metrics: list[dict]):
    """
    Render a row of styled metric cards.
    Each dict: {"label": str, "value": str, "delta": str (optional), "color": str (optional)}
    """
    cols = st.columns(len(metrics))
    for col, m in zip(cols, metrics):
        with col:
            color = m.get("color", TEXT)
            delta_html = ""
            if "delta" in m:
                d_color = GREEN if m["delta"].startswith("+") or m["delta"].startswith("$") else RED
                delta_html = (f'<div style="font-size:0.72rem; color:{d_color}; '
                              f'margin-top:2px;">{m["delta"]}</div>')

            st.markdown(f"""
            <div style="background:linear-gradient(135deg, #111827, #0d1220);
                        border:1px solid #1e293b; border-radius:8px;
                        padding:1rem 1.25rem; transition:border-color 0.2s;">
                <div style="font-family:Outfit,sans-serif; font-weight:500;
                            font-size:0.7rem; text-transform:uppercase;
                            letter-spacing:0.1em; color:#64748b;">
                    {m['label']}
                </div>
                <div style="font-family:JetBrains Mono,monospace; font-weight:600;
                            font-size:1.4rem; color:{color}; margin-top:4px;">
                    {m['value']}
                </div>
                {delta_html}
            </div>
            """, unsafe_allow_html=True)


def section_label(text: str):
    """Render a subtle section divider label."""
    st.markdown(f"""
    <div style="font-family:Outfit,sans-serif; font-weight:500; font-size:0.7rem;
                text-transform:uppercase; letter-spacing:0.1em; color:#475569;
                border-bottom:1px solid #1e293b; padding-bottom:0.4rem;
                margin:1.5rem 0 1rem 0;">
        {text}
    </div>
    """, unsafe_allow_html=True)


def _hex_to_rgb(hex_color: str) -> str:
    """Convert hex to comma-separated RGB string."""
    h = hex_color.lstrip('#')
    return f"{int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)}"
