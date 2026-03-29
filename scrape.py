"""
Standalone scraper — no Streamlit dependency.
Usage:
  python scrape.py                        # all channels
  python scrape.py amazon_us amazon_uk    # specific channels
  python scrape.py tier1                  # tier 1 only
  python scrape.py tier2                  # tier 2 only
  python scrape.py tier3                  # tier 3 only
"""

import sys
import uuid
import logging
from datetime import datetime, timezone

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scraper")

from database.schema import init_db, DB_PATH, RETAIL_CHANNELS
from scrapers.all_channels import build_scraper_registry
from scoring.opportunity_engine import compute_all_scores


def main():
    args = sys.argv[1:]

    conn = init_db(DB_PATH)
    registry = build_scraper_registry(conn)

    # Determine which channels to run
    if not args:
        active = list(registry.keys())
    elif args[0].startswith("tier"):
        tier = int(args[0].replace("tier", ""))
        tier_set = {ch[0] for ch in RETAIL_CHANNELS if ch[3] == tier}
        active = [c for c in registry if c in tier_set]
    else:
        active = [c for c in args if c in registry]
        unknown = [c for c in args if c not in registry]
        if unknown:
            logger.warning(f"Unknown channels: {unknown}")

    run_id = str(uuid.uuid4())
    logger.info(f"Run {run_id[:8]} — {len(active)} channels × 10 products = {len(active)*10} scrapes")

    conn.execute(
        "INSERT INTO scrape_runs (run_id, started_at, channels) VALUES (?,?,?)",
        (run_id, datetime.now(timezone.utc).isoformat(), str(active))
    )
    conn.commit()

    total_scraped = total_success = total_errors = 0

    for channel_id in active:
        scraper, url_map = registry[channel_id]
        logger.info(f"▶  {channel_id} ({len(url_map)} products)")
        try:
            results = scraper.run(url_map)
            ok = sum(1 for r in results if r.get("scrape_status") == "success")
            err = len(results) - ok
            total_scraped += len(results)
            total_success += ok
            total_errors += err
            logger.info(f"   ✓ {channel_id}: {ok}/{len(results)} succeeded")
        except Exception as e:
            logger.error(f"   ✗ {channel_id} crashed: {e}")
            total_errors += len(url_map)

    conn.execute(
        "UPDATE scrape_runs SET finished_at=?, total_scraped=?, total_success=?, total_errors=? WHERE run_id=?",
        (datetime.now(timezone.utc).isoformat(), total_scraped, total_success, total_errors, run_id)
    )
    conn.commit()

    logger.info("⚙  Computing opportunity scores...")
    scored = compute_all_scores(conn)
    logger.info(f"   ✓ {scored} scores computed")
    logger.info(f"Done — {total_success}/{total_scraped} succeeded, {total_errors} errors")
    conn.close()


if __name__ == "__main__":
    main()