from fastapi import APIRouter
from api.endpoints import ipos, check, progress, results, history, logs, sync, captcha, clients

api_router = APIRouter()
api_router.include_router(ipos.router, prefix="/ipos", tags=["ipos"])
api_router.include_router(check.router, prefix="/check", tags=["check"])
api_router.include_router(progress.router, prefix="/progress", tags=["progress"])
api_router.include_router(results.router, prefix="/results", tags=["results"])
api_router.include_router(history.router, prefix="/history", tags=["history"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(sync.router, prefix="/sync", tags=["sync"])
api_router.include_router(captcha.router, prefix="/captcha", tags=["captcha"])
api_router.include_router(clients.router, prefix="/clients", tags=["clients"])
