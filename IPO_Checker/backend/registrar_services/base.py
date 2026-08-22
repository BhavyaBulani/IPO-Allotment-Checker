from abc import ABC, abstractmethod
from db.models import ResultStatus

class RegistrarResult:
    def __init__(self, status: ResultStatus, raw_message: str = "", captcha_path: str = "none"):
        self.status = status
        self.raw_message = raw_message
        self.captcha_path = captcha_path

class BaseRegistrar(ABC):
    # True when the implementation talks to a real registrar portal. Mock
    # implementations leave this False so the orchestrator can refuse them
    # once APP_ENV=production (never fabricate an allotment verdict).
    is_live: bool = False

    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the registrar (e.g., 'Link Intime')."""
        pass

    @property
    @abstractmethod
    def registrar_id(self) -> int:
        """The database ID of this registrar."""
        pass

    @abstractmethod
    def check(self, pan: str, client_code: str, ipo_name: str) -> RegistrarResult:
        """
        Check the allotment status for a given client and IPO name.
        Registrars may use pan, client_code, or both depending on their requirements.
        Either value may be None if unavailable.
        Returns a RegistrarResult.
        """
        pass

