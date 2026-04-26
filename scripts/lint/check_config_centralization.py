"""
check_config_centralization.py — Phase 3 lint guard for the
CONFIG_CENTRALIZATION refactor.

Disallows `os.getenv` / `os.environ` outside `app/config.py`. Every config
read must flow through `from app.config import get_config`.

Two narrow exceptions:
    1. Comment-only lines (lines whose stripped code is empty or starts with `#`)
       are skipped — they're documentation, not code.
    2. Lines tagged with the inline annotation `# config-bootstrap` are skipped.
       This is reserved for the Streamlit Cloud secrets bootstrap in
       `webapp/services.py`, which writes `os.environ` from `st.secrets`
       *before* downstream imports cache `cfg`. It's the input side of cfg,
       not config consumption.

Exit codes:
    0 — clean
    1 — violations found (printed to stdout)

Invocation:
    python scripts/lint/check_config_centralization.py
    make lint-config
    pre-commit run check-config-centralization --all-files
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
ALLOWED_FILE = (ROOT / "app" / "config.py").resolve()
SEARCH_DIRS = ("app", "scripts", "webapp")
EXCLUDED_SUBDIRS = (
    "scripts/custom",  # user automation, out of refactor scope
    "scripts/lint",    # this directory; the lint script itself names the
                       # forbidden strings to communicate the rule.
)
PATTERN = re.compile(r"\bos\.(getenv|environ)\b")
ALLOWLIST_TAG = "config-bootstrap"


def is_code_line(line: str) -> bool:
    """Return True if the line has executable code (not pure comment/blank)."""
    stripped = line.lstrip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return False
    return True


def is_excluded(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel.startswith(prefix) for prefix in EXCLUDED_SUBDIRS)


def scan() -> list[tuple[Path, int, str]]:
    violations: list[tuple[Path, int, str]] = []
    for d in SEARCH_DIRS:
        for path in (ROOT / d).rglob("*.py"):
            if path.resolve() == ALLOWED_FILE:
                continue
            if is_excluded(path):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(lines, start=1):
                if not PATTERN.search(line):
                    continue
                if not is_code_line(line):
                    continue
                if ALLOWLIST_TAG in line:
                    continue
                violations.append((path.relative_to(ROOT), i, line.rstrip()))
    return violations


def main() -> int:
    violations = scan()
    if not violations:
        return 0

    print("CONFIG_CENTRALIZATION violations found:")
    print(f"  os.getenv / os.environ may only appear in app/config.py.")
    print()
    for path, lineno, text in violations:
        print(f"  {path.as_posix()}:{lineno}: {text.strip()}")
    print()
    print("Fix:")
    print("  - Reads: replace with `get_config().<group>.<field>` "
          "(import via `from app.config import get_config`).")
    print("  - Writes (e.g. Streamlit secrets bootstrap): tag the line with")
    print("    `# config-bootstrap` so the lint guard skips it.")
    print()
    print(f"See docs/my-documents/enhancements/CONFIG_CENTRALIZATION.md")
    return 1


if __name__ == "__main__":
    sys.exit(main())
