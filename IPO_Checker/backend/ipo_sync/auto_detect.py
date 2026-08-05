import sys
import os
import datetime
import logging
import httpx
import requests
from bs4 import BeautifulSoup

# Add backend directory to path so we can import from db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import IPO, IPOStatus
from sqlalchemy import func
import re

def is_sane_ipo(name: str, status: IPOStatus) -> bool:
    if not name or len(name) < 3 or len(name) > 150:
        return False
    # Basic check for suspicious characters (script tags, etc.)
    if re.search(r"[<>{}\\[\\]]", name):
        return False
    if status not in [IPOStatus.Open, IPOStatus.Closed, IPOStatus.Allotment_Announced, IPOStatus.Upcoming]:
        return False
    return True

logger = logging.getLogger(__name__)

# --- Source 1: Chittorgarh GMP Report (primary) ---
CHITTORGARH_GMP_URL = "https://www.chittorgarh.com/report/latest-ipo-gmp-grey-market-premium/97/"
# Fallback: IPO Timetable page
CHITTORGARH_TIMETABLE_URL = "https://www.chittorgarh.com/report/ipo-list-by-time-table-and-lot-size/118/mainboard/"

# --- Source 2: Upstox Public IPO Page ---
UPSTOX_IPO_URL = "https://upstox.com/ipo/"

# --- Source 3: Moneycontrol as fallback ---
MONEYCONTROL_IPO_URL = "https://www.moneycontrol.com/ipo/ipo-allotment-status/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}

CHITTORGARH_DASHBOARD_URL = "https://www.chittorgarh.com/ipo/ipo_dashboard.asp"
CURRENT_IPO_TABLE_SELECTOR = "table.table.striped.my-0.table-hover"
EVENT_CALENDAR_TABLE_SELECTOR = "table.table.striped.table-hover.my-0"
CURRENT_IPO_EVENT_RE = re.compile(r"^(?P<name>.+?)\s+IPO\s+(?P<action>Opens|Closes)\s+on\s+(?P<date>.+)$", re.IGNORECASE)


