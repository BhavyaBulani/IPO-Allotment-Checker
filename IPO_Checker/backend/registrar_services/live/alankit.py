"""Alankit (Alankit Assignments Limited) live IPO allotment integration.

Targets Alankit's public allotment portal at https://ipo.alankit.com/.
The page loads the company list via ``GET /Query/companylist`` and submits a
search via ``POST /Query/GetQueryResult`` with a JSON body:

    {"CompCode": "...", "SearchParam": "APPLNO|DPID|PANNO",
     "SearchValue": "...", "ASBAType": "888|999"}   # ASBAType only for APPLNO

The form's "CAPTCHA" is a client-side arithmetic puzzle only — the label
``#lblcaptcha`` shows e.g. "3 + 12 =" and the user types the numeric sum into
``#txtcaptcha``. The sum is never sent to the server (the search body carries
no captcha field), so we solve it by reading the two operands off the page; no
external solver is required.

Response is a JSON array:

    []                                        -> record not found / not allotted
    [{"CLID","PANNO","APPLNO","NAME","APPLIED","ALLOTED"}, ...]
                                              -> record(s) found

``ALLOTED > 0`` means allotted; ``ALLOTED == 0`` means applied but no
allotment. Every unexpected shape degrades to ``Website_Error`` so a stale
selector or API change never fabricates a verdict.

Selectors and JSON contract validated against the live portal on 26-08-2026.
"""

import json
import re

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar
from ..base import RegistrarResult

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
API_MARKER = "GetQueryResult"
PLACEHOLDER = "PLEASE SELECT COMPANY"

SELECTORS = {
    "company_select": "select#drpComp",
    "pan_radio": "input[name='optrad'][value='PANNO']",
    "pan_input": "input#txtPAN",
    "captcha_label": "#lblcaptcha",
    "captcha_input": "input#txtcaptcha",
    "search_btn": "#btnsearch",
}


class AlankitLiveRegistrar(BaseLiveRegistrar):
    @property
    def name(self) -> str:
        return "Alankit (live)"

    @property
    def registrar_id(self) -> int:
        return 7

    portal_url = "https://ipo.alankit.com/"

    def submit_query(self, page, pan, client_code, ipo_name) -> str:
        pan_value = (pan or "").strip().upper()
        if not PAN_RE.match(pan_value):
            raise RuntimeError("Alankit live check requires a well-formed PAN.")

        # The company list loads via AJAX on page load; wait for it.
        page.wait_for_function(
            "() => { const s = document.getElementById('drpComp');"
            " return s && s.options && s.options.length > 1; }"
        )

        company_value = self._find_company_value(page, ipo_name)
        if company_value is None:
            raise RuntimeError(f"IPO not found in Alankit dropdown: {ipo_name}")
        page.select_option(SELECTORS["company_select"], value=company_value)

        # Search by PAN.
        page.check(SELECTORS["pan_radio"])
        page.wait_for_selector(SELECTORS["pan_input"], state="visible")
        page.fill(SELECTORS["pan_input"], pan_value)

        # Solve the client-side arithmetic captcha (read two operands, sum).
        captcha_text = (page.inner_text(SELECTORS["captcha_label"]) or "").strip()
        answer = self._solve_arithmetic(captcha_text)
        if answer is None:
            raise RuntimeError("Could not read Alankit arithmetic captcha.")
        page.fill(SELECTORS["captcha_input"], answer)

        with page.expect_response(
            lambda r: API_MARKER in r.url, timeout=self.action_timeout_ms
        ) as resp_info:
            page.click(SELECTORS["search_btn"])

        resp = resp_info.value
        if resp.status != 200:
            raise RuntimeError(f"Alankit search returned HTTP {resp.status}.")
        return resp.text()

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
            (v, t) for v, t in candidates if v and t and t != PLACEHOLDER
        ]
        for value, text in candidates:
            if text == wanted:
                return value
        for value, text in candidates:
            if wanted in text or text in wanted:
                return value
        return None

    @staticmethod
    def _solve_arithmetic(text):
        # Label renders like "7 + 12 ="; extract the two numeric operands.
        parts = (text or "").split()
        numbers = [p for p in parts if p.isdigit()]
        if len(numbers) != 2:
            return None
        return str(int(numbers[0]) + int(numbers[1]))

    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        if not text or not text.strip():
            return RegistrarResult(ResultStatus.Website_Error, "Empty Alankit response.")

        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return RegistrarResult(
                ResultStatus.Website_Error, "Alankit returned a non-JSON response."
            )

        if not isinstance(data, list):
            return RegistrarResult(
                ResultStatus.Website_Error, "Unexpected Alankit response shape."
            )

        if len(data) == 0:
            return RegistrarResult(
                ResultStatus.Not_Allotted,
                "Record not found in Alankit's allotment database (no allotment).",
            )

        shares = self._max_allotted(data)
        if shares is None:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Could not interpret Alankit allotted share count.",
            )
        if shares > 0:
            return RegistrarResult(
                ResultStatus.Allotted, f"Allotted {shares} shares (Alankit)."
            )
        return RegistrarResult(
            ResultStatus.Not_Allotted, "Allotted shares is zero (Alankit)."
        )

    @staticmethod
    def _max_allotted(rows):
        """Highest parsed ALLOTED value across result rows, or None."""
        max_shares = None
        for row in rows:
            if not isinstance(row, dict):
                continue
            shares = _parse_shares(row.get("ALLOTED"))
            if shares is None:
                continue
            max_shares = shares if max_shares is None else max(max_shares, shares)
        return max_shares


def _parse_shares(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None
