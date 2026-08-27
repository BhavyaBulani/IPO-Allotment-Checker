"""
Registrar dropdown discovery source.

Scrapes each live registrar's public allotment portal to learn which IPOs
are currently *checkable* — i.e. their allotment results are live on that
registrar's portal. This is the authoritative signal for
``Allotment Announced`` that the exchanges' ``listed`` status arrives at too
late (listing typically lags allotment by several days).

WHY THIS IS SAFE
----------------
This source only ever *adds* ``Allotment Announced`` names. It never
inspects any applicant's PAN, never calls a search endpoint, and never
produces a verdict. A parse error, a changed DOM, or an unreachable portal
yields ``[]`` for that registrar — it never fabricates a name and never
demotes an existing row.

SELECTOR DRIFT
--------------
Each adapter below reuses the ``SELECTORS`` and ``portal_url`` already
validated in the corresponding ``registrar_services/live/*.py`` module, so
there is exactly one source of truth for a portal's selectors. When the
live checker's selector is updated after a site change, this discovery
source follows automatically.
"""

import logging
import os
import re
import sys

# Make the backend package root importable when this module is run directly
# (diagnose scripts, etc.), matching the setup in auto_detect.py.
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from registrar_services.live import kfin as _kfin
from registrar_services.live import link_intime as _link
from registrar_services.live import bigshare as _bigshare
from registrar_services.live import alankit as _alankit
from registrar_services.live import purva as _purva
from registrar_services.live import mas as _mas

logger = logging.getLogger(__name__)

STATUS_ANNOUNCED = "Allotment Announced"

# Registrar portals host NCDs, INVITs, REITs, bond issues, rights issues etc.
# in the same dropdown as equity IPOs. We only ever auto-create equity IPO
# rows, so filter those instruments out here. The pattern is word-boundary
# aware so a company like "Bondada Engineering" is not dropped.
_NON_EQUITY_RE = re.compile(
    r"\b(NCD|DEBENTURES?|BONDS?|INVIT|INV\s?IT|REIT|BUYBACK|QIP|ETF|"
    r"PREFERENTIAL|NON[- ]CONVERTIBLE|COMMERCIAL\s+PAPER|MUTUAL\s+FUND|"
    r"RIGHTS?\s+ISSUE)\b",
    re.IGNORECASE,
)


def is_equity_ipo(name: str) -> bool:
    """True when a dropdown name looks like an equity IPO, not a non-equity instrument."""
    if not name:
        return False
    return _NON_EQUITY_RE.search(str(name)) is None


_IPO_SUFFIX_RE = re.compile(r"\s*[-\u2013]?\s*IPO\s*$", re.IGNORECASE)


def _clean_issue_name(name: str) -> str:
    """Strip registrar-specific suffixes like "Gaja ... Limited - IPO".

    Kept so the stored IPO name matches the plain company name used by the
    exchanges and the live checkers (which already substring-match), and so a
    dropdown row and an exchange row for the same company don't diverge.
    """
    return _IPO_SUFFIX_RE.sub("", (name or "").strip()).strip()

# Link Intime and MUFG Intime are the same company/portal (MUFG is the
# renamed Link Intime), so the one portal serves both registrar IDs.
LINK_MUFG_PORTAL = [1, 4]

# One adapter per live portal. ``kind`` selects the reader:
#   "select"       -> a native <select> whose <option>s list the IPOs
#   "kfin_combobox"-> KFin's React autocomplete (listbox of role=option)
#   "mas_hub"      -> MAS serves exactly one issue; read it off the hub page
_ADAPTERS = [
    {
        "registrar_name": "KFin Technologies",
        "registrar_ids": [2],
        "portal_url": _kfin.KFinLiveRegistrar.portal_url,
        "kind": "kfin_combobox",
    },
    {
        "registrar_name": "Link Intime",
        "registrar_ids": list(LINK_MUFG_PORTAL),
        "portal_url": _link.LinkIntimeLiveRegistrar.portal_url,
        "kind": "select",
        "select_selector": _link.SELECTORS["company_select"],
        "placeholder": "----SELECT COMPANY----",
    },
    {
        "registrar_name": "Bigshare Services",
        "registrar_ids": [3],
        "portal_url": _bigshare.BigshareLiveRegistrar.portal_url,
        "kind": "select",
        "select_selector": _bigshare.SELECTORS["company_select"],
        "placeholder": "--SELECT COMPANY--",
    },
    {
        "registrar_name": "Alankit",
        "registrar_ids": [7],
        "portal_url": _alankit.AlankitLiveRegistrar.portal_url,
        "kind": "select",
        "select_selector": _alankit.SELECTORS["company_select"],
        "placeholder": "PLEASE SELECT COMPANY",
    },
    {
        "registrar_name": "Purva Sharegistry",
        "registrar_ids": [8],
        "portal_url": _purva.PurvaLiveRegistrar.portal_url,
        "kind": "select",
        "select_selector": _purva.SELECTORS["company_select"],
        "placeholder": "CHOOSE A COMPANY...",
    },
    {
        "registrar_name": "MAS Services",
        "registrar_ids": [5],
        "portal_url": _mas.MasLiveRegistrar.portal_url,
        "kind": "mas_hub",
    },
]


