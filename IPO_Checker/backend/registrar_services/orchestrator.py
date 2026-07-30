from db.models import ResultStatus
from .base import RegistrarResult
from .link_intime import LinkIntimeRegistrar
from .kfin import KFinRegistrar
from .bigshare import BigshareRegistrar
from .mufg import MufgRegistrar
from .rate_limiter import rate_limiter

class FallbackOrchestrator:
    def __init__(self):
        self.registrars = {
            1: LinkIntimeRegistrar(),
            2: KFinRegistrar(),
            3: BigshareRegistrar(),
            4: MufgRegistrar()
        }
        
    def check_allotment(self, pan: str = None, client_code: str = None, ipo_name: str = "", primary_registrar_id: int = 1) -> RegistrarResult:
        primary = self.registrars.get(primary_registrar_id)
        if not primary:
            return RegistrarResult(ResultStatus.Website_Error, "Primary registrar not configured.")
            
        # Apply rate limiting pacing
        rate_limiter.wait(primary_registrar_id)
        
        # Execute the check — pass both identifiers; each registrar decides which to use
        result = primary.check(pan, client_code, ipo_name)
        
        # Fallback/Retry logic
        if result.status in [ResultStatus.Website_Error, ResultStatus.Timeout]:
            # Retry once for transient errors (Timeout, Server_Busy)
            # In a real system, we might switch to an alternative data provider if available.
            rate_limiter.wait(primary_registrar_id)
            result = primary.check(pan, client_code, ipo_name)
            
        return result

# Global instance
orchestrator = FallbackOrchestrator()
