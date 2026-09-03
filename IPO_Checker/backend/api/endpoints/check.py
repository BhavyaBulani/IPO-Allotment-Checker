import datetime
import io
import logging
import re

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.deps import require_auth
from db.models import IPO, IPOStatus, Registrar
from db.session import get_db
from schemas.input import PanCheckRequest, SingleCheckRequest, IdentifierCheckRequest

logger = logging.getLogger(__name__)

router = APIRouter()

# Cap the raw upload size before pandas reads it, to avoid memory exhaustion.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def validate_pan(pan: str) -> bool:
    """Validate standard Indian PAN format."""
    return bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', pan.upper()))


# Only these stages have a final allotment list to query. Checking a PAN
# against an IPO that is still Open/Upcoming yields a fabricated "Not
# Allotted" (the registrar simply has no record yet), so we never do it.
_CHECKABLE_STATUSES = (IPOStatus.Closed,)

_NO_CHECKABLE_IPOS_MSG = (
    "No Closed IPOs are available to check right now. "
)


def _checkable_ipos(db):
    """Return only Closed IPOs to check their allotment status."""
    return (
        db.query(IPO)
        .filter(IPO.validated == True, IPO.status.in_(_CHECKABLE_STATUSES))
        .all()
    )


def resolve_registrar_id(ipo: IPO, active_registrar_ids: list[int]) -> int | None:
    """
    Resolve the registrar that actually handles this IPO.

    Returns ``None`` when the IPO has no resolved registrar or its registrar is
    inactive. The previous round-robin fallback could send a KFin-registered
    IPO's PAN to Bigshare and report a confident-looking but wrong verdict, so
    we now fail loud instead of guessing.
    """
    if ipo.registrar_id and ipo.registrar_id in active_registrar_ids:
        return ipo.registrar_id

    if ipo.registrar_id:
        logger.warning(
            "IPO '%s' (id=%s) maps to registrar_id=%s, but that registrar is not active.",
            ipo.name, ipo.id, ipo.registrar_id,
        )
    else:
        logger.warning(
            "IPO '%s' (id=%s) has no resolved registrar. Check the sync review queue.",
            ipo.name, ipo.id,
        )
    return None


def _run_check(orchestrator, db, pan, client_code, ipo, registrar_ids):
    registrar_id = resolve_registrar_id(ipo, registrar_ids)
    if registrar_id is None:
        return {
            "ipo": ipo.name,
            "status": "Website Error",
            "message": "No active registrar is mapped for this IPO; check was not run.",
        }
    try:
        res = orchestrator.check_allotment(
            pan=pan,
            client_code=client_code,
            ipo_name=ipo.name,
            primary_registrar_id=registrar_id,
        )
        return {"ipo": ipo.name, "status": res.status.value, "message": res.raw_message}
    except Exception as exc:  # noqa: BLE001 - keep the endpoint resilient per IPO
        return {
            "ipo": ipo.name,
            "status": "Website Error",
            "message": f"Failed to perform check: {str(exc)}",
        }


@router.post("/pan")
def check_single_pan(request: PanCheckRequest, db: Session = Depends(get_db)):
    """Check one PAN against every validated IPO (no IPO selection needed)."""
    pan = request.identifier.upper()
    if not validate_pan(pan):
        raise HTTPException(
            status_code=400,
            detail="Invalid PAN format. Expected 10 characters: 5 letters, 4 digits, 1 letter.",
        )

    ipos = _checkable_ipos(db)
    if not ipos:
        raise HTTPException(status_code=404, detail=_NO_CHECKABLE_IPOS_MSG)

    from db.models import Client
    from registrar_services.orchestrator import orchestrator

    client = db.query(Client).filter(Client.pan == pan).first()
    client_code = client.client_code if client else None

    active_registrars = db.query(Registrar).filter(Registrar.active == True).all()
    registrar_ids = [r.id for r in active_registrars] if active_registrars else [1]

    results_detail = [
        _run_check(orchestrator, db, pan, client_code, ipo, registrar_ids) for ipo in ipos
    ]

    return {
        "status": "success",
        "message": f"Checked PAN against {len(ipos)} IPO(s).",
        "identifier_type": "PAN",
        "ipos": [ipo.name for ipo in ipos],
        "results": results_detail,
    }


