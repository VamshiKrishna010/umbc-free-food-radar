"""Scraper for biology.umbc.edu/seminars-events/ - Biology Department Seminars."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class BiologyScraper(BaseScraper):
    """Scraper for UMBC Biology Department seminars and events."""

    BASE_URL = "https://biology.umbc.edu"
    EVENTS_URL = "https://biology.umbc.edu/seminars-events/"

    def __init__(self):
        super().__init__(self.EVENTS_URL)

    def scrape(self) -> List[Dict]:
        all_events = []
        seen = set()
        page = 1
        max_pages = 5

        while page <= max_pages:
            url = self.EVENTS_URL if page == 1 else f"{self.EVENTS_URL}page/{page}/"
            try:
                soup = self.get_soup(url)
                events = self._parse_page(soup)
                if not events:
                    break
                for ev in events:
                    if ev["link"] not in seen:
                        seen.add(ev["link"])
                        all_events.append(ev)
                page += 1
            except Exception as e:
                print(f"Error scraping Biology seminars page {page}: {e}")
                break

        return all_events

    def _parse_page(self, soup) -> List[Dict]:
        events = []
        seen_links = set()

        for a in soup.find_all("a", href=re.compile(r"/seminars-events/event/\d+")):
            href = a.get("href", "")
            link = href if href.startswith("http") else self.BASE_URL + href
            if link in seen_links:
                continue
            seen_links.add(link)

            container = a.find_parent(["article", "div", "li"])
            title_el = container.find(["h2", "h3"]) if container else None
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)[:200]
            if not title or len(title) < 2:
                continue

            ev = self.scrape_localist_detail(link, title, source="Biology Department")
            events.append(ev)

        return events
