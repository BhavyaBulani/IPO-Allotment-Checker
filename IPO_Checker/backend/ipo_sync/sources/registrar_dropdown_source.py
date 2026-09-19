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
    r"\b(NCD\w*|DEBENTURES?|BONDS?|INVIT|INV\s?IT|REIT|BUYBACK|QIP|ETF|"
    r"PREFERENTIAL|NON[- ]CONVERTIBLE|COMMERCIAL\s+PAPER|MUTUAL\s+FUND|"
    r"RIGHTS?\s+ISSUE|TRUST|COUPON)\b",
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
# renamed Link Intime), so the one portal serves both registrar IDs. The
# portal is branded MUFG Intime today, so discovered rows are labelled
# MUFG Intime even though the portal also serves legacy Link Intime issues.
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
        "registrar_name": "MUFG Intime",
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
        # Purva renders the full company list server-side into the initial
        # HTML. An empty <select> is therefore a trustworthy "nothing is
        # checkable right now" signal, not a half-loaded DOM — so the scanner
        # may treat it as conclusive and retire names Purva has dropped.
        "empty_is_conclusive": True,
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


def _empty_read_outcome(adapter: dict) -> tuple[str, str | None]:
    """Classify a native-<select> read that returned no options.

    A server-rendered select (``empty_is_conclusive``) that contains only its
    placeholder is a successful read of an empty dropdown — "nothing checkable
    right now". Any other empty read is far more likely a half-loaded DOM than
    a genuinely empty portal, so it must be treated as unread.

    Returns ``("conclusive", None)`` or ``("failed", reason)``.
    """
    if adapter.get("empty_is_conclusive"):
        return ("conclusive", None)
    return ("failed", "no options returned (possible DOM change)")


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

        # Native <select>.
        selector = adapter["select_selector"]
        if adapter.get("empty_is_conclusive"):
            # The full dropdown is rendered server-side into the initial HTML,
            # so once the <select> itself is present its options are already
            # authoritative. An empty list here means "no live IPOs", not
            # "the options are still loading".
            page.wait_for_selector(selector, state="attached")
        else:
            # Options load via AJAX after the initial HTML; wait until the
            # select has more than just the placeholder before reading it.
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


def fetch_registrar_dropdown_scan(headless: bool | None = None) -> dict:
    """Scrape every registrar portal and report what was found *and* what was read reliably.

    Returns::

        {
          "rows":       [{name, status, registrar_name, registrar_ids}, ...],
          "live_names": {"KFin Technologies": ["Foo Ltd", ...], ...},
          "conclusive": ["KFin Technologies", ...],
          "failed":     {"Bigshare Services": "timeout ..."},
        }

    ``conclusive`` lists the registrars whose dropdown was read without error AND
    yielded at least one option — or, for a server-rendered portal marked
    ``empty_is_conclusive``, whose dropdown was read without error and found to
    be empty. A portal that raised, or that returned an empty list without that
    marker (the classic symptom of a changed DOM), is deliberately NOT
    conclusive: absence from a list that could not be read means nothing, so
    callers must consult this set — never ``rows`` alone — before treating a
    missing name as having been removed from the portal.

    Never raises.
    """
    if headless is None:
        raw = os.environ.get("REGISTRAR_DROPDOWN_HEADLESS", "1")
        headless = raw.strip().lower() in {"1", "true", "yes", "on"}

    scan: dict = {"rows": [], "live_names": {}, "conclusive": [], "failed": {}}

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("Playwright is not installed; skipping registrar dropdown discovery.")
        return scan

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
                        scan["failed"][registrar] = str(exc)
                        continue

                    if not names:
                        outcome, reason = _empty_read_outcome(adapter)
                        if outcome == "conclusive":
                            # A server-rendered select that contains only its
                            # placeholder was read successfully: the registrar
                            # has nothing checkable right now. That is a
                            # conclusive read — and it is what lets a name that
                            # has vanished from this portal be retired.
                            scan["conclusive"].append(registrar)
                            scan["live_names"].setdefault(registrar, [])
                            logger.info(
                                "Registrar dropdown discovery: %s -> 0 equity IPOs (empty dropdown).",
                                registrar,
                            )
                        else:
                            logger.warning(
                                "Registrar dropdown for %s returned no options; "
                                "treating this scan as inconclusive for that registrar.",
                                registrar,
                            )
                            scan["failed"][registrar] = reason
                        continue

                    # Read reliably: its absence from here on is meaningful.
                    scan["conclusive"].append(registrar)
                    scan["live_names"].setdefault(registrar, [])

                    equity_names = []
                    for name in names:
                        name = _clean_issue_name(name)
                        if not is_equity_ipo(name):
                            continue
                        equity_names.append(name)
                        scan["live_names"][registrar].append(name)
                        scan["rows"].append({
                            "name": name,
                            "status": STATUS_ANNOUNCED,
                            "registrar_name": registrar,
                            "registrar_ids": list(adapter["registrar_ids"]),
                        })
                    logger.info(
                        "Registrar dropdown discovery: %s -> %d equity IPO(s): %s",
                        registrar, len(equity_names), ", ".join(equity_names),
                    )
            finally:
                try:
                    browser.close()
                except Exception:  # noqa: BLE001 - ignore cleanup errors
                    pass
    except Exception as exc:  # noqa: BLE001 - never let discovery break a sync
        logger.warning("Registrar dropdown discovery failed: %s", exc)
        # Attribute the failure to every portal this run never got a verdict
        # for. A browser that fails to launch, or a crash between adapters, is
        # otherwise recorded as *nothing at all* — no registrar in ``failed``,
        # none in ``conclusive`` — which looks identical to a healthy scan that
        # found no names, including to the scan-health tracker.
        for adapter in _ADAPTERS:
            scan["failed"].setdefault(adapter["registrar_name"], str(exc))
        return scan

    logger.info(
        "Registrar dropdown discovery returned %d checkable IPO name(s) from %d registrar(s); %d registrar(s) unread.",
        len(scan["rows"]), len(scan["conclusive"]), len(scan["failed"]),
    )
    return scan


def fetch_registrar_checkable_ipos(headless: bool | None = None) -> list[dict]:
    """
    Return a list of dicts for IPOs currently offered in each registrar's
    allotment dropdown:

        {name, status: "Allotment Announced", registrar_name, registrar_ids}

    Flat-list view of :func:`fetch_registrar_dropdown_scan`, kept for callers
    that only care about the names. Callers that decide *removal* must use the
    detailed scan instead, so they can tell a name that is genuinely gone from
    one that merely could not be read.

    Never raises — a failing registrar contributes [] and logs a warning.
    """
    return fetch_registrar_dropdown_scan(headless=headless)["rows"]
