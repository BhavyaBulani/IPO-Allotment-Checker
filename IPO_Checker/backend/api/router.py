from fastapi import APIRouter, Depends

from api.endpoints import (
    ipos,
    check,
    progress,
    results,
    history,
    logs,
    sync,
    captcha,
    clients,
    auth,
)
from api.security import require_auth

api_router = APIRouter()

# Public: authentication and read-only IPO metadata (IPO names are not client data).
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(ipos.router, prefix="/ipos", tags=["ipos"])

# Everything that touches client identifiers or batch data requires a bearer token.
api_router.include_router(
    check.router, prefix="/check", tags=["check"], dependencies=[Depends(require_auth)]
)
api_router.include_router(
    progress.router, prefix="/progress", tags=["progress"], dependencies=[Depends(require_auth)]
)
api_router.include_router(
    results.router, prefix="/results", tags=["results"], dependencies=[Depends(require_auth)]
)
api_router.include_router(
    history.router, prefix="/history", tags=["history"], dependencies=[Depends(require_auth)]
)
api_router.include_router(
    logs.router, prefix="/logs", tags=["logs"], dependencies=[Depends(require_auth)]
)
api_router.include_router(
    sync.router, prefix="/sync", tags=["sync"], dependencies=[Depends(require_auth)]
)
api_router.include_router(
    captcha.router, prefix="/captcha", tags=["captcha"], dependencies=[Depends(require_auth)]
)
api_router.include_router(
    clients.router, prefix="/clients", tags=["clients"], dependencies=[Depends(require_auth)]
)
