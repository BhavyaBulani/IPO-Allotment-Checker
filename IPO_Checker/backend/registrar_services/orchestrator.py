import os

from db.models import ResultStatus
from .base import RegistrarResult
from .link_intime import LinkIntimeRegistrar
from .mufg import MufgRegistrar
from .live.kfin import KFinLiveRegistrar
from .live.bigshare import BigshareLiveRegistrar
from .rate_limiter import rate_limiter

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()


class FallbackOrchestrator:
    def __init__(self):
        # Registrars 2 (KFin) and 3 (Bigshare) now have real live integrations.
        # Link Intime (1) and MUFG Intime (4) remain mock and are refused in
        # production, so a live brokerage never reports a made-up verdict.
        self.registrars = {
            1: LinkIntimeRegistrar(),
            2: KFinLiveRegistrar(),
            3: BigshareLiveRegistrar(),
            4: MufgRegistrar(),
        }

    def check_allotment(
        self,
        pan: str = None,
        client_code: str = None,
        ipo_name: str = "",
        primary_registrar_id: int = 1,
    ) -> RegistrarResult:
        primary = self.registrars.get(primary_registrar_id) if primary_registrar_id else None
        if not primary:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "No registrar resolved for this IPO; check was not run.",
            )

        if APP_ENV == "production" and not primary.is_live:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Live registrar integration is not configured for this registrar; "
                "refusing to return mock data in production.",
            )

        # Pace requests to the registrar to avoid being rate-limited or blocked.
        rate_limiter.wait(primary_registrar_id)

        # Execute the check — pass both identifiers; each registrar decides which to use.
        result = primary.check(pan, client_code, ipo_name)

        # Retry only genuinely transient outcomes (a live site can time out or
        # be busy). A Website_Error from a live parser is not retried.
        if result.status in [ResultStatus.Timeout, ResultStatus.Server_Busy]:
            rate_limiter.wait(primary_registrar_id)
            result = primary.check(pan, client_code, ipo_name)

        return result


# Global instance
orchestrator = FallbackOrchestrator()
