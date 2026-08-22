"""KFin Technologies live IPO allotment integration (Playwright).

Targets KFin's public IPO status portal at https://ipostatus.kfintech.com.
The portal is a React/MUI single-page app backed by a serverless query API.
The form has no CAPTCHA: it asks for an IPO (autocomplete), a search type
(PAN by default) and the identifier, then submits to:

    https://0uz601ms56.execute-api.ap-south-1.amazonaws.com/prod/api/query?type=pan

Responses:

    404 -> {"error": "Record Not Found"}   (no allotment for this PAN + IPO)
    200 -> {"Name", "DP_CLID", "Pan_No", "App_Shares", "All_Shares", ...}

``All_Shares > 0`` means allotted. Every unexpected shape degrades to
``Website_Error`` so a stale selector or API change never fabricates a verdict.
"""

import json

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar
from ..base import RegistrarResult

# Validated against the live DOM on 22-08-2026.
SELECTORS = {
    "ipo_combobox": "#demo-multiple-name",
    "ipo_option_list": "[role='listbox']",
    "ipo_option": "[role='listbox'] [role='option']",
    "pan_radio": "input[type='radio'][value='PAN']",
    "pan_input": "#outlined-start-adornment",
    "submit": "button:has-text('Submit')",
}

API_URL_MARKER = "/api/query"
RECORD_NOT_FOUND = "Record Not Found"


class KFinLiveRegistrar(BaseLiveRegistrar):
    @property
    def name(self) -> str:
        return "KFin Technologies (live)"

    @property
    def registrar_id(self) -> int:
        return 2

    portal_url = "https://ipostatus.kfintech.com"

    def submit_query(self, page, pan, client_code, ipo_name) -> str:
        pan_value = (pan or "").strip().upper()
        if not pan_value:
            raise RuntimeError("KFin live check requires a PAN.")

        # 1) Choose the IPO in the autocomplete dropdown.
        page.click(SELECTORS["ipo_combobox"])
        page.wait_for_selector(SELECTORS["ipo_option_list"], state="visible")
        page.wait_for_timeout(500)  # options render asynchronously
        option = self._find_ipo_option(page, ipo_name)
        if option is None:
            raise RuntimeError(f"IPO not found in KFin dropdown: {ipo_name}")
        option.click()
        page.wait_for_timeout(300)

        # 2) PAN is the default search type; select it explicitly and fill it.
        page.check(SELECTORS["pan_radio"])
        page.fill(SELECTORS["pan_input"], pan_value)

        # 3) Submit and capture the query API response.
        with page.expect_response(
            lambda r: API_URL_MARKER in r.url,
            timeout=self.action_timeout_ms,
        ) as resp_info:
            page.click(SELECTORS["submit"])
        return resp_info.value.text()

    def _find_ipo_option(self, page, ipo_name):
        wanted = (ipo_name or "").strip().upper()
        if not wanted:
            return None
        options = page.query_selector_all(SELECTORS["ipo_option"])
        for opt in options:
            if (opt.inner_text() or "").strip().upper() == wanted:
                return opt
        for opt in options:
            label = (opt.inner_text() or "").strip().upper()
            if wanted in label or label in wanted:
                return opt
        return None

    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        if not text or not text.strip():
            return RegistrarResult(ResultStatus.Website_Error, "Empty KFin response.")

        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return RegistrarResult(
                ResultStatus.Website_Error, "KFin returned a non-JSON response."
            )

        if not isinstance(data, dict):
            return RegistrarResult(
                ResultStatus.Website_Error, "Unexpected KFin response shape."
            )

        if "error" in data:
            if str(data.get("error")).strip() == RECORD_NOT_FOUND:
                return RegistrarResult(
                    ResultStatus.Not_Allotted,
                    "Record not found in KFin's allotment database (no allotment).",
                )
            return RegistrarResult(
                ResultStatus.Website_Error,
                f"KFin query error: {data.get('error')}",
            )

        if "All_Shares" in data:
            shares = _parse_shares(data.get("All_Shares"))
            if shares is None:
                return RegistrarResult(
                    ResultStatus.Website_Error,
                    "Could not interpret KFin allotted share count.",
                )
            if shares > 0:
                return RegistrarResult(
                    ResultStatus.Allotted, f"Allotted {shares} shares (KFin)."
                )
            return RegistrarResult(
                ResultStatus.Not_Allotted, "Allotted shares is zero (KFin)."
            )

        return RegistrarResult(
            ResultStatus.Website_Error,
            "Could not determine allotment from KFin response.",
        )


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
