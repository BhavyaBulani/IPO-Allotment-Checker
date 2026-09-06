import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Playwright downloads browsers to ~/.cache/ms-playwright by default, but
# Render does not carry /opt/render/.cache from the build into the runtime
# filesystem (this service uses the "no-cache" profile). Pin the browser cache
# inside the deployed backend directory instead, so the Chromium installed at
# build time is present when the registrar-dropdown / live-check scrapers launch
# it. The build command installs into $PWD/.playwright-cache for the same reason.
os.environ.setdefault(
    "PLAYWRIGHT_BROWSERS_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), ".playwright-cache"),
)

# Sync interval in seconds (4 hours)
IPO_SYNC_INTERVAL_SECONDS = 4 * 60 * 60

# Registrar dropdown discovery interval (6 hours). This is the heavier
# Playwright scan that detects which IPOs have live allotment results; it
# runs as a separate, slower loop so the 4-hour HTTP sync stays fast.
REGISTRAR_DROPDOWN_SYNC_INTERVAL_SECONDS = 6 * 60 * 60

# Database keep-alive interval (10 minutes). Aiven's free tier powers the
# service off after ~2h without traffic, which drops DNS and 500s every
# DB-backed route; a trivial SELECT 1 on this cadence keeps it warm.
DB_KEEPALIVE_INTERVAL_SECONDS = 10 * 60


def _registrar_dropdown_enabled() -> bool:
    raw = os.environ.get("ENABLE_REGISTRAR_DROPDOWN_DISCOVERY")
    if raw is None:
        # Default ON: registrar portals are the authoritative source of which
        # IPOs are currently checkable, so the app stays self-sufficient even
        # if this flag was never set on the host. Set "0" to explicitly disable.
        return True
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _db_keepalive_enabled() -> bool:
    raw = os.environ.get("DB_KEEPALIVE_ENABLED")
    if raw is None:
        # Default ON: prevents a managed MySQL (Aiven free tier) from
        # auto-powering-off. Set "0" once the DB is on an always-on plan.
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


async def _db_keepalive():
    """Ping the database periodically so a managed MySQL (Aiven free tier)
    doesn't auto-power-off from inactivity.

    Aiven's free tier powers the service off after ~2h with no traffic, which
    drops DNS and turns every DB-backed route into a 500. This runs a trivial
    SELECT 1 on a short interval so there is always recent DB activity. Note:
    this only helps while THIS service is itself kept awake by external /health
    pings — Render's free tier also sleeps after ~15 min of no HTTP traffic.
    """
    # Import lazily so importing main.py never requires DB configuration.
    from sqlalchemy import text

    from db.session import engine

    await asyncio.sleep(60)  # let startup settle before the first ping
    while True:
        try:
            def _ping():
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))

            await asyncio.to_thread(_ping)
            logger.debug("DB keep-alive ping succeeded.")
        except Exception as e:
            logger.warning(f"DB keep-alive ping failed: {e}")
        await asyncio.sleep(DB_KEEPALIVE_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the application."""
    # --- Startup ---
    logger.info("Application starting up. Running IPO auto-sync...")
    try:
        from ipo_sync.auto_detect import sync_ipos
        # Run the sync in a worker thread so its HTTP calls never block the
        # event loop, and explicitly skip the Playwright registrar-dropdown
        # scan here (the dedicated `_periodic_registrar_dropdown_sync` task
        # handles that shortly after startup). Running Playwright's sync API
        # inside the asyncio loop raises "Sync API inside the asyncio loop".
        result = await asyncio.to_thread(sync_ipos, False)
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
    
    # Keep-alive ping so a managed MySQL (Aiven free tier) doesn't auto-pause.
    keepalive_task = None
    if _db_keepalive_enabled():
        keepalive_task = asyncio.create_task(_db_keepalive())
        logger.info(
            f"DB keep-alive scheduled every {DB_KEEPALIVE_INTERVAL_SECONDS // 60} "
            "minutes (first ping in 60s)."
        )
    else:
        logger.info("DB keep-alive is disabled (DB_KEEPALIVE_ENABLED=0).")

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
    if keepalive_task is not None:
        keepalive_task.cancel()
        try:
            await keepalive_task
        except asyncio.CancelledError:
            pass
    logger.info("Application shutting down.")

app = FastAPI(title="IPO Allotment Verification API", lifespan=lifespan)

# Configure CORS for frontend access. Origins are read from CORS_ORIGINS
# (comma-separated) so the wildcard is never used with credentials.
def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "http://localhost:5173").strip()
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    # The production SPA is served from Vercel and calls this API directly from
    # the browser, so its origin must always be allowed. A stale/missing
    # CORS_ORIGINS env var must never leave the live frontend CORS-blocked.
    for origin in ("https://ipoallotmentchecker.vercel.app", "http://localhost:5173"):
        if origin not in origins:
            origins.append(origin)
    return origins

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


@app.get("/health/db")
def health_db_check():
    """Readiness probe that actually touches MySQL.

    Unlike ``/health``, this runs a real ``SELECT 1`` against the database so a
    single external ping (GitHub Actions / cron-job.org / UptimeRobot) warms
    BOTH Render's free-tier web service and Aiven's free-tier MySQL at once.

    This matters because Aiven powers off after ~2h with no traffic, while the
    in-process ``_db_keepalive`` background task freezes whenever Render sleeps
    (~15 min of no HTTP). A request handler runs synchronously on wake-up, so
    it is the reliable place to exercise the DB connection.
    """
    from sqlalchemy import text

    from db.session import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)
        return JSONResponse(
            status_code=503,
            content={"status": "error", "detail": "database unreachable"},
        )
    return {"status": "ok", "database": "ok"}
