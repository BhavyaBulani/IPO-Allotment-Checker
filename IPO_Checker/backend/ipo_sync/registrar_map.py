"""
Maps free-text registrar names from NSE/BSE/Upstox ("KFin Technologies
Ltd.", "Link Intime India Pvt Ltd", etc.) to the 4 canonical registrar
names your `registrars` table uses.

Unmapped variants return None so the caller can hold that IPO for manual
review instead of silently guessing or crashing.
"""

import re

# Canonical names — must match the `name` column seeded by
# scripts/seed_registrars.py and used by registrar_services/orchestrator.py
CANONICAL_REGISTRARS = [
    "Link Intime",
    "KFin Technologies",
    "Bigshare Services",
    "MUFG Intime",
]

# Known free-text variants seen from exchanges/aggregators, lowercased.
_ALIASES = {
    "link intime": "Link Intime",
    "link intime india": "Link Intime",
    "link intime india private limited": "Link Intime",
    "link intime india pvt ltd": "Link Intime",
    "link intime india pvt. ltd.": "Link Intime",

    "kfin": "KFin Technologies",
    "kfin technologies": "KFin Technologies",
    "kfin technologies ltd": "KFin Technologies",
    "kfin technologies limited": "KFin Technologies",
    "kfintech": "KFin Technologies",
    "karvy": "KFin Technologies",  # KFintech's former name
    "karvy fintech": "KFin Technologies",

    "bigshare": "Bigshare Services",
    "bigshare services": "Bigshare Services",
    "bigshare services ltd": "Bigshare Services",
    "bigshare services limited": "Bigshare Services",
    "bigshare services pvt ltd": "Bigshare Services",

    "mufg": "MUFG Intime",
    "mufg intime": "MUFG Intime",
    "mufg intime india": "MUFG Intime",
    "link intime (mufg)": "MUFG Intime",
    "mufg intime india private limited": "MUFG Intime",
}


def _normalize(value: str) -> str:
    value = re.sub(r"[.,]", "", value or "")
    value = re.sub(r"\s+", " ", value).strip().lower()
    return value


def resolve_registrar_name(raw_name: str | None) -> str | None:
    """
    Returns the canonical registrar name, or None if unmapped.
    None means "hold for review" to the caller — never guess.
    """
    if not raw_name:
        return None
    key = _normalize(raw_name)
    if key in _ALIASES:
        return _ALIASES[key]

    # Loose fallback: substring match against canonical names themselves,
    # e.g. raw "KFIN TECHNOLOGIES LIMITED - REGISTRAR" still contains "kfin".
    for alias, canonical in _ALIASES.items():
        if alias in key:
            return canonical

    return None