@router.post("/all")
def check_all_identifier(request: IdentifierCheckRequest, db: Session = Depends(get_db)):
    """Check a PAN or Client Code against every validated IPO (no selection needed)."""
    identifier = request.identifier.strip().upper()
    is_pan = validate_pan(identifier)

    if not is_pan and len(identifier) < 5:
        raise HTTPException(
            status_code=400,
            detail="Client Code must be at least 5 characters.",
        )

    pan_value = identifier if is_pan else None
    client_code_value = identifier if not is_pan else None

    # Cross-reference the missing identifier from previously imported clients.
    from db.models import Client
    if is_pan:
        existing = db.query(Client).filter(Client.pan == identifier).first()
        if existing and existing.client_code:
            client_code_value = existing.client_code
    else:
        existing = db.query(Client).filter(Client.client_code == identifier).first()
        if existing and existing.pan:
            pan_value = existing.pan

    ipos = _checkable_ipos(db)
    if not ipos:
        raise HTTPException(status_code=404, detail=_NO_CHECKABLE_IPOS_MSG)

    from registrar_services.orchestrator import orchestrator

    active_registrars = db.query(Registrar).filter(Registrar.active == True).all()
    registrar_ids = [r.id for r in active_registrars] if active_registrars else [1]

    results_detail = [
        _run_check(orchestrator, db, pan_value, client_code_value, ipo, registrar_ids)
        for ipo in ipos
    ]

    return {
        "status": "success",
        "message": f"Checked against {len(ipos)} IPO(s).",
        "identifier_type": "PAN" if is_pan else "Client Code",
        "ipos": [ipo.name for ipo in ipos],
        "results": results_detail,
    }


@router.post("/single")
def check_single_client(request: SingleCheckRequest, db: Session = Depends(get_db)):
    # Validate IPOs — only Closed IPOs can be checked.
    ipos = db.query(IPO).filter(
        IPO.id.in_(request.ipo_ids),
        IPO.validated == True,
        IPO.status.in_(_CHECKABLE_STATUSES),
    ).all()
    if len(ipos) != len(request.ipo_ids):
        raise HTTPException(
            status_code=400,
            detail="One or more selected IPOs are invalid, not found, or are not Closed.",
        )

    # Determine if the input is a PAN or Client Code
    is_pan = validate_pan(request.identifier)
    pan_value = request.identifier if is_pan else None
    client_code_value = request.identifier if not is_pan else None

    # Try to cross-reference the missing identifier from the DB
    from db.models import Client
    if is_pan:
        existing = db.query(Client).filter(Client.pan == request.identifier).first()
        if existing and existing.client_code:
            client_code_value = existing.client_code
    else:
        existing = db.query(Client).filter(Client.client_code == request.identifier).first()
        if existing and existing.pan:
            pan_value = existing.pan

    # Execute the check via Orchestrator
    from registrar_services.orchestrator import orchestrator

    active_registrars = db.query(Registrar).filter(Registrar.active == True).all()
    registrar_ids = [r.id for r in active_registrars] if active_registrars else [1]

    results_detail = [
        _run_check(orchestrator, db, pan_value, client_code_value, ipo, registrar_ids)
        for ipo in ipos
    ]

    return {
        "status": "success",
        "message": "Check completed.",
        "identifier_type": "PAN" if is_pan else "Client Code",
        "ipos": [ipo.name for ipo in ipos],
        "results": results_detail,
    }


