"""
install_windows_task.py
Create, update, or remove Edge-Radar scheduled tasks in Windows Task Scheduler.

Supports multiple task profiles for different automation scenarios:
  - scan:         Morning preview scan (no bets placed)
  - execute:      Morning scan + live execution
  - settle:       Nightly settlement + P&L report
  - next-day:     Evening scan + execute for tomorrow's games
  - calibration:  Weekly calibration report + C8 stdev recalibration
  - account-graph: Weekly account-growth graph refresh + publish

TASK FOLDER — read this before running `install`.
    Tasks are created under a Task Scheduler folder, `TASK_FOLDER` below,
    default "Edge-Radar" and overridable per-run with --task-folder.
    This file is a **reference template**, not a turnkey
    installer for any particular machine (see docs/task-schedules/README.md) —
    the repo owner's live tasks, for instance, live under
    "Edge-Radar-MikesAILab" and were built by other means with richer settings
    (run-as principal, wake/retry policy) than `schtasks /Create` sets here.

    That mismatch is a trap in both directions, so it is now checked rather
    than left to the reader:

      - pointed at a *different* folder than your live tasks, `install` would
        silently create a **parallel duplicate** — a second settler, or worse a
        second execute task placing real bets alongside the first;
      - pointed at the *same* folder, it would silently **clobber** a live task,
        replacing a carefully-configured definition with the minimal one here.

    `install` therefore refuses when a task of the same leaf name already
    exists in any other folder, and reports both paths. Pass --force once you
    have decided which one you actually want.

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

import csv
import io
import sys
import subprocess
import argparse
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SCHEDULERS = PROJECT_ROOT / "scripts" / "schedulers"

# Task Scheduler folder these profiles install into, overridable per-run with
# --task-folder. See the module docstring: this is a template, so it
# deliberately does NOT default to any particular machine's live folder.
#
# Deliberately a CLI flag rather than an env var: this is an installer-only,
# Windows-only developer setting, not a runtime knob for the betting system, so
# it has no business in app/config.py (and `check_config_centralization.py`
# correctly rejects a bare os.environ read here).
TASK_FOLDER = "Edge-Radar"

# Task profiles: name -> (leaf, schedule_time, script_path, description).
# The Task Scheduler folder is TASK_FOLDER, applied centrally by task_name().
TASK_PROFILES = {
    "scan": {
        "leaf": "MorningScan",
        "time": "08:00",
        "script": SCHEDULERS / "same_day_executions" / "same_day_scan.bat",
        "description": "Morning preview scan (no bets) at 8 AM",
    },
    "execute": {
        "leaf": "MorningExecute",
        "time": "08:00",
        "script": SCHEDULERS / "same_day_executions" / "same_day_execute.bat",
        "description": "Morning scan + live execution at 8 AM",
    },
    "settle": {
        "leaf": "NightlySettle",
        "time": "23:00",
        "script": PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        "args": f'"{PROJECT_ROOT / "scripts" / "kalshi" / "kalshi_settler.py"}" settle',
        "description": "Nightly settlement + P&L update at 11 PM",
    },
    "next-day": {
        "leaf": "NextDayExecute",
        "time": "21:00",
        "script": SCHEDULERS / "next_day_executions" / "next_day_execute.bat",
        "description": "Evening scan + execute tomorrow's games at 9 PM",
    },
    # 2026-07-31: was MONTHLY / day 1 / 02:00 under the name MonthlyCalibration.
    # That task was registered but had NEVER run (Last Run 11/30/1999) and was
    # deleted the same day. The task actually doing the work on the owner's
    # machine is a WEEKLY one (Sun 7 PM) driven by
    # scripts/schedulers/maintenance/calibration.bat, which this installer did
    # not describe at all. Reprofiled to weekly so the template teaches the
    # cadence that actually works, and pointed at the .bat so the --days
    # argument has exactly one definition (a --days 7 window silently disables
    # the C8 stdev loop -- see the .bat header and tests/test_calibration_config).
    # The leaf is "Calibration" to match the live task; see TASK_FOLDER above
    # for how folder mismatches are now handled.
    "calibration": {
        "leaf": "Calibration",
        "time": "19:00",
        "schedule": "WEEKLY",
        "day": "SUN",
        "script": SCHEDULERS / "maintenance" / "calibration.bat",
        "description": "Weekly calibration report + C8 stdev recalibration (Sun 7 PM)",
    },
    "account-graph": {
        "leaf": "WeeklyAccountGraph",
        "time": "09:00",
        "schedule": "WEEKLY",
        "day": "SUN",
        "script": PROJECT_ROOT / ".venv" / "Scripts" / "python.exe",
        "args": f'"{PROJECT_ROOT / "scripts" / "schedulers" / "automation" / "refresh_account_graph.py"}"',
        "description": "Weekly account-graph refresh + publish to GitHub Pages (Sun 9 AM)",
    },
}


def _run_schtasks(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    """Run a schtasks command and return the result."""
    return subprocess.run(["schtasks"] + args, capture_output=True, text=True, check=check)


def task_name(profile_name: str) -> str:
    """Full `Folder\\Leaf` path this profile installs to."""
    return f"{TASK_FOLDER}\\{TASK_PROFILES[profile_name]['leaf']}"


def _all_task_paths() -> list[str]:
    """Every registered task path on the machine (best-effort).

    Returns [] if schtasks can't be queried — a machine we cannot inspect is
    not a reason to block an install, only a reason to skip the warning.
    """
    result = _run_schtasks(["/Query", "/FO", "CSV", "/NH"], check=False)
    if result.returncode != 0 or not result.stdout:
        return []
    paths = []
    for row in csv.reader(io.StringIO(result.stdout)):
        if row and row[0].strip() and row[0].strip() != "TaskName":
            paths.append(row[0].strip())
    return paths


def _conflicts(profile_name: str) -> list[str]:
    """Same leaf name registered under a DIFFERENT folder.

    This is the check that makes the folder mismatch visible. Installing over
    the top of your own task is fine and expected (that is how `install`
    updates). Installing a second copy of a task that already exists somewhere
    else is almost never what anyone wants — two settlers double-settle, and
    two execute tasks place two sets of real bets.
    """
    leaf = TASK_PROFILES[profile_name]["leaf"].lower()
    mine = task_name(profile_name).lower()
    return [
        path for path in _all_task_paths()
        if path.rsplit("\\", 1)[-1].lower() == leaf and path.lstrip("\\").lower() != mine
    ]


# ── Commands ─────────────────────────────────────────────────────────────────

def install(profile_name: str, force: bool = False):
    """Create a scheduled task for the given profile."""
    profile = TASK_PROFILES[profile_name]
    tn = task_name(profile_name)
    script = profile["script"]

    if not script.exists():
        print(f"ERROR: Script not found at {script}")
        sys.exit(1)

    clashes = _conflicts(profile_name)
    if clashes and not force:
        print(f"  [SKIP] {profile_name}: '{profile['leaf']}' already exists elsewhere.")
        for path in clashes:
            print(f"         existing: {path}")
        print(f"         would create: \\{tn}")
        print( "         Installing anyway would leave BOTH registered and both")
        print( "         would fire. Re-run with --task-folder set to the folder")
        print( "         you actually manage, or --force to truly want a second.")
        return False

    # Build the command to run
    if "args" in profile:
        tr = f'"{script}" {profile["args"]}'
    else:
        tr = f'"{script}"'

    # Schedule — default is DAILY. MONTHLY supplies /D for the day of month;
    # WEEKLY supplies /D for the weekday (e.g. SUN).
    schedule = profile.get("schedule", "DAILY")
    sc_args = ["/SC", schedule]
    if schedule == "MONTHLY":
        sc_args += ["/D", profile.get("day", "1")]
    elif schedule == "WEEKLY":
        sc_args += ["/D", profile.get("day", "SUN")]
    sc_args += ["/ST", profile["time"]]

    # Remove existing task if present (update)
    _run_schtasks(["/Delete", "/TN", tn, "/F"], check=False)

    result = _run_schtasks([
        "/Create",
        "/TN", tn,
        "/TR", tr,
        *sc_args,
        "/F",
    ], check=False)

    if result.returncode == 0:
        if schedule == "DAILY":
            cadence = f"{profile['time']} daily"
        elif schedule == "WEEKLY":
            cadence = f"{profile['time']} weekly ({profile.get('day', 'SUN')})"
        else:
            cadence = f"{profile['time']} monthly (day {profile.get('day', '1')})"
        print(f"  [OK] {profile_name}: {profile['description']}")
        print(f"       Task:   {tn}")
        print(f"       Time:   {cadence}")
        print(f"       Script: {script}")
    else:
        print(f"  [FAIL] {profile_name}: {result.stderr.strip()}")
        return False
    return True


def remove(profile_name: str):
    """Remove a scheduled task."""
    tn = task_name(profile_name)
    result = _run_schtasks(["/Delete", "/TN", tn, "/F"], check=False)

    if result.returncode == 0:
        print(f"  [OK] Removed: {tn}")
    else:
        print(f"  [--] Not found: {tn}")


def status():
    """Check all Edge-Radar tasks."""
    print(f"Task folder: \\{TASK_FOLDER}\\  (override with --task-folder)")
    found = False
    for name, profile in TASK_PROFILES.items():
        tn = task_name(name)
        result = _run_schtasks(["/Query", "/TN", tn, "/V", "/FO", "LIST"], check=False)

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
    result = _run_schtasks(["/Run", "/TN", task_name(profile_name)], check=False)

    if result.returncode == 0:
        print(f"  [OK] Triggered: {profile_name}")
    else:
        print(f"  [FAIL] Could not run '{profile_name}'. Is it installed?")
        print(f"         {result.stderr.strip()}")


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    # Rebound from --task-folder below; declared up front because the argparse
    # setup reads TASK_FOLDER for the flag's default and help text.
    global TASK_FOLDER

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
    parser.add_argument(
        "--task-folder", default=TASK_FOLDER,
        help=f"Task Scheduler folder to manage (default: {TASK_FOLDER}). Point "
             "this at the folder your real tasks live in to update them in place.",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Install even when a task of the same name exists in another "
             "folder (leaves BOTH registered and both will fire).",
    )

    args = parser.parse_args()
    TASK_FOLDER = args.task_folder.strip("\\/")

    profiles = list(TASK_PROFILES.keys()) if args.profile == "all" else [args.profile]

    if args.command == "status":
        status()
    elif args.command == "install":
        print(f"Installing Edge-Radar scheduled tasks into \\{TASK_FOLDER}\\ ...\n")
        for p in profiles:
            install(p, force=args.force)
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
