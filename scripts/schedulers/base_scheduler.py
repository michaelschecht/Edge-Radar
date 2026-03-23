"""
base_scheduler.py
Core scheduler class that all market-specific schedulers inherit from.

Handles:
- DRY_RUN enforcement (respects .env setting)
- APScheduler lifecycle (start, stop, graceful shutdown)
- Consecutive failure tracking with automatic pause
- Structured logging per scheduler instance
"""

import sys
import signal
import logging
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

# Shared imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401
from config import DRY_RUN
from logging_setup import setup_logging

from scheduler_config import SchedulerProfile


class BaseScheduler:
    """
    Base class for all betting pipeline schedulers.

    Subclass and override `run_pipeline()` to implement market-specific logic.
    The base class handles scheduling, safety gates, and error tracking.

    Usage:
        class NBAScheduler(BaseScheduler):
            def run_pipeline(self) -> bool:
                # ... your pipeline logic ...
                return True  # success

        sched = NBAScheduler(profile)
        sched.start()  # blocks until interrupted
    """

    # After this many consecutive failures, pause the scheduler
    MAX_CONSECUTIVE_FAILURES = 5

    def __init__(self, profile: SchedulerProfile):
        self.profile = profile
        self.log = setup_logging(f"sched_{profile.name}")
        self._consecutive_failures = 0
        self._total_runs = 0
        self._total_failures = 0
        self._paused = False
        self._scheduler: BlockingScheduler | BackgroundScheduler | None = None

    @property
    def is_dry_run(self) -> bool:
        """Check the global DRY_RUN setting from .env."""
        return DRY_RUN

    def run_pipeline(self) -> bool:
        """
        Execute one cycle of the betting pipeline.

        Override in subclass. Return True on success, False on failure.
        The base class never calls this directly in production —
        it goes through `_guarded_run()` which enforces safety checks.
        """
        raise NotImplementedError("Subclasses must implement run_pipeline()")

    def _guarded_run(self):
        """
        Wrapper that enforces DRY_RUN, tracks failures, and pauses on
        repeated errors.
        """
        if self._paused:
            self.log.warning(
                f"[{self.profile.name}] Scheduler is paused after "
                f"{self.MAX_CONSECUTIVE_FAILURES} consecutive failures. "
                f"Resolve the issue and restart."
            )
            return

        self._total_runs += 1
        ts = datetime.now(timezone.utc).isoformat()
        mode = "DRY RUN" if self.is_dry_run else "LIVE"

        self.log.info(
            f"[{self.profile.name}] --- Run #{self._total_runs} ({mode}) "
            f"at {ts} ---"
        )

        try:
            success = self.run_pipeline()
        except Exception:
            self.log.exception(
                f"[{self.profile.name}] Unhandled exception in pipeline"
            )
            success = False

        if success:
            self._consecutive_failures = 0
            self.log.info(f"[{self.profile.name}] Run #{self._total_runs} complete.")
        else:
            self._consecutive_failures += 1
            self._total_failures += 1
            self.log.error(
                f"[{self.profile.name}] Run #{self._total_runs} FAILED "
                f"(consecutive: {self._consecutive_failures}/"
                f"{self.MAX_CONSECUTIVE_FAILURES})"
            )

            if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self._paused = True
                self.log.critical(
                    f"[{self.profile.name}] PAUSED — "
                    f"{self.MAX_CONSECUTIVE_FAILURES} consecutive failures. "
                    f"Manual restart required."
                )

    def start(self, blocking: bool = True):
        """
        Start the scheduler.

        Args:
            blocking: If True, blocks the current thread (use for single-
                      scheduler mode). If False, runs in background (use
                      when orchestrating multiple schedulers).
        """
        cls = BlockingScheduler if blocking else BackgroundScheduler
        self._scheduler = cls()

        self.log.info(
            f"[{self.profile.name}] Starting scheduler — "
            f"interval={self.profile.interval_minutes}m, "
            f"filters={self.profile.filters}, "
            f"max_bets={self.profile.max_bets}, "
            f"prediction={self.profile.prediction}, "
            f"dry_run={self.is_dry_run}"
        )

        # Run once immediately
        self._guarded_run()

        # Schedule recurring runs
        self._scheduler.add_job(
            self._guarded_run,
            "interval",
            minutes=self.profile.interval_minutes,
            id=f"sched_{self.profile.name}",
            replace_existing=True,
        )

        try:
            self._scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            self.log.info(f"[{self.profile.name}] Scheduler stopped.")

    def stop(self):
        """Gracefully shut down the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self.log.info(f"[{self.profile.name}] Scheduler shut down.")

    def status(self) -> dict:
        """Return scheduler health summary."""
        return {
            "name": self.profile.name,
            "enabled": self.profile.enabled,
            "paused": self._paused,
            "dry_run": self.is_dry_run,
            "total_runs": self._total_runs,
            "total_failures": self._total_failures,
            "consecutive_failures": self._consecutive_failures,
            "interval_minutes": self.profile.interval_minutes,
            "filters": self.profile.filters,
            "max_bets": self.profile.max_bets,
            "prediction": self.profile.prediction,
        }
