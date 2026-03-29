"""
Logitech Brand Intelligence Platform — Auto Scheduler
Runs scrape.py automatically on a configurable interval.

Usage:
  python scheduler.py                    # scrape all channels every 6 hours
  python scheduler.py --interval 2       # every 2 hours
  python scheduler.py --channels amazon_us amazon_uk --interval 1  # every hour
  python scheduler.py --tier 3 --interval 12  # global Amazon every 12 hours

Run this in a separate terminal alongside the dashboard:
  Terminal 1: streamlit run dashboard.py
  Terminal 2: python scheduler.py
"""

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] scheduler — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")


def run_scrape(channels=None, tier=None):
    """Run scrape.py as a subprocess."""
    cmd = [sys.executable, "scrape.py"]
    if tier:
        cmd.append(f"tier{tier}")
    elif channels:
        cmd.extend(channels)

    logger.info(f"Starting scrape: {' '.join(cmd)}")
    start = datetime.now(timezone.utc)

    try:
        result = subprocess.run(
            cmd,
            capture_output=False,   # let logs print to terminal
            text=True,
            cwd=".",
        )
        elapsed = (datetime.now(timezone.utc) - start).seconds
        if result.returncode == 0:
            logger.info(f"Scrape completed in {elapsed}s ✓")
        else:
            logger.error(f"Scrape exited with code {result.returncode}")
    except Exception as e:
        logger.error(f"Scrape failed: {e}")


def format_next(next_run):
    """Human-readable countdown."""
    remaining = (next_run - datetime.now(timezone.utc)).seconds
    mins, secs = divmod(remaining, 60)
    hours, mins = divmod(mins, 60)
    if hours:
        return f"{hours}h {mins}m"
    if mins:
        return f"{mins}m {secs}s"
    return f"{secs}s"


def main():
    parser = argparse.ArgumentParser(description="Logitech Intelligence Auto Scheduler")
    parser.add_argument("--interval", type=float, default=6.0,
                        help="Hours between scrapes (default: 6)")
    parser.add_argument("--channels", nargs="*",
                        help="Specific channels to scrape")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3],
                        help="Scrape all channels of a tier")
    parser.add_argument("--no-startup", action="store_true",
                        help="Skip the initial scrape on startup")
    args = parser.parse_args()

    interval_seconds = int(args.interval * 3600)

    logger.info("=" * 60)
    logger.info("Logitech Brand Intelligence — Auto Scheduler")
    logger.info(f"Interval  : every {args.interval}h ({interval_seconds}s)")
    if args.tier:
        logger.info(f"Channels  : Tier {args.tier}")
    elif args.channels:
        logger.info(f"Channels  : {args.channels}")
    else:
        logger.info("Channels  : all")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 60)

    run_count = 0

    # Run immediately on startup (unless --no-startup)
    if not args.no_startup:
        logger.info("Running initial scrape on startup...")
        run_scrape(channels=args.channels, tier=args.tier)
        run_count += 1

    while True:
        from datetime import timedelta
        next_run = datetime.now(timezone.utc) + timedelta(seconds=interval_seconds)
        logger.info(f"Next scrape at {next_run.strftime('%Y-%m-%d %H:%M:%S UTC')} "
                    f"(in {args.interval}h) — run #{run_count + 1} completed so far")

        # Sleep in 60s chunks so Ctrl+C is responsive
        remaining = interval_seconds
        while remaining > 0:
            sleep_time = min(60, remaining)
            time.sleep(sleep_time)
            remaining -= sleep_time
            if remaining > 0 and remaining % 600 == 0:
                logger.info(f"Next scrape in {format_next(next_run)}")

        logger.info(f"Starting scheduled scrape #{run_count + 1}...")
        run_scrape(channels=args.channels, tier=args.tier)
        run_count += 1


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
        sys.exit(0)