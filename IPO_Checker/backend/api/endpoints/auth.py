from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.security import (
    APP_PASSWORD,
    check_login_allowed,
    client_ip,
    create_access_token,
    record_login_failure,
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
