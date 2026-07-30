from .base import BaseRegistrar, RegistrarResult
from db.models import ResultStatus
import time
import random

class KFinRegistrar(BaseRegistrar):
    @property
    def name(self) -> str:
        return "KFin Technologies"
        
    @property
    def registrar_id(self) -> int:
        return 2

    def check(self, pan: str, client_code: str, ipo_name: str) -> RegistrarResult:
        try:
            # Use whichever identifier is available (PAN preferred)
            identifier = pan or client_code or ""
            
            time.sleep(1.2)
            
            if identifier.startswith("ERROR"):
                return RegistrarResult(ResultStatus.Website_Error, "Simulated website error from KFin")
            elif identifier.startswith("TIME"):
                time.sleep(4) 
                return RegistrarResult(ResultStatus.Timeout, "Simulated timeout from KFin")
            elif identifier.startswith("CAPTCHA") or random.random() < 0.1:
                # Simulate encountering a CAPTCHA
                from .captcha_manager import captcha_manager
                dummy_image = b"fake_image_bytes"
                solution = captcha_manager.request_solve(
                    dummy_image, 
                    context={"registrar": self.name, "ipo": ipo_name}
                )
                if not solution:
                    return RegistrarResult(ResultStatus.Website_Error, "CAPTCHA failed or aborted", captcha_path="none")
                captcha_path = "auto" if captcha_manager.use_auto_solver else "manual"
                status = random.choice([ResultStatus.Allotted, ResultStatus.Not_Allotted])
                return RegistrarResult(status, f"Simulated success from {self.name} (CAPTCHA: {solution})", captcha_path=captcha_path)
                
            status = random.choice([ResultStatus.Allotted, ResultStatus.Not_Allotted])
            msg = f"Simulated success from {self.name} (PAN: {pan}, Code: {client_code})"
            return RegistrarResult(status, msg)
        except Exception as e:
            return RegistrarResult(ResultStatus.Website_Error, str(e))
