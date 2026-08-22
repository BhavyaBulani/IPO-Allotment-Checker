"""Playwright-backed live registrar base.

Real allotment checks drive a headless Chromium against a registrar's official
portal. A live registrar only reports a verdict when the result page is parsed
confidently; every error, timeout, or ambiguous page becomes ``Website_Error``
so a stale selector degrades to "could not check" — never to a fabricated
"Allotted" / "Not Allotted" result.
"""

import logging
import os
from abc import abstractmethod

from db.models import ResultStatus
from ..base import BaseRegistrar, RegistrarResult

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class BaseLiveRegistrar(BaseRegistrar):
    """Base class for Playwright-driven registrar checks.

    Subclasses must set ``portal_url`` and implement ``submit_query`` and
    ``parse_result_text``. The ``check`` method owns the browser lifecycle.
    """

    is_live = True

    portal_url: str = ""

    navigation_timeout_ms: int = int(os.environ.get("LIVE_NAV_TIMEOUT_MS", "30000"))
    action_timeout_ms: int = int(os.environ.get("LIVE_ACTION_TIMEOUT_MS", "15000"))
    headless: bool = _env_bool("LIVE_REGISTRAR_HEADLESS", True)

    @abstractmethod
    def submit_query(self, page, pan, client_code, ipo_name) -> str:
        """Drive the portal form and return the page text containing the result.

        Raise any exception to signal failure; ``check`` converts it into a
        Website_Error result.
        """

    @abstractmethod
    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        """Parse page text into a RegistrarResult.

        Return Website_Error unless the verdict is confident.
        """

    def check(self, pan, client_code, ipo_name) -> RegistrarResult:
        identifier = (pan or client_code or "").strip()
        if not identifier:
            return RegistrarResult(
                ResultStatus.Invalid_PAN,
                "No PAN or client code was provided for the live check.",
            )

        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Playwright is not installed; cannot run the live registrar check.",
            )

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                try:
                    page = browser.new_page()
                    page.set_default_navigation_timeout(self.navigation_timeout_ms)
                    page.set_default_timeout(self.action_timeout_ms)
                    page.goto(self.portal_url, wait_until="domcontentloaded")
                    text = self.submit_query(page, pan, client_code, ipo_name)
                    return self.parse_result_text(text, pan, client_code, ipo_name)
                finally:
                    try:
                        browser.close()
                    except Exception:  # noqa: BLE001 - ignore cleanup errors
                        pass
        except Exception as exc:  # noqa: BLE001 - live sites fail in many ways
            logger.warning("Live %s check failed: %s", self.name, exc)
            return RegistrarResult(
                ResultStatus.Website_Error,
                f"Live check failed: {type(exc).__name__}: {exc}",
            )
