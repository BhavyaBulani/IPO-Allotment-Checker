from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import desc
from db.session import get_db
from db.models import UploadBatch, BatchStatus

router = APIRouter()

@router.get("/batches")
def get_historical_batches(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    query = db.query(UploadBatch).order_by(desc(UploadBatch.uploaded_at))
    total = query.count()
    batches = query.offset(skip).limit(limit).all()
    
    data = []
    for b in batches:
        data.append({
            "id": b.id,
            "file_name": b.file_name,
            "row_count": b.row_count,
            "valid_row_count": b.valid_row_count,
            "status": b.status.value,
            "uploaded_at": b.uploaded_at.isoformat() if b.uploaded_at else None
        })
        
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": data
    }
