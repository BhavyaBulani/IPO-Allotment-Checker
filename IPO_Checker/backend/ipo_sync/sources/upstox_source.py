"""
Upstox IPO API — official broker-sourced IPO data, launched May 2026.

Unlike NSE/BSE direct scraping, this is a documented REST API served from
Upstox's own infrastructure, so it isn't subject to NSE's cloud-IP blocking
of Render/AWS/GCP ranges. Requires an Upstox developer app + OAuth access
token (see https://upstox.com/developer/api-documentation/).

Set the token via the UPSTOX_ACCESS_TOKEN environment variable. If it's
missing or invalid, this source returns [] and logs a warning rather than
raising, same contract as nse_source/bse_source.

VERIFY BEFORE RELYING ON THIS IN PRODUCTION:
  1. Whether IPO endpoints require a funded/active Upstox trading account
     behind the token, or just an app registration.
  2. The exact base URL — Upstox's own docs are inconsistent between
     api.upstox.com/v2 and api-v2.upstox.com across different pages.
     Run diagnose_sources.py against both if the primary one 401/404s.
"""

import logging
import os
import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.upstox.com/v2/ipos"

_STATUS_MAP = {
    "upcoming": "Upcoming",
    "open": "Open",
    "closed": "Closed",
    "listed": "Closed",
}


def fetch_upstox_ipos() -> list[dict]:
    token = os.environ.get("UPSTOX_ACCESS_TOKEN")
    if not token:
        logger.info("UPSTOX_ACCESS_TOKEN not set — skipping Upstox source.")
        return []

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    try:
        resp = requests.get(_BASE_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
    except requests.RequestException as exc:
        logger.warning("Upstox IPO fetch failed: %s", exc)
        return []
    except ValueError as exc:
        logger.warning("Upstox IPO response wasn't valid JSON: %s", exc)
        return []

    rows = payload.get("data", []) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        logger.warning("Upstox IPO response shape unexpected: %r", type(payload))
        return []

    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = row.get("company_name") or row.get("name") or row.get("symbol")
        raw_status = str(row.get("status", "")).strip().lower()
        status = _STATUS_MAP.get(raw_status)
        if not name or not status:
            logger.debug("Skipping unparseable Upstox row: %r", row)
            continue
        parsed.append({
            "name": str(name).strip(),
            "status": status,
            "open_date": row.get("bidding_start_date") or row.get("open_date"),
            "close_date": row.get("bidding_end_date") or row.get("close_date"),
            "registrar_name": row.get("registrar") or row.get("registrar_name"),
        })

    logger.info("Upstox source returned %d parseable IPO rows", len(parsed))
    return parsed
