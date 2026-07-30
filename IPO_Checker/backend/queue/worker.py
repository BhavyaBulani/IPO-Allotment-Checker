import asyncio
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from db.session import SessionLocal
from db.models import UploadBatch, BatchIPO, Client, AllotmentResult, BatchStatus, ResultStatus, IPO
from registrar_services.orchestrator import orchestrator

logger = logging.getLogger(__name__)

# Configurable worker pool size
WORKER_CONCURRENCY = 20

async def process_client_check(batch_id: int, client_id: int, ipo_id: int, ipo_name: str, registrar_id: int):
    """
    Executes a single check using the orchestrator in a separate thread.
    Fetches the full Client record to get both PAN and Client Code.
    Writes the result to the AllotmentResult table.
    """
    try:
        with SessionLocal() as db:
            cached_result = db.query(AllotmentResult).filter(
                AllotmentResult.client_id == client_id,
                AllotmentResult.ipo_id == ipo_id,
                AllotmentResult.cache_expires_at > datetime.utcnow()
            ).order_by(AllotmentResult.id.desc()).first()
            
            if cached_result:
                allotment = AllotmentResult(
                    client_id=client_id,
                    ipo_id=ipo_id,
                    batch_id=batch_id,
                    registrar_id=registrar_id,
                    status=cached_result.status,
                    checked_at=datetime.utcnow(),
                    served_from_cache=True,
                    cache_expires_at=cached_result.cache_expires_at,
                    captcha_path=cached_result.captcha_path or "none"
                )
                db.add(allotment)
                db.commit()
                return
            
            # Fetch the full Client record to get both identifiers
            client = db.query(Client).filter(Client.id == client_id).first()
            client_pan = client.pan if client else None
            client_code = client.client_code if client else None

        # Run the synchronous Playwright check in a thread to prevent blocking the event loop
        result = await asyncio.to_thread(
            orchestrator.check_allotment,
            pan=client_pan,
            client_code=client_code,
            ipo_name=ipo_name,
            primary_registrar_id=registrar_id
        )

        with SessionLocal() as db:
            if result.status in [ResultStatus.Allotted, ResultStatus.Not_Allotted]:
                expires_at = datetime.utcnow() + timedelta(hours=24)
            else:
                expires_at = None

            allotment = AllotmentResult(
                client_id=client_id,
                ipo_id=ipo_id,
                batch_id=batch_id,
                registrar_id=registrar_id,
                status=result.status,
                checked_at=datetime.utcnow(),
                served_from_cache=False,
                cache_expires_at=expires_at,
                captcha_path=result.captcha_path
            )
            db.add(allotment)
            db.commit()

    except Exception as e:
        logger.error(f"Error checking allotment for client {client_id}, IPO {ipo_id}: {e}")
        with SessionLocal() as db:
            allotment = AllotmentResult(
                client_id=client_id,
                ipo_id=ipo_id,
                batch_id=batch_id,
                registrar_id=registrar_id,
                status=ResultStatus.Website_Error,
                checked_at=datetime.utcnow(),
                served_from_cache=False,
                cache_expires_at=None,
                captcha_path="none"
            )
            db.add(allotment)
            db.commit()

async def worker(queue: asyncio.Queue):
    """
    Worker task that continuously pulls jobs from the queue and processes them.
    """
    while True:
        job = await queue.get()
        try:
            await process_client_check(**job)
        finally:
            queue.task_done()

async def run_batch_jobs(batch_id: int, jobs: list):
    """
    Creates the queue, starts the workers, feeds the queue, and waits for completion.
    Updates batch status accordingly.
    """
    started_at = datetime.utcnow()
    with SessionLocal() as db:
        batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if batch:
            batch.status = BatchStatus.In_Progress
            db.commit()

    queue = asyncio.Queue()
    for job in jobs:
        queue.put_nowait(job)

    # Start workers
    tasks = []
    for _ in range(min(WORKER_CONCURRENCY, len(jobs))):
        task = asyncio.create_task(worker(queue))
        tasks.append(task)

    # Wait until the queue is fully processed
    await queue.join()

    # Cancel worker tasks
    for task in tasks:
        task.cancel()

    # Wait until all worker tasks are cancelled
    await asyncio.gather(*tasks, return_exceptions=True)

    completed_at = datetime.utcnow()

    with SessionLocal() as db:
        batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
        if batch:
            batch.status = BatchStatus.Completed
            
        # Calculate log stats
        from sqlalchemy import func
        status_counts = db.query(
            AllotmentResult.status, 
            func.count(AllotmentResult.id)
        ).filter(
            AllotmentResult.batch_id == batch_id
        ).group_by(
            AllotmentResult.status
        ).all()

        success_count = 0
        failure_count = 0
        timeout_count = 0

        for status, count in status_counts:
            if status in [ResultStatus.Allotted, ResultStatus.Not_Allotted]:
                success_count += count
            elif status == ResultStatus.Timeout:
                timeout_count += count
            else:
                failure_count += count
                
        cache_hit_count = db.query(func.count(AllotmentResult.id)).filter(
            AllotmentResult.batch_id == batch_id,
            AllotmentResult.served_from_cache == True
        ).scalar() or 0

        from db.models import RunLog
        run_log = RunLog(
            batch_id=batch_id,
            started_at=started_at,
            completed_at=completed_at,
            success_count=success_count,
            failure_count=failure_count,
            timeout_count=timeout_count,
            cache_hit_count=cache_hit_count,
            registrars_used=",".join(set([str(j["registrar_id"]) for j in jobs]))
        )
        db.add(run_log)
        db.commit()
        
        logger.info(f"Batch {batch_id} completed. RunLog saved. Success: {success_count}, Fail: {failure_count}")

def process_batch(batch_id: int, jobs: list):
    """
    Entry point for the background task to run the async event loop.
    Since FastAPI runs background tasks in threads, we can create a new event loop here.
    """
    asyncio.run(run_batch_jobs(batch_id, jobs))
