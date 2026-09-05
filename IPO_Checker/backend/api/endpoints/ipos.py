import hashlib
import io
import re
from datetime import date, datetime
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import require_auth
from db.models import IPO, IPOStatus, Registrar
from db.session import get_db
from ipo_sync.registrar_map import resolve_registrar_name

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_UPLOAD_ROWS = 10000

class IpoResponse(BaseModel):
    id: int
    name: str
    status: str
    auto_detected: bool
    open_date: Optional[datetime]
    close_date: Optional[datetime]
    source: Optional[str]

    class Config:
        from_attributes = True

@router.get("/", response_model=List[IpoResponse])
def get_validated_ipos(
    db: Session = Depends(get_db),
    checkable: bool = Query(
        False,
        description="Return only IPOs whose allotment is announced (i.e. actually checkable right now).",
    ),
):
    """Fetch validated IPOs available for selection.

    With ``checkable=true`` only IPOs in ``Allotment Announced`` status are
    returned, so the dashboard dropdown never offers an IPO whose verdict is
    still pending (a registrar has no record yet for those).
    """
    query = db.query(IPO).filter(IPO.validated == True)
    if checkable:
        from api.endpoints.check import _CHECKABLE_STATUSES
        query = query.filter(IPO.status.in_(_CHECKABLE_STATUSES))
    ipos = query.all()
    
    def sort_key(ipo):
        priority = 4
        if ipo.status == IPOStatus.Open:
            priority = 1
        elif ipo.status == IPOStatus.Upcoming:
            priority = 2
        elif ipo.status == IPOStatus.Allotment_Announced:
            priority = 3
        elif ipo.status == IPOStatus.Closed:
            priority = 4
        return (priority, ipo.name)
        
    sorted_ipos = sorted(ipos, key=sort_key)
    
    return [
        {
            "id": ipo.id, 
            "name": ipo.name, 
            "status": ipo.status.value, 
            "auto_detected": ipo.auto_detected,
            "open_date": ipo.open_date,
            "close_date": ipo.close_date,
            "source": ipo.source
        } for ipo in sorted_ipos
    ]


# ---------------------------------------------------------------------------
# Manual IPO upload (CSV / Excel)
# ---------------------------------------------------------------------------

_STATUS_ALIASES = {
    "open": IPOStatus.Open,
    "upcoming": IPOStatus.Upcoming,
    "closed": IPOStatus.Closed,
    "allotment announced": IPOStatus.Allotment_Announced,
    "allotment_announced": IPOStatus.Allotment_Announced,
    "announced": IPOStatus.Allotment_Announced,
}

_DATE_FORMATS = (
    "%d-%b-%Y",            # 28-Aug-2026
    "%d %b %Y",            # 28 Aug 2026
    "%d/%m/%Y",            # 28/08/2026
    "%d-%m-%Y",            # 28-08-2026
    "%d.%m.%Y",            # 28.08.2026
    "%Y-%m-%d",            # 2026-08-28
    "%Y/%m/%d",            # 2026/08/28
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def _normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).lower())


def _normalize_name(value: str) -> str:
    """Same suffix-insensitive key used by the auto-sync pipeline."""
    value = re.sub(r"\s*&\s*", " and ", value or "")
    value = re.sub(r"\b(limited|ltd|private|pvt)\b\.?", "", value or "", flags=re.I)
    return re.sub(r"\s+", " ", value).strip().lower()


def _detect_column(df, keywords, exclude=()):
    """First column whose normalized header contains a keyword, skipping excludes."""
    exclude_set = set(exclude)
    for col in df.columns:
        if col in exclude_set:
            continue
        header = _normalize_header(col)
        if header and any(keyword in header for keyword in keywords):
            return col
    return None


def _parse_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _parse_status(value) -> IPOStatus:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return IPOStatus.Closed
    text = str(value).strip().lower().replace("_", " ")
    return _STATUS_ALIASES.get(text, IPOStatus.Closed)


def _clean_text(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    return text or None


def _resolve_registrar(db, raw_name: str | None):
    """Return (registrar_id, canonical_name). registrar_id is None when unmapped."""
    if not raw_name:
        return None, None
    canonical = resolve_registrar_name(raw_name)
    if not canonical:
        return None, None
    registrar = db.query(Registrar).filter(Registrar.name == canonical).first()
    if not registrar:
        return None, canonical
    return registrar.id, canonical


def _make_manual_external_id(normalized_name: str) -> str:
    digest = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:12]
    return f"manual-upload-{digest}"


