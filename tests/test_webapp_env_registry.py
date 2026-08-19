"""Lock `webapp/services.ENV_VAR_SPEC` to `app/config.py`.

The webapp keeps its own list of environment variable names because the
Streamlit Cloud secrets bootstrap has to know which flat TOML keys to lift
into `os.environ` *before* any script imports run — it cannot introspect
`app.config`, which reads `os.environ` at that point.

That duplication silently rotted: by 2026-07 the list was missing every
NO-side global (R28), both live-bet gates (L1), the whole odds/scan cache
group (R24b/R26), and all Polymarket credentials. On Cloud those knobs were
simply ignored — set in Secrets, never read, no error. These tests fail the
build when the two drift apart again.
"""

import re
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WEBAPP_DIR = PROJECT_ROOT / "webapp"
CONFIG_PATH = PROJECT_ROOT / "app" / "config.py"

# webapp/ is not on the default test path (pyproject's pythonpath covers
# scripts/*), and services.py imports Streamlit at module scope.
sys.path.insert(0, str(WEBAPP_DIR))
services = pytest.importorskip(
    "services", reason="webapp deps (streamlit) not installed")


def _config_env_names() -> set[str]:
    """Every env var `app/config.py` reads, by name.

    Covers both the `_bool("X", ...)` / `_float("X", ...)` helper form and the
    direct `os.getenv("X")` calls in `PerSportOverrides.from_env`, whose
    f-string names are expanded against the module's own sport tuple.
    """
    source = CONFIG_PATH.read_text(encoding="utf-8")

    names = set(re.findall(r'_(?:bool|float|int|str|list)\(\s*"([A-Z0-9_]+)"', source))

    # Per-sport overrides are built as f"PREFIX_{sport.upper()}".
    from app.config import _SUPPORTED_SPORTS
    for prefix in re.findall(r'os\.getenv\(f"([A-Z0-9_]+)_\{sport\.upper\(\)\}"', source):
        names.update(f"{prefix}_{s.upper()}" for s in _SUPPORTED_SPORTS)

    return names


def test_spec_covers_every_config_env_var():
    """Anything app/config.py reads must be liftable from Cloud secrets."""
    missing = _config_env_names() - set(services.ENV_VAR_NAMES)
    assert not missing, (
        "app/config.py reads env vars the webapp registry doesn't know about, "
        "so they are ignored on Streamlit Cloud. Add them to ENV_VAR_SPEC in "
        f"webapp/services.py: {sorted(missing)}"
    )


def test_spec_has_no_unknown_vars():
    """The reverse: no phantom knobs implying support that doesn't exist.

    PROJECT_ROOT and the notification vars are read outside app/config.py
    (paths.py and the report-emailer scripts respectively), so they are
    legitimately absent from it.
    """
    allowed_outside_config = {"NOTIFY_EMAIL", "RESEND_FROM", "RESEND_REPLY_TO"}
    unknown = (set(services.ENV_VAR_NAMES)
               - _config_env_names()
               - allowed_outside_config)
    assert not unknown, (
        "webapp/services.py advertises env vars app/config.py never reads — "
        f"they would show on the Config page but do nothing: {sorted(unknown)}"
    )


def test_spec_entries_are_well_formed():
    seen = set()
    for spec in services.ENV_VAR_SPEC:
        name = spec["name"]
        assert name not in seen, f"duplicate ENV_VAR_SPEC entry: {name}"
        seen.add(name)
        assert name.isupper(), f"env var names are upper-case: {name}"
        assert spec["group"], f"{name} has no group"
        assert spec["note"], f"{name} has no note (it renders on the Config page)"
        assert isinstance(spec["secret"], bool)


def test_credentials_are_marked_secret():
    """A credential rendered in full on the Config page is a leak."""
    must_be_secret = {
        "KALSHI_API_KEY", "KALSHI_PRIVATE_KEY",
        "ODDS_API_KEY", "ODDS_API_KEYS",
        "POLYMARKET_KEY_ID", "POLYMARKET_SECRET_KEY",
    }
    assert must_be_secret <= services.SECRET_ENV_VARS


def test_env_var_rows_masks_secret_values(monkeypatch):
    monkeypatch.setenv("KALSHI_API_KEY", "super-secret-key-value")
    rows = {r["Variable"]: r for r in services.env_var_rows()}
    row = rows["KALSHI_API_KEY"]
    assert "super-secret-key-value" not in row["Value"]
    assert row["Source"] == "set"


def test_env_var_rows_reports_defaults(monkeypatch):
    monkeypatch.delenv("MIN_COMPOSITE_SCORE", raising=False)
    rows = {r["Variable"]: r for r in services.env_var_rows()}
    assert rows["MIN_COMPOSITE_SCORE"]["Source"] == "default"
    assert rows["MIN_COMPOSITE_SCORE"]["Value"] == "6.0"