def _dedupe(names: list[str]) -> list[str]:
    """Case-insensitive, whitespace-normalised de-dupe preserving order."""
    seen: set[str] = set()
    out: list[str] = []
    for name in names:
        key = re.sub(r"\s+", " ", name or "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(name.strip())
    return out


def _is_placeholder(text: str, placeholder: str | None) -> bool:
    if not text:
        return True
    if placeholder and text.strip().upper() == placeholder.strip().upper():
        return True
    return False


def _read_select_names(page, selector: str, placeholder: str | None) -> list[str]:
    names = []
    options = page.query_selector_all(f"{selector} option")
    for opt in options:
        text = (opt.inner_text() or "").strip()
        value = (opt.get_attribute("value") or "").strip()
        if _is_placeholder(text, placeholder):
            continue
        if not value:
            continue
        names.append(text)
    return names


def _read_kfin_names(page) -> list[str]:
    # KFin's IPO picker is a MUI autocomplete, not a <select>. Click to open
    # the listbox, then read the rendered options.
    page.click(_kfin.SELECTORS["ipo_combobox"])
    page.wait_for_selector(_kfin.SELECTORS["ipo_option_list"], state="visible")
    page.wait_for_timeout(500)  # options render asynchronously
    names = []
    for opt in page.query_selector_all(_kfin.SELECTORS["ipo_option"]):
        text = (opt.inner_text() or "").strip()
        if text:
            names.append(text)
    return names


def _read_mas_name(page) -> list[str]:
    # MAS serves exactly one active issue, named on the hub page.
    match = _mas.ISSUE_RE.search(page.content())
    return [match.group(1).strip()] if match else []


def _scrape_adapter(browser, adapter: dict) -> list[str]:
    page = browser.new_page()
    try:
        page.set_default_navigation_timeout(30000)
        page.set_default_timeout(15000)
        page.goto(adapter["portal_url"], wait_until="domcontentloaded")

        kind = adapter["kind"]
        if kind == "kfin_combobox":
            return _dedupe(_read_kfin_names(page))
        if kind == "mas_hub":
            return _dedupe(_read_mas_name(page))

        # Native <select>: wait until it has more than just the placeholder.
        selector = adapter["select_selector"]
        page.wait_for_function(
            "(sel) => { const s = document.querySelector(sel);"
            " return s && s.options && s.options.length > 1; }",
            arg=selector,
        )
        return _dedupe(_read_select_names(page, selector, adapter.get("placeholder")))
    finally:
        try:
            page.close()
        except Exception:  # noqa: BLE001 - ignore cleanup errors
            pass


def fetch_registrar_checkable_ipos(headless: bool | None = None) -> list[dict]:
    """
    Return a list of dicts for IPOs currently offered in each registrar's
    allotment dropdown:

        {name, status: "Allotment Announced", registrar_name, registrar_ids}

    Never raises — a failing registrar contributes [] and logs a warning.
    """
    if headless is None:
        raw = os.environ.get("REGISTRAR_DROPDOWN_HEADLESS", "1")
        headless = raw.strip().lower() in {"1", "true", "yes", "on"}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright is not installed; skipping registrar dropdown discovery.")
        return []

    results: list[dict] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                for adapter in _ADAPTERS:
                    registrar = adapter["registrar_name"]
                    try:
                        names = _scrape_adapter(browser, adapter)
                    except Exception as exc:  # noqa: BLE001 - site failures are expected
                        logger.warning(
                            "Registrar dropdown discovery failed for %s: %s",
                            registrar, exc,
                        )
                        names = []
                    for name in names:
                        name = _clean_issue_name(name)
                        if not is_equity_ipo(name):
                            continue
                        results.append({
                            "name": name,
                            "status": STATUS_ANNOUNCED,
                            "registrar_name": registrar,
                            "registrar_ids": list(adapter["registrar_ids"]),
                        })
                    if names:
                        logger.info(
                            "Registrar dropdown discovery: %s -> %d IPO(s): %s",
                            registrar, len(names), ", ".join(names),
                        )
            finally:
                try:
                    browser.close()
                except Exception:  # noqa: BLE001 - ignore cleanup errors
                    pass
    except Exception as exc:  # noqa: BLE001 - never let discovery break a sync
        logger.warning("Registrar dropdown discovery failed: %s", exc)
        return []

    logger.info("Registrar dropdown discovery returned %d checkable IPO names", len(results))
    return results
