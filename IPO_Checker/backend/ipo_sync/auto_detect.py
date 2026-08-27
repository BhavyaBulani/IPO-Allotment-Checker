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
from ipo_sync.sources.upstox_source import fetch_upstox_ipos
from ipo_sync.sources.registrar_dropdown_source import fetch_registrar_checkable_ipos
from ipo_sync.reconcile import reconcile, ReconciledIPO

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "Open": IPOStatus.Open,
    "Upcoming": IPOStatus.Upcoming,
    "Closed": IPOStatus.Closed,
    "Allotment Announced": IPOStatus.Allotment_Announced,
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
    # Match on the same suffix-insensitive key everywhere so a dropdown name
    # like "Foo Ltd" and an exchange name "Foo Limited" update one row instead
    # of creating a duplicate.
    return _normalize_name_loose(value)


def _normalize_name_loose(value: str) -> str:
    """Name key that ignores legal-suffix differences (Ltd/Pvt/Limited)."""
    value = re.sub(r"\b(limited|ltd|private|pvt)\b\.?", "", value or "", flags=re.I)
    return re.sub(r"\s+", " ", value).strip().lower()


# Link Intime and MUFG Intime are the same portal (MUFG is the renamed
# Link Intime), so an IPO mapped to either registrar is checkable there.
_LINK_MUFG_PAIR = {"Link Intime", "MUFG Intime"}


def _registrars_compatible(a: str | None, b: str | None) -> bool:
    """True when two canonical registrar names describe the same portal."""
    if not a or not b:
        return True
    if a == b:
        return True
    return {a, b} == _LINK_MUFG_PAIR


def _merge_checkable(records: list[ReconciledIPO], dropdown_rows: list[dict]) -> list[ReconciledIPO]:
    """Promote exchange records whose name is live on their registrar portal.

    A name present in its registrar's allotment dropdown is the authoritative
    "results are live" signal, so it promotes the status to Allotment Announced
    and clears validation. Promotion is additive and name-matched only: we
    never create new IPO rows from the registrar list (those lists also carry
    NCDs/INVITs/REITs/SMEs), and a name not in the exchange feeds simply gets
    no promotion — fail in the safe direction.

    Pure function (no DB) so the promotion rule can be unit-tested.
    """
    checkable_by_name: dict[str, dict] = {}
    for row in dropdown_rows:
        key = _normalize_name_loose(row.get("name"))
        if key:
            checkable_by_name[key] = row

    merged: list[ReconciledIPO] = []
    for record in records:
        key = _normalize_name_loose(record.name)
        checkable = checkable_by_name.get(key)
        if checkable and _registrars_compatible(record.registrar_name, checkable.get("registrar_name")):
            record.status = "Allotment Announced"
            # The registrar portal literally lists this company, so it is the
            # authoritative registrar for the row — not just a status signal.
            record.registrar_name = checkable.get("registrar_name") or record.registrar_name
            if "registrar-dropdown" not in record.sources:
                record.sources = list(record.sources) + ["registrar-dropdown"]
            record.validated = True
        merged.append(record)
    return merged


def _dropdown_only_records(records: list[ReconciledIPO], dropdown_rows: list[dict]) -> list[ReconciledIPO]:
    """Create Allotment Announced records for dropdown names absent from exchange feeds.

    The registrar allotment dropdown is the authoritative list of "results are
    live right now". If an exchange feed is blocked or a company has already
    dropped off NSE/BSE's upcoming-issues endpoint, the dropdown is the only
    place its checkable name appears — so we create the row directly instead of
    waiting for a promotion. Non-equity instruments are already filtered in the
    source, so these are real, checkable equity IPOs.
    """
    existing_keys = {_normalize_name_loose(r.name) for r in records}
    created: list[ReconciledIPO] = []
    seen: set[str] = set()
    for row in dropdown_rows:
        name = row.get("name")
        if not name:
            continue
        key = _normalize_name_loose(name)
        if not key or key in existing_keys or key in seen:
            continue
        seen.add(key)
        created.append(ReconciledIPO(
            name=str(name).strip(),
            status="Allotment Announced",
            open_date=None,
            close_date=None,
            registrar_name=row.get("registrar_name"),
            sources=["registrar-dropdown"],
            validated=True,
            reason="listed on registrar allotment portal",
        ))
    return created


