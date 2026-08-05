"""
Standalone IPO sync job.

Can be run directly: python jobs/sync_job.py
Or scheduled via cron / Windows Task Scheduler.

This calls the live Chittorgarh dashboard sync directly — no HTTP overhead,
no admin key required.
"""
import sys
import os
import logging

# Add the parent directory to the path so we can import from backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_sync():
    """Execute the IPO sync and log the result."""
    logger.info("Starting scheduled IPO sync job...")
    try:
        from ipo_sync.auto_detect import sync_ipos
        result = sync_ipos()
        logger.info(
            f"IPO sync job completed. "
            f"Added: {result['added']}, "
            f"Updated: {result['updated']}, "
            f"Source: {result['source']}"
        )
        return result
    except Exception as e:
        logger.error(f"IPO sync job failed: {e}", exc_info=True)
        return {"added": 0, "updated": 0, "source": "error"}


if __name__ == "__main__":
    run_sync()
