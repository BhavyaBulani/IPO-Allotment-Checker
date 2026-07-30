import time
from typing import Optional
from .captcha_provider import CaptchaProvider

class ManualProvider(CaptchaProvider):
    def __init__(self, manager):
        self.manager = manager
        
    def solve(self, image_bytes: bytes, context: dict = None) -> Optional[str]:
        captcha_id = self.manager.register_manual_captcha(image_bytes)
        
        # Poll for solution for up to 60 seconds
        timeout = 60
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            entry = self.manager.pending_captchas.get(captcha_id)
            if entry and entry["status"] == "solved":
                return entry["solution"]
            time.sleep(2)
            
        return None

    @property
    def provider_name(self) -> str:
        return "manual"
