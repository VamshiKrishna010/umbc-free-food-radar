"""Scraper for seb.umbc.edu - Student Events Board (many events have free food)."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class SEBScraper(BaseScraper):
    """Scraper for Student Events Board at seb.umbc.edu."""

    BASE_URL = "https://seb.umbc.edu"
    EVENTS_URL = "https://seb.umbc.edu/events/"

    def __init__(self):
        super().__init__(self.EVENTS_URL)

    def scrape(self) -> List[Dict]:
        all_events = []
        seen = set()
        page = 1
        max_pages = 8
        while page <= max_pages:
            url = self.EVENTS_URL if page == 1 else f"{self.EVENTS_URL}page/{page}/"
            try:
                soup = self.get_soup(url)
                links = self._collect_links(soup)
                if not links:
                    break
                for link, title in links:
                    if link in seen:
                        continue
                    seen.add(link)
                    ev = self._scrape_detail(link, title)
                    if ev:
                        all_events.append(ev)
                page += 1
            except Exception as e:
                print(f"Error scraping SEB page {page}: {e}")
                break
        return all_events

    def _collect_links(self, soup) -> List[tuple]:
        """Return (link, title) pairs from a listing page."""
        results = []
        for a in soup.find_all("a", href=re.compile(r"/events/event/\d+")):
            href = a.get("href", "")
            link = href if href.startswith("http") else self.BASE_URL + href
            container = a.find_parent(["article", "div"])
            title_el = container.find(["h2", "h3"]) if container else None
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)[:100]
            if title and len(title) >= 2:
                results.append((link, title))
        return results

    def _scrape_detail(self, link: str, fallback_title: str) -> Dict | None:
        return self.scrape_localist_detail(link, fallback_title, source="Student Events Board")
