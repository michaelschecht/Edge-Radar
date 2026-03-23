"""
sports_scheduler.py
Scheduler for sports betting markets (NBA, NHL, MLB, NFL, NCAA, soccer, etc.).

Calls the existing edge_detector → kalshi_executor pipeline with the
sport-specific filters defined in the scheduler profile.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401

from base_scheduler import BaseScheduler
from scheduler_config import SchedulerProfile

from kalshi_client import make_prod_client
from edge_detector import scan_all_markets
from kalshi_executor import execute_pipeline


class SportsScheduler(BaseScheduler):
    """Scheduler for a specific sport or group of sports."""

    def run_pipeline(self) -> bool:
        try:
            client = make_prod_client()

            # Scan for opportunities using sport-specific filters
            opportunities = scan_all_markets(
                client=client,
                filter_prefixes=self.profile.filters or None,
            )

            if not opportunities:
                self.log.info(
                    f"[{self.profile.name}] No opportunities found this cycle."
                )
                return True  # no opportunities is not a failure

            self.log.info(
                f"[{self.profile.name}] Found {len(opportunities)} opportunities."
            )

            # Execute pipeline (respects DRY_RUN via --execute flag)
            execute_pipeline(
                client=client,
                opportunities=opportunities,
                execute=not self.is_dry_run,
                max_bets=self.profile.max_bets,
            )

            return True

        except Exception:
            self.log.exception(f"[{self.profile.name}] Pipeline error")
            return False
