"""Purva Sharegistry live IPO allotment integration.

Targets Purva Sharegistry's public allotment query form at
https://www.purvashare.com/investor-service/ipo-query — a Django page that
POSTs back to itself with fields ``csrfmiddlewaretoken``, ``company_id``,
``applicationNumber`` and ``panNumber``. There is currently no CAPTCHA on the
form.

For a no-match identifier the page re-renders with an explicit message:

    No record found. Please re-check your Application Number or PAN Number.

The found-record page renders a ``results-table`` with one data row whose
columns include ``Pan No`` and ``Shares Allotted``. ``0``/``NIL`` means not
allotted; a positive number means allotted. Any other shape degrades to
``Website_Error`` so a site change never fabricates a verdict.

Selectors validated against the live DOM on 26-08-2026.
"""

import re

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar, labels_token_match, normalize_pan
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
        matches = [value for value, text in candidates if labels_token_match(wanted, text)]
        if len(matches) == 1:
            return matches[0]
        return None

    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        if not text or not text.strip():
            return RegistrarResult(ResultStatus.Website_Error, "Empty Purva response.")

        if NO_RECORD_MARKER in text:
            return RegistrarResult(
                ResultStatus.Not_Allotted,
                "Record not found in Purva Sharegistry's allotment database (no allotment).",
            )

        record = _parse_purva_record(text)
        if record is None:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Unrecognized Purva response; could not determine allotment.",
            )

        queried_pan = normalize_pan(pan)
        returned_pan = normalize_pan(record.get("pan"))
        if returned_pan and queried_pan and returned_pan != queried_pan:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Purva returned a record for a different PAN; not treated as a verdict.",
            )

        allotted = _parse_int(record.get("allotted"))
        if allotted is None:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Could not interpret Purva allotted share count.",
            )
        if allotted > 0:
            return RegistrarResult(
                ResultStatus.Allotted, f"Allotted {allotted} shares (Purva)."
            )
        return RegistrarResult(
            ResultStatus.Not_Allotted, "Allotted shares is zero (Purva)."
        )


_TAG_RE = re.compile(r"<[^>]+>")
_RESULTS_TABLE_RE = re.compile(
    r"<table[^>]*results-table[^>]*>(.*?)</table>", re.IGNORECASE | re.DOTALL
)
_THEAD_RE = re.compile(r"<thead[^>]*>(.*?)</thead>", re.IGNORECASE | re.DOTALL)
_TBODY_RE = re.compile(r"<tbody[^>]*>(.*?)</tbody>", re.IGNORECASE | re.DOTALL)
_TH_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.IGNORECASE | re.DOTALL)
_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)


def _strip_tags(html: str) -> str:
    return _TAG_RE.sub(" ", html or "")


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _normalize_header(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (text or "").upper())


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


def _parse_purva_record(html: str) -> dict | None:
    table = _RESULTS_TABLE_RE.search(html)
    if not table:
        return None
    table_html = table.group(1)

    thead = _THEAD_RE.search(table_html)
    if not thead:
        return None
    headers = [_collapse_ws(_strip_tags(h)) for h in _TH_RE.findall(thead.group(1))]
    norm_headers = [_normalize_header(h) for h in headers]

    try:
        allotted_idx = norm_headers.index("SHARESALLOTTED")
    except ValueError:
        return None

    pan_idx = None
    for idx, header in enumerate(norm_headers):
        if header in ("PAN", "PANNO", "PANNUMBER"):
            pan_idx = idx
            break
    if pan_idx is None:
        return None

    tbody = _TBODY_RE.search(table_html)
    if not tbody:
        return None
    row = _TR_RE.search(tbody.group(1))
    if not row:
        return None
    cells = [_collapse_ws(_strip_tags(td)) for td in _TD_RE.findall(row.group(1))]

    if allotted_idx >= len(cells) or pan_idx >= len(cells):
        return None
    return {"allotted": cells[allotted_idx], "pan": cells[pan_idx]}
