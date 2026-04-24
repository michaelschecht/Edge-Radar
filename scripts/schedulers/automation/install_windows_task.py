"""
install_windows_task.py
Create, update, or remove Edge-Radar scheduled tasks in Windows Task Scheduler.

Supports multiple task profiles for different automation scenarios:
  - scan:         Morning preview scan (no bets placed)
  - execute:      Morning scan + live execution
  - settle:       Nightly settlement + P&L report
  - next-day:     Evening scan + execute for tomorrow's games
  - calibration:  Monthly 30-day calibration report (R16)

Usage:
    python scripts/schedulers/automation/install_windows_task.py install scan
    python scripts/schedulers/automation/install_windows_task.py install execute
    python scripts/schedulers/automation/install_windows_task.py install settle
    python scripts/schedulers/automation/install_windows_task.py install next-day
    python scripts/schedulers/automation/install_windows_task.py install calibration
    python scripts/schedulers/automation/install_windows_task.py install all
    python scripts/schedulers/automation/install_windows_task.py status
    python scripts/schedulers/automation/install_windows_task.py remove all
    python scripts/schedulers/automation/install_windows_task.py run scan

See docs/setup/AUTOMATION_GUIDE.md for the full setup walkthrough.
"""

import sys
import subprocess
import argparse
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCHEDULERS = PROJECT_ROOT / "scripts" / "schedulers"

# Task profiles: name -> (task_name, schedule_time, script_path, description)
TASK_PROFILES = {
    "scan": {
        "task_name": "Edge-Radar\\MorningScan",
        "time": "08:00",
        "script": SCHEDULERS / "same_day_executions" / "same_day_scan.bat",
        "description": "Morning preview scan (no bets) at 8 AM",
    },
    "execute": {
        "task_name": "Edge-Radar\\MorningExecute",
        "time": "08:00",
        "script": SCHEDULERS / "same_day_executions" / "same_day_execute.bat",
        "description": "Morning scan + live execution at 8 AM",
    },
    "settle": {
        "task_name": "Edge-Radar\\NightlySettle",
        "time": "23:00",
        "script": PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        "args": f'"{PROJECT_ROOT / "scripts" / "kalshi" / "kalshi_settler.py"}" settle',
        "description": "Nightly settlement + P&L update at 11 PM",
    },
    "next-day": {
        "task_name": "Edge-Radar\\NextDayExecute",
        "time": "21:00",
        "script": SCHEDULERS / "next_day_executions" / "next_day_execute.bat",
        "description": "Evening scan + execute tomorrow's games at 9 PM",
    },
    "calibration": {
        "task_name": "Edge-Radar\\MonthlyCalibration",
        "time": "02:00",
        "schedule": "MONTHLY",
        "day": "1",
        "script": PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        "args": f'"{PROJECT_ROOT / "scripts" / "kalshi" / "model_calibration.py"}" --days 30 --save',
        "description": "Monthly 30-day calibration report (R16, day 1 at 2 AM)",
    },
}


def _run_schtasks(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a schtasks command and return the result."""
    return subprocess.run(["schtasks"] + args, capture_output=True, text=True, check=check)


# ── Commands ─────────────────────────────────────────────────────────────────

def install(profile_name: str):
    """Create a scheduled task for the given profile."""
    profile = TASK_PROFILES[profile_name]
    task_name = profile["task_name"]
    script = profile["script"]

    if not script.exists():
        print(f"ERROR: Script not found at {script}")
        sys.exit(1)

    # Build the command to run
    if "args" in profile:
        tr = f'"{script}" {profile["args"]}'
    else:
        tr = f'"{script}"'

    # Schedule — default is DAILY. MONTHLY profiles supply /D for the day of month.
    schedule = profile.get("schedule", "DAILY")
    sc_args = ["/SC", schedule]
    if schedule == "MONTHLY":
        sc_args += ["/D", profile.get("day", "1")]
    sc_args += ["/ST", profile["time"]]

    # Remove existing task if present (update)
    _run_schtasks(["/Delete", "/TN", task_name, "/F"], check=False)

    result = _run_schtasks([
        "/Create",
        "/TN", task_name,
        "/TR", tr,
        *sc_args,
        "/F",
    ], check=False)

    if result.returncode == 0:
        cadence = (
            f"{profile['time']} daily" if schedule == "DAILY"
            else f"{profile['time']} monthly (day {profile.get('day', '1')})"
        )
        print(f"  [OK] {profile_name}: {profile['description']}")
        print(f"       Task:   {task_name}")
        print(f"       Time:   {cadence}")
        print(f"       Script: {script}")
    else:
        print(f"  [FAIL] {profile_name}: {result.stderr.strip()}")
        return False
    return True


def remove(profile_name: str):
    """Remove a scheduled task."""
    task_name = TASK_PROFILES[profile_name]["task_name"]
    result = _run_schtasks(["/Delete", "/TN", task_name, "/F"], check=False)

    if result.returncode == 0:
        print(f"  [OK] Removed: {task_name}")
    else:
        print(f"  [--] Not found: {task_name}")


def status():
    """Check all Edge-Radar tasks."""
    found = False
    for name, profile in TASK_PROFILES.items():
        task_name = profile["task_name"]
        result = _run_schtasks(["/Query", "/TN", task_name, "/V", "/FO", "LIST"], check=False)

        if result.returncode == 0:
            found = True
            print(f"\n  {name} ({profile['description']})")
            for line in result.stdout.splitlines():
                line = line.strip()
                if any(k in line for k in ["Status", "Next Run", "Last Run", "Last Result"]):
                    print(f"    {line}")
        else:
            print(f"\n  {name}: NOT installed")

    if not found:
        print("\nNo Edge-Radar tasks installed.")
        print("Run: python scripts/schedulers/automation/install_windows_task.py install all")


def run_now(profile_name: str):
    """Trigger a task to run immediately."""
    task_name = TASK_PROFILES[profile_name]["task_name"]
    result = _run_schtasks(["/Run", "/TN", task_name], check=False)

    if result.returncode == 0:
        print(f"  [OK] Triggered: {profile_name}")
    else:
        print(f"  [FAIL] Could not run '{profile_name}'. Is it installed?")
        print(f"         {result.stderr.strip()}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Manage Edge-Radar scheduled tasks on Windows",
        epilog="See docs/setup/AUTOMATION_GUIDE.md for the full walkthrough.",
    )
    parser.add_argument(
        "command", choices=["install", "remove", "status", "run"],
        help="install | remove | status | run",
    )
    parser.add_argument(
        "profile", nargs="?", default="all",
        choices=list(TASK_PROFILES.keys()) + ["all"],
        help="Task profile (default: all)",
    )

    args = parser.parse_args()
    profiles = list(TASK_PROFILES.keys()) if args.profile == "all" else [args.profile]

    if args.command == "status":
        status()
    elif args.command == "install":
        print(f"Installing Edge-Radar scheduled tasks...\n")
        for p in profiles:
            install(p)
        print(f"\nManage via: taskschd.msc (Task Scheduler GUI)")
    elif args.command == "remove":
        print(f"Removing Edge-Radar scheduled tasks...\n")
        for p in profiles:
            remove(p)
    elif args.command == "run":
        for p in profiles:
            run_now(p)


if __name__ == "__main__":
    main()
