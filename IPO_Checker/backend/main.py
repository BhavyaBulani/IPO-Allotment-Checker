import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the application."""
    # --- Startup ---
    logger.info("Application starting up. Running IPO auto-sync...")
    try:
        from ipo_sync.auto_detect import sync_ipos_from_web, mock_sync_ipos
        result = sync_ipos_from_web()
        logger.info(f"IPO auto-sync result: Added {result['added']}, Updated {result['updated']} from {result['source']}")
        if result["added"] == 0 and result["updated"] == 0 and result["source"] == "none":
            logger.info("No live IPOs found. Seeding mock data as fallback...")
            mock_sync_ipos()
    except Exception as e:
        logger.warning(f"IPO auto-sync failed on startup: {e}. Seeding mock data as fallback.")
        try:
            from ipo_sync.auto_detect import mock_sync_ipos
            mock_sync_ipos()
        except Exception as e2:
            logger.error(f"Mock seed also failed: {e2}")
    
    yield  # Application runs here
    
    # --- Shutdown ---
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
