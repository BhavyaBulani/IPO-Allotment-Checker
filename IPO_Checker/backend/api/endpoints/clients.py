from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from db.session import get_db
from db.models import Client
import pandas as pd
import io
import re

router = APIRouter()

def validate_pan(pan: str) -> bool:
    """Validate standard Indian PAN format."""
    return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan.upper()))

@router.post("/upload")
async def upload_client_list(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Import a client list from an Excel file.
    Expected columns: Name (required), PAN (optional), Client Code (optional).
    At least one of PAN or Client Code must be present per row.
    Existing clients (matched by PAN or Client Code) will have their records backfilled.
    """
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .xlsx and .xls are supported.")

    content = await file.read()
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse Excel file: {str(e)}")

    if len(df) > 10000:
        raise HTTPException(status_code=400, detail="File exceeds maximum limit of 10,000 rows.")

    # Auto-detect columns
    name_col = None
    pan_col = None
    code_col = None
    
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if col_lower in ("name", "client name", "client_name", "full name"):
            name_col = col
        elif "pan" in col_lower and pan_col is None:
            pan_col = col
        elif ("client" in col_lower and "code" in col_lower) and code_col is None:
            code_col = col

    if not name_col:
        # Try first column as name if it looks textual
        first_col = df.columns[0]
        if df[first_col].dtype == object:
            name_col = first_col
    
    if not pan_col and not code_col:
        raise HTTPException(
            status_code=400, 
            detail="Could not auto-detect PAN or Client Code columns. Ensure your headers include 'PAN' and/or 'Client Code'."
        )

    # Process rows
    created_count = 0
    updated_count = 0
    skipped_count = 0
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2  # Excel row (1-indexed header + 1)
        
        name_val = str(row[name_col]).strip() if name_col and pd.notna(row.get(name_col)) else None
        pan_val = str(row[pan_col]).strip().upper() if pan_col and pd.notna(row.get(pan_col)) else None
        code_val = str(row[code_col]).strip().upper() if code_col and pd.notna(row.get(code_col)) else None
        
        # Validate PAN format
        if pan_val and not validate_pan(pan_val):
            pan_val = None
        
        # Validate client code
        if code_val and len(code_val) < 3:
            code_val = None
        
        # Skip if no identifiers
        if not pan_val and not code_val:
            skipped_count += 1
            continue
        
        # Try to find existing client
        existing = None
        if pan_val:
            existing = db.query(Client).filter(Client.pan == pan_val).first()
        if not existing and code_val:
            existing = db.query(Client).filter(Client.client_code == code_val).first()
        
        if existing:
            # Backfill missing fields
            changed = False
            if name_val and (not existing.name or existing.name.startswith("User_")):
                existing.name = name_val
                changed = True
            if pan_val and not existing.pan:
                existing.pan = pan_val
                changed = True
            if code_val and not existing.client_code:
                existing.client_code = code_val
                changed = True
            if changed:
                updated_count += 1
            else:
                skipped_count += 1
        else:
            # Create new client
            client_name = name_val or f"User_{pan_val or code_val}"
            try:
                new_client = Client(name=client_name, pan=pan_val, client_code=code_val)
                db.add(new_client)
                db.flush()
                created_count += 1
            except Exception as e:
                db.rollback()
                errors.append(f"Row {row_num}: {str(e)}")
                continue
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save client records: {str(e)}")
    
    return {
        "status": "success",
        "message": f"Client import complete. {created_count} created, {updated_count} updated, {skipped_count} skipped.",
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "total_rows": len(df),
        "errors": errors[:10]  # Cap error list at 10
    }
