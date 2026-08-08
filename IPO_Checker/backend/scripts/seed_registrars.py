"""
Seeds the `registrars` table.

IDs here MUST stay in this exact order — registrar_services/orchestrator.py
hardcodes 1=Link Intime, 2=KFin, 3=Bigshare, 4=MUFG, and
ipo_sync/registrar_map.py's CANONICAL_REGISTRARS list uses these same
`name` values to resolve which registrar an IPO maps to.

Safe to run multiple times: skips any name that already exists.

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
]


def seed_registrars():
    db = SessionLocal()
    try:
        existing_names = {r.name for r in db.query(Registrar).all()}
        added = 0
        for row in REGISTRARS:
            if row["name"] in existing_names:
                print(f"Skipping '{row['name']}' — already seeded.")
                continue
            db.add(Registrar(**row))
            added += 1
            print(f"Adding registrar: {row['name']}")
        db.commit()
        print(f"Done. Added {added} new registrar(s).")
    finally:
        db.close()


if __name__ == "__main__":
    seed_registrars()
