from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from db.session import get_db
from db.models import UploadBatch, AllotmentResult, ResultStatus, Client, IPO, Registrar
from api.security import mask_identifier
from typing import Dict, Any, List
import pandas as pd
import io

router = APIRouter()

@router.get("/batch/{batch_id}/summary")
def get_batch_summary(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    status_counts = db.query(
        AllotmentResult.status, 
        func.count(AllotmentResult.id)
    ).filter(
        AllotmentResult.batch_id == batch_id
    ).group_by(
        AllotmentResult.status
    ).all()

    summary = {
        "total_processed": 0,
        "allotted": 0,
        "not_allotted": 0,
        "errors": 0,
        "invalid_pan": 0
    }

    for status, count in status_counts:
        summary["total_processed"] += count
        if status == ResultStatus.Allotted:
            summary["allotted"] += count
        elif status == ResultStatus.Not_Allotted:
            summary["not_allotted"] += count
        elif status == ResultStatus.Invalid_PAN:
            summary["invalid_pan"] += count
        else:
            # Website_Error, Timeout, Server_Busy
            summary["errors"] += count

    return summary

@router.get("/batch/{batch_id}")
def get_batch_results(batch_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    query = db.query(
        AllotmentResult.status,
        AllotmentResult.checked_at,
        AllotmentResult.served_from_cache,
        Client.pan,
        Client.name.label('client_name'),
        Client.client_code,
        IPO.name.label('ipo_name'),
        Registrar.name.label('registrar_name')
    ).join(Client, AllotmentResult.client_id == Client.id)\
     .join(IPO, AllotmentResult.ipo_id == IPO.id)\
     .outerjoin(Registrar, AllotmentResult.registrar_id == Registrar.id)\
     .filter(AllotmentResult.batch_id == batch_id)

    total = query.count()
    results = query.offset(skip).limit(limit).all()

    data = []
    for r in results:
        data.append({
            # Mask identifiers in the JSON response: never return a full PAN.
            "pan": mask_identifier(r.pan or r.client_code),
            "client_name": r.client_name,
            "ipo_name": r.ipo_name,
            "registrar_name": r.registrar_name or "Unknown",
            "status": r.status.value,
            "served_from_cache": r.served_from_cache,
            "checked_at": r.checked_at.isoformat() if r.checked_at else None
        })

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": data
    }

@router.get("/batch/{batch_id}/export")
def export_batch_results(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(UploadBatch).filter(UploadBatch.id == batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    results = db.query(
        Client.pan,
        Client.client_code,
        IPO.name.label('ipo_name'),
        Registrar.name.label('registrar_name'),
        AllotmentResult.status,
        AllotmentResult.served_from_cache,
        AllotmentResult.checked_at
    ).join(Client, AllotmentResult.client_id == Client.id)\
     .join(IPO, AllotmentResult.ipo_id == IPO.id)\
     .outerjoin(Registrar, AllotmentResult.registrar_id == Registrar.id)\
     .filter(AllotmentResult.batch_id == batch_id).all()

    data = []
    for r in results:
        data.append({
            "Identifier (PAN/Code)": r.pan or r.client_code,
            "IPO": r.ipo_name,
            "Registrar": r.registrar_name,
            "Status": r.status.value if r.status else "Unknown",
            "Cached": "Yes" if r.served_from_cache else "No",
            "Checked At": r.checked_at.strftime("%Y-%m-%d %H:%M:%S") if r.checked_at else ""
        })

    df = pd.DataFrame(data)
    
    stream = io.BytesIO()
    with pd.ExcelWriter(stream, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Results')
    
    stream.seek(0)
    filename = f"IPO_Results_Batch_{batch_id}.xlsx"
    
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
