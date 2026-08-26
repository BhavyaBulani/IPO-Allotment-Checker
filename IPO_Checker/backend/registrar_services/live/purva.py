"""Purva Sharegistry live IPO allotment integration.

Targets Purva Sharegistry's public allotment query form at
https://www.purvashare.com/investor-service/ipo-query — a Django page that
POSTs back to itself with fields ``csrfmiddlewaretoken``, ``company_id``,
``applicationNumber`` and ``panNumber``. There is currently no CAPTCHA on the
form.

For a no-match identifier the page re-renders with an explicit message:

    No record found. Please re-check your Application Number or PAN Number.

The found-record ("allotted") page shape has NOT been observed from a live
allottee, so this parser deliberately does not guess at it: any response other
than the fixed no-record message degrades to ``Website_Error``. Purva can
therefore never fabricate an "Allotted" verdict off an unverified shape.

Selectors validated against the live DOM on 26-08-2026.
"""

import re

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar
from ..base import RegistrarResult

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
NO_RECORD_MARKER = "No record found. Please re-check your Application Number or PAN Number."

SELECTORS = {
    "company_select": "select#company_id",
    "pan_input": "input[name='panNumber']",
    "app_input": "input[name='applicationNumber']",
    "submit": "form#ipo-query button[type='submit']",
}


class PurvaLiveRegistrar(BaseLiveRegistrar):
    @property
    def name(self) -> str:
        return "Purva Sharegistry (live)"

    @property
    def registrar_id(self) -> int:
        return 8

    portal_url = "https://www.purvashare.com/investor-service/ipo-query"

    def submit_query(self, page, pan, client_code, ipo_name) -> str:
        page.wait_for_selector(
            f"{SELECTORS['company_select']} option[value]:not([value=''])",
            state="attached",
        )

        company_value = self._find_company_value(page, ipo_name)
        if company_value is None:
            raise RuntimeError(f"IPO not found in Purva dropdown: {ipo_name}")
        page.select_option(SELECTORS["company_select"], value=company_value)

        # Identifier: prefer a well-formed PAN; else fall back to a client
        # code as the application number. A malformed PAN is refused rather
        # than submitted (the site's no-record message is only trustworthy
        # for an identifier the applicant could actually have).
        pan_value = (pan or "").strip().upper()
        if PAN_RE.match(pan_value):
            page.fill(SELECTORS["pan_input"], pan_value)
        elif (client_code or "").strip():
            page.fill(SELECTORS["app_input"], (client_code or "").strip())
        else:
            raise RuntimeError("Purva live check requires a PAN or application number.")

        # Classic form POST: submit navigates back to the same URL and renders
        # the result server-side. Capture the rendered result page.
        with page.expect_navigation(
            wait_until="domcontentloaded", timeout=self.action_timeout_ms
        ):
            page.click(SELECTORS["submit"])
        return page.content()

    def _find_company_value(self, page, ipo_name):
        wanted = (ipo_name or "").strip().upper()
        if not wanted:
            return None
        options = page.query_selector_all(f"{SELECTORS['company_select']} option")
        candidates = [
            (opt.get_attribute("value"), (opt.inner_text() or "").strip().upper())
            for opt in options
        ]
        candidates = [
            (v, t) for v, t in candidates if v and t and t != "CHOOSE A COMPANY..."
        ]
        for value, text in candidates:
            if text == wanted:
                return value
        for value, text in candidates:
            if wanted in text or text in wanted:
                return value
        return None

    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        if not text or not text.strip():
            return RegistrarResult(ResultStatus.Website_Error, "Empty Purva response.")

        if NO_RECORD_MARKER in text:
            return RegistrarResult(
                ResultStatus.Not_Allotted,
                "Record not found in Purva Sharegistry's allotment database (no allotment).",
            )

        # The found-record (allotted) page shape is not yet verified; never
        # guess at it. Any other shape is a site change we cannot interpret.
        return RegistrarResult(
            ResultStatus.Website_Error,
            "Unrecognized Purva response; could not determine allotment.",
        )
