"""Tests for the Phase 3 lint guard.

Verifies that:
1. The current codebase passes the lint cleanly.
2. The lint correctly catches a regression (an `os.getenv` call introduced
   into a previously-clean file).
3. The `# config-bootstrap` annotation suppresses violations.
"""

import sys
from pathlib import Path

import pytest

# Make the lint module importable.
LINT_DIR = Path(__file__).resolve().parent.parent / "scripts" / "lint"
sys.path.insert(0, str(LINT_DIR))

from check_config_centralization import scan, ROOT, ALLOWED_FILE  # noqa: E402


def test_codebase_is_clean():
    """The current production codebase has no lint violations."""
    violations = scan()
    if violations:
        # Fail with a useful message.
        msgs = [f"{p.as_posix()}:{lineno}: {text.strip()}"
                for p, lineno, text in violations]
        pytest.fail("CONFIG_CENTRALIZATION violations found:\n  " + "\n  ".join(msgs))


def test_violation_detected(tmp_path, monkeypatch):
    """A fresh os.getenv call in a previously-clean file is flagged."""
    target = ROOT / "scripts" / "doctor.py"
    original = target.read_text(encoding="utf-8")
    try:
        target.write_text(original + '\nx = os.getenv("FOO")\n', encoding="utf-8")
        violations = scan()
        matches = [v for v in violations if v[0].as_posix().endswith("doctor.py")]
        assert len(matches) == 1, f"expected 1 violation, got {len(matches)}"
        assert "doctor.py" in matches[0][0].as_posix()
    finally:
        target.write_text(original, encoding="utf-8")


def test_bootstrap_annotation_suppresses(tmp_path):
    """A line carrying `# config-bootstrap` is allowed to use os.environ."""
    target = ROOT / "scripts" / "doctor.py"
    original = target.read_text(encoding="utf-8")
    try:
        target.write_text(
            original + '\nos.environ["X"] = "y"  # config-bootstrap\n',
            encoding="utf-8",
        )
        violations = scan()
        matches = [v for v in violations if v[0].as_posix().endswith("doctor.py")]
        assert matches == [], f"annotated line should be allowed, got {matches}"
    finally:
        target.write_text(original, encoding="utf-8")


def test_comment_only_line_ignored(tmp_path):
    """A pure-comment line mentioning os.getenv is not a violation."""
    target = ROOT / "scripts" / "doctor.py"
    original = target.read_text(encoding="utf-8")
    try:
        target.write_text(
            original + "\n# Reference to os.getenv in a comment\n",
            encoding="utf-8",
        )
        violations = scan()
        matches = [v for v in violations if v[0].as_posix().endswith("doctor.py")]
        assert matches == [], f"comment-only line should be ignored, got {matches}"
    finally:
        target.write_text(original, encoding="utf-8")


def test_app_config_is_excluded():
    """The single source-of-truth file is allowed to use os.getenv freely."""
    assert ALLOWED_FILE.exists()
    # Confirm by checking that adding more os.getenv usages there wouldn't
    # show up in scan() — i.e. ALLOWED_FILE is unconditionally skipped.
    # We rely on the fact that the production app/config.py already has
    # several os.getenv calls; if they appeared in scan() the codebase-clean
    # test above would already fail.
    violations = scan()
    config_hits = [v for v in violations if v[0].as_posix() == "app/config.py"]
    assert config_hits == []
