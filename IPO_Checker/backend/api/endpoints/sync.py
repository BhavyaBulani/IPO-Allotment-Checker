from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import require_auth
from db.session import get_db
from ipo_sync.auto_detect import sync_ipos as sync_ipos_from_dashboard

router = APIRouter()


@router.post("")
def sync_ipos(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    """
    Triggers a manual sync of IPOs from the configured exchange sources.
    """
    try:
        result = sync_ipos_from_dashboard()
        retired = result.get("retired", 0)
        message = (
            f"IPO sync complete. Added {result['added']}, updated {result['updated']}"
            f" from {result['source']}."
        )
        if retired:
            message += f" Retired {retired} IPO(s) no longer listed on their registrar portal."
        return {
            "status": "success",
            "message": message,
            "added": result["added"],
            "updated": result["updated"],
            "retired": retired,
            "retired_names": result.get("retired_names", []),
            "source": result["source"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to sync IPOs: {str(e)}")
