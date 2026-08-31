"""
ipotracker.site IPO catalog source.

The user's own IPO tracker (a Next.js app backed by Supabase). Its
``ipo_catalog`` table is the master list that still contains IPOs *after*
their subscription window closes — exactly the rows NSE/BSE's
``all-upcoming-issues`` endpoints stop returning once an issue closes. That
makes this source the fallback that keeps closed/listed IPOs checkable.

Auth flow: Supabase email/password -> access token -> PostgREST select on
``ipo_catalog``. The table has no status column, so status is derived from
dates the same way the standalone ``tools/ipotracker`` probe does:

    upcoming: today < opening_date
    open:     opening_date <= today <= closing_date
    closed:   closing_date < today <= listing_date
    listed:   listing_date < today            -> "Allotment Announced"

Environment variables (all required; missing any -> the source logs and
returns [] rather than raising):

    IPOT_SUPABASE_URL  e.g. https://<ref>.supabase.co
    IPOT_ANON_KEY      Supabase publishable (anon) key
    IPOT_EMAIL         account email
    IPOT_PASSWORD      account password

The returned dicts carry the same ``{name, status, open_date, close_date,
registrar_name}`` contract as the other sources, plus ``symbol``,
``ipo_type``, ``lot_size``, ``issue_size``, ``price_band_lower``,
``price_band_upper``, ``listing_date`` and ``allotment_date`` as optional
enrichment fields for future persistence.
"""

import datetime
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))

_STATUS_MAP = {
    "upcoming": "Upcoming",
    "open": "Open",
    "closed": "Closed",
    "listed": "Allotment Announced",
}

# ipotracker's display ``name`` often carries a trailing "- IPO" or " IPO"
# suffix (and sometimes a legal suffix too). Strip the "IPO" marker so the
# stored name matches the plain company name used by the exchanges and the
# live registrar checkers, and so cross-source matching doesn't diverge.
_IPO_SUFFIX_RE = re.compile(r"\s*[-\u2013]?\s*IPO\s*$", re.IGNORECASE)


def _clean_name(value) -> str:
    name = (value or "").strip()
    return _IPO_SUFFIX_RE.sub("", name).strip()


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _derive_status(opening_date, closing_date, listing_date, today):
    op = _parse_date(opening_date)
    cl = _parse_date(closing_date)
    li = _parse_date(listing_date)
    if op and today < op:
        return "upcoming"
    if op and cl and op <= today <= cl:
        return "open"
    if cl and today > cl and (not li or today <= li):
        return "closed"
    if li and today > li:
        return "listed"
    return None


def _login(base: str, anon_key: str, email: str, password: str) -> str | None:
    resp = requests.post(
        f"{base}/auth/v1/token?grant_type=password",
        json={"email": email, "password": password},
        headers={"apikey": anon_key, "Content-Type": "application/json"},
        timeout=20,
    )
    resp.raise_for_status()
    return (resp.json() or {}).get("access_token")


def fetch_ipotracker_ipos() -> list[dict]:
    """
    Return parsed IPO rows from ipotracker's ``ipo_catalog``.

    Never raises — on any auth/network/parsing failure it logs a warning and
    returns [], matching the contract the other sources follow.
    """
    supabase_url = (os.environ.get("IPOT_SUPABASE_URL") or "").rstrip("/")
    anon_key = os.environ.get("IPOT_ANON_KEY")
    email = os.environ.get("IPOT_EMAIL")
    password = os.environ.get("IPOT_PASSWORD")

    if not (supabase_url and anon_key and email and password):
        logger.info(
            "ipotracker env vars not set (IPOT_SUPABASE_URL / IPOT_ANON_KEY / "
            "IPOT_EMAIL / IPOT_PASSWORD) — skipping ipotracker source."
        )
        return []

    try:
        access_token = _login(supabase_url, anon_key, email, password)
        if not access_token:
            logger.warning("ipotracker login returned no access token.")
            return []
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("ipotracker login failed: %s", exc)
        return []

    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    try:
        resp = requests.get(
            f"{supabase_url}/rest/v1/ipo_catalog?select=*",
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        rows = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning("ipotracker ipo_catalog fetch failed: %s", exc)
        return []

    if not isinstance(rows, list):
        logger.warning("ipotracker ipo_catalog response shape unexpected: %r", type(rows))
        return []

    today = datetime.datetime.now(IST).date()
    parsed: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        # company_name is the clean legal name (e.g. "Shiprocket Limited");
        # name is the tracker title (e.g. "Shiprocket Limited IPO"). Prefer
        # company_name so the stored name matches the exchanges.
        name = _clean_name(row.get("company_name") or row.get("name"))
        raw_status = _derive_status(
            row.get("opening_date"),
            row.get("closing_date"),
            row.get("listing_date"),
            today,
        )
        status = _STATUS_MAP.get(raw_status or "")
        if not name or not status:
            logger.debug("Skipping unparseable ipotracker row: %r", row)
            continue

        parsed.append({
            "name": name,
            "status": status,
            "open_date": row.get("opening_date"),
            "close_date": row.get("closing_date"),
            "registrar_name": row.get("registrar"),
            # Optional enrichment fields (not yet persisted to the model).
            "symbol": row.get("symbol"),
            "ipo_type": row.get("ipo_type"),
            "lot_size": row.get("lot_size"),
            "issue_size": row.get("issue_size"),
            "price_band_lower": row.get("price_band_lower"),
            "price_band_upper": row.get("price_band_upper"),
            "listing_date": row.get("listing_date"),
            "allotment_date": row.get("allotment_date"),
        })

    logger.info("ipotracker source returned %d parseable IPO rows", len(parsed))
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

    rows = fetch_ipotracker_ipos()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    print(f"rows: {len(rows)}  status: {counts}")
    for row in rows:
        line = (
            f"[{row['status']:18}] {row['name'][:40]:40} | "
            f"close {row.get('close_date')} | list {row.get('listing_date')} | "
            f"{row.get('registrar_name') or ''}"
        )
        # ASCII-safe: the Windows console is often cp1252 and can't print `₹`.
        print(line.encode("ascii", "replace").decode())
