"""
prediction_scheduler.py
Scheduler for prediction markets (crypto, weather, S&P 500, etc.).

Calls the prediction_scanner → kalshi_executor pipeline with the
market-specific filters defined in the scheduler profile.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401

from base_scheduler import BaseScheduler
from scheduler_config import SchedulerProfile

from kalshi_client import make_prod_client
from prediction_scanner import scan_prediction_markets
from kalshi_executor import execute_pipeline


class PredictionScheduler(BaseScheduler):
    """Scheduler for prediction market categories."""

    def run_pipeline(self) -> bool:
        try:
            client = make_prod_client()

            # Scan for prediction market opportunities
            opportunities = scan_prediction_markets(
                client=client,
                filter_categories=self.profile.filters or None,
            )

            if not opportunities:
                self.log.info(
                    f"[{self.profile.name}] No opportunities found this cycle."
                )
                return True

            self.log.info(
                f"[{self.profile.name}] Found {len(opportunities)} opportunities."
            )

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
