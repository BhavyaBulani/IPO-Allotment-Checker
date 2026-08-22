"""KFin Technologies live IPO allotment scraper (Playwright).

Targets KFin's public IPO status portal. ``SELECTORS`` below are a best-effort
starting point and MUST be re-validated against the current live DOM before
this is trusted in production — KFin changes the portal periodically. Every
uncertain step raises or returns Website_Error, so a stale selector degrades
to "could not check", never a wrong verdict.

The portal is CAPTCHA-gated. Solving goes through 2Captcha when
TWOCAPTCHA_API_KEY is set; without it the live check fails safely at the
CAPTCHA step.
"""

import re

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar
from ..base import RegistrarResult
from ..auto_solver_provider import AutoSolverProvider

# Best-effort selectors. Re-validate against https://kcas.kfintech.com/ipostatus/
# before relying on this in production.
SELECTORS = {
    "search_type_pan": "input[name='searchType'][value='PAN']",  # TODO: validate
    "pan_input": "input[name='pan']",                            # TODO: validate
    "application_input": "input[name='applicationNo']",          # TODO: validate
    "captcha_input": "input[name='captcha']",                    # TODO: validate
    "captcha_image": "img#captchaImg",                           # TODO: validate
    "submit": "button[type='submit']",                           # TODO: validate
    "result_container": "#result, .result, .status",             # TODO: validate
}

# Confident verdict phrases. These are best-effort and must be checked against
# the live portal's actual result copy before this is trusted in production.
ALLOTTED_RE = re.compile(
    r"(?:you\s+have\s+been\s+allotted|\ballotted\s+shares?|\bshares?\s+allotted)",
    re.IGNORECASE,
)
NOT_ALLOTTED_RE = re.compile(
    r"(?:\bnot(?:\s+been)?\s+allotted\b|\bno\s+allotment\b)",
    re.IGNORECASE,
)


class KFinLiveRegistrar(BaseLiveRegistrar):
    @property
    def name(self) -> str:
        return "KFin Technologies (live)"

    @property
    def registrar_id(self) -> int:
        return 2

    portal_url = "https://kcas.kfintech.com/ipostatus/"

    def submit_query(self, page, pan, client_code, ipo_name) -> str:
        # Prefer PAN; fall back to application number / client code.
        if pan:
            page.click(SELECTORS["search_type_pan"])
            page.fill(SELECTORS["pan_input"], pan.strip().upper())
        else:
            page.fill(SELECTORS["application_input"], (client_code or "").strip().upper())

        self._solve_captcha(page, ipo_name)
        page.click(SELECTORS["submit"])
        page.wait_for_selector(SELECTORS["result_container"], state="visible")
        return page.inner_text("body")

    def _solve_captcha(self, page, ipo_name) -> None:
        try:
            locator = page.locator(SELECTORS["captcha_image"])
            if locator.count() == 0:
                raise RuntimeError("CAPTCHA image not found")
            image_bytes = locator.screenshot()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Could not capture CAPTCHA image: {exc}")

        solution = AutoSolverProvider().solve(
            image_bytes, context={"registrar": self.name, "ipo": ipo_name}
        )
        if not solution:
            raise RuntimeError(
                "CAPTCHA solve failed; ensure TWOCAPTCHA_API_KEY is set and valid."
            )
        page.fill(SELECTORS["captcha_input"], solution)

    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        if not text or not text.strip():
            return RegistrarResult(
                ResultStatus.Website_Error, "Empty result page from KFin."
            )

        # Negative first: "not allotted" must not be caught by the positive rule.
        if NOT_ALLOTTED_RE.search(text):
            return RegistrarResult(
                ResultStatus.Not_Allotted, "Not allotted (parsed from KFin portal)."
            )
        if ALLOTTED_RE.search(text):
            return RegistrarResult(
                ResultStatus.Allotted, "Allotted (parsed from KFin portal)."
            )
        return RegistrarResult(
            ResultStatus.Website_Error,
            "Could not confidently determine the KFin result from the page.",
        )
