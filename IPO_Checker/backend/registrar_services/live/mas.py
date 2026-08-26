"""MAS Services live IPO allotment integration (Playwright).

Targets MAS Services' public allotment portal at https://www.masserv.com.
MAS is a classic ASP site that serves exactly one active issue at a time.
The hub page ``ipoopt.asp`` names the current issue:

    IPO - <ISSUE NAME> ALLOTMENT STATUS

and links to two search forms, both scoped to that one issue:

    ipo_asearch.asp  -> PAN search   (posts texthn= to ipo_search1.asp)
    ipo_dpclid.asp   -> DPID/Client  (posts textdpid=, textclid= to ipo_dpcld.asp)

For any identifier with no matching record the result page shows a fixed
message — "PAN NO. ENTERED BY YOU IS NOT CORRECT. PLEASE CHECK THE PAN NO.
ENTERED BY YOU." (DPID: "DPID/CLIENT ID ENTERED BY YOU IS NOT CORRECT...") —
and it returns that same message for malformed, unknown and genuinely
no-record identifiers alike. We therefore validate the PAN format ourselves
before submitting, so the site's message is only treated as "no allotment
record" for a well-formed PAN.

The found-record ("allotted") page shape has NOT been observed from a live
allottee, so this parser deliberately does not guess at it: any response
other than the fixed no-record message degrades to ``Website_Error``. MAS can
therefore never fabricate an "Allotted" verdict off an unverified shape.

Selectors validated against the live DOM on 26-08-2026.
"""

import re

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar
from ..base import RegistrarResult

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
ISSUE_RE = re.compile(r"IPO\s*[-:]\s*(.+?)\s+ALLOTMENT\s+STATUS", re.IGNORECASE)
NO_RECORD_MARKER = "PAN NO. ENTERED BY YOU IS NOT CORRECT"

PORTAL_HUB = "https://www.masserv.com/ipoopt.asp"
SEARCH_PAGE = "https://www.masserv.com/ipo_asearch.asp"

SELECTORS = {
    "pan_input": "input[name='texthn']",
    "submit": "input[name='DtLogin']",
}


class MasLiveRegistrar(BaseLiveRegistrar):
    @property
    def name(self) -> str:
        return "MAS Services (live)"

    @property
    def registrar_id(self) -> int:
        return 5

    portal_url = PORTAL_HUB

    def submit_query(self, page, pan, client_code, ipo_name) -> str:
        pan_value = (pan or "").strip().upper()
        if not PAN_RE.match(pan_value):
            raise RuntimeError("MAS live check requires a well-formed PAN.")

        # MAS only checks the one issue its hub page currently advertises.
        # Fail closed rather than check a different IPO against this issue.
        current_issue = self._current_issue(page)
        if current_issue is None:
            raise RuntimeError("Could not determine the active MAS issue.")
        if not self._issue_matches(ipo_name, current_issue):
            raise RuntimeError(
                f"MAS currently serves only '{current_issue}'; "
                f"cannot check '{ipo_name}'."
            )

        page.goto(SEARCH_PAGE, wait_until="domcontentloaded")
        page.wait_for_selector(SELECTORS["pan_input"], state="visible")
        page.fill(SELECTORS["pan_input"], pan_value)

        # Classic form POST: submit navigates to ipo_search1.asp and renders
        # the result server-side. Capture the rendered result page.
        with page.expect_navigation(
            wait_until="domcontentloaded", timeout=self.action_timeout_ms
        ):
            page.click(SELECTORS["submit"])
        return page.content()

    def _current_issue(self, page) -> str | None:
        """Read the active issue name off the hub page (already loaded)."""
        html = page.content()
        match = ISSUE_RE.search(html)
        return match.group(1).strip() if match else None

    @staticmethod
    def _issue_matches(ipo_name, current_issue) -> bool:
        wanted = (ipo_name or "").strip().upper()
        current = (current_issue or "").strip().upper()
        if not wanted or not current:
            return False
        return wanted == current or wanted in current or current in wanted

    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        if not text or not text.strip():
            return RegistrarResult(ResultStatus.Website_Error, "Empty MAS response.")

        if NO_RECORD_MARKER in text:
            return RegistrarResult(
                ResultStatus.Not_Allotted,
                "Record not found in MAS Services' allotment database (no allotment).",
            )

        # The found-record (allotted) page shape is not yet verified; never
        # guess at it. Any other shape is a site change we cannot interpret.
        return RegistrarResult(
            ResultStatus.Website_Error,
            "Unrecognized MAS response; could not determine allotment.",
        )
