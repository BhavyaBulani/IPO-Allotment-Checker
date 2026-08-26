import os
import uuid
import time
from typing import Dict, Optional
from .captcha_provider import CaptchaProvider
from db.models import ResultStatus

class CaptchaManager:
    """Manages routing and state for CAPTCHA resolution."""
    def __init__(self):
        # Store pending captchas in memory: { captcha_id: {"image": bytes, "solution": str, "status": "pending|solved|failed"} }
        self.pending_captchas: Dict[str, dict] = {}

    @property
    def use_auto_solver(self) -> bool:
        """True when CAPTCHA_AUTO_SOLVER is enabled in the environment."""
        return os.environ.get("CAPTCHA_AUTO_SOLVER", "").strip().lower() in {
            "1", "true", "yes", "on",
        }

    def request_solve(self, image_bytes: bytes, context: dict = None) -> Optional[str]:
        if self.use_auto_solver:
            from .auto_solver_provider import AutoSolverProvider
            provider = AutoSolverProvider()
            return provider.solve(image_bytes, context)
        else:
            from .manual_provider import ManualProvider
            provider = ManualProvider(self)
            return provider.solve(image_bytes, context)

    def register_manual_captcha(self, image_bytes: bytes) -> str:
        captcha_id = str(uuid.uuid4())
        self.pending_captchas[captcha_id] = {
            "image": image_bytes,
            "solution": None,
            "status": "pending",
            "created_at": time.time()
        }
        return captcha_id

    def get_captcha_image(self, captcha_id: str) -> Optional[bytes]:
        entry = self.pending_captchas.get(captcha_id)
        return entry["image"] if entry else None
        
    def submit_solution(self, captcha_id: str, solution: str):
        if captcha_id in self.pending_captchas:
            self.pending_captchas[captcha_id]["solution"] = solution
            self.pending_captchas[captcha_id]["status"] = "solved"
            return True
        return False

# Global instance
captcha_manager = CaptchaManager()
