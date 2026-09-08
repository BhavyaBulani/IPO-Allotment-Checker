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

The found-record page echoes the applicant's details plus a
"Shares Allotted" cell whose value is either ``NIL`` (zero) or a number.
``NIL``/``0`` means not allotted; a positive number means allotted. Any other
shape degrades to ``Website_Error`` so a site change never fabricates a verdict.

Selectors validated against the live DOM on 26-08-2026.
"""

import re

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar, labels_token_match, normalize_pan
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
        if wanted == current:
            return True
        return labels_token_match(wanted, current)

    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        if not text or not text.strip():
            return RegistrarResult(ResultStatus.Website_Error, "Empty MAS response.")

        if NO_RECORD_MARKER in text:
            return RegistrarResult(
                ResultStatus.Not_Allotted,
                "Record not found in MAS Services' allotment database (no allotment).",
            )

        # Found-record page: verify the echoed PAN, then read the
        # "Shares Allotted" cell (NIL/0 -> not allotted, number -> allotted).
        queried_pan = normalize_pan(pan)
        if queried_pan:
            page_text = _collapse_ws(_strip_tags(text)).upper()
            if queried_pan not in page_text:
                return RegistrarResult(
                    ResultStatus.Website_Error,
                    "MAS returned a record that does not echo the queried PAN; "
                    "not treated as a verdict.",
                )

        allotted = _parse_mas_allotted(text)
        if allotted is None:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Unrecognized MAS response; could not determine allotment.",
            )
        if allotted > 0:
            return RegistrarResult(
                ResultStatus.Allotted, f"Allotted {allotted} shares (MAS)."
            )
        return RegistrarResult(
            ResultStatus.Not_Allotted, "Allotted shares is zero (MAS)."
        )


_TAG_RE = re.compile(r"<[^>]+>")
_ALLOTTED_RE = re.compile(
    r"SHARES\s+ALLOTTED\s*[:=]?\s*(NIL\.?|[\d,]+)", re.IGNORECASE
)


def _strip_tags(html: str) -> str:
    return _TAG_RE.sub(" ", html or "")


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _parse_int(value: str) -> int | None:
    text = (value or "").replace(",", "").strip()
    if not text:
        return None
    if text.upper() in ("NIL", "NIL."):
        return 0
    try:
        return int(text)
    except ValueError:
        return None


def _parse_mas_allotted(html: str) -> int | None:
    text = _collapse_ws(_strip_tags(html)).upper()
    match = _ALLOTTED_RE.search(text)
    if not match:
        return None
    return _parse_int(match.group(1))
