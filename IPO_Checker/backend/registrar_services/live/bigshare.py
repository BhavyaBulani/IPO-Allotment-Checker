"""Bigshare Services live IPO allotment integration.

Targets Bigshare's public IPO allotment portal at
https://ipo.bigshareonline.com/. Unlike KFin (a React SPA), Bigshare is a
jQuery/ASP.NET page that posts JSON to a web method:

    GET  Captcha.ashx                    -> {"token", "image"}   (image = data URI)
    POST Data.aspx/FetchIpodetails       -> {"d": {...}}

The POST body carries ``CaptchaToken`` (a signed handle issued by
Captcha.ashx) and ``CaptchaAnswer`` (what the user typed). The server
recomputes the HMAC from the typed answer, so the CAPTCHA is genuinely
server-verified and cannot be skipped.

Response ``d`` shape:

    {"Status": "NOTFOUND"}                        -> no allotment
    {"Status": "OK", "ALLOTED": N, "APPLIED": M}  -> record found
    {"Status": "CAPTCHA"|"RATELIMIT"|"WARMING"}   -> transient / retryable

``ALLOTED > 0`` means allotted. Every unexpected shape degrades to
``Website_Error`` so a stale selector or API change never fabricates a verdict.

Selectors validated against the live DOM on 22-08-2026.
"""

import base64
import json

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar, find_pan_field, normalize_pan
from ..base import RegistrarResult

SELECTORS = {
    "company_select": "#ddlCompany",
    "selection_type": "#SelectionType",
    "pan_input": "#txtpan",
    "captcha_img": "#captcha",
    "captcha_input": "#captcha-input",
    "search_btn": "#btn_Search",
}

# SelectionType option value that makes the form search by PAN.
SELECTION_PAN = "PN"
API_MARKER = "FetchIpodetails"
NOTFOUND = "NOTFOUND"
RATELIMIT = "RATELIMIT"
WARMING = "WARMING"
CAPTCHA = "CAPTCHA"


