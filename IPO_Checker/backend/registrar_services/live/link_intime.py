"""Link Intime (now MUFG Intime) live IPO allotment integration (Playwright).

Link Intime India Pvt Ltd was renamed MUFG Intime India Pvt Ltd. Its public
IPO allotment portal now lives at:

    https://in.mpms.mufg.com/Initial_Offer/public-issues.html

The page is a jQuery/ASP.NET form. On load it fetches the company list
(``IPO.aspx/GetDetails``) and an anti-replay token (``IPO.aspx/generateToken``,
stored AES-encrypted in ``#hidToken`` by the page's own JavaScript). Submitting
posts to ``IPO.aspx/SearchOnPan``, which returns a .NET DataSet as XML wrapped
in JSON:

    {"d": "<NewDataSet />"}                                -> no record / not allotted
    {"d": "<NewDataSet><Table><ALLOT>N</ALLOT>...</Table></NewDataSet>"}
                                                           -> record found
    {"d": "<NewDataSet><Table1><Msg>...</Msg></Table1></NewDataSet>"}
                                                           -> server message / error

``ALLOT > 0`` means allotted. The form's CAPTCHA validation is currently
commented out in the page (the captcha box is hidden), so no CAPTCHA is
required today — mirroring KFin. Every unexpected shape degrades to
``Website_Error`` so a stale selector or API change never fabricates a verdict.

Selectors validated against the live DOM on 25-08-2026.
"""

import json
import xml.etree.ElementTree as ET

from db.models import ResultStatus
from .base_live import BaseLiveRegistrar, normalize_pan
from ..base import RegistrarResult

SELECTORS = {
    "company_select": "#ddlCompany",
    "pan_radio": "input[name='gender'][value='PAN']",
    "pan_input": "#txtStat",
    "submit": "#btnsearc",
}

API_MARKER = "SearchOnPan"
PLACEHOLDER = "----SELECT COMPANY----"


def _local(tag: str) -> str:
    """Return a tag name with any XML namespace prefix stripped."""
    return tag.rsplit("}", 1)[-1]


def _children(elem, name: str):
    return [c for c in elem if _local(c.tag) == name]


def _child(elem, name: str):
    for c in elem:
        if _local(c.tag) == name:
            return c
    return None


def _row_pan(row) -> str | None:
    """Return a non-empty PAN value from an XML result row, or None."""
    for child in row:
        if "PAN" in _local(child.tag).upper():
            pan = normalize_pan(child.text)
            if pan:
                return pan
    return None


class LinkIntimeLiveRegistrar(BaseLiveRegistrar):
    # Human label used in result messages; MUFG overrides it.
    label = "Link Intime"

    @property
    def name(self) -> str:
        return "Link Intime (live)"

    @property
    def registrar_id(self) -> int:
        return 1

    portal_url = "https://in.mpms.mufg.com/Initial_Offer/public-issues.html"

    def submit_query(self, page, pan, client_code, ipo_name) -> str:
        pan_value = (pan or "").strip().upper()
        if not pan_value:
            raise RuntimeError(f"{self.label} live check requires a PAN.")

        # The company list and anti-replay token load via AJAX on page load;
        # wait until both are ready before touching the form.
        page.wait_for_function(
            "() => { const s = document.getElementById('ddlCompany');"
            " return s && s.options && s.options.length > 1; }"
        )
        page.wait_for_function(
            "() => { const t = document.getElementById('hidToken');"
            " return t && t.value && t.value.length > 0; }"
        )

        # 1) Choose the company (IPO) whose text matches the requested IPO.
        company_value = self._find_company_value(page, ipo_name)
        if company_value is None:
            raise RuntimeError(f"IPO not found in {self.label} dropdown: {ipo_name}")
        page.select_option(SELECTORS["company_select"], value=company_value)

        # 2) Search by PAN (the default type) and fill the identifier.
        page.check(SELECTORS["pan_radio"])
        page.fill(SELECTORS["pan_input"], pan_value)

        # 3) Submit and capture the web-method response.
        with page.expect_response(
            lambda r: API_MARKER in r.url, timeout=self.action_timeout_ms
        ) as resp_info:
            page.click(SELECTORS["submit"])
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
            (v, t) for v, t in candidates if v and t and t != PLACEHOLDER
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
            return RegistrarResult(
                ResultStatus.Website_Error, f"Empty {self.label} response."
            )

        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            return RegistrarResult(
                ResultStatus.Website_Error,
                f"{self.label} returned a non-JSON response.",
            )

        xml_text = data.get("d") if isinstance(data, dict) else None
        if not xml_text or not xml_text.strip():
            return RegistrarResult(
                ResultStatus.Website_Error, f"Unexpected {self.label} response shape."
            )

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return RegistrarResult(
                ResultStatus.Website_Error,
                f"Could not parse {self.label} response XML.",
            )

        tables = _children(root, "Table")
        messages = _children(root, "Table1")

        if tables:
            # Only trust rows that belong to the PAN we queried. A portal
            # response can carry rows for more than one applicant; taking the
            # max across all of them would fabricate "Allotted" from someone
            # else's positive row.
            queried_pan = normalize_pan(pan)
            matched = []
            saw_pan_field = False
            for table in tables:
                row_pan = _row_pan(table)
                if row_pan is not None:
                    saw_pan_field = True
                    if queried_pan and row_pan != queried_pan:
                        continue
                matched.append(table)

            if saw_pan_field and not matched:
                return RegistrarResult(
                    ResultStatus.Website_Error,
                    f"{self.label} returned rows for a different PAN; not treated as a verdict.",
                )

            shares = self._max_allotted(matched)
            if shares is None:
                return RegistrarResult(
                    ResultStatus.Website_Error,
                    f"Could not interpret {self.label} allotted share count.",
                )
            if shares > 0:
                return RegistrarResult(
                    ResultStatus.Allotted,
                    f"Allotted {shares} shares ({self.label}).",
                )
            return RegistrarResult(
                ResultStatus.Not_Allotted, f"Allotted shares is zero ({self.label})."
            )

        if messages:
            msg = ""
            for m in messages:
                msg_el = _child(m, "Msg")
                if msg_el is not None and (msg_el.text or "").strip():
                    msg = msg_el.text.strip()
                    break
            upper = msg.upper()
            if "NO RECORD" in upper or "NOT FOUND" in upper:
                return RegistrarResult(
                    ResultStatus.Not_Allotted,
                    f"Record not found in {self.label}'s allotment database (no allotment).",
                )
            if "PAN" in upper and ("INVALID" in upper or "VALID" in upper):
                return RegistrarResult(ResultStatus.Invalid_PAN, msg)
            return RegistrarResult(
                ResultStatus.Website_Error,
                msg or f"{self.label} returned an unexpected server message.",
            )

        # Only a genuinely empty <NewDataSet /> means "no record / not allotted".
        # Any other unrecognized shape is a site change we must not guess at.
        if len(root) == 0:
            return RegistrarResult(
                ResultStatus.Not_Allotted,
                f"Record not found in {self.label}'s allotment database (no allotment).",
            )

        return RegistrarResult(
            ResultStatus.Website_Error,
            f"Unexpected {self.label} response XML (no Table/Table1 element).",
        )

    @staticmethod
    def _max_allotted(tables):
        """Highest parsed ALLOT value across application rows, or None."""
        max_shares = None
        for table in tables:
            allot = _child(table, "ALLOT")
            if allot is None or not (allot.text or "").strip():
                continue
            shares = _parse_shares(allot.text)
            if shares is None:
                continue
            max_shares = shares if max_shares is None else max(max_shares, shares)
        return max_shares


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