def _parse_date(value) -> datetime.datetime | None:
    """Coerce a source date (str / datetime / date) into a naive datetime.

    NSE/BSE return dates as free-text strings (e.g. '28-Aug-2026'); the
    model columns are DateTime, and MySQL rejects the raw string. If the
    value can't be parsed we return None (store NULL) rather than crash the
    whole sync on one malformed row.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value
    if isinstance(value, datetime.date):
        return datetime.datetime(value.year, value.month, value.day)

    text = str(value).strip()
    if not text:
        return None

    for fmt in (
        "%d-%b-%Y",           # 28-Aug-2026
        "%d %b %Y",           # 28 Aug 2026
        "%d/%m/%Y",           # 28/08/2026
        "%d-%m-%Y",           # 28-08-2026
        "%Y-%m-%d",           # 2026-08-28
        "%Y/%m/%d",           # 2026/08/28
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue

    try:
        return datetime.datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


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
    open_dt = _parse_date(record.open_date)
    close_dt = _parse_date(record.close_date)

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
        if open_dt is not None and existing.open_date != open_dt:
            existing.open_date = open_dt
            changed = True
        if close_dt is not None and existing.close_date != close_dt:
            existing.close_date = close_dt
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
        open_date=open_dt,
        close_date=close_dt,
        synced_at=datetime.datetime.utcnow(),
        auto_detected=True,
        validated=final_validated,
        registrar_id=registrar_id,
    )
    db.add(new_ipo)
    return "added"


def sync_ipos(include_registrar_dropdown: bool | None = None) -> dict:
    """
    Main entry point. Fetches NSE + BSE (+ Upstox), reconciles, and — when
    enabled — promotes IPOs whose allotment is live on their registrar portal
    (the authoritative "Allotment Announced" signal).

    ``include_registrar_dropdown`` defaults to the
    ENABLE_REGISTRAR_DROPDOWN_DISCOVERY env var (default off) so the 4-hour
    HTTP sync stays fast; the nightly job passes True to run the Playwright
    dropdown scan.

    Never raises — callers (startup hook, scheduled job, admin endpoint)
    all expect a dict back even on partial/total failure.
    """
    if include_registrar_dropdown is None:
        raw = os.environ.get("ENABLE_REGISTRAR_DROPDOWN_DISCOVERY", "0")
        include_registrar_dropdown = raw.strip().lower() in {"1", "true", "yes", "on"}

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

    try:
        upstox_rows = fetch_upstox_ipos()
    except Exception as exc:
        logger.error("Upstox fetch raised unexpectedly: %s", exc, exc_info=True)
        upstox_rows = []

    dropdown_rows = []
    if include_registrar_dropdown:
        try:
            dropdown_rows = fetch_registrar_checkable_ipos()
        except Exception as exc:
            logger.error("Registrar dropdown discovery raised unexpectedly: %s", exc, exc_info=True)
            dropdown_rows = []

    if not nse_rows and not bse_rows and not upstox_rows and not dropdown_rows:
        logger.warning("NSE, BSE, Upstox, and registrar dropdowns were all unreachable this run. Database left unchanged.")
        return {"added": 0, "updated": 0, "held_for_review": 0, "source": "none"}

    records = reconcile(nse_rows, bse_rows, upstox_rows)
    records = _merge_checkable(records, dropdown_rows)
    records += _dropdown_only_records(records, dropdown_rows)

    db = SessionLocal()
    added = updated = held_for_review = 0
    try:
        existing_by_name = {
            _normalize_name_for_match(ipo.name): ipo for ipo in db.query(IPO).all()
        }
        for record in records:
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
        s for s, rows in (
            ("NSE", nse_rows),
            ("BSE", bse_rows),
            ("Upstox", upstox_rows),
            ("registrar-dropdown", dropdown_rows),
        ) if rows
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