class BigshareLiveRegistrar(BaseLiveRegistrar):
    @property
    def name(self) -> str:
        return "Bigshare Services (live)"

    @property
    def registrar_id(self) -> int:
        return 3

    portal_url = "https://ipo.bigshareonline.com/"

    def submit_query(self, page, pan, client_code, ipo_name) -> str:
        pan_value = (pan or "").strip().upper()
        if not pan_value:
            raise RuntimeError("Bigshare live check requires a PAN.")

        # The CAPTCHA is generated on page load via AJAX; wait for the image.
        page.wait_for_function(
            "() => { const el = document.getElementById('captcha');"
            " return el && el.getAttribute('src'); }"
        )
        page.wait_for_timeout(300)

        # 1) Choose the company (IPO) whose text matches the requested IPO.
        company_value = self._find_company_value(page, ipo_name)
        if company_value is None:
            raise RuntimeError(f"IPO not found in Bigshare dropdown: {ipo_name}")
        page.select_option(SELECTORS["company_select"], value=company_value)

        # 2) Search by PAN.
        page.select_option(SELECTORS["selection_type"], value=SELECTION_PAN)
        page.wait_for_selector(SELECTORS["pan_input"], state="visible")
        page.fill(SELECTORS["pan_input"], pan_value)

        # 3) Solve the server-verified CAPTCHA through the shared manager.
        captcha_bytes = self._get_captcha_bytes(page)
        from ..captcha_manager import captcha_manager
        solution = captcha_manager.request_solve(
            captcha_bytes, {"registrar": self.name, "ipo": ipo_name}
        )
        if not solution:
            raise RuntimeError("Bigshare CAPTCHA was not solved.")
        page.fill(SELECTORS["captcha_input"], solution)

        # 4) Submit and capture the web-method response. The page's own JS
        #    supplies the CaptchaToken (kept in a closure) and performs the
        #    POST, so we only have to observe it.
        with page.expect_response(
            lambda r: API_MARKER in r.url, timeout=self.action_timeout_ms
        ) as resp_info:
            page.click(SELECTORS["search_btn"])
        return resp_info.value.text()

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
            (v, t) for v, t in candidates if v and t and t != "--SELECT COMPANY--"
        ]
        for value, text in candidates:
            if text == wanted:
                return value
        for value, text in candidates:
            if wanted in text or text in wanted:
                return value
        return None

    def _get_captcha_bytes(self, page) -> bytes:
        src = (page.get_attribute(SELECTORS["captcha_img"], "src") or "").strip()
        if not src:
            raise RuntimeError("Bigshare CAPTCHA image has no src.")

        if src.startswith("data:"):
            _, _, payload = src.partition(",")
            if not payload:
                raise RuntimeError("Bigshare CAPTCHA data URI is malformed.")
            try:
                return base64.b64decode(payload)
            except (ValueError, TypeError) as exc:
                raise RuntimeError("Could not decode Bigshare CAPTCHA image.") from exc

        # Absolute or relative URL: fetch through the page's request context so
        # any session cookies are preserved.
        if not src.startswith("http"):
            from urllib.parse import urljoin
            src = urljoin(self.portal_url, src)
        resp = page.request.get(src)
        if not resp.ok:
            raise RuntimeError(
                f"Could not fetch Bigshare CAPTCHA image (HTTP {resp.status})."
            )
        return resp.body()

    def parse_result_text(self, text, pan, client_code, ipo_name) -> RegistrarResult:
        if not text or not text.strip():
            return RegistrarResult(ResultStatus.Website_Error, "Empty Bigshare response.")

        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return RegistrarResult(
                ResultStatus.Website_Error, "Bigshare returned a non-JSON response."
            )

        comp = data.get("d") if isinstance(data, dict) else None
        if not isinstance(comp, dict):
            return RegistrarResult(
                ResultStatus.Website_Error, "Unexpected Bigshare response shape."
            )

        status = str(comp.get("Status") or "").strip().upper()
        message = str(comp.get("Message") or "").strip()

        if status == NOTFOUND:
            return RegistrarResult(
                ResultStatus.Not_Allotted,
                "Record not found in Bigshare's allotment database (no allotment).",
            )
        if status == CAPTCHA:
            return RegistrarResult(
                ResultStatus.Website_Error, f"Bigshare CAPTCHA rejected: {message}"
            )
        if status in (RATELIMIT, WARMING):
            return RegistrarResult(
                ResultStatus.Server_Busy, message or "Bigshare is busy; retry later."
            )

        # The site reuses the DPID field to carry "Please Enter Valid Pan No"
        # style input errors. Treat those as invalid input, not a verdict.
        dpid = str(comp.get("DPID") or "").strip()
        if "VALID PAN" in dpid.upper():
            return RegistrarResult(ResultStatus.Invalid_PAN, dpid)

        # Only a successful lookup ("OK") carries a trustworthy ALLOTED value.
        # Any other status is a site message, not an allotment record.
        if status != "OK":
            return RegistrarResult(
                ResultStatus.Website_Error,
                (f"Bigshare returned status '{status}': {message}" if message
                 else f"Bigshare returned status '{status}'."),
            )

        returned_pan = find_pan_field(comp)
        queried_pan = normalize_pan(pan)
        if returned_pan and queried_pan and returned_pan != queried_pan:
            return RegistrarResult(
                ResultStatus.Website_Error,
                "Bigshare returned a record for a different PAN; not treated as a verdict.",
            )

        if "ALLOTED" in comp:
            shares = _parse_shares(comp.get("ALLOTED"))
            if shares is None:
                return RegistrarResult(
                    ResultStatus.Website_Error,
                    "Could not interpret Bigshare allotted share count.",
                )
            if shares > 0:
                return RegistrarResult(
                    ResultStatus.Allotted, f"Allotted {shares} shares (Bigshare)."
                )
            return RegistrarResult(
                ResultStatus.Not_Allotted, "Allotted shares is zero (Bigshare)."
            )

        return RegistrarResult(
            ResultStatus.Website_Error,
            "Could not determine allotment from Bigshare response.",
        )


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
