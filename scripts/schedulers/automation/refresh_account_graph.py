"""
refresh_account_graph.py
Weekly unattended refresh of the private Kalshi account-growth graph.

Pipeline (all local — needs .env Kalshi keys + the local settlements ledger):
  1. Pull the live snapshot (cash / portfolio / open positions) from the Kalshi API.
  2. Regenerate the interactive HTML + static PNG into the `latest/` snapshot folder,
     which lives under `docs/my-documents/` — gitignored, never published.

This graph carries real account-balance figures and is intentionally kept off the
public repo and off GitHub Pages (see CHANGELOG 2026-09-07).

Run manually:
    .venv/Scripts/python.exe scripts/schedulers/automation/refresh_account_graph.py

Installed as a weekly Windows task via:
    python scripts/schedulers/automation/install_windows_task.py install account-graph
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # automation -> schedulers -> scripts -> root
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
GRAPH_SCRIPT_DIR = PROJECT_ROOT / "docs" / "my-documents" / "account-graph" / "Script"
LATEST_DIR = PROJECT_ROOT / "docs" / "my-documents" / "account-graph" / "latest"

LOG_PATH = PROJECT_ROOT / "logs" / "account_graph_refresh.log"

SNAPSHOT_RE = re.compile(r"CASH=(-?[\d.]+)\s+PORTFOLIO=(-?[\d.]+)\s+POSITIONS=(\d+)")


# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    """Print + append to the rolling log file."""
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    """Run a command, capturing output as text."""
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


# ── Steps ─────────────────────────────────────────────────────────────────────

def pull_snapshot() -> tuple[float, float, int]:
    """Pull live cash / portfolio / open-position count from the Kalshi API."""
    result = run([str(PYTHON), str(GRAPH_SCRIPT_DIR / "pull_snapshot.py")])
    if result.returncode != 0:
        raise RuntimeError(f"pull_snapshot.py failed: {result.stderr.strip() or result.stdout.strip()}")
    m = SNAPSHOT_RE.search(result.stdout)
    if not m:
        raise RuntimeError(f"could not parse snapshot from: {result.stdout.strip()!r}")
    cash, portfolio, positions = float(m.group(1)), float(m.group(2)), int(m.group(3))
    log(f"Snapshot: cash=${cash:.2f} portfolio=${portfolio:.2f} positions={positions}")
    return cash, portfolio, positions


def build(cash: float, portfolio: float, positions: int) -> None:
    """Regenerate the interactive HTML and static PNG into LATEST_DIR."""
    common = ["--cash", str(cash), "--portfolio", str(portfolio),
              "--positions", str(positions), "--out-dir", str(LATEST_DIR)]
    for script in ("build_account_graph.py", "build_account_png.py"):
        result = run([str(PYTHON), str(GRAPH_SCRIPT_DIR / script), *common])
        if result.returncode != 0:
            # PNG is non-critical.
            if script == "build_account_png.py":
                log(f"WARN: {script} failed (non-fatal): {result.stderr.strip()}")
                continue
            raise RuntimeError(f"{script} failed: {result.stderr.strip() or result.stdout.strip()}")
        log(f"Built {script} -> {LATEST_DIR}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    log("=== account-graph refresh start ===")
    try:
        cash, portfolio, positions = pull_snapshot()
        build(cash, portfolio, positions)
    except Exception as e:  # noqa: BLE001 — log and surface a non-zero exit to the scheduler
        log(f"ERROR: {e}")
        return 1
    log("=== account-graph refresh done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
