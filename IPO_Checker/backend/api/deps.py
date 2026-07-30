import os
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

API_KEY_NAME = "X-Admin-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

def verify_admin_key(api_key: str = Security(api_key_header)):
    expected_key = os.environ.get("ADMIN_API_KEY", "admin_secret_key_123")
    if api_key == expected_key:
        return api_key
    raise HTTPException(status_code=403, detail="Forbidden: Invalid or missing Admin API Key")
