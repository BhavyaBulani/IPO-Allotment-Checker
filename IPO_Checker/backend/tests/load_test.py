import sys
import os
import time
import logging
import concurrent.futures
from datetime import datetime

# Add the parent directory to the path so we can import from backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import AllotmentResult, ResultStatus, Client, IPO, Registrar

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

CONCURRENCY = 30
INSERTS_PER_WORKER = 50

def worker_task(worker_id):
    """
    Simulates a worker inserting multiple allotment results.
    """
    db = SessionLocal()
    success_count = 0
    try:
        # For a true test, we need some existing client/ipo/registrar IDs.
        # Let's try to get a valid one, or create dummies if they don't exist.
        client = db.query(Client).first()
        ipo = db.query(IPO).first()
        registrar = db.query(Registrar).first()
        
        if not client or not ipo:
            logger.warning("No clients or IPOs in DB. Run mock sync first or test will fail.")
            return 0
            
        for i in range(INSERTS_PER_WORKER):
            result = AllotmentResult(
                client_id=client.id,
                ipo_id=ipo.id,
                registrar_id=registrar.id if registrar else None,
                status=ResultStatus.Allotted,
                checked_at=datetime.utcnow()
            )
            db.add(result)
            # Commit individually to simulate real-world contention
            db.commit()
            success_count += 1
            
    except Exception as e:
        logger.error(f"Worker {worker_id} encountered an error: {e}")
        db.rollback()
    finally:
        db.close()
        
    return success_count

def run_load_test():
    logger.info(f"Starting load test with {CONCURRENCY} concurrent workers...")
    logger.info(f"Each worker will insert {INSERTS_PER_WORKER} records.")
    
    start_time = time.time()
    
    total_inserted = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = {executor.submit(worker_task, i): i for i in range(CONCURRENCY)}
        
        for future in concurrent.futures.as_completed(futures):
            worker_id = futures[future]
            try:
                result = future.result()
                total_inserted += result
            except Exception as e:
                logger.error(f"Worker {worker_id} generated an exception: {e}")
                
    duration = time.time() - start_time
    expected_total = CONCURRENCY * INSERTS_PER_WORKER
    
    logger.info("=== Load Test Complete ===")
    logger.info(f"Duration: {duration:.2f} seconds")
    logger.info(f"Total inserted: {total_inserted} / {expected_total}")
    
    if total_inserted == expected_total:
        logger.info("SUCCESS: No lock contention or dropped results detected.")
    else:
        logger.error(f"FAILURE: Dropped {expected_total - total_inserted} results.")

if __name__ == "__main__":
    run_load_test()
