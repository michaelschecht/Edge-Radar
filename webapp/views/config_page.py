"""Config page — every env-driven knob and what is actually in force.

Exists because `kalshi_executor.py` snapshots gate thresholds into module-level
globals at import time, so a long-running Streamlit process can be running
against values that no longer match `.env`. This page reads the live process
env, which is the state the scan and execute paths actually see after
`reload_risk_config()`.
"""

import os
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services import env_var_rows, polymarket_order_mode
from theme import page_header, section_label, metric_row, CYAN, GREEN, RED, AMBER, DIM

from app.config import get_config


_GROUP_ORDER = [
    "Credentials", "System", "Risk limits", "Sizing", "Reject gates",
    "Data quality", "Caching", "Per-sport overrides", "Notifications",
    "Integrations",
]


def _is_cloud() -> bool:
    return os.path.exists("/mount/src")


def render():
    page_header("Config", "Every environment variable and its live value")

    try:
        cfg = get_config()
    except ValueError as e:
        # Config.validate() rejects impossible combinations at build time.
        st.error(f"Config is invalid — the app is running on stale values: {e}")
        return

    # ── Live mode summary ───────────────────────────────────────────────
    section_label("Execution Mode")

    global_dry = cfg.system.dry_run
    pm_live, pm_mode = polymarket_order_mode()

    metric_row([
        {"label": "Kalshi Orders",
         "value": "DRY RUN" if global_dry else "LIVE",
         "color": AMBER if global_dry else RED},
        {"label": "Polymarket Orders",
         "value": "LIVE" if pm_live else "BLOCKED",
         "color": RED if pm_live else AMBER},
        {"label": "Unit Size", "value": f"${cfg.risk.unit_size:.2f}", "color": CYAN},
        {"label": "Kelly Fraction", "value": f"{cfg.kelly.kelly_fraction:g}", "color": CYAN},
    ])

    st.caption(
        f"Polymarket: {pm_mode}. The venue needs BOTH DRY_RUN=false and "
        f"POLYMARKET_DRY_RUN=false to place an order — set POLYMARKET_DRY_RUN=true "
        f"to halt it without touching Kalshi."
    )

    # C11 pairs the Kelly fix with a KELLY_FRACTION ceiling; flag a config that
    # walks past it rather than leaving it to be discovered from a slate.
    if cfg.kelly.kelly_fraction > 0.5:
        st.warning(
            f"KELLY_FRACTION={cfg.kelly.kelly_fraction:g} exceeds the 0.5 ceiling. "
            "It is divided by batch size at runtime, making it a *portfolio* "
            "fraction — at 1.0 a fully correlated slate reaches full Kelly."
        )
    st.caption(
        f"MAX_BET_SIZE=${cfg.risk.max_bet_size:g} is the backstop for the "
        "10%-of-bankroll hard stop. Bankroll isn't a config value, so nothing "
        "can check the ratio for you — re-check it after a large swing."
    )

    # ── Restart notice ──────────────────────────────────────────────────
    if _is_cloud():
        st.info(
            "Cloud deployment: values come from **Settings → Secrets**, not "
            "`.env`. Saving secrets auto-reboots the app."
        )
    else:
        st.info(
            "Local deployment: values come from `.env`. Scan and execute call "
            "`reload_risk_config()` so gate edits apply without a restart, but "
            "anything read at import time (and this summary) needs "
            "`Ctrl+C` → `streamlit run webapp/app.py`."
        )

    # ── Full variable table ─────────────────────────────────────────────
    section_label("Environment Variables")

    rows = env_var_rows()
    df = pd.DataFrame(rows)

    fcol1, fcol2 = st.columns([1, 3])
    with fcol1:
        show_unset = st.checkbox(
            "Show unset", value=False,
            help="Include variables with no value and no code default — "
                 "optional overrides you have not set.",
        )
    with fcol2:
        groups = st.multiselect(
            "Groups", _GROUP_ORDER, default=[],
            help="Empty shows every group.",
        )

    view = df if show_unset else df[df["Source"] != "unset"]
    if groups:
        view = view[view["Group"].isin(groups)]

    st.dataframe(
        view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Variable": st.column_config.TextColumn(width="medium"),
            "Value": st.column_config.TextColumn(width="small"),
            "Source": st.column_config.TextColumn(
                width="small",
                help="'set' = present in the environment (.env or Secrets). "
                     "'default' = falling back to the code default in "
                     "app/config.py. 'unset' = no value and no default.",
            ),
            "Group": st.column_config.TextColumn(width="small"),
            "Notes": st.column_config.TextColumn(width="large"),
        },
    )

    n_set = int((df["Source"] == "set").sum())
    st.caption(
        f"{len(df)} variables known to the app · {n_set} set in this "
        f"environment · secrets are shown as a length only, never a value."
    )

    st.download_button(
        "Export .env template",
        _env_template(rows),
        file_name="edge-radar.env.template",
        mime="text/plain",
        help="Every variable with its live value (secrets blanked), ready to "
             "paste into a fresh .env.",
    )


def _env_template(rows: list[dict]) -> str:
    """Build a copy-pasteable .env from the live values.

    Secret values are emitted blank rather than masked — a template with
    `KALSHI_API_KEY=set (36 chars)` in it is worse than useless, and writing
    the real key into a downloadable file is not something this page should
    ever do.
    """
    from services import SECRET_ENV_VARS

    lines = ["# Edge-Radar — generated from the live dashboard config.",
             "# Secret values are blanked; fill them in yourself.", ""]
    current_group = None
    for r in rows:
        if r["Group"] != current_group:
            current_group = r["Group"]
            lines.append(f"\n# === {current_group.upper()} ===")
        name = r["Variable"]
        value = "" if name in SECRET_ENV_VARS else (
            "" if r["Value"] == "—" else r["Value"])
        prefix = "" if r["Source"] != "unset" else "# "
        lines.append(f"{prefix}{name}={value}")
    return "\n".join(lines) + "\n"
