"""KFin Technologies live IPO allotment integration (Playwright).

Targets KFin's public IPO status portal at https://ipostatus.kfintech.com.
The portal is a React/MUI single-page app backed by a serverless query API.
The form has no CAPTCHA: it asks for an IPO (autocomplete), a search type
(PAN by default) and the identifier, then submits to:

    https://0uz601ms56.execute-api.ap-south-1.amazonaws.com/prod/api/query?type=pan

Responses:

    404 -> {"error": "Record Not Found"}   (no allotment for this PAN + IPO)
    200 -> {"data": [{"Name", "DP_CLID", "Pan_No", "App_Shares", "All_Shares", ...}]}

The success envelope was previously a flat object; it is now wrapped in a
``data`` list, so ``parse_result_text`` accepts both. ``All_Shares > 0`` means
allotted. Every unexpected shape degrades to ``Website_Error`` so a stale
selector or API change never fabricates a verdict.
"""

import json

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar, labels_token_match, normalize_pan
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
        labeled = [
            (opt, (opt.inner_text() or "").strip().upper())
            for opt in options
        ]
        for opt, label in labeled:
            if label == wanted:
                return opt
        # Fail loud unless exactly one option matches on tokens: a wrong issue
        # here would produce a confident-looking but wrong verdict.
        matches = [opt for opt, label in labeled if labels_token_match(wanted, label)]
        if len(matches) == 1:
            return matches[0]
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
            err_msg = str(data.get("error")).strip()
            if err_msg == RECORD_NOT_FOUND:
                return RegistrarResult(
                    ResultStatus.Not_Allotted,
                    "Record not found in KFin's allotment database (no allotment).",
                )
            if err_msg.lower() == "unknown error":
                # "unknown error" is the portal's not-yet-published signal, not
                # proof of no allotment. Reporting it as Not_Allotted would be a
                # false negative the worker then caches for 24h. Fail loud
                # instead: Website_Error is never cached.
                return RegistrarResult(
                    ResultStatus.Website_Error,
                    "KFin returned 'unknown error' — allotment data may not be "
                    "available yet; check not treated as a verdict.",
                )
            return RegistrarResult(
                ResultStatus.Website_Error,
                f"KFin query error: {err_msg}",
            )

        records = _extract_records(data)
        if records is None:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Could not determine allotment from KFin response.",
            )

        queried_pan = normalize_pan(pan)
        record = _choose_record(records, queried_pan)
        if record is None:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "KFin returned multiple records but none matched the queried PAN; "
                "not treated as a verdict.",
            )

        returned_pan = normalize_pan(record.get("Pan_No"))
        if returned_pan and queried_pan and returned_pan != queried_pan:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "KFin returned a record for a different PAN; not treated as a verdict.",
            )

        shares = _parse_shares(record.get("All_Shares"))
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


def _extract_records(data):
    """Return KFin allotment records as a list, or None for an unknown shape.

    KFin's query API now wraps the result in a ``data`` envelope (a list of
    record objects); older responses were a flat object. Accept both so a
    response-shape change can never silently fabricate a verdict.
    """
    if not isinstance(data, dict):
        return None

    if "data" in data:
        inner = data["data"]
        if isinstance(inner, list):
            return [r for r in inner if isinstance(r, dict)]
        if isinstance(inner, dict):
            return [inner]
        return []

    if "All_Shares" in data:
        return [data]

    return None


def _choose_record(records, queried_pan):
    """Pick the record for the queried PAN, tolerating only an unambiguous match."""
    if not records:
        return None
    if queried_pan:
        matches = [r for r in records if normalize_pan(r.get("Pan_No")) == queried_pan]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None
    if len(records) == 1:
        return records[0]
    return None


def _parse_shares(value):
    if value is None:
        return None
    if isinstance(value, bool):
        # A boolean is never a share count; treating True as 1 share would
        # fabricate an "Allotted" verdict from an unexpected shape.
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None