@router.post("/bulk")
async def check_bulk_upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    ipo_ids: str = Form(""),
    db: Session = Depends(get_db),
):
    if not (file.filename.endswith('.xlsx') or file.filename.endswith('.xls')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only .xlsx and .xls are supported.")

    if ipo_ids.strip():
        try:
            ipo_id_list = [int(i) for i in ipo_ids.split(",") if i.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid IPO IDs format.")

        ipos = db.query(IPO).filter(
            IPO.id.in_(ipo_id_list),
            IPO.validated == True,
            IPO.status.in_(_CHECKABLE_STATUSES),
        ).all()
        if len(ipos) != len(ipo_id_list) or len(ipos) == 0:
            raise HTTPException(status_code=400, detail="Invalid IPO selection: one or more IPOs are not Closed.")
    else:
        # No selection means "check every Closed IPO".
        ipos = _checkable_ipos(db)
        if not ipos:
            raise HTTPException(status_code=400, detail=_NO_CHECKABLE_IPOS_MSG)

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File is too large. Maximum size is 10 MB.")

    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail="Failed to parse Excel file.")

    if len(df) > 10000:
        raise HTTPException(status_code=400, detail="File exceeds maximum limit of 10,000 rows.")

    # Auto-detect PAN and Client Code columns separately
    pan_col = None
    code_col = None
    for col in df.columns:
        col_lower = str(col).lower()
        if "pan" in col_lower and pan_col is None:
            pan_col = col
        elif "client" in col_lower and "code" in col_lower and code_col is None:
            code_col = col

    if not pan_col and not code_col:
        # Fallback: try to find any single identifier column
        for col in df.columns:
            col_lower = str(col).lower()
            if "identifier" in col_lower or "id" == col_lower:
                pan_col = col
                break
        if not pan_col:
            raise HTTPException(status_code=400, detail="Could not auto-detect a PAN or Client Code column. Please ensure your header has 'PAN' and/or 'Client Code'.")

    # Extract valid row-level records with both fields
    row_records = []
    for _, row in df.iterrows():
        pan_val = str(row[pan_col]).strip().upper() if pan_col and pd.notna(row.get(pan_col)) else None
        code_val = str(row[code_col]).strip().upper() if code_col and pd.notna(row.get(code_col)) else None

        # Validate: at least one identifier must be present
        if not pan_val and not code_val:
            continue
        # Validate PAN format if present
        if pan_val and not validate_pan(pan_val):
            pan_val = None  # Not a valid PAN, ignore it (but keep client_code if present)
        # Validate client code: must be at least 5 chars
        if code_val and len(code_val) < 5:
            code_val = None

        if not pan_val and not code_val:
            continue

        row_records.append({"pan": pan_val, "client_code": code_val})

    valid_rows = len(row_records)
    invalid_rows = len(df) - valid_rows

    if valid_rows == 0:
        raise HTTPException(status_code=400, detail="No valid PANs or Client Codes found in the uploaded file.")

    # Create UploadBatch
    from db.models import UploadBatch, BatchIPO, BatchStatus, Client
    from queue.worker import process_batch

    batch = UploadBatch(
        file_name=file.filename,
        row_count=len(df),
        valid_row_count=valid_rows,
        invalid_row_count=invalid_rows,
        status=BatchStatus.Queued
    )
    db.add(batch)
    db.flush()  # flush to get batch.id

    # Create BatchIPOs
    for ipo in ipos:
        batch_ipo = BatchIPO(batch_id=batch.id, ipo_id=ipo.id)
        db.add(batch_ipo)

    db.commit()

    # Pre-fetch or create Client records, keyed by (pan, client_code)
    # Build sets of all PANs and client codes for querying
    all_pans = {r["pan"] for r in row_records if r["pan"]}
    all_codes = {r["client_code"] for r in row_records if r["client_code"]}

    existing_clients = []
    if all_pans:
        existing_clients += db.query(Client).filter(Client.pan.in_(all_pans)).all()
    if all_codes:
        existing_clients += db.query(Client).filter(Client.client_code.in_(all_codes)).all()

    # Deduplicate
    seen_ids = set()
    unique_clients = []
    for c in existing_clients:
        if c.id not in seen_ids:
            seen_ids.add(c.id)
            unique_clients.append(c)

    # Build a lookup map: pan -> client, client_code -> client
    client_map = {}
    for c in unique_clients:
        if c.pan:
            client_map[("pan", c.pan)] = c
        if c.client_code:
            client_map[("code", c.client_code)] = c

    def find_or_create_client(rec):
        """Find existing client or create new one. Also backfill missing identifiers."""
        pan = rec["pan"]
        code = rec["client_code"]

        # Try to find by PAN first, then by client_code
        client = None
        if pan:
            client = client_map.get(("pan", pan))
        if not client and code:
            client = client_map.get(("code", code))

        if client:
            # Backfill: if the existing client is missing one of the identifiers, add it
            updated = False
            if pan and not client.pan:
                client.pan = pan
                client_map[("pan", pan)] = client
                updated = True
            if code and not client.client_code:
                client.client_code = code
                client_map[("code", code)] = client
                updated = True
            return client, False

        # Create new client
        name = f"User_{pan or code}"
        new_client = Client(name=name, pan=pan, client_code=code)
        # Register in map
        if pan:
            client_map[("pan", pan)] = new_client
        if code:
            client_map[("code", code)] = new_client
        return new_client, True

    new_clients = []
    resolved_clients = []
    for rec in row_records:
        client, is_new = find_or_create_client(rec)
        resolved_clients.append(client)
        if is_new:
            new_clients.append(client)

    if new_clients:
        db.bulk_save_objects(new_clients)
        db.commit()
        # Re-fetch to get IDs for newly created clients
        refetch_pans = {c.pan for c in new_clients if c.pan}
        refetch_codes = {c.client_code for c in new_clients if c.client_code}
        refetched = []
        if refetch_pans:
            refetched += db.query(Client).filter(Client.pan.in_(refetch_pans)).all()
        if refetch_codes:
            refetched += db.query(Client).filter(Client.client_code.in_(refetch_codes)).all()
        # Update map with real IDs
        for c in refetched:
            if c.pan:
                client_map[("pan", c.pan)] = c
            if c.client_code:
                client_map[("code", c.client_code)] = c
    else:
        db.commit()  # commit any backfill updates

    active_registrars = db.query(Registrar).filter(Registrar.active == True).all()
    registrar_ids = [r.id for r in active_registrars] if active_registrars else [1]

    # Prepare jobs — worker will fetch full client from DB using client_id
    jobs = []
    for rec in row_records:
        pan = rec["pan"]
        code = rec["client_code"]
        client = client_map.get(("pan", pan)) if pan else client_map.get(("code", code))
        if not client or not client.id:
            continue
        for ipo in ipos:
            registrar_id = resolve_registrar_id(ipo, registrar_ids)
            jobs.append({
                "batch_id": batch.id,
                "client_id": client.id,
                "ipo_id": ipo.id,
                "ipo_name": ipo.name,
                "registrar_id": registrar_id
            })

    # Queue background task
    background_tasks.add_task(process_batch, batch.id, jobs)

    return {
        "status": "success",
        "message": f"File uploaded. Found {len(df)} total rows. ({valid_rows} valid, {invalid_rows} invalid).",
        "batch_id": batch.id,
        "selected_ipos": [ipo.name for ipo in ipos]
    }


@router.delete("/cache/clear")
def clear_allotment_cache(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    """Clears all cached allotment results"""
    from db.models import AllotmentResult
    try:
        updated = db.query(AllotmentResult).filter(
            AllotmentResult.cache_expires_at > datetime.datetime.utcnow()
        ).update({"cache_expires_at": datetime.datetime.utcnow()})
        db.commit()
        return {"status": "success", "message": f"Cleared {updated} cached results."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to clear cache: {str(e)}")
