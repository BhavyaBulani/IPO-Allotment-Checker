"""
BSE official IPO listing source.

api.bseindia.com serves this as free public JSON, no key needed. It's less
aggressive about blocking than NSE but can still return an HTML error page
for a plain requests.get() without a browser-like User-Agent — this shows
up as "invalid JSON" rather than a clean HTTP error, so we guard for that.

Field names are unconfirmed against a live response (see diagnose_sources.py)
and may need adjusting in _NAME_KEYS etc. once you've verified them.
"""

import logging
import requests

logger = logging.getLogger(__name__)

_IPO_URL = "https://api.bseindia.com/BseIndiaAPI/api/IPOMainboardCurrentIssue_New/w"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
}

_NAME_KEYS = ["Scrip_Name", "SCRIP_NAME", "CompanyName", "IssueName"]
_STATUS_KEYS = ["Status", "STATUS", "IssueStatus"]
_OPEN_DATE_KEYS = ["Start_Date", "StartDate", "ISSUE_START_DATE"]
_CLOSE_DATE_KEYS = ["End_Date", "EndDate", "ISSUE_END_DATE"]
_REGISTRAR_KEYS = ["Registrar", "REGISTRAR_NAME", "RegistrarName"]

_STATUS_NORMALIZE = {
    "open": "Open",
    "active": "Open",
    "forthcoming": "Upcoming",
    "upcoming": "Upcoming",
    "closed": "Closed",
    "listed": "Closed",
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
