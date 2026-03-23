import os
import sys
import subprocess
import logging
from datetime import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

# Shared imports
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401 -- configures sys.path
from logging_setup import setup_logging

load_dotenv()
log = setup_logging("scheduler")

# Interval in minutes
INTERVAL = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))

def run_pipeline(prediction: bool = False, execute: bool = True):
    """Run the executor pipeline."""
    cmd = [sys.executable, str(Path(__file__).parent / "kalshi_executor.py"), "run"]
    if prediction:
        cmd.append("--prediction")
    if execute:
        cmd.append("--execute")

    mode = "Prediction" if prediction else "Sports"
    log.info(f"Starting {mode} pipeline run at {datetime.now().isoformat()}...")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            log.error(f"{mode} pipeline failed with exit code {result.returncode}")
            log.error(f"Stderr: {result.stderr}")
        else:
            log.info(f"{mode} pipeline finished successfully.")
            # Print last few lines of output for monitoring
            out_lines = result.stdout.splitlines()
            if len(out_lines) > 5:
                for line in out_lines[-5:]:
                    log.info(f"  {line}")
    except Exception as e:
        log.error(f"Exception running {mode} pipeline: {e}")

def run_all():
    log.info("--- Scheduled Run Started ---")
    run_pipeline(prediction=False, execute=True)
    run_pipeline(prediction=True, execute=True)
    log.info("--- Scheduled Run Complete ---")

def main():
    log.info(f"Starting Kalshi automated scheduler. Interval: {INTERVAL} minutes.")

    scheduler = BlockingScheduler()

    # Run once immediately
    run_all()

    # Schedule recurring
    scheduler.add_job(run_all, 'interval', minutes=INTERVAL)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")

if __name__ == "__main__":
    main()
