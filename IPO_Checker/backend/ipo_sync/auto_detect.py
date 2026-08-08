"""
IPO auto-sync orchestration.

This replaces the old aggregator-scraping pipeline (Chittorgarh /
Upstox / Moneycontrol HTML scraping) with two official exchange
sources — NSE and BSE — that are cross-checked against each other
before anything is auto-published to the client-facing IPO dropdown.

Flow:
    1. Fetch raw rows from NSE and BSE independently (sources/).
    2. Reconcile them: agree on name/status/registrar -> validated=True,
       disagree or unmapped registrar -> validated=False (review queue).
    3. Upsert into the `ipos` table, matching existing rows by
       normalized name (not external_id — NSE/BSE don't give us a
       stable external id we can rely on across sources).
    4. Resolve `registrar_id` from the reconciled registrar name so
       downstream allotment checks route to the correct registrar
       scraper instead of guessing.

Entry point `sync_ipos()` is intentionally kept as the public function
name — main.py, jobs/sync_job.py, and api/endpoints/sync.py all import
it by this name and none of them need to change.
"""

import datetime
import logging
import re
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import IPO, IPOStatus, Registrar
from ipo_sync.sources.nse_source import fetch_nse_ipos
from ipo_sync.sources.bse_source import fetch_bse_ipos
from ipo_sync.reconcile import reconcile, ReconciledIPO

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "Open": IPOStatus.Open,
    "Upcoming": IPOStatus.Upcoming,
    "Closed": IPOStatus.Closed,
}


def is_sane_ipo(name: str, status: IPOStatus) -> bool:
    """Final sanity guard applied regardless of source or validation state."""
    if not name or len(name) < 3 or len(name) > 150:
        return False
    if re.search(r"[<>{}\\[\\]]", name):
        return False
    if status not in _STATUS_MAP.values():
        return False
    return True


def _normalize_name_for_match(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _resolve_registrar_id(db, registrar_name: str | None) -> int | None:
    if not registrar_name:
        return None
    registrar = db.query(Registrar).filter(Registrar.name == registrar_name).first()
    if not registrar:
        logger.warning(
            "Registrar '%s' is mapped by name but has no row in the registrars table yet. "
            "IPOs referencing it will be held for review until it's seeded.",
            registrar_name,
        )
        return None
    return registrar.id


def _upsert(db, record: ReconciledIPO, existing_by_name: dict[str, IPO]) -> str:
    """Returns 'added', 'updated', or 'unchanged'."""
    status_enum = _STATUS_MAP.get(record.status, IPOStatus.Upcoming)
    is_valid_shape = is_sane_ipo(record.name, status_enum)
    final_validated = record.validated and is_valid_shape

    registrar_id = _resolve_registrar_id(db, record.registrar_name)
    if record.registrar_name and registrar_id is None:
        # Mapped to a name, but that registrar isn't seeded in the DB yet —
        # don't auto-publish an IPO we can't route a check for.
        final_validated = False

    # Matched by normalized name, not external_id: NSE/BSE don't give us a
    # stable id we can rely on across sources or across sync runs, and a
    # company should map to exactly one IPO row regardless of which
    # exchange(s) most recently reported it.
    normalized_name = _normalize_name_for_match(record.name)
    existing = existing_by_name.get(normalized_name)

    if existing:
        changed = False
        if existing.status != status_enum:
            existing.status = status_enum
            changed = True
        if record.open_date and existing.open_date != record.open_date:
            existing.open_date = record.open_date
            changed = True
        if record.close_date and existing.close_date != record.close_date:
            existing.close_date = record.close_date
            changed = True
        if existing.registrar_id != registrar_id:
            existing.registrar_id = registrar_id
            changed = True
        if existing.validated != final_validated:
            existing.validated = final_validated
            changed = True
        existing.source = "+".join(record.sources)
        if changed:
            existing.synced_at = datetime.datetime.utcnow()
            return "updated"
        return "unchanged"

    new_ipo = IPO(
        external_id=f"{'-'.join(s.lower() for s in record.sources)}-{normalized_name.replace(' ', '-')[:80]}",
        name=record.name,
        status=status_enum,
        source="+".join(record.sources),
        open_date=record.open_date,
        close_date=record.close_date,
        synced_at=datetime.datetime.utcnow(),
        auto_detected=True,
        validated=final_validated,
        registrar_id=registrar_id,
    )
    db.add(new_ipo)
    return "added"


def sync_ipos() -> dict:
    """
    Main entry point. Fetches NSE + BSE, reconciles, upserts.
    Returns a summary dict: added, updated, held_for_review, source.
    Never raises — callers (startup hook, scheduled job, admin endpoint)
    all expect a dict back even on partial/total failure.
    """
    try:
        nse_rows = fetch_nse_ipos()
    except Exception as exc:
        logger.error("NSE fetch raised unexpectedly: %s", exc, exc_info=True)
        nse_rows = []

    try:
        bse_rows = fetch_bse_ipos()
    except Exception as exc:
        logger.error("BSE fetch raised unexpectedly: %s", exc, exc_info=True)
        bse_rows = []

    if not nse_rows and not bse_rows:
        logger.warning("Both NSE and BSE were unreachable this run. Database left unchanged.")
        return {"added": 0, "updated": 0, "held_for_review": 0, "source": "none"}

    reconciled = reconcile(nse_rows, bse_rows)

    db = SessionLocal()
    added = updated = held_for_review = 0
    try:
        existing_by_name = {
            _normalize_name_for_match(ipo.name): ipo for ipo in db.query(IPO).all()
        }
        for record in reconciled:
            outcome = _upsert(db, record, existing_by_name)
            if outcome == "added":
                added += 1
            elif outcome == "updated":
                updated += 1
            if not record.validated:
                held_for_review += 1
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Database error during IPO sync: %s", exc, exc_info=True)
        return {"added": 0, "updated": 0, "held_for_review": 0, "source": "error", "error": str(exc)}
    finally:
        db.close()

    sources_used = "+".join(
        s for s, rows in (("NSE", nse_rows), ("BSE", bse_rows)) if rows
    ) or "none"

    logger.info(
        "IPO sync complete. Added: %d, Updated: %d, Held for review: %d, Sources: %s",
        added, updated, held_for_review, sources_used,
    )
    return {
        "added": added,
        "updated": updated,
        "held_for_review": held_for_review,
        "source": sources_used,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = sync_ipos()
    print(f"Sync result: {result}")
