"""
Maps free-text registrar names from NSE/BSE/Upstox ("KFin Technologies
Ltd.", "Link Intime India Pvt Ltd", etc.) to the canonical registrar names
your `registrars` table uses.

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
    "MAS Services",
    "Skyline Financial Services",
    "Alankit",
    "Purva Sharegistry",
    "Cameo Corporate Services",
    "Adroit Corporate Services",
    "Sarthak Global",
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

    # MAS Services (active issue only; see live/mas.py)
    "mas": "MAS Services",
    "mas services": "MAS Services",
    "mas services limited": "MAS Services",
    "mas services ltd": "MAS Services",
    "mas services private limited": "MAS Services",
    "mas services pvt ltd": "MAS Services",

    # Skyline Financial Services
    "skyline": "Skyline Financial Services",
    "skyline financial": "Skyline Financial Services",
    "skyline financial services": "Skyline Financial Services",
    "skyline financial services private limited": "Skyline Financial Services",
    "skyline financial services pvt ltd": "Skyline Financial Services",
    "skyline rta": "Skyline Financial Services",

    # Alankit (registrar & share transfer agent)
    "alankit": "Alankit",
    "alankit assignments": "Alankit",
    "alankit assignments limited": "Alankit",
    "alankit assignments ltd": "Alankit",
    "alankit limited": "Alankit",
    "alankit ltd": "Alankit",

    # Purva Sharegistry
    "purva": "Purva Sharegistry",
    "purva sharegistry": "Purva Sharegistry",
    "purva sharegistry private limited": "Purva Sharegistry",
    "purva sharegistry pvt ltd": "Purva Sharegistry",
    "purvashare": "Purva Sharegistry",

    # Cameo Corporate Services
    "cameo": "Cameo Corporate Services",
    "cameo corporate": "Cameo Corporate Services",
    "cameo corporate services": "Cameo Corporate Services",
    "cameo corporate services limited": "Cameo Corporate Services",
    "cameo corporate services ltd": "Cameo Corporate Services",

    # Adroit Corporate Services (no verified endpoint yet)
    "adroit": "Adroit Corporate Services",
    "adroit corporate": "Adroit Corporate Services",
    "adroit corporate services": "Adroit Corporate Services",
    "adroit corporate services limited": "Adroit Corporate Services",
    "adroit corporate services pvt ltd": "Adroit Corporate Services",

    # Sarthak Global (no public allotment endpoint found)
    "sarthak": "Sarthak Global",
    "sarthak global": "Sarthak Global",
    "sarthak global limited": "Sarthak Global",
    "sarthak global ltd": "Sarthak Global",
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

    # Loose fallback: substring match against longer, distinctive aliases
    # (e.g. "KFIN TECHNOLOGIES LIMITED - REGISTRAR" still contains "kfin").
    # Short aliases such as "mas" match exactly only, so "christmas" can't
    # false-positive into MAS Services.
    for alias, canonical in _ALIASES.items():
        if len(alias) >= 4 and alias in key:
            return canonical

    return None