def _normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _parse_dashboard_date(date_str: str) -> datetime.datetime | None:
    if not date_str:
        return None

    cleaned = _normalize_name(date_str).replace("  ", " ")
    for fmt in ("%b %d, %Y", "%d %b, %Y", "%d %b %Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _parse_issue_range(range_text: str) -> tuple[datetime.datetime | None, datetime.datetime | None]:
    if not range_text:
        return None, None

    cleaned = _normalize_name(range_text)
    current_year = datetime.datetime.utcnow().year

    match = re.search(
        r"(?P<start_day>\d{1,2})\s+(?P<start_month>[A-Za-z]{3})\s*-\s*(?P<end_day>\d{1,2})\s+(?P<end_month>[A-Za-z]{3})",
        cleaned,
    )
    if match:
        try:
            start_date = datetime.datetime.strptime(
                f"{match.group('start_day')} {match.group('start_month')} {current_year}",
                "%d %b %Y",
            )
            end_date = datetime.datetime.strptime(
                f"{match.group('end_day')} {match.group('end_month')} {current_year}",
                "%d %b %Y",
            )
            return start_date, end_date
        except ValueError:
            return None, None

    match = re.search(
        r"(?P<start_day>\d{1,2})\s*-\s*(?P<end_day>\d{1,2})\s+(?P<month>[A-Za-z]{3})",
        cleaned,
    )
    if match:
        try:
            start_date = datetime.datetime.strptime(
                f"{match.group('start_day')} {match.group('month')} {current_year}",
                "%d %b %Y",
            )
            end_date = datetime.datetime.strptime(
                f"{match.group('end_day')} {match.group('month')} {current_year}",
                "%d %b %Y",
            )
            return start_date, end_date
        except ValueError:
            return None, None

    return None, None


def _infer_status(open_date: datetime.datetime | None, close_date: datetime.datetime | None) -> IPOStatus:
    now = datetime.datetime.utcnow()

    if open_date and close_date:
        if now < open_date:
            return IPOStatus.Upcoming
        if open_date <= now <= close_date:
            return IPOStatus.Open
        return IPOStatus.Closed

    if open_date and now < open_date:
        return IPOStatus.Upcoming
    if close_date and now > close_date:
        return IPOStatus.Closed
    return IPOStatus.Open


def _build_dashboard_ipos(soup: BeautifulSoup) -> list[dict]:
    current_table = soup.select_one(CURRENT_IPO_TABLE_SELECTOR)
    if current_table is None:
        logger.warning("Chittorgarh dashboard scraper could not find the current IPO table.")
        return []

    event_calendar_table = None
    for table in soup.select(EVENT_CALENDAR_TABLE_SELECTOR):
        if "IPO Opens" in table.get_text(" ", strip=True) or "IPO Closes" in table.get_text(" ", strip=True):
            event_calendar_table = table
            break

    calendar_dates: dict[str, dict[str, datetime.datetime | None]] = {}
    if event_calendar_table is not None:
        for row in event_calendar_table.select("tbody tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            event_text = cells[-1].get_text(" ", strip=True)
            match = CURRENT_IPO_EVENT_RE.match(event_text)
            if not match:
                continue

            name = _normalize_name(match.group("name"))
            event_date = _parse_dashboard_date(match.group("date"))
            if name not in calendar_dates:
                calendar_dates[name] = {"open_date": None, "close_date": None}

            if match.group("action").lower() == "opens":
                calendar_dates[name]["open_date"] = event_date
            else:
                calendar_dates[name]["close_date"] = event_date

    scraped_ipos: dict[str, dict] = {}

    for row in current_table.select("tbody tr"):
        cells = row.find_all("td")
        if not cells:
            continue

        first_cell = cells[0]
        link = first_cell.find("a")
        name = _normalize_name(link.get_text(" ", strip=True) if link else first_cell.get_text(" ", strip=True))
        if not name:
            continue

        issue_text = _normalize_name(first_cell.get_text(" ", strip=True))
        range_text = issue_text[len(name):].strip() if issue_text.startswith(name) else issue_text
        open_date, close_date = _parse_issue_range(range_text)

        calendar_entry = calendar_dates.get(name, {})
        if calendar_entry.get("open_date"):
            open_date = calendar_entry["open_date"]
        if calendar_entry.get("close_date"):
            close_date = calendar_entry["close_date"]

        scraped_ipos[name] = {
            "name": name,
            "open_date": open_date,
            "close_date": close_date,
            "status": _infer_status(open_date, close_date),
            "source": "Chittorgarh",
            "auto_detected": True,
            "validated": True,
        }

    for name, dates in calendar_dates.items():
        if name in scraped_ipos:
            continue

        open_date = dates.get("open_date")
        close_date = dates.get("close_date")
        scraped_ipos[name] = {
            "name": name,
            "open_date": open_date,
            "close_date": close_date,
            "status": _infer_status(open_date, close_date),
            "source": "Chittorgarh",
            "auto_detected": True,
            "validated": True,
        }

    return list(scraped_ipos.values())


def fetch_current_ipos() -> list[dict]:
    """Fetch the live IPO list from the Chittorgarh IPO dashboard."""
    try:
        response = httpx.get(CHITTORGARH_DASHBOARD_URL, headers=HEADERS, timeout=20.0, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:
        logger.warning(f"Chittorgarh dashboard scrape failed: {exc}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    scraped_ipos = _build_dashboard_ipos(soup)

    if not scraped_ipos:
        logger.warning("Chittorgarh dashboard scrape returned no IPO rows.")

    return scraped_ipos


def sync_ipos() -> dict:
    """Upsert live IPOs from the Chittorgarh dashboard into the IPO table."""
    scraped_ipos = fetch_current_ipos()
    if not scraped_ipos:
        return {"added": 0, "updated": 0, "source": "Chittorgarh", "scraped": 0}

    db = SessionLocal()
    added = 0
    updated = 0

    try:
        for data in scraped_ipos:
            normalized_name = _normalize_name(data["name"]).lower()
            existing = db.query(IPO).filter(func.lower(func.trim(IPO.name)) == normalized_name).first()

            if existing:
                changed = False
                for field in ("status", "open_date", "close_date", "source", "auto_detected", "validated"):
                    new_value = data.get(field)
                    if getattr(existing, field) != new_value:
                        setattr(existing, field, new_value)
                        changed = True

                if changed:
                    existing.synced_at = datetime.datetime.utcnow()
                    updated += 1
            else:
                db.add(
                    IPO(
                        external_id=f"chittorgarh-{normalized_name.replace(' ', '-')[:80]}",
                        name=data["name"],
                        status=data["status"],
                        source=data["source"],
                        open_date=data.get("open_date"),
                        close_date=data.get("close_date"),
                        synced_at=datetime.datetime.utcnow(),
                        auto_detected=data.get("auto_detected", True),
                        validated=data.get("validated", True),
                    )
                )
                added += 1

        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error(f"Database error during IPO sync: {exc}", exc_info=True)
        return {"added": 0, "updated": 0, "source": "Chittorgarh", "error": str(exc), "scraped": len(scraped_ipos)}
    finally:
        db.close()

    logger.info(f"IPO sync complete from Chittorgarh. Added: {added}, Updated: {updated}")
    return {"added": added, "updated": updated, "source": "Chittorgarh", "scraped": len(scraped_ipos)}


def _parse_chittorgarh_date(date_str: str) -> datetime.datetime | None:
    """Parse date strings in various formats from Chittorgarh pages."""
    if not date_str or date_str.strip() in ("", "-", "N/A", "TBA"):
        return None
    date_str = date_str.strip()
    for fmt in ("%b %d, %Y", "%d-%b-%Y", "%d %b %Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _map_chittorgarh_status(status_text: str) -> IPOStatus:
    """Map Chittorgarh status text to IPOStatus enum."""
    status_lower = status_text.strip().lower()
    if "open" in status_lower or "live" in status_lower:
        return IPOStatus.Open
    elif "upcoming" in status_lower or "forthcoming" in status_lower:
        return IPOStatus.Upcoming
    elif "allotment" in status_lower or "listed" in status_lower:
        return IPOStatus.Allotment_Announced
    elif "closed" in status_lower:
        return IPOStatus.Closed
    else:
        # Default: if we can't determine, mark as Open to surface it
        return IPOStatus.Open


def _scrape_chittorgarh_ipos() -> list[dict]:
    """
    Scrapes Chittorgarh's GMP report page for current IPO listings.
    Falls back to the IPO Timetable page if GMP page fails.

    Note: Chittorgarh migrated to Next.js. If their pages render tables
    client-side via JS, this scraper will return an empty list and the
    sync function will fall through to Upstox/Moneycontrol sources.
    """
    scraped = []

    for url, page_label in [
        (CHITTORGARH_GMP_URL, "GMP Report"),
        (CHITTORGARH_TIMETABLE_URL, "IPO Timetable"),
    ]:
        if scraped:
            break  # Already got results from a previous page
        try:
            resp = requests.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for data tables — Chittorgarh uses Bootstrap tables
            # with class "table" inside the main content area
            tables = soup.find_all("table", class_=lambda c: c and "table" in c)
            if not tables:
                # Broader fallback: any table element
                tables = soup.find_all("table")

            for table in tables:
                # Read table headers to determine column mapping
                header_row = table.find("thead")
                if header_row:
                    headers = [th.get_text(strip=True).lower() for th in header_row.find_all("th")]
                else:
                    # Try first row as header
                    first_row = table.find("tr")
                    if first_row:
                        headers = [cell.get_text(strip=True).lower() for cell in first_row.find_all(["th", "td"])]
                    else:
                        continue

                # Find column indices by matching header text
                name_idx = None
                open_idx = None
                close_idx = None
                status_idx = None

                for i, h in enumerate(headers):
                    h_clean = h.strip()
                    if any(kw in h_clean for kw in ["ipo", "company", "issue name", "issuer"]) and name_idx is None:
                        name_idx = i
                    elif any(kw in h_clean for kw in ["open", "start", "open date"]) and open_idx is None:
                        open_idx = i
                    elif any(kw in h_clean for kw in ["close", "end", "close date"]) and close_idx is None:
                        close_idx = i
                    elif any(kw in h_clean for kw in ["status", "listing"]) and status_idx is None:
                        status_idx = i

                if name_idx is None:
                    continue  # Can't identify IPO names — skip this table

                # Parse data rows
                tbody = table.find("tbody")
                rows = tbody.find_all("tr") if tbody else table.find_all("tr")[1:]

                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) <= name_idx:
                        continue

                    # Extract IPO name — prefer the text from the first <a> link
                    name_cell = cells[name_idx]
                    link = name_cell.find("a")
                    name = link.get_text(strip=True) if link else name_cell.get_text(strip=True)

                    # Clean up the name: remove "IPO" suffix artifacts like extra spaces
                    name = re.sub(r"\s+", " ", name).strip()

                    if not name or len(name) < 4:
                        continue

                    # Extract dates if columns exist
                    open_date_str = cells[open_idx].get_text(strip=True) if open_idx is not None and len(cells) > open_idx else None
                    close_date_str = cells[close_idx].get_text(strip=True) if close_idx is not None and len(cells) > close_idx else None

                    # Extract status if column exists; otherwise infer from dates
                    if status_idx is not None and len(cells) > status_idx:
                        raw_status = cells[status_idx].get_text(strip=True)
                        status = _map_chittorgarh_status(raw_status)
                    else:
                        # Infer status from dates
                        open_dt = _parse_chittorgarh_date(open_date_str) if open_date_str else None
                        close_dt = _parse_chittorgarh_date(close_date_str) if close_date_str else None
                        now = datetime.datetime.utcnow()
                        if open_dt and close_dt:
                            if now < open_dt:
                                status = IPOStatus.Upcoming
                            elif open_dt <= now <= close_dt:
                                status = IPOStatus.Open
                            else:
                                status = IPOStatus.Closed
                        else:
                            status = IPOStatus.Open  # Safe default

                    # Generate a stable external_id
                    ext_id = f"chit-{name.lower().replace(' ', '-')[:60]}"

                    # Deduplicate
                    if any(s["external_id"] == ext_id for s in scraped):
                        continue

                    scraped.append({
                        "external_id": ext_id,
                        "name": name,
                        "status": status,
                        "source": "Chittorgarh",
                        "open_date": _parse_chittorgarh_date(open_date_str) if open_date_str else None,
                        "close_date": _parse_chittorgarh_date(close_date_str) if close_date_str else None,
                    })

            logger.info(f"Chittorgarh {page_label} scrape found {len(scraped)} IPOs")
        except Exception as e:
            logger.warning(f"Chittorgarh {page_label} scrape failed: {e}")

    return scraped


def _scrape_upstox_ipos() -> list[dict]:
    """Scrapes the Upstox public IPO page for current IPO listings."""
    scraped = []
    try:
        resp = requests.get(UPSTOX_IPO_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Upstox renders IPO cards in various layouts. We look for common patterns.
        # Try structured data first (JSON-LD or meta tags)
        ipo_cards = soup.find_all("div", class_=lambda c: c and "ipo" in c.lower() and ("card" in c.lower() or "item" in c.lower()))

        if not ipo_cards:
            # Broader fallback: look for any <a> or <h2>/<h3> containing "IPO"
            links = soup.find_all("a", href=True)
            for link in links:
                text = link.get_text(strip=True)
                if "IPO" in text and len(text) > 5 and len(text) < 120:
                    # Deduplicate by checking if we already have this name
                    if not any(s["name"] == text for s in scraped):
                        scraped.append({
                            "external_id": f"upstox-{text.lower().replace(' ', '-')[:60]}",
                            "name": text,
                            "status": IPOStatus.Open,
                            "source": "Upstox"
                        })
        else:
            for card in ipo_cards:
                title_el = card.find(["h2", "h3", "h4", "a", "span"])
                if title_el:
                    name = title_el.get_text(strip=True)
                    if name and len(name) > 3:
                        status = IPOStatus.Open
                        card_text = card.get_text(strip=True).lower()
                        if "allotment" in card_text:
                            status = IPOStatus.Allotment_Announced
                        elif "closed" in card_text:
                            status = IPOStatus.Closed

                        scraped.append({
                            "external_id": f"upstox-{name.lower().replace(' ', '-')[:60]}",
                            "name": name,
                            "status": status,
                            "source": "Upstox"
                        })

        logger.info(f"Upstox scrape found {len(scraped)} IPOs")
    except Exception as e:
        logger.warning(f"Upstox scrape failed: {e}")
    return scraped


def _scrape_moneycontrol_ipos() -> list[dict]:
    """Fallback scraper for Moneycontrol IPO allotment page."""
    scraped = []
    try:
        resp = requests.get(MONEYCONTROL_IPO_URL, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Moneycontrol typically lists IPOs in tables or list items
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # skip header
                cells = row.find_all("td")
                if cells and len(cells) >= 1:
                    name = cells[0].get_text(strip=True)
                    if name and "IPO" in name and len(name) > 5:
                        scraped.append({
                            "external_id": f"mc-{name.lower().replace(' ', '-')[:60]}",
                            "name": name,
                            "status": IPOStatus.Allotment_Announced,
                            "source": "Moneycontrol"
                        })

        # Also try list-based layouts
        if not scraped:
            links = soup.find_all("a", href=True)
            for link in links:
                text = link.get_text(strip=True)
                if "IPO" in text and len(text) > 5 and len(text) < 120:
                    if not any(s["name"] == text for s in scraped):
                        scraped.append({
                            "external_id": f"mc-{text.lower().replace(' ', '-')[:60]}",
                            "name": text,
                            "status": IPOStatus.Allotment_Announced,
                            "source": "Moneycontrol"
                        })

        logger.info(f"Moneycontrol scrape found {len(scraped)} IPOs")
    except Exception as e:
        logger.warning(f"Moneycontrol scrape failed: {e}")
    return scraped


def sync_ipos_from_web() -> dict:
    """
    Main sync function. Tries Chittorgarh first, then Upstox, then Moneycontrol.
    Upserts IPOs into the database.
    Returns a summary dict with counts.
    """
    scraped_ipos = []
    source = "none"

    # Try sources in priority order: Chittorgarh → Upstox → Moneycontrol
    for scraper, scraper_name in [
        (_scrape_chittorgarh_ipos, "Chittorgarh"),
        (_scrape_upstox_ipos, "Upstox"),
        (_scrape_moneycontrol_ipos, "Moneycontrol"),
    ]:
        if scraped_ipos:
            break
        try:
            scraped_ipos = scraper()
            if scraped_ipos:
                source = scraper_name
                logger.info(f"Using {scraper_name} as IPO source ({len(scraped_ipos)} IPOs)")
            else:
                logger.info(f"{scraper_name} returned no IPOs, trying next source...")
        except Exception as e:
            logger.warning(f"{scraper_name} scraper raised an exception: {e}")

    if not scraped_ipos:
        logger.warning("No IPOs found from any source. Database unchanged.")
        return {"added": 0, "updated": 0, "source": "none"}

    db = SessionLocal()
    added = 0
    updated = 0
    try:
        for data in scraped_ipos:
            is_valid = is_sane_ipo(data["name"], data["status"])
            if not is_valid:
                logger.warning(f"Validation failed for IPO: {data['name']}")
                
            existing = db.query(IPO).filter(IPO.external_id == data["external_id"]).first()
            if not existing:
                new_ipo = IPO(
                    external_id=data["external_id"],
                    name=data["name"],
                    status=data["status"],
                    source=data["source"],
                    open_date=data.get("open_date"),
                    close_date=data.get("close_date"),
                    synced_at=datetime.datetime.utcnow(),
                    auto_detected=True,
                    validated=is_valid
                )
                db.add(new_ipo)
                added += 1
            else:
                # Update status and dates if they changed
                changed = False
                if existing.status != data["status"]:
                    existing.status = data["status"]
                    changed = True
                if data.get("open_date") and existing.open_date != data["open_date"]:
                    existing.open_date = data["open_date"]
                    changed = True
                if data.get("close_date") and existing.close_date != data["close_date"]:
                    existing.close_date = data["close_date"]
                    changed = True
                if changed:
                    existing.synced_at = datetime.datetime.utcnow()
                    updated += 1

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Database error during IPO sync: {e}")
    finally:
        db.close()

    logger.info(f"IPO sync complete from {source}. Added: {added}, Updated: {updated}")
    return {"added": added, "updated": updated, "source": source}


# Keep the old mock function for backwards compatibility / testing
def mock_sync_ipos():
    """Legacy mock function. Seeds the DB with fake IPOs for testing."""
    db = SessionLocal()

    mock_data = [
        {"external_id": "mock-nsdl-1", "name": "NSDL IPO", "status": IPOStatus.Allotment_Announced, "source": "MockUpstox"},
        {"external_id": "mock-hdb-2", "name": "HDB Financial Services IPO", "status": IPOStatus.Open, "source": "MockUpstox"},
        {"external_id": "mock-hero-3", "name": "Hero Fincorp IPO", "status": IPOStatus.Open, "source": "MockUpstox"},
        {"external_id": "mock-bajaj-4", "name": "Bajaj Housing Finance IPO", "status": IPOStatus.Closed, "source": "MockUpstox"}
    ]

    added = 0
    for data in mock_data:
        existing = db.query(IPO).filter(IPO.external_id == data["external_id"]).first()
        is_valid = is_sane_ipo(data["name"], data["status"])
        if not existing:
            new_ipo = IPO(
                external_id=data["external_id"],
                name=data["name"],
                status=data["status"],
                source=data["source"],
                synced_at=datetime.datetime.utcnow(),
                auto_detected=True,
                validated=is_valid
            )
            db.add(new_ipo)
            added += 1

    db.commit()
    db.close()
    print(f"Mock sync complete. Added {added} new IPOs.")


if __name__ == "__main__":
    result = sync_ipos_from_web()
    print(f"Sync result: {result}")
