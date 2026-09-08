"""Server-side Bigshare CAPTCHA flow (user-assisted only — no auto-solving).

Bigshare's allotment portal issues its CAPTCHA from ``Captcha.ashx`` as a JSON
payload ``{"token", "image"}`` where ``image`` is a ``data:image/png;base64,...``
URI and ``token`` is a signed handle. The search is a plain JSON POST to
``Data.aspx/FetchIpodetails`` carrying that token plus the answer the user
typed. The server recomputes the answer's HMAC against the token, so the
CAPTCHA is genuinely verified server-side and cannot be skipped.

Both calls are stateless over HTTP today (no session cookie is issued): the
CAPTCHA token is the only state that binds the image to its submit. We persist
that token (plus the PAN and matched company value required to submit) in the
``bigshare_flows`` table rather than process memory, so the two steps of a
single check work regardless of which uvicorn worker handles each request.
A fresh ``requests.Session`` is created per HTTP call; should Bigshare start
issuing cookies later, the flow state would need a session-aware store.

This module implements ONLY the user-assisted flow and deliberately:
  * never solves the CAPTCHA automatically,
  * never uses OCR,
  * never calls a CAPTCHA-solving service,
  * never logs PAN numbers, CAPTCHA answers, tokens or cookies.

Result parsing reuses ``BigshareLiveRegistrar.parse_result_text`` so the
verdict logic lives in one place and this module cannot drift from it.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from db.models import BigshareFlow

logger = logging.getLogger(__name__)

PORTAL_URL = "https://ipo.bigshareonline.com/"
CAPTCHA_URL = "https://ipo.bigshareonline.com/Captcha.ashx"
FETCH_URL = "https://ipo.bigshareonline.com/Data.aspx/FetchIpodetails"

SELECTION_TYPE_PAN = "PN"
BIGSHARE_REGISTRAR_ID = 3

# How long an in-flight flow may sit idle before it is discarded. The PAN,
# token and matched company value are held in the DB only and removed on use
# or expiry.
FLOW_TTL_SECONDS = 10 * 60

REQUEST_TIMEOUT_SECONDS = 30

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124 Safari/537.36"
)

_JSON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Content-Type": "application/json; charset=utf-8",
    "X-Requested-With": "XMLHttpRequest",
}


class BigshareHttpError(RuntimeError):
    """Raised when the Bigshare HTTP flow cannot be completed safely."""


def _now() -> datetime:
    return datetime.utcnow()


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


def _fetch_company_options(session: requests.Session) -> list[tuple[str, str]]:
    """Return ``[(value, text), ...]`` from Bigshare's company dropdown."""
    try:
        resp = session.get(PORTAL_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Bigshare home page fetch failed: %s", exc)
        raise BigshareHttpError(
            "Could not reach Bigshare's allotment portal to load the company list."
        ) from exc

    soup = BeautifulSoup(resp.text, "html.parser")
    select = soup.find("select", id="ddlCompany")
    options: list[tuple[str, str]] = []
    if select is None:
        raise BigshareHttpError(
            "Bigshare's company dropdown was not found on the portal page "
            "(the page structure may have changed)."
        )
    for opt in select.find_all("option"):
        value = (opt.get("value") or "").strip()
        text = (opt.get_text() or "").strip()
        if value and text and text.upper() != "--SELECT COMPANY--":
            options.append((value, text))
    if not options:
        raise BigshareHttpError("Bigshare returned an empty company list.")
    return options


def _resolve_company_value(options: list[tuple[str, str]], ipo_name: str) -> Optional[str]:
    """Match ``ipo_name`` against the dropdown, reusing the live matcher."""
    from .live.base_live import labels_token_match

    wanted = (ipo_name or "").strip().upper()
    if not wanted:
        return None

    for value, text in options:
        if text.upper() == wanted:
            return value

    matches = [value for value, text in options if labels_token_match(wanted, text)]
    if len(matches) == 1:
        return matches[0]
    return None


def _fetch_captcha(session: requests.Session) -> tuple[str, str]:
    """Fetch a fresh CAPTCHA; return ``(token, image_data_uri)``."""
    try:
        resp = session.get(CAPTCHA_URL, timeout=REQUEST_TIMEOUT_SECONDS, headers=_JSON_HEADERS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Bigshare CAPTCHA fetch failed: %s", exc)
        raise BigshareHttpError(
            "Could not load Bigshare's CAPTCHA image. Please try again."
        ) from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise BigshareHttpError("Bigshare CAPTCHA endpoint returned a non-JSON response.") from exc

    token = data.get("token") or data.get("Token")
    image = data.get("image") or data.get("Image")
    if not token or not image:
        logger.warning("Bigshare CAPTCHA payload missing token/image keys: %s", sorted(data.keys()))
        raise BigshareHttpError(
            "Bigshare's CAPTCHA response was missing the image or token."
        )
    return str(token), str(image)


def _submit_answer(
    session: requests.Session,
    token: str,
    answer: str,
    company_value: str,
    selection_type: str,
    pan: str,
) -> str:
    """POST the user's answer back to Bigshare and return the raw JSON text."""
    payload = {
        "Applicationno": "",
        "Company": company_value,
        "SelectionType": selection_type,
        "PanNo": pan,
        "txtcsdl": "",
        "txtDPID": "",
        "txtClId": "",
        "ddlType": "0",
        "lang": "",
        "CaptchaToken": token,
        "CaptchaAnswer": answer,
        "ResultToken": "",
    }
    try:
        resp = session.post(FETCH_URL, json=payload, timeout=REQUEST_TIMEOUT_SECONDS, headers=_JSON_HEADERS)
        resp.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Bigshare search submit failed: %s", exc)
        raise BigshareHttpError(
            "Bigshare did not accept the status request. Please try again."
        ) from exc
    return resp.text


def _parse_result(text: str, pan: str, ipo_name: str):
    """Reuse the existing Bigshare response parser."""
    from .live.bigshare import BigshareLiveRegistrar

    return BigshareLiveRegistrar().parse_result_text(text, pan, None, ipo_name)


def _response_status(text: str) -> str:
    from .live.bigshare import _response_status

    return _response_status(text)


def _get_flow(db: Session, flow_id: str) -> Optional[BigshareFlow]:
    """Load a live flow, deleting it if its TTL has lapsed."""
    flow = db.query(BigshareFlow).filter(BigshareFlow.id == flow_id).first()
    if flow is None:
        return None

    age = _now() - flow.last_activity
    if age.total_seconds() > FLOW_TTL_SECONDS:
        db.delete(flow)
        db.commit()
        return None
    return flow


def _prune_expired(db: Session) -> None:
    cutoff = _now() - timedelta(seconds=FLOW_TTL_SECONDS)
    deleted = (
        db.query(BigshareFlow)
        .filter(BigshareFlow.last_activity < cutoff)
        .delete(synchronize_session=False)
    )
    if deleted:
        db.commit()
        logger.info("Pruned %d expired Bigshare CAPTCHA flows.", deleted)


def _image_payload(image_data_uri: str) -> str:
    """Return the base64 payload part of a ``data:...;base64,<payload>`` URI."""
    if "," in image_data_uri:
        return image_data_uri.split(",", 1)[1]
    return image_data_uri


def start_bigshare_check(db: Session, pan: str, ipo_name: str) -> tuple[str, str]:
    """Create an isolated Bigshare flow and obtain the first CAPTCHA.

    Returns ``(flow_id, image_data_uri)``.
    """
    pan = (pan or "").strip().upper()
    if not pan:
        raise BigshareHttpError("Bigshare checks require a PAN.")

    session = _new_session()
    options = _fetch_company_options(session)
    company_value = _resolve_company_value(options, ipo_name)
    if company_value is None:
        raise BigshareHttpError(
            f"IPO not found in Bigshare's company dropdown: {ipo_name}"
        )

    token, image = _fetch_captcha(session)

    _prune_expired(db)

    flow_id = str(uuid.uuid4())
    flow = BigshareFlow(
        id=flow_id,
        ipo_name=ipo_name,
        company_value=company_value,
        selection_type=SELECTION_TYPE_PAN,
        pan=pan,
        captcha_token=token,
        last_activity=_now(),
    )
    db.add(flow)
    db.commit()
    logger.info("Started Bigshare CAPTCHA flow %s for IPO '%s'.", flow_id, ipo_name)
    return flow_id, image


def refresh_bigshare_captcha(db: Session, flow_id: str) -> str:
    """Fetch a fresh CAPTCHA for an existing flow, invalidating the previous one."""
    flow = _get_flow(db, flow_id)
    if flow is None:
        raise BigshareHttpError(
            "CAPTCHA session expired. Please start the check again."
        )

    session = _new_session()
    token, image = _fetch_captcha(session)
    flow.captcha_token = token
    flow.last_activity = _now()
    db.commit()
    logger.info("Refreshed Bigshare CAPTCHA for flow %s.", flow_id)
    return image


def submit_bigshare_check(db: Session, flow_id: str, answer: str) -> dict:
    """Submit the user's typed answer using the same token that issued it.

    Returns a dict suitable for the API layer. On a rejected CAPTCHA the flow
    is kept alive and a fresh CAPTCHA is issued (mirroring Bigshare's own page,
    which regenerates the image after a rejection). On any other outcome the
    flow is deleted so the held PAN/token are released.
    """
    flow = _get_flow(db, flow_id)
    if flow is None:
        raise BigshareHttpError(
            "CAPTCHA session expired. Please start the check again."
        )

    answer = (answer or "").strip()
    if not answer:
        raise BigshareHttpError("Please enter the CAPTCHA text.")

    session = _new_session()
    text = _submit_answer(
        session,
        flow.captcha_token,
        answer,
        flow.company_value,
        flow.selection_type,
        flow.pan,
    )
    bigshare_status = _response_status(text)

    # A rejected answer is not a fatal error: keep the flow, rotate the image,
    # and ask the user to try again. Never reuse the rejected token/image.
    if bigshare_status == "CAPTCHA":
        token, image = _fetch_captcha(session)
        flow.captcha_token = token
        flow.last_activity = _now()
        db.commit()
        logger.info("Bigshare rejected CAPTCHA for flow %s; new image issued.", flow_id)
        return {
            "captcha_rejected": True,
            "message": "Invalid CAPTCHA, please try again.",
            "image": image,
            "image_base64": _image_payload(image),
        }

    result = _parse_result(text, flow.pan, flow.ipo_name)
    db.delete(flow)
    db.commit()
    logger.info(
        "Bigshare flow %s completed with status '%s'.",
        flow_id, result.status.value,
    )
    return {
        "captcha_rejected": False,
        "message": result.raw_message,
        "status": result.status.value,
        "ipo": flow.ipo_name,
    }
