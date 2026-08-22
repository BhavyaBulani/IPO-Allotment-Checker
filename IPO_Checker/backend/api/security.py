"""
Minimal, dependency-free access control for the internal tool.

Uses a single shared application password (``APP_PASSWORD``) exchanged for a
short-lived, HMAC-signed bearer token. This is deliberately simple: the app is
an internal brokerage tool with no per-user identity yet. It replaces the
previous ``X-Admin-Key`` approach, which was both hardcoded in the backend and
exposed to the browser.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()

# A token only needs to survive the length of a work session.
TOKEN_TTL_SECONDS = 12 * 60 * 60

_bearer = HTTPBearer(auto_error=False)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        if APP_ENV == "production":
            raise RuntimeError(f"{name} must be set when APP_ENV=production")
        value = f"dev-{name.lower()}-change-me"
    return value


SECRET_KEY = _require_env("SECRET_KEY")
APP_PASSWORD = _require_env("APP_PASSWORD")

if APP_ENV == "production" and SECRET_KEY == "dev-secret_key-change-me":
    raise RuntimeError("SECRET_KEY is still the insecure development default")


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(body: str) -> str:
    digest = hmac.new(SECRET_KEY.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return _b64encode(digest)


def create_access_token() -> str:
    payload = {
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
        "nonce": secrets.token_hex(8),
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{body}.{_sign(body)}"


def verify_access_token(token: str) -> bool:
    try:
        body, signature = token.split(".", 1)
    except (ValueError, AttributeError):
        return False

    if not hmac.compare_digest(_sign(body), signature):
        return False

    try:
        payload = json.loads(_b64decode(body))
    except (ValueError, json.JSONDecodeError):
        return False

    return isinstance(payload.get("exp"), (int, float)) and payload["exp"] > time.time()


def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> str:
    """FastAPI dependency: require a valid bearer token."""
    if credentials is None or not verify_access_token(credentials.credentials):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a valid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


def mask_identifier(value: str | None) -> str | None:
    """Mask a PAN or client code for display in API responses.

    PANs are the primary concern: a PAN like ``ABCDE1234F`` is reduced to the
    trailing four characters (``***234F``), which is enough to identify a row
    while revealing nothing a search against the registrar would accept.
    """
    if not value:
        return value
    if len(value) <= 4:
        return "***"
    return "***" + value[-4:]


# --- Login brute-force throttle (in-memory, per-IP) ---

_LOGIN_WINDOW_SECONDS = 5 * 60
_LOGIN_MAX_ATTEMPTS = 10
_login_attempts: dict[str, list[float]] = {}


def _prune_attempts(ip: str, now: float) -> None:
    cutoff = now - _LOGIN_WINDOW_SECONDS
    _login_attempts[ip] = [t for t in _login_attempts.get(ip, []) if t > cutoff]


def check_login_allowed(ip: str) -> bool:
    now = time.time()
    _prune_attempts(ip, now)
    return len(_login_attempts.get(ip, [])) < _LOGIN_MAX_ATTEMPTS


def record_login_failure(ip: str) -> None:
    now = time.time()
    _prune_attempts(ip, now)
    _login_attempts.setdefault(ip, []).append(now)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
