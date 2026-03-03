"""Scraper for dineoncampus.com/UMBC - UMBC Dining Services specials and events."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class DiningScraper(BaseScraper):
    """Scraper for UMBC Dining Services. Looks for special dining events and promotions."""

    BASE_URL = "https://dineoncampus.com"
    EVENTS_URL = "https://dineoncampus.com/UMBC"

    def __init__(self):
        super().__init__(self.EVENTS_URL)

    def scrape(self) -> List[Dict]:
        try:
            soup = self.get_soup_js(
                self.EVENTS_URL,
                wait_selector="main, a[href*='event'], a[href*='special'], a[href*='offer']",
            )
            events = self._parse_page(soup)
            return events
        except Exception as e:
            print(f"Error scraping Dining events: {e}")
            return []

    def _parse_page(self, soup) -> List[Dict]:
        events = []
        seen = set()

        # Look for any event/special/promotion related links or sections
        for a in soup.find_all("a", href=re.compile(r"(event|special|promotion|news|offer)", re.I)):
            href = a.get("href", "")
            link = href if href.startswith("http") else self.BASE_URL + href
            if link in seen:
                continue
            title = a.get_text(strip=True)[:200]
            if not title or len(title) < 3:
                continue
            seen.add(link)
            container = a.find_parent(["div", "section", "article", "li"])
            desc_el = container.find("p") if container else None
            desc = desc_el.get_text(strip=True)[:400] if desc_el else ""
            date_text = self._extract_date(container) if container else ""
            events.append({
                "title": title,
                "date": date_text or "Check site for hours",
                "description": desc or "UMBC Dining Services special or event.",
                "link": link,
                "source": "UMBC Dining",
            })

        # Always include static entry for the dining hall
        dining_hall_link = self.EVENTS_URL
        if dining_hall_link not in seen:
            events.append({
                "title": "UMBC Dining Hall – True Grits",
                "date": "Ongoing",
                "description": (
                    "UMBC's main all-you-can-eat dining hall. Accepts meal plans and Flex points. "
                    "Check dineoncampus.com/UMBC for daily menus and hours."
                ),
                "link": self.EVENTS_URL,
                "source": "UMBC Dining",
            })

        return events

    def _extract_date(self, container) -> str:
        if not container:
            return ""
        for node in container.find_all(string=True):
            t = str(node).strip()
            if re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}", t, re.I):
                return t[:100]
            if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", t):
                return t[:100]
        return ""
