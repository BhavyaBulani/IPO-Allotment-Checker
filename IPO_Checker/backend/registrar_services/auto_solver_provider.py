"""2Captcha-backed CAPTCHA solver.

Solves image CAPTCHAs via the 2Captcha HTTP API. Requires TWOCAPTCHA_API_KEY.
Returns None (rather than raising) on any failure so callers fail safely.

The request/response shape follows 2Captcha's documented API; verify it
against a real key before relying on it in production.
"""

import os
import time
from typing import Optional

import requests

from .captcha_provider import CaptchaProvider

_API_IN_URL = "https://2captcha.com/in.php"
_API_RES_URL = "https://2captcha.com/res.php"
_POLL_INTERVAL_SECONDS = 5
_POLL_TIMEOUT_SECONDS = 180
_REQUEST_TIMEOUT_SECONDS = 30


class AutoSolverProvider(CaptchaProvider):
    def solve(self, image_bytes: bytes, context: dict = None) -> Optional[str]:
        api_key = os.environ.get("TWOCAPTCHA_API_KEY")
        if not api_key:
            return None

        captcha_id = self._submit(api_key, image_bytes)
        if not captcha_id:
            return None
        return self._poll(api_key, captcha_id)

    def _submit(self, api_key: str, image_bytes: bytes) -> Optional[str]:
        try:
            resp = requests.post(
                _API_IN_URL,
                data={"key": api_key, "method": "post"},
                files={"file": ("captcha.png", image_bytes, "image/png")},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
        except requests.RequestException:
            return None

        body = resp.text.strip()
        if not body.startswith("OK|"):
            return None
        return body.split("|", 1)[1]

    def _poll(self, api_key: str, captcha_id: str) -> Optional[str]:
        deadline = time.time() + _POLL_TIMEOUT_SECONDS
        while time.time() < deadline:
            time.sleep(_POLL_INTERVAL_SECONDS)
            try:
                resp = requests.get(
                    _API_RES_URL,
                    params={
                        "key": api_key,
                        "action": "get",
                        "id": captcha_id,
                        "json": 1,
                    },
                    timeout=_REQUEST_TIMEOUT_SECONDS,
                )
                resp.raise_for_status()
                data = resp.json()
            except (requests.RequestException, ValueError):
                continue

            if data.get("status") == 1:
                solution = str(data.get("request", "")).strip()
                return solution or None
            if data.get("request") == "CAPCHA_NOT_READY":
                continue
            # Any other response (wrong key, expired id, etc.) is terminal.
            return None
        return None

    @property
    def provider_name(self) -> str:
        return "2captcha"
