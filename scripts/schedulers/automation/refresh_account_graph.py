"""
refresh_account_graph.py
Weekly unattended refresh of the public Kalshi account-growth graph.

Pipeline (all local — needs .env Kalshi keys + the local settlements ledger):
  1. Pull the live snapshot (cash / portfolio / open positions) from the Kalshi API.
  2. Regenerate the interactive HTML + static PNG into the `latest/` snapshot folder.
  3. Copy the HTML into the GitHub-Pages-published tree (`.claude/html/<obscure>.html`).
  4. Push ONLY that one file to `master` via the `gh` contents API, which triggers the
     Pages deploy. The local working branch is never touched.

Step 4 is best-effort: if `gh` is unavailable or the push fails, the local graph is still
regenerated and the failure is logged — the task never hard-fails on the publish step.

Run manually:
    .venv/Scripts/python.exe scripts/schedulers/automation/refresh_account_graph.py

Installed as a weekly Windows task via:
    python scripts/schedulers/automation/install_windows_task.py install account-graph
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # automation -> schedulers -> scripts -> root
PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
GRAPH_SCRIPT_DIR = PROJECT_ROOT / "docs" / "my-documents" / "account-graph" / "Script"
LATEST_DIR = PROJECT_ROOT / "docs" / "my-documents" / "account-graph" / "latest"

# The published file lives at an unguessable path inside the only directory GitHub
# Pages serves (.claude/html/). Linked from the homepage with rel="nofollow" + noindex,
# so it's lightly hidden, not access-controlled — do not put secrets in the graph.
PUBLISHED_NAME = "account-40c3eb1d3d3cb9c4e07fee61.html"
PUBLISHED_REL = f".claude/html/{PUBLISHED_NAME}"
PUBLISHED_PATH = PROJECT_ROOT / ".claude" / "html" / PUBLISHED_NAME

REPO = "michaelschecht/Edge-Radar"
BRANCH = "master"

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
            # PNG is non-critical; the HTML is what gets published.
            if script == "build_account_png.py":
                log(f"WARN: {script} failed (non-fatal): {result.stderr.strip()}")
                continue
            raise RuntimeError(f"{script} failed: {result.stderr.strip() or result.stdout.strip()}")
        log(f"Built {script} -> {LATEST_DIR}")


def publish_local() -> str:
    """Copy the freshly built HTML into the Pages-served tree. Returns the HTML text."""
    html = (LATEST_DIR / "account_graph.html").read_text(encoding="utf-8")
    PUBLISHED_PATH.write_text(html, encoding="utf-8")
    log(f"Copied HTML -> {PUBLISHED_REL}")
    return html


def push_to_master(html: str) -> None:
    """Push only the published HTML file to master via the gh contents API."""
    if not _gh_available():
        log("WARN: gh CLI not found — skipping push. Local graph regenerated only.")
        return

    # Look up the existing blob sha on master (required to update, omitted to create).
    sha = None
    head = run(["gh", "api", f"repos/{REPO}/contents/{PUBLISHED_REL}?ref={BRANCH}"])
    if head.returncode == 0:
        try:
            sha = json.loads(head.stdout).get("sha")
        except json.JSONDecodeError:
            pass

    body = {
        "message": f"chore(pages): weekly account-graph refresh ({datetime.now(timezone.utc).date()})",
        "content": base64.b64encode(html.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if sha:
        body["sha"] = sha

    # base64 of the HTML exceeds the Windows command-line limit, so pass the body via stdin.
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(body, tf)
        body_path = tf.name
    try:
        result = run(["gh", "api", "--method", "PUT",
                      f"repos/{REPO}/contents/{PUBLISHED_REL}", "--input", body_path])
    finally:
        Path(body_path).unlink(missing_ok=True)

    if result.returncode == 0:
        log(f"Pushed {PUBLISHED_REL} to {BRANCH} — Pages deploy triggered.")
    else:
        log(f"WARN: gh push failed (non-fatal): {result.stderr.strip() or result.stdout.strip()}")


def _gh_available() -> bool:
    try:
        return run(["gh", "--version"]).returncode == 0
    except FileNotFoundError:
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    log("=== account-graph refresh start ===")
    try:
        cash, portfolio, positions = pull_snapshot()
        build(cash, portfolio, positions)
        html = publish_local()
        push_to_master(html)
    except Exception as e:  # noqa: BLE001 — log and surface a non-zero exit to the scheduler
        log(f"ERROR: {e}")
        return 1
    log("=== account-graph refresh done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
