import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sync interval in seconds (4 hours)
IPO_SYNC_INTERVAL_SECONDS = 4 * 60 * 60


async def _periodic_ipo_sync():
    """Background task that syncs IPOs every IPO_SYNC_INTERVAL_SECONDS."""
    while True:
        await asyncio.sleep(IPO_SYNC_INTERVAL_SECONDS)
        logger.info("Periodic IPO sync triggered...")
        try:
            from ipo_sync.auto_detect import sync_ipos
            # Run the sync in a thread to avoid blocking the event loop
            result = await asyncio.to_thread(sync_ipos)
            logger.info(
                f"Periodic IPO sync complete. "
                f"Added: {result['added']}, Updated: {result['updated']}, "
                f"Source: {result['source']}"
            )
        except Exception as e:
            logger.error(f"Periodic IPO sync failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the application."""
    # --- Startup ---
    logger.info("Application starting up. Running IPO auto-sync...")
    try:
        from ipo_sync.auto_detect import sync_ipos
        result = sync_ipos()
        logger.info(f"IPO auto-sync result: Added {result['added']}, Updated {result['updated']} from {result['source']}")
    except Exception as e:
        logger.warning(f"IPO auto-sync failed on startup: {e}. Keeping existing IPO rows as fallback.")

    # Start the periodic sync background task
    sync_task = asyncio.create_task(_periodic_ipo_sync())
    logger.info(f"Periodic IPO sync scheduled every {IPO_SYNC_INTERVAL_SECONDS // 3600} hours.")
    
    yield  # Application runs here
    
    # --- Shutdown ---
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    logger.info("Application shutting down.")

app = FastAPI(title="IPO Allotment Verification API", lifespan=lifespan)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "ok"}
