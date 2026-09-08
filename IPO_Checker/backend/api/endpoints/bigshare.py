"""User-assisted Bigshare CAPTCHA endpoints.

These implement the two-step flow the frontend needs for Bigshare (whose
CAPTCHA cannot be auto-solved and must be typed by the user):

  1. ``POST /api/bigshare/captcha``          -> create a server-side session,
                                                fetch the CAPTCHA image.
  2. ``POST /api/bigshare/captcha/refresh``  -> rotate the CAPTCHA image.
  3. ``POST /api/bigshare/check``            -> submit the typed answer using
                                                the SAME server-side session.

The Bigshare session (and the PAN + token it temporarily needs) never leaves
the backend; the browser only ever sees an opaque ``flow_id`` and the image.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import require_auth
from db.models import Client, IPO
from db.session import get_db
from registrar_services.bigshare_http import (
    BIGSHARE_REGISTRAR_ID,
    BigshareHttpError,
    _image_payload,
    refresh_bigshare_captcha,
    start_bigshare_check,
    submit_bigshare_check,
)

router = APIRouter()


class BigshareCaptchaRequest(BaseModel):
    identifier: str = Field(..., min_length=5, max_length=20, description="PAN or Client Code")
    ipo_id: int = Field(..., description="Selected IPO id")


class BigshareRefreshRequest(BaseModel):
    flow_id: str


class BigshareCheckRequest(BaseModel):
    flow_id: str
    captcha_answer: str = Field(..., min_length=1, max_length=20)


def _validate_pan(pan: str) -> bool:
    import re

    return bool(re.match(r"^[A-Z]{5}[0-9]{4}[A-Z]{1}$", pan))


def _resolve_pan(db: Session, identifier: str) -> str:
    """Return a valid PAN for the identifier, cross-referencing client codes.

    Raises HTTPException with a clear message when no PAN can be resolved.
    """
    candidate = identifier.strip().upper()
    if _validate_pan(candidate):
        return candidate

    # Not a PAN — maybe a client code we already imported.
    client = db.query(Client).filter(Client.client_code == candidate).first()
    if client and client.pan and _validate_pan(client.pan):
        return client.pan

    raise HTTPException(
        status_code=400,
        detail="Bigshare checks require a valid PAN. Enter a 10-character PAN "
               "(5 letters, 4 digits, 1 letter) for Bigshare IPOs.",
    )


def _resolve_bigshare_ipo(db: Session, ipo_id: int) -> IPO:
    ipo = db.query(IPO).filter(IPO.id == ipo_id, IPO.validated == True).first()  # noqa: E712
    if ipo is None:
        raise HTTPException(status_code=404, detail="IPO not found.")
    if ipo.registrar_id != BIGSHARE_REGISTRAR_ID:
        raise HTTPException(
            status_code=400,
            detail="This IPO is not handled by Bigshare; use the standard check instead.",
        )
    return ipo


@router.post("/captcha")
def bigshare_captcha(
    request: BigshareCaptchaRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    """Create an isolated Bigshare session and return the CAPTCHA image."""
    ipo = _resolve_bigshare_ipo(db, request.ipo_id)
    pan = _resolve_pan(db, request.identifier)

    try:
        flow_id, image = start_bigshare_check(db, pan, ipo.name)
    except BigshareHttpError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {
        "flow_id": flow_id,
        "image": image,
        "image_base64": _image_payload(image),
        "ipo": ipo.name,
    }


@router.post("/captcha/refresh")
def bigshare_captcha_refresh(
    request: BigshareRefreshRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    """Rotate the CAPTCHA image for an existing flow (old image is invalidated)."""
    try:
        image = refresh_bigshare_captcha(db, request.flow_id)
    except BigshareHttpError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    return {"image": image, "image_base64": _image_payload(image)}


@router.post("/check")
def bigshare_check(
    request: BigshareCheckRequest,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    """Submit the user's typed answer using the same Bigshare token."""
    try:
        result = submit_bigshare_check(db, request.flow_id, request.captcha_answer)
    except BigshareHttpError as exc:
        raise HTTPException(status_code=410, detail=str(exc)) from exc

    if result.get("captcha_rejected"):
        # 422 -> the answer was rejected; a fresh image is included.
        return {
            "status": "error",
            "message": result["message"],
            "captcha_rejected": True,
            "image": result["image"],
            "image_base64": result["image_base64"],
            "results": [],
        }

    return {
        "status": "success",
        "message": "Check completed.",
        "identifier_type": "PAN",
        "ipo": result["ipo"],
        "ipos": [result["ipo"]],
        "results": [
            {"ipo": result["ipo"], "status": result["status"], "message": result["message"]}
        ],
        "captcha_rejected": False,
    }