@router.post("/upload", dependencies=[Depends(require_auth)])
async def upload_ipo_list(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Import IPO names from a CSV or Excel file.

    Expected columns (case- and order-insensitive):
      - Name / Company / IPO Name          (required)
      - Close Date / Closing Date          (optional)
      - Status (Closed / Allotment Announced / Open / Upcoming)  (optional, defaults to Closed)
      - Registrar / RTA                    (optional, strongly recommended)

    Uploaded rows are treated as curated by the brokerage and are published
    immediately (validated=True, source=manual-upload), so they appear in the
    single-check dropdown. Rows whose registrar cannot be mapped are still saved
    but surface in ``unmapped_registrars`` so an admin can fix the mapping.
    """
    lower_name = (file.filename or "").lower()
    if not (
        lower_name.endswith(".csv")
        or lower_name.endswith(".xlsx")
        or lower_name.endswith(".xls")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .csv, .xlsx and .xls are supported.",
        )

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File is too large. Maximum size is 10 MB.")

    try:
        if lower_name.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(content), encoding="utf-8-sig")
            except UnicodeDecodeError:
                df = pd.read_csv(io.BytesIO(content), encoding="latin-1")
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(exc)}")

    if len(df) > MAX_UPLOAD_ROWS:
        raise HTTPException(
            status_code=400, detail=f"File exceeds maximum limit of {MAX_UPLOAD_ROWS} rows."
        )

    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file has no data rows.")

    close_col = _detect_column(
        df, ("closedate", "closingdate", "closing", "dateofclosing", "closedon")
    )
    status_col = _detect_column(df, ("status", "stage", "allotmentstatus"), exclude=(close_col,))
    registrar_col = _detect_column(
        df, ("registrar", "rta", "sharetransferagent"), exclude=(close_col, status_col)
    )
    name_col = _detect_column(
        df, ("name", "company"), exclude=(close_col, status_col, registrar_col)
    )

    if name_col is None:
        raise HTTPException(
            status_code=400,
            detail="Could not find a 'Name' / 'Company' column. Please include an IPO name column.",
        )

    existing_by_name = {
        _normalize_name(ipo.name): ipo for ipo in db.query(IPO).all()
    }

    created = 0
    updated = 0
    skipped = 0
    unmapped = []
    errors = []

    for idx, row in df.iterrows():
        row_num = idx + 2  # header row is 1, data starts at 2

        name = _clean_text(row.get(name_col))
        if not name or len(name) < 3 or len(name) > 150:
            skipped += 1
            errors.append(f"Row {row_num}: missing or invalid IPO name.")
            continue

        close_dt = _parse_date(row.get(close_col)) if close_col is not None else None
        status = _parse_status(row.get(status_col)) if status_col is not None else IPOStatus.Closed
        raw_registrar = _clean_text(row.get(registrar_col)) if registrar_col is not None else None
        registrar_id, _canonical = _resolve_registrar(db, raw_registrar)

        if raw_registrar and registrar_id is None:
            unmapped.append(
                f"Row {row_num}: '{name}' — registrar '{raw_registrar}' not recognized; "
                "IPO saved without a mapped registrar."
            )

        normalized = _normalize_name(name)
        existing = existing_by_name.get(normalized)

        if existing:
            changed = False
            if existing.status != status:
                existing.status = status
                changed = True
            if close_dt is not None and existing.close_date != close_dt:
                existing.close_date = close_dt
                changed = True
            if registrar_id is not None and existing.registrar_id != registrar_id:
                existing.registrar_id = registrar_id
                changed = True
            if not existing.validated:
                existing.validated = True
                changed = True
            existing.source = "manual-upload"
            if changed:
                existing.synced_at = datetime.utcnow()
                updated += 1
        else:
            new_ipo = IPO(
                external_id=_make_manual_external_id(normalized),
                name=name,
                status=status,
                source="manual-upload",
                open_date=None,
                close_date=close_dt,
                synced_at=datetime.utcnow(),
                auto_detected=False,
                validated=True,
                registrar_id=registrar_id,
            )
            db.add(new_ipo)
            existing_by_name[normalized] = new_ipo
            created += 1

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save IPO records: {str(exc)}")

    return {
        "status": "success",
        "message": f"IPO import complete. {created} created, {updated} updated, {skipped} skipped.",
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "total_rows": len(df),
        "unmapped_registrars": unmapped[:10],
        "errors": errors[:10],
    }
