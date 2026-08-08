import time
import os
from typing import Optional
from .captcha_provider import CaptchaProvider

class AutoSolverProvider(CaptchaProvider):
    def solve(self, image_bytes: bytes, context: dict = None) -> Optional[str]:
        api_key = os.environ.get("TWOCAPTCHA_API_KEY")
        if api_key:
            # Here we would normally use the 2Captcha API to solve it
            time.sleep(3) # simulate network request
            return "REAL_SOLVED_123"
        else:
            # Fallback mock for local development
            time.sleep(2)
            return "AUTO_SOLVED_MOCK"

    @property
    def provider_name(self) -> str:
        return "auto"
