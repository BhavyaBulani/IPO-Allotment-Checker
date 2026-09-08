from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.security import (
    APP_PASSWORD,
    check_login_allowed,
    client_ip,
    create_access_token,
    record_login_failure,
    require_auth,
)

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(request: LoginRequest, http_request: Request):
    ip = client_ip(http_request)

    if not check_login_allowed(ip):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    if not APP_PASSWORD or request.password != APP_PASSWORD:
        record_login_failure(ip)
        raise HTTPException(status_code=401, detail="Invalid password.")

    return {"token": create_access_token(), "token_type": "bearer"}


@router.get("/verify")
def verify_token(_: str = Depends(require_auth)):
    """Cheap bearer-token validation for the SPA boot gate.

    The frontend calls this on startup so it can hold a splash screen while the
    stored token is verified, instead of flashing the dashboard and then being
    bounced to /login when the first protected request returns 401.
    """
    return {"authenticated": True}
