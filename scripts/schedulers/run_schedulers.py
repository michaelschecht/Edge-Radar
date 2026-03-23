"""
run_schedulers.py
Entry point for launching one or more betting schedulers.

Usage:
    # Launch all enabled schedulers (reads SCHED_* env vars)
    python scripts/schedulers/run_schedulers.py

    # Launch a single scheduler by name
    python scripts/schedulers/run_schedulers.py --only nba

    # List all registered profiles and their status
    python scripts/schedulers/run_schedulers.py --list
"""

import sys
import signal
import argparse
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401
from logging_setup import setup_logging

from scheduler_config import load_all_profiles, load_enabled_profiles, SchedulerProfile
from sports_scheduler import SportsScheduler
from prediction_scheduler import PredictionScheduler

log = setup_logging("run_schedulers")


def create_scheduler(profile: SchedulerProfile):
    """Factory: return the right scheduler subclass for a profile."""
    if profile.prediction:
        return PredictionScheduler(profile)
    return SportsScheduler(profile)


def list_profiles():
    """Print a table of all registered scheduler profiles."""
    profiles = load_all_profiles()
    print(f"\n{'Name':<12} {'Enabled':<9} {'Interval':<10} {'Filters':<25} "
          f"{'Max Bets':<10} {'Type'}")
    print("-" * 85)
    for p in profiles:
        kind = "prediction" if p.prediction else "sports"
        filters = ", ".join(p.filters) if p.filters else "(all)"
        enabled = "YES" if p.enabled else "no"
        print(f"{p.name:<12} {enabled:<9} {p.interval_minutes:<10} "
              f"{filters:<25} {p.max_bets:<10} {kind}")
    print()


def run_single(name: str):
    """Launch a single scheduler by name (blocking)."""
    profiles = load_all_profiles()
    match = [p for p in profiles if p.name == name]

    if not match:
        log.error(f"No scheduler profile found for '{name}'. "
                  f"Available: {[p.name for p in profiles]}")
        sys.exit(1)

    profile = match[0]
    if not profile.enabled:
        log.warning(f"Scheduler '{name}' is not enabled. "
                    f"Set SCHED_{name.upper()}_ENABLED=true in .env to enable.")
        sys.exit(1)

    scheduler = create_scheduler(profile)
    scheduler.start(blocking=True)


def run_all():
    """Launch all enabled schedulers in background threads."""
    profiles = load_enabled_profiles()

    if not profiles:
        log.warning(
            "No schedulers enabled. Set SCHED_{NAME}_ENABLED=true in .env. "
            "Run with --list to see available profiles."
        )
        sys.exit(0)

    log.info(f"Launching {len(profiles)} enabled scheduler(s): "
             f"{[p.name for p in profiles]}")

    schedulers = []
    threads = []

    for profile in profiles:
        sched = create_scheduler(profile)
        schedulers.append(sched)

        t = threading.Thread(
            target=sched.start,
            kwargs={"blocking": True},
            name=f"sched_{profile.name}",
            daemon=True,
        )
        threads.append(t)
        t.start()
        log.info(f"  Started: {profile.name}")

    # Wait for interrupt
    def shutdown(signum, frame):
        log.info("Shutdown signal received. Stopping all schedulers...")
        for s in schedulers:
            s.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    # Block main thread
    for t in threads:
        t.join()


def main():
    parser = argparse.ArgumentParser(
        description="Launch Kalshi betting schedulers"
    )
    parser.add_argument(
        "--only", type=str, default=None,
        help="Launch a single scheduler by name (e.g., --only nba)"
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all registered scheduler profiles and exit"
    )

    args = parser.parse_args()

    if args.list:
        list_profiles()
        return

    if args.only:
        run_single(args.only)
    else:
        run_all()


if __name__ == "__main__":
    main()
