from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.session import get_db
from db.models import UploadBatch, AllotmentResult, ResultStatus, BatchIPO
from typing import Dict, Any

router = APIRouter()

@router.get("/{batch_id}")
def get_batch_progress(batch_id: int, db: Session = Depends(get_db)) -> Dict[str, Any]:
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    # Get the number of expected results
    batch_ipos_count = db.query(func.count(BatchIPO.id)).filter(BatchIPO.batch_id == batch_id).scalar()
    total_expected = batch.valid_row_count * batch_ipos_count if batch_ipos_count else 0

    # Get current completion counts grouped by status
    status_counts = db.query(
        AllotmentResult.status, 
        func.count(AllotmentResult.id)
    ).filter(
        AllotmentResult.batch_id == batch_id
    ).group_by(
        AllotmentResult.status
    ).all()

    completed_count = 0
    success_count = 0
    failure_count = 0
    error_count = 0

    for status, count in status_counts:
        completed_count += count
        if status in [ResultStatus.Allotted, ResultStatus.Not_Allotted]:
            success_count += count
        elif status == ResultStatus.Invalid_PAN:
            failure_count += count
        else:
            error_count += count

    # Progress calculation
    progress = (completed_count / total_expected * 100) if total_expected > 0 else 100
    
    return {
        "batch_id": batch.id,
        "status": batch.status.value,
        "progress": round(progress, 2),
        "total_expected": total_expected,
        "completed": completed_count,
        "successful_checks": success_count,
        "invalid_data": failure_count,
        "errors": error_count,
        "valid_rows": batch.valid_row_count,
        "invalid_rows": batch.invalid_row_count
    }
