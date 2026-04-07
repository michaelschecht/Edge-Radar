"""
Smoke tests that verify imports work in the REAL script runtime environment.

These tests run key entry-point scripts as subprocesses (the same way users
invoke them), catching import errors that unit tests miss because pytest
configures sys.path differently than the .pth file / paths.py mechanism.
"""

import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Use the venv Python if available (matches how users run scripts),
# otherwise fall back to the current interpreter.
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
if not VENV_PYTHON.exists():
    VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def _run_script(args: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    """Run a script as a subprocess and return the result."""
    return subprocess.run(
        [PYTHON] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(PROJECT_ROOT),
    )


class TestScriptImports:
    """Verify that key scripts can be imported without errors.

    These catch the class of bug where a module-level import fails in
    the real runtime but passes in pytest (which has different sys.path).
    """

    @pytest.mark.parametrize("module_path", [
        "scripts/shared/opportunity.py",
        "scripts/shared/trade_log.py",
        "scripts/shared/ticker_display.py",
        "scripts/shared/paths.py",
        "scripts/kalshi/kalshi_executor.py",
        "scripts/kalshi/edge_detector.py",
        "scripts/kalshi/kalshi_settler.py",
        "scripts/kalshi/risk_check.py",
    ])
    def test_script_imports_cleanly(self, module_path):
        """Each script can be imported without ModuleNotFoundError."""
        # Use -c to import the module's top-level code, but bail before
        # any CLI main() runs by only importing the module.
        module_name = Path(module_path).stem
        # We need the paths.py side-effect to set up sys.path, so we
        # add the shared dir explicitly (same as what .pth does).
        result = _run_script([
            "-c",
            f"import sys; sys.path.insert(0, 'scripts/shared'); "
            f"sys.path.insert(0, 'scripts/kalshi'); "
            f"import {module_name}",
        ])
        assert result.returncode == 0, (
            f"Import of {module_path} failed:\n{result.stderr}"
        )

    def test_app_domain_importable(self):
        """app.domain package imports correctly."""
        result = _run_script([
            "-c",
            "from app.domain import Opportunity, RiskDecision, "
            "ExecutionPreview, ExecutionResult; "
            "print('OK')",
        ])
        assert result.returncode == 0, (
            f"app.domain import failed:\n{result.stderr}"
        )

    def test_opportunity_identity(self):
        """Opportunity from both import paths is the same class."""
        result = _run_script([
            "-c",
            "import sys; sys.path.insert(0, 'scripts/shared'); "
            "from opportunity import Opportunity as A; "
            "from app.domain import Opportunity as B; "
            "assert A is B, f'Classes differ: {A!r} vs {B!r}'; "
            "print('OK')",
        ])
        assert result.returncode == 0, (
            f"Opportunity identity check failed:\n{result.stderr}"
        )

    def test_scan_help(self):
        """scan.py --help runs without import errors."""
        result = _run_script(["scripts/scan.py", "--help"])
        assert result.returncode == 0, (
            f"scan.py --help failed:\n{result.stderr}"
        )
