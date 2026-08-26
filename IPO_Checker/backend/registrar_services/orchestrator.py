import os

from db.models import ResultStatus
from .base import RegistrarResult
from .live.kfin import KFinLiveRegistrar
from .live.bigshare import BigshareLiveRegistrar
from .live.link_intime import LinkIntimeLiveRegistrar
from .live.mufg import MufgIntimeLiveRegistrar
from .live.mas import MasLiveRegistrar
from .live.alankit import AlankitLiveRegistrar
from .live.purva import PurvaLiveRegistrar
from .rate_limiter import rate_limiter

APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()


class FallbackOrchestrator:
    def __init__(self):
        # Registrars with verified live integrations. Link Intime (1) and
        # MUFG Intime (4) are the same company/portal; MUFG reuses the Link
        # Intime implementation under its own registrar ID. MAS (5) checks the
        # one issue its portal currently serves; see live/mas.py.
        self.registrars = {
            1: LinkIntimeLiveRegistrar(),
            2: KFinLiveRegistrar(),
            3: BigshareLiveRegistrar(),
            4: MufgIntimeLiveRegistrar(),
            5: MasLiveRegistrar(),
            7: AlankitLiveRegistrar(),
            8: PurvaLiveRegistrar(),
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
