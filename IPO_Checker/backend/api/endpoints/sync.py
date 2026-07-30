from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from db.session import get_db
from ipo_sync.auto_detect import sync_ipos_from_web
from api.deps import verify_admin_key

router = APIRouter()

@router.post("", dependencies=[Depends(verify_admin_key)])
def sync_ipos(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Triggers a manual sync of the IPOs by scraping Upstox (with Moneycontrol fallback).
    """
    try:
        result = sync_ipos_from_web()
        return {
            "status": "success",
            "message": f"IPO sync complete. Added {result['added']}, updated {result['updated']} from {result['source']}.",
            "added": result["added"],
            "updated": result["updated"],
            "source": result["source"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync IPOs: {str(e)}")
