import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sync interval in seconds (4 hours)
IPO_SYNC_INTERVAL_SECONDS = 4 * 60 * 60

# Registrar dropdown discovery interval (6 hours). This is the heavier
# Playwright scan that detects which IPOs have live allotment results; it
# runs as a separate, slower loop so the 4-hour HTTP sync stays fast.
REGISTRAR_DROPDOWN_SYNC_INTERVAL_SECONDS = 6 * 60 * 60


def _registrar_dropdown_enabled() -> bool:
    raw = os.environ.get("ENABLE_REGISTRAR_DROPDOWN_DISCOVERY")
    if raw is None:
        # Default ON: registrar portals are the authoritative source of which
        # IPOs are currently checkable, so the app stays self-sufficient even
        # if this flag was never set on the host. Set "0" to explicitly disable.
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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


async def _periodic_registrar_dropdown_sync():
    """Background task that scans registrar dropdowns once a day.

    Runs the first scan shortly after startup (so a fresh deploy doesn't
    have to wait 24 hours), then every 24 hours. The service's keep-alive
    pings keep this loop running; no separate Render cron service is needed.
    """
    # Small delay so the first scan doesn't compete with the startup sync.
    await asyncio.sleep(60)
    while True:
        logger.info("Registrar dropdown sync triggered...")
        try:
            from ipo_sync.auto_detect import sync_ipos
            result = await asyncio.to_thread(sync_ipos, include_registrar_dropdown=True)
            logger.info(
                f"Registrar dropdown sync complete. "
                f"Added: {result['added']}, Updated: {result['updated']}, "
                f"Source: {result['source']}"
            )
        except Exception as e:
            logger.error(f"Registrar dropdown sync failed: {e}", exc_info=True)
        await asyncio.sleep(REGISTRAR_DROPDOWN_SYNC_INTERVAL_SECONDS)


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

    # Start the daily registrar dropdown scan if enabled.
    dropdown_task = None
    if _registrar_dropdown_enabled():
        dropdown_task = asyncio.create_task(_periodic_registrar_dropdown_sync())
        logger.info("Registrar dropdown sync scheduled daily (first run in 60s).")
    else:
        logger.info("Registrar dropdown sync is disabled (ENABLE_REGISTRAR_DROPDOWN_DISCOVERY=0).")
    
    yield  # Application runs here
    
    # --- Shutdown ---
    sync_task.cancel()
    try:
        await sync_task
    except asyncio.CancelledError:
        pass
    if dropdown_task is not None:
        dropdown_task.cancel()
        try:
            await dropdown_task
        except asyncio.CancelledError:
            pass
    logger.info("Application shutting down.")

app = FastAPI(title="IPO Allotment Verification API", lifespan=lifespan)

# Configure CORS for frontend access. Origins are read from CORS_ORIGINS
# (comma-separated) so the wildcard is never used with credentials.
def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173").strip()
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

@app.get("/health")
def health_check():
    return {"status": "ok"}
