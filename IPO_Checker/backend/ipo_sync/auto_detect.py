import sys
import os
import datetime
import logging
import requests
from bs4 import BeautifulSoup

# Add backend directory to path so we can import from db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import SessionLocal
from db.models import IPO, IPOStatus
import re

def is_sane_ipo(name: str, status: IPOStatus) -> bool:
    if not name or len(name) < 3 or len(name) > 150:
        return False
    # Basic check for suspicious characters (script tags, etc.)
    if re.search(r"[<>{}\[\]]", name):
        return False
    if status not in [IPOStatus.Open, IPOStatus.Closed, IPOStatus.Allotment_Announced]:
        return False
    return True

logger = logging.getLogger(__name__)

# --- Source 1: Upstox Public IPO Page ---
UPSTOX_IPO_URL = "https://upstox.com/ipo/"

# --- Source 2: Moneycontrol as fallback ---
MONEYCONTROL_IPO_URL = "https://www.moneycontrol.com/ipo/ipo-allotment-status/"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}


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
    Main sync function. Tries Upstox first, falls back to Moneycontrol.
    Upserts IPOs into the database.
    Returns a summary dict with counts.
    """
    scraped_ipos = _scrape_upstox_ipos()

    if not scraped_ipos:
        logger.info("Upstox returned no IPOs, trying Moneycontrol fallback...")
        scraped_ipos = _scrape_moneycontrol_ipos()

    if not scraped_ipos:
        logger.warning("No IPOs found from any source. Database unchanged.")
        return {"added": 0, "updated": 0, "source": "none"}

    source = scraped_ipos[0]["source"] if scraped_ipos else "none"

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
                    synced_at=datetime.datetime.utcnow(),
                    auto_detected=True,
                    validated=is_valid
                )
                db.add(new_ipo)
                added += 1
            else:
                # Update status if it changed
                if existing.status != data["status"]:
                    existing.status = data["status"]
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
