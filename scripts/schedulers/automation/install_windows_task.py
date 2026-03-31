"""
install_windows_task.py
Create, update, or remove the Edge-Radar daily scan as a Windows Scheduled Task.

Usage:
    python scripts/schedulers/automation/install_windows_task.py install    # Create the task
    python scripts/schedulers/automation/install_windows_task.py remove     # Remove the task
    python scripts/schedulers/automation/install_windows_task.py status     # Check if task exists
    python scripts/schedulers/automation/install_windows_task.py run        # Run the task now (test)
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

TASK_NAME = "Edge-Radar\\DailyScan"
SCAN_TIME = "08:00"  # 8:00 AM local time
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "schedulers" / "automation" / "daily_sports_scan.py"


def _run_schtasks(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a schtasks command and return the result."""
    cmd = ["schtasks"] + args
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


# ── Commands ─────────────────────────────────────────────────────────────────

def install():
    """Create the scheduled task."""
    if not PYTHON_EXE.exists():
        print(f"ERROR: Python not found at {PYTHON_EXE}")
        print("Make sure .venv is set up: python -m venv .venv && .venv\\Scripts\\pip install -r requirements.txt")
        sys.exit(1)

    if not SCRIPT_PATH.exists():
        print(f"ERROR: Script not found at {SCRIPT_PATH}")
        sys.exit(1)

    # Remove existing task if present (update)
    _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"], check=False)

    # Create the task (no admin required)
    result = _run_schtasks([
        "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{PYTHON_EXE}" "{SCRIPT_PATH}"',
        "/SC", "DAILY",
        "/ST", SCAN_TIME,
        "/F",                 # force overwrite
    ], check=False)

    if result.returncode == 0:
        print(f"Task '{TASK_NAME}' created successfully.")
        print(f"  Schedule:  Daily at {SCAN_TIME}")
        print(f"  Python:    {PYTHON_EXE}")
        print(f"  Script:    {SCRIPT_PATH}")
        print(f"  Working:   {PROJECT_ROOT}")
        print()
        print("Manage via:")
        print(f"  View:    schtasks /Query /TN {TASK_NAME} /V /FO LIST")
        print(f"  Run now: schtasks /Run /TN {TASK_NAME}")
        print(f"  Delete:  schtasks /Delete /TN {TASK_NAME} /F")
        print(f"  GUI:     taskschd.msc (search for '{TASK_NAME}')")
    else:
        print(f"ERROR: Failed to create task.")
        print(result.stderr)
        sys.exit(1)


def remove():
    """Remove the scheduled task."""
    result = _run_schtasks(["/Delete", "/TN", TASK_NAME, "/F"], check=False)

    if result.returncode == 0:
        print(f"Task '{TASK_NAME}' removed.")
    else:
        print(f"Task '{TASK_NAME}' not found or already removed.")


def status():
    """Check if the task exists and show its config."""
    result = _run_schtasks(["/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST"], check=False)

    if result.returncode == 0:
        print(f"Task '{TASK_NAME}' is installed:\n")
        # Show relevant lines
        for line in result.stdout.splitlines():
            line = line.strip()
            if any(k in line for k in ["Task Name", "Status", "Next Run", "Last Run",
                                        "Schedule", "Start Time", "Last Result"]):
                print(f"  {line}")
    else:
        print(f"Task '{TASK_NAME}' is NOT installed.")
        print(f"Run: python scripts/schedulers/install_windows_task.py install")


def run_now():
    """Trigger the task to run immediately."""
    result = _run_schtasks(["/Run", "/TN", TASK_NAME], check=False)

    if result.returncode == 0:
        print(f"Task '{TASK_NAME}' triggered. Check reports/Sports/daily_edge_reports/ for output.")
    else:
        print(f"ERROR: Could not run task. Is it installed?")
        print(result.stderr)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Manage Edge-Radar daily scan as a Windows Scheduled Task"
    )
    parser.add_argument(
        "command", choices=["install", "remove", "status", "run"],
        help="install: create task | remove: delete task | status: check task | run: trigger now"
    )

    args = parser.parse_args()

    if args.command == "install":
        install()
    elif args.command == "remove":
        remove()
    elif args.command == "status":
        status()
    elif args.command == "run":
        run_now()


if __name__ == "__main__":
    main()
