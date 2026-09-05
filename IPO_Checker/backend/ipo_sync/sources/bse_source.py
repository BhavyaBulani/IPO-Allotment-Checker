"""
BSE official IPO listing source.

BSE's "Live / Forthcoming Issues" page is driven by:

    https://api.bseindia.com/BseIndiaAPI/api/GetPublicIssue_par_updated/w?flag=1

That endpoint returns JSON as ``{"Table": [...]}`` and needs a browser-like
User-Agent + Referer, otherwise it serves an HTML 404 page with HTTP 200 —
which shows up as "invalid JSON" rather than a clean HTTP error, so we guard
for that. This is the current replacement for the retired
``IPOMainboardCurrentIssue_New`` endpoint.

The feed mixes many instrument types, so only equity public offers
(``IR_FLAG_FULL`` of ``IPO`` / ``FPO``) are kept — rights issues (RI),
buybacks, OFS and other instruments on the same page are ignored. Status is
a single letter: ``F`` (Forthcoming) -> Upcoming and ``L`` (Live) -> Open.
"""

import logging
import requests

logger = logging.getLogger(__name__)

_IPO_URL = "https://api.bseindia.com/BseIndiaAPI/api/GetPublicIssue_par_updated/w?flag=1"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/markets/publicIssues/DisplayIPO.aspx",
}

_NAME_KEYS = ["Scrip_Name", "SCRIP_NAME", "CompanyName", "IssueName"]
_STATUS_KEYS = ["Status", "STATUS", "IssueStatus"]
_OPEN_DATE_KEYS = ["Start_Dt", "StartDate", "ISSUE_START_DATE"]
_CLOSE_DATE_KEYS = ["End_Dt", "EndDate", "ISSUE_END_DATE"]
_REGISTRAR_KEYS = ["Registrar", "REGISTRAR_NAME", "RegistrarName"]

# Only these instrument types are equity public offers relevant to an IPO
# allotment check. The same feed also carries RI (rights issue), OTB, CMN,
# BuyBack and others under the "Live / Forthcoming Issues" page.
_EQUITY_IR_FLAGS = {"IPO", "FPO"}

_STATUS_NORMALIZE = {
    "open": "Open",
    "active": "Open",
    "live": "Open",
    "l": "Open",          # BSE single-letter status: subscription currently open
    "forthcoming": "Upcoming",
    "upcoming": "Upcoming",
    "f": "Upcoming",      # BSE single-letter status: not yet open
    "closed": "Closed",
    # "listed" means trading has begun, i.e. allotment is final and the
    # result is available on the registrar portal — the only state where an
    # allotment check can return a real verdict.
    "listed": "Allotment Announced",
}


def _first(row: dict, keys: list[str]):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_status(raw_status) -> str | None:
    if not raw_status:
        return None
    return _STATUS_NORMALIZE.get(str(raw_status).strip().lower())


def fetch_bse_ipos() -> list[dict]:
    """
    Returns a list of dicts: {name, status, open_date, close_date, registrar_name}
    Never raises — returns [] and logs on any failure.
    """
    try:
        resp = requests.get(_IPO_URL, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.warning("BSE IPO fetch failed: %s", exc)
        return []
    except ValueError as exc:
        logger.warning(
            "BSE IPO response wasn't valid JSON (likely an HTML block page "
            "instead of data — check User-Agent/Referer headers): %s", exc
        )
        return []

    rows = payload if isinstance(payload, list) else payload.get("Table", payload.get("data", []))
    if not isinstance(rows, list):
        logger.warning("BSE IPO response shape unexpected: %r", type(payload))
        return []

    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        ir_flag = str(row.get("IR_FLAG_FULL") or row.get("IR_flag") or "").strip().upper()
        if ir_flag not in _EQUITY_IR_FLAGS:
            continue
        name = _first(row, _NAME_KEYS)
        status = _normalize_status(_first(row, _STATUS_KEYS))
        if not name or not status:
            logger.debug("Skipping unparseable BSE row: %r", row)
            continue
        parsed.append({
            "name": str(name).strip(),
            "status": status,
            "open_date": _first(row, _OPEN_DATE_KEYS),
            "close_date": _first(row, _CLOSE_DATE_KEYS),
            "registrar_name": _first(row, _REGISTRAR_KEYS),
        })

    logger.info("BSE source returned %d parseable IPO rows", len(parsed))
    return parsed
