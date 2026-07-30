import sys
import os
import time
from datetime import datetime, timedelta
import logging
from sqlalchemy import text

# Add the parent directory to the path so we can import from backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

RETENTION_DAYS = 30
BATCH_SIZE = 1000
DELAY_BETWEEN_BATCHES_SEC = 0.5

def purge_table_in_batches(db, table_name, date_column, cutoff_date):
    """
    Deletes rows from a table older than cutoff_date in batches.
    """
    total_deleted = 0
    while True:
        # We use a raw SQL approach for efficient batched delete
        # Note: MySQL doesn't natively support DELETE ... LIMIT directly with subqueries well,
        # but we can do a simple DELETE with LIMIT.
        query = text(f"""
            DELETE FROM {table_name} 
            WHERE {date_column} < :cutoff_date 
            LIMIT :batch_size
        """)
        
        result = db.execute(query, {"cutoff_date": cutoff_date, "batch_size": BATCH_SIZE})
        db.commit()
        
        deleted_this_batch = result.rowcount
        total_deleted += deleted_this_batch
        
        logger.info(f"Deleted {deleted_this_batch} rows from {table_name} in this batch.")
        
        if deleted_this_batch < BATCH_SIZE:
            # We've deleted all matching rows
            break
            
        time.sleep(DELAY_BETWEEN_BATCHES_SEC)
        
    return total_deleted

def run_purge():
    logger.info(f"Starting batched purge job. Retention: {RETENTION_DAYS} days.")
    cutoff_date = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    
    db = SessionLocal()
    try:
        # Purge run_logs
        logger.info("Purging old run_logs...")
        logs_deleted = purge_table_in_batches(db, "run_logs", "started_at", cutoff_date)
        
        # Purge allotment_results
        logger.info("Purging old allotment_results...")
        results_deleted = purge_table_in_batches(db, "allotment_results", "checked_at", cutoff_date)
        
        logger.info(f"Purge job completed successfully. Deleted {logs_deleted} logs and {results_deleted} results.")
    except Exception as e:
        logger.error(f"Error during purge job: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    run_purge()
