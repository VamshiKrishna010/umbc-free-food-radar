"""Scraper for my3.my.umbc.edu/groups/official-dates - Official UMBC Dates & Deadlines."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re
from urllib.parse import urljoin


class OfficialDatesScraper(BaseScraper):
    """Scraper for the myUMBC Official Dates & Deadlines group page."""

    BASE_URL = "https://my.umbc.edu"
    EVENTS_URL = "https://my.umbc.edu/groups/official-dates/events"

    def __init__(self):
        super().__init__(self.EVENTS_URL)

    def scrape(self) -> List[Dict]:
        all_events = []
        seen = set()

        for url in [self.EVENTS_URL, f"{self.BASE_URL}/groups/official-dates"]:
            try:
                soup = self.get_soup_authenticated(url, wait_selector="a[href*='/events/']")
                events = self._parse_page(soup)
                for ev in events:
                    if ev["link"] not in seen:
                        seen.add(ev["link"])
                        all_events.append(ev)
            except Exception as e:
                print(f"Error scraping Official Dates ({url}): {e}")

        return all_events

    def _parse_page(self, soup) -> List[Dict]:
        events = []
        # myUMBC group event links
        for a in soup.find_all("a", href=re.compile(r"/groups/official-dates/events/\d+|/events/\d+")):
            href = a.get("href", "")
            link = urljoin(self.BASE_URL, href)

            container = a.find_parent(["article", "div", "li"])
            title_el = container.find(["h2", "h3", "h4"]) if container else None
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)[:200]
            if not title or len(title) < 2:
                continue

            desc_el = container.find("p") if container else None
            desc = desc_el.get_text(strip=True)[:400] if desc_el else ""

            date_text = ""
            if container:
                for node in container.find_all(string=True):
                    t = str(node).strip()
                    if re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}", t, re.I) \
                            or re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", t):
                        date_text = t[:100]
                        break

            events.append({
                "title": title[:200],
                "date": date_text or "TBA",
                "description": desc,
                "link": link,
                "source": "UMBC Official Dates",
            })

        return events
