from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import RunLog

router = APIRouter()

@router.get("/{batch_id}")
def get_batch_logs(batch_id: int, db: Session = Depends(get_db)):
    log = db.query(RunLog).filter(RunLog.batch_id == batch_id).first()
    if not log:
        raise HTTPException(status_code=404, detail="Run logs not found for this batch.")
        
    return {
        "id": log.id,
        "batch_id": log.batch_id,
        "started_at": log.started_at.isoformat() if log.started_at else None,
        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
        "success_count": log.success_count,
        "failure_count": log.failure_count,
        "timeout_count": log.timeout_count,
        "cache_hit_count": log.cache_hit_count,
        "registrars_used": log.registrars_used
    }
