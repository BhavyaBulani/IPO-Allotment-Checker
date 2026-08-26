"""
NSE official IPO listing source.

nseindia.com serves IPO data as JSON but 403s any request that doesn't look
like a real browser session: you must hit the homepage first to receive
cookies, then reuse that session for the API call with browser-like headers.

Known blocker: NSE rate-limits / blocks traffic from cloud provider IP
ranges (AWS, GCP, Azure, and by extension most PaaS hosts like Render).
If this keeps 403ing from your deployment, that's IP reputation, not a bug
here — see diagnose_sources.py and README notes on fallbacks.

NSE does not publish a stable schema for this endpoint, so field lookups
below try several known key variants and log a warning (not a crash) if a
row doesn't have a name/status we can parse.
"""

import logging
import requests

logger = logging.getLogger(__name__)

_HOMEPAGE_URL = "https://www.nseindia.com"
_IPO_URL = "https://www.nseindia.com/api/all-upcoming-issues?category=ipo"
_DETAIL_URL = "https://www.nseindia.com/api/ipo-detail?symbol={symbol}"
_REGISTRAR_TITLE = "Name of the Registrar"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/all-upcoming-issues-ipo",
}

# NSE's field names for this endpoint aren't documented and have shifted
# before, so we try each of these in order per logical field.
_NAME_KEYS = ["companyName", "symbol", "issueName", "name"]
_STATUS_KEYS = ["status", "seriesStatus", "issueStatus"]
_OPEN_DATE_KEYS = ["issueStartDate", "startDate", "openDate"]
_CLOSE_DATE_KEYS = ["issueEndDate", "endDate", "closeDate"]
_REGISTRAR_KEYS = ["registrar", "registrarName", "issueRegistrar"]

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


def _fetch_registrar_name(session: requests.Session, symbol) -> str | None:
    """Fetch the registrar for one symbol from NSE's per-IPO detail endpoint.

    The listing endpoint does not carry a registrar field, but the detail
    endpoint (same official exchange, same session) exposes it under
    ``issueInfo.dataList`` as {title: "Name of the Registrar", value: ...}.
    Returns None on any failure so the caller holds the IPO for review rather
    than guessing a registrar.
    """
    if not symbol:
        return None
    try:
        resp = session.get(_DETAIL_URL.format(symbol=str(symbol)), timeout=15)
        if resp.status_code != 200:
            return None
        payload = resp.json()
        data_list = (payload.get("issueInfo") or {}).get("dataList") or []
        for item in data_list:
            if isinstance(item, dict) and (item.get("title") or "") == _REGISTRAR_TITLE:
                value = item.get("value")
                return str(value).strip() if value else None
    except (requests.RequestException, ValueError, TypeError):
        logger.debug("NSE detail registrar fetch failed for %s", symbol, exc_info=True)
    return None


def fetch_nse_ipos() -> list[dict]:
    """
    Returns a list of dicts: {name, status, open_date, close_date, registrar_name}
    Never raises past this function for network/parsing errors — returns []
    and logs instead, matching auto_detect.py's expectation that a source
    failing doesn't take down the whole sync.
    """
    session = requests.Session()
    session.headers.update(_HEADERS)

    try:
        # Cookie warm-up: NSE 403s any API call that arrives without first
        # visiting a normal page in the same session.
        session.get(_HOMEPAGE_URL, timeout=10)
    except requests.RequestException as exc:
        logger.warning("NSE homepage warm-up failed: %s", exc)
        return []

    try:
        resp = session.get(_IPO_URL, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.warning("NSE IPO fetch failed: %s", exc)
        return []
    except ValueError as exc:
        logger.warning("NSE IPO response wasn't valid JSON: %s", exc)
        return []

    rows = payload if isinstance(payload, list) else payload.get("data", [])
    if not isinstance(rows, list):
        logger.warning("NSE IPO response shape unexpected: %r", type(payload))
        return []

    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = _first(row, _NAME_KEYS)
        status = _normalize_status(_first(row, _STATUS_KEYS))
        if not name or not status:
            logger.debug("Skipping unparseable NSE row: %r", row)
            continue
        symbol = row.get("symbol")
        registrar_name = _first(row, _REGISTRAR_KEYS) or _fetch_registrar_name(session, symbol)
        parsed.append({
            "name": str(name).strip(),
            "status": status,
            "open_date": _first(row, _OPEN_DATE_KEYS),
            "close_date": _first(row, _CLOSE_DATE_KEYS),
            "registrar_name": registrar_name,
        })

    logger.info("NSE source returned %d parseable IPO rows", len(parsed))
    return parsed
