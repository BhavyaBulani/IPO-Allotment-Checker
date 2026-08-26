"""
Seeds the `registrars` table.

IDs here MUST stay in this exact order — registrar_services/orchestrator.py
hardcodes 1=Link Intime, 2=KFin, 3=Bigshare, 4=MUFG, 5=MAS Services, and
ipo_sync/registrar_map.py's CANONICAL_REGISTRARS list uses these same
`name` values to resolve which registrar an IPO maps to. Registrars without
a verified live module are seeded active=False so they surface for review
instead of being checked against a half-built integration.

Safe to run multiple times: inserts missing names and updates existing rows'
``active`` / ``priority`` / ``endpoint_type`` to match this list, so re-running
is how you activate a registrar whose module was added later (e.g. Alankit,
Purva). IDs are assigned in this order on a fresh database.

Usage:
    cd IPO_Checker/backend
    python scripts/seed_registrars.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import Registrar, EndpointType

REGISTRARS = [
    {"name": "Link Intime", "priority": 1, "endpoint_type": EndpointType.browser_automation, "active": True},
    {"name": "KFin Technologies", "priority": 2, "endpoint_type": EndpointType.browser_automation, "active": True},
    {"name": "Bigshare Services", "priority": 3, "endpoint_type": EndpointType.browser_automation, "active": True},
    {"name": "MUFG Intime", "priority": 4, "endpoint_type": EndpointType.browser_automation, "active": True},
    {"name": "MAS Services", "priority": 5, "endpoint_type": EndpointType.browser_automation, "active": True},
    # The rest are mapped but not yet checkable: no verified live module, or
    # the portal can't be parsed safely. Keep active=False.
    #
    # Skyline (display_ipo_rightissue_allotment.php): posts company + PAN/CAF/
    # client_id + csrf and reCAPTCHA-v3 site key, but the result region
    # (.searchapp) is EMPTY for a no-record PAN — and stays empty even with a
    # real reCAPTCHA v3 token. There is no "no record" marker and the
    # allotted shape is unobserved, so an empty page is ambiguous between
    # "not allotted" and a silent failure; do not map it to Not_Allotted.
    # Cameo: portal is currently returning HTTP 500. Adroit/Sarthak: no public
    # allotment endpoint is mapped yet.
    {"name": "Skyline Financial Services", "priority": 6, "endpoint_type": EndpointType.browser_automation, "active": False},
    {"name": "Alankit", "priority": 7, "endpoint_type": EndpointType.browser_automation, "active": True},
    {"name": "Purva Sharegistry", "priority": 8, "endpoint_type": EndpointType.browser_automation, "active": True},
    {"name": "Cameo Corporate Services", "priority": 9, "endpoint_type": EndpointType.browser_automation, "active": False},
    {"name": "Adroit Corporate Services", "priority": 10, "endpoint_type": EndpointType.browser_automation, "active": False},
    {"name": "Sarthak Global", "priority": 11, "endpoint_type": EndpointType.browser_automation, "active": False},
]


def seed_registrars():
    db = SessionLocal()
    try:
        existing = {r.name: r for r in db.query(Registrar).all()}
        added = 0
        updated = 0
        for row in REGISTRARS:
            name = row["name"]
            registrar = existing.get(name)
            if registrar is None:
                db.add(Registrar(**row))
                added += 1
                print(f"Adding registrar: {name}")
                continue
            changed = []
            for field in ("active", "priority", "endpoint_type"):
                if getattr(registrar, field) != row[field]:
                    setattr(registrar, field, row[field])
                    changed.append(field)
            if changed:
                updated += 1
                print(f"Updating '{name}': {', '.join(changed)}")
            else:
                print(f"Unchanged '{name}'.")
        db.commit()
        print(f"Done. Added {added}, updated {updated} registrar(s).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_registrars()
