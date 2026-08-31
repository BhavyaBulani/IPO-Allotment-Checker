"""
FinAPI (finapi.upvaly.com) IPO catalog source.

A structured, API-key-authenticated REST API. ``/api/ipo`` returns a catalog
of 50 IPOs with a per-issue schedule, price band, lot size and type — more
coverage than NSE/BSE's upcoming-issues endpoints, and not subject to NSE's
cloud-IP blocking.

Status handling
---------------
FinAPI reports ``status`` as LIVE / UPCOMING / CLOSED. "listed" is derived
from ``schedule.listingDate`` being in the past -> ``Allotment Announced``,
matching the convention used by every other source (listing means allotment
is final and the result is checkable on the registrar portal).

Registrar
---------
The catalog endpoint does not expose a registrar. Rows from this source are
therefore held for review unless the same company also appears in a source
that does provide a registrar (ipotracker/NSE/BSE/Upstox), so an allotment
check can always be routed.

Environment variables:

    FINAPI_BASE_URL  default https://finapi.upvaly.com
    FINAPI_API_KEY   required; missing -> logs and returns []
"""

import datetime
import logging
import os

import requests

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "https://finapi.upvaly.com"

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

_STATUS_MAP = {
    "LIVE": "Open",
    "UPCOMING": "Upcoming",
    "CLOSED": "Closed",
}


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _derive_status(raw_status, listing_date, today) -> str | None:
    listing = _parse_date(listing_date)
    if listing and today > listing:
        return "Allotment Announced"
    return _STATUS_MAP.get(str(raw_status or "").strip().upper())


def fetch_finapi_ipos() -> list[dict]:
    """
    Return parsed IPO rows from FinAPI's ``/api/ipo`` catalog.

    Never raises — on any auth/network/parsing failure it logs a warning and
    returns [], matching the contract the other sources follow.
    """
    api_key = os.environ.get("FINAPI_API_KEY")
    if not api_key:
        logger.info("FINAPI_API_KEY not set — skipping FinAPI source.")
        return []

    base = (os.environ.get("FINAPI_BASE_URL") or _DEFAULT_BASE_URL).rstrip("/")
    try:
        resp = requests.get(
            f"{base}/api/ipo",
            headers={"X-API-Key": api_key, "Accept": "application/json"},
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("FinAPI IPO fetch failed: %s", exc)
        return []

    rows = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        logger.warning("FinAPI IPO response shape unexpected: %r", type(payload))
        return []

    today = datetime.datetime.now(IST).date()
    parsed: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        schedule = row.get("schedule") or {}
        open_date = schedule.get("startDate")
        close_date = schedule.get("endDate")
        listing_date = schedule.get("listingDate")
        # FinAPI's catalog also carries rumoured/filed names (NSE, OYO,
        # PhonePe, ...) with no schedule at all. Those have no open/close/
        # listing date, so they're noise for an allotment checker — skip them.
        if not (open_date or close_date or listing_date):
            logger.debug("Skipping FinAPI row without any schedule dates: %r", row)
            continue
        name = (row.get("name") or row.get("symbol") or "").strip()
        status = _derive_status(
            row.get("status"),
            listing_date,
            today,
        )
        if not name or not status:
            logger.debug("Skipping unparseable FinAPI row: %r", row)
            continue

        parsed.append({
            "name": name,
            "status": status,
            "open_date": open_date,
            "close_date": close_date,
            "registrar_name": None,
            # Optional enrichment fields (not yet persisted to the model).
            "symbol": row.get("symbol"),
            "ipo_type": row.get("type"),
            "lot_size": row.get("lotSize"),
            "price_band": row.get("priceRange"),
            "listing_date": listing_date,
            "allotment_date": schedule.get("allotmentFinalization"),
        })

    logger.info("FinAPI source returned %d parseable IPO rows", len(parsed))
    return parsed


def _load_backend_env() -> None:
    """Best-effort .env load so the CLI works when run directly."""
    from pathlib import Path

    candidates = [
        Path(__file__).resolve().parent.parent.parent / ".env",  # backend/.env
        Path.cwd() / ".env",
    ]
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    for path in candidates:
        if path.exists():
            load_dotenv(path, override=False)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    _load_backend_env()

    rows = fetch_finapi_ipos()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    print(f"rows: {len(rows)}  status: {counts}")
    for row in rows:
        line = (
            f"[{row['status']:18}] {row['name'][:40]:40} | "
            f"open {row.get('open_date')} | close {row.get('close_date')} | "
            f"type {row.get('ipo_type') or ''}"
        )
        print(line.encode("ascii", "replace").decode())
