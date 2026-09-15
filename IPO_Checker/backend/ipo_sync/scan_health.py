"""
Registrar scan health — is the scraping still working?

THE GAP THIS CLOSES
-------------------
``ipo_sync/retire.py`` hides an IPO only when its registrar's portal was read
*conclusively* — a scrape that raised, or that returned zero options, proves
nothing about which names are live and is deliberately ignored. That is the
right call for one scan, and it has an unhappy failure mode across many scans:

    A portal changes its DOM. Every scan now raises, so ``conclusive`` stays
    empty, so nothing is ever retired. The dropdown quietly fills back up with
    IPOs whose allotment results are long gone — the original bug, restored and
    invisible, because a check against a retired-looking IPO still returns a
    confident "Not Allotted".

``/health`` and ``/health/db`` cannot catch this: both are green while the
scrapers are entirely broken. ``/health/scrapers`` reports a rolling
Website_Error signal from *checks*, which needs a user to have run one.

What was missing is a per-registrar record of whether the last scan actually
read the portal. This module keeps it: ``last_success_at``, ``last_attempt_at``
and a ``consecutive_failures`` count per registrar, surfaced at
``/health/registrars`` and logged once the count crosses
``SCAN_FAILURE_ALERT_THRESHOLD``.

Like ``retire.py``, the decision ("conclusive or not, and what is the new
failure count") is a pure function — ``plan_scan_health`` — with a thin,
never-raising DB writer around it.
"""

import datetime
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Consecutive unreadable scans before this is treated as "the scraper is
# broken" rather than "the portal had a bad minute". With the 6-hourly scan
# interval that is ~18 hours of a registrar being unreadable before an alert —
# long enough to ride out a transient outage, short enough to catch a DOM
# change well before it matters.
SCAN_FAILURE_ALERT_THRESHOLD = 3


@dataclass(frozen=True)
class ScanHealthUpdate:
    """What one registrar's health row should become after a scan."""

    registrar_name: str
    conclusive: bool
    live_name_count: int
    error: str | None
    consecutive_failures: int
    alerting: bool


def plan_scan_health(
    scan: dict | None,
    previous_failures: dict[str, int] | None = None,
    alert_threshold: int = SCAN_FAILURE_ALERT_THRESHOLD,
) -> list[ScanHealthUpdate]:
    """Decide each registrar's new health state after one scan. Pure.

    ``scan`` is a ``fetch_registrar_dropdown_scan()`` result. Every registrar
    that appears in ``conclusive`` or ``failed`` gets exactly one update;
    a registrar present in neither (the scan never got to it) is left alone
    rather than counted as a failure, because it was not attempted.

    A conclusive read resets ``consecutive_failures`` to 0 — that is what makes
    the counter "consecutive" rather than "total", so a single bad night years
    ago never contributes to a later alert.
    """
    scan = scan or {}
    conclusive = {str(n) for n in (scan.get("conclusive") or [])}
    failed = {str(k): v for k, v in (scan.get("failed") or {}).items()}
    live_names = scan.get("live_names") or {}
    previous = {str(k): int(v or 0) for k, v in (previous_failures or {}).items()}

    updates: list[ScanHealthUpdate] = []
    for registrar in sorted(conclusive | set(failed)):
        if registrar in conclusive:
            updates.append(ScanHealthUpdate(
                registrar_name=registrar,
                conclusive=True,
                live_name_count=len(live_names.get(registrar) or []),
                error=None,
                consecutive_failures=0,
                alerting=False,
            ))
            continue

        failures = previous.get(registrar, 0) + 1
        updates.append(ScanHealthUpdate(
            registrar_name=registrar,
            conclusive=False,
            live_name_count=0,
            error=failed.get(registrar),
            consecutive_failures=failures,
            alerting=failures >= alert_threshold,
        ))
    return updates


def record_scan_health(scan: dict | None) -> dict:
    """Persist the scan's outcome per registrar. Never raises.

    Called after every registrar dropdown scan, including one where every
    portal failed — that is the case this exists to make visible.
    """
    from db.models import RegistrarScanHealth
    from db.session import SessionLocal

    summary = {"recorded": 0, "healthy": [], "failing": [], "alerting": []}
    db = None
    try:
        db = SessionLocal()
        existing = {
            row.registrar_name: row for row in db.query(RegistrarScanHealth).all()
        }
        updates = plan_scan_health(
            scan, {name: row.consecutive_failures for name, row in existing.items()}
        )

        now = datetime.datetime.utcnow()
        for update in updates:
            row = existing.get(update.registrar_name)
            if row is None:
                row = RegistrarScanHealth(registrar_name=update.registrar_name)
                db.add(row)
                existing[update.registrar_name] = row

            row.last_attempt_at = now
            row.consecutive_failures = update.consecutive_failures
            row.last_error = (update.error or None)
            if update.conclusive:
                row.last_success_at = now
                row.last_error = None

            summary["recorded"] += 1
            (summary["healthy"] if update.conclusive else summary["failing"]).append(
                update.registrar_name
            )
            if update.alerting:
                summary["alerting"].append(update.registrar_name)

        db.commit()

        if summary["alerting"]:
            logger.error(
                "Registrar dropdown scan has failed %d+ consecutive times for: %s. "
                "IPOs on those portals can no longer be retired or newly published, "
                "because a scan that cannot read a portal proves nothing about which "
                "names are live. The portal's DOM has most likely changed.",
                SCAN_FAILURE_ALERT_THRESHOLD, ", ".join(summary["alerting"]),
            )
    except Exception as exc:  # noqa: BLE001 - health tracking must never break a sync
        logger.warning("Could not record registrar scan health: %s", exc)
        if db is not None:
            try:
                db.rollback()
            except Exception:  # noqa: BLE001 - best effort
                pass
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:  # noqa: BLE001 - best effort
                pass
    return summary


def snapshot() -> dict:
    """Current per-registrar scan health, for ``/health/registrars``. Never raises."""
    from db.models import RegistrarScanHealth
    from db.session import SessionLocal

    result = {
        "status": "ok",
        "alert_threshold": SCAN_FAILURE_ALERT_THRESHOLD,
        "registrars": [],
    }
    db = None
    try:
        db = SessionLocal()
        rows = db.query(RegistrarScanHealth).order_by(
            RegistrarScanHealth.registrar_name
        ).all()
        registrars = []
        for row in rows:
            failing = (row.consecutive_failures or 0) >= SCAN_FAILURE_ALERT_THRESHOLD
            registrars.append({
                "registrar": row.registrar_name,
                "healthy": not failing,
                "consecutive_failures": row.consecutive_failures or 0,
                "last_success_at": (
                    row.last_success_at.isoformat() if row.last_success_at else None
                ),
                "last_attempt_at": (
                    row.last_attempt_at.isoformat() if row.last_attempt_at else None
                ),
                "last_error": row.last_error,
            })
        result["registrars"] = registrars
        if any(not r["healthy"] for r in registrars):
            result["status"] = "degraded"
        elif not registrars:
            # No scan has completed since the health table was introduced — say
            # so rather than reporting a confident "everything is fine".
            result["status"] = "unknown"
            result["detail"] = "No registrar scan has been recorded yet."
    except Exception as exc:  # noqa: BLE001 - a health endpoint must not 500
        result["status"] = "unknown"
        result["detail"] = f"Registrar scan health is unavailable: {exc}"
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:  # noqa: BLE001 - best effort
                pass
    return result
