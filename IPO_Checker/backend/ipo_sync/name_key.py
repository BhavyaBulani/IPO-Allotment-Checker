"""
The single name-matching key for IPO rows.

WHY THIS MODULE EXISTS
----------------------
The same company reaches this app under several spellings: an exchange calls
it "Tempsens Instruments (India) Limited", a registrar dropdown calls it
"TEMPSENS INSTRUMENTS INDIA LTD", a manual upload spreadsheet calls it
"Tempsens Instruments Limited - SME". All three describe one IPO, and the app
must map them to one row — otherwise the dropdown shows the same company twice
and a check can be routed against a row the registrar does not know.

Before this module there were three separate implementations of that key:

  * ``ipo_sync.reconcile._normalize_name_for_match``
  * ``ipo_sync.auto_detect._normalize_name_loose``
  * ``api.endpoints.ipos._normalize_name``

The first two were identical, but the third — the one the *manual upload* path
uses — did not strip "SME" or parenthetical qualifiers. So "Ashutosh Fibre"
and "ASHUTOSH FIBRE LIMITED SME" produced two different keys on the upload
path and two rows in ``ipos``, which is exactly the duplicate pair observed in
production. Worse, ``ipos.name`` had no uniqueness constraint behind it, so
nothing caught it.

There is now one implementation, and ``ipos.name_key`` stores its output with
a unique index over it, so a duplicate is rejected by the database rather than
noticed by a human later.

The normalizer is deliberately conservative: it folds legal suffixes
(Ltd/Limited/Pvt/Private), trailing "SME" exchange tags, parenthetical
qualifiers, and hyphen-vs-space differences. It does NOT fold arbitrary
similarity — two genuinely different companies must never share a key, because
the unique index would then reject a legitimate row.
"""

import re

# Longest name allowed by db.models.IPO.name (String(200)); one key column is
# String(255) so a key can never be silently truncated into a collision.
MAX_NAME_KEY_LENGTH = 255

_AMPERSAND_RE = re.compile(r"\s*&\s*")
_PARENTHETICAL_RE = re.compile(r"\([^)]*\)")
_DASH_RE = re.compile(r"[-\u2013\u2014]")
_LEGAL_SUFFIX_RE = re.compile(r"\b(limited|ltd|private|pvt)\b\.?", re.IGNORECASE)
_SME_TAG_RE = re.compile(r"\bsme\b\.?", re.IGNORECASE)
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_ipo_name(value) -> str:
    """Return the matching key for an IPO name ("" when there is nothing usable).

    ``None``, empty and whitespace-only input all yield "" so callers can treat
    a falsy return as "no usable name" instead of special-casing None.
    """
    text = "" if value is None else str(value)
    # "A & B Ltd" and "A and B Limited" are the same issuer.
    text = _AMPERSAND_RE.sub(" and ", text)
    # Parenthetical qualifiers ("(India)", "(NSE)", "(Formerly X)") carry no
    # matching signal.
    text = _PARENTHETICAL_RE.sub(" ", text)
    # Hyphens/en-dashes are usually just spacing: "Fly-Hi" == "Fly Hi".
    text = _DASH_RE.sub(" ", text)
    text = _LEGAL_SUFFIX_RE.sub("", text)
    # A trailing/embedded SME marker is an exchange tag, not part of the name.
    text = _SME_TAG_RE.sub("", text)
    return _WHITESPACE_RE.sub(" ", text).strip().lower()[:MAX_NAME_KEY_LENGTH]


def name_keys_match(a, b) -> bool:
    """True when two names refer to the same IPO. False when either is unusable."""
    key_a, key_b = normalize_ipo_name(a), normalize_ipo_name(b)
    return bool(key_a) and key_a == key_b
