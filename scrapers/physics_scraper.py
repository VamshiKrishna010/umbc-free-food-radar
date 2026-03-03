"""Scraper for physics.umbc.edu/colloquium-schedule/ - Physics Department Colloquia."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class PhysicsScraper(BaseScraper):
    """Scraper for UMBC Physics Department colloquium schedule."""

    BASE_URL = "https://physics.umbc.edu"
    EVENTS_URL = "https://physics.umbc.edu/colloquium-schedule/"

    def __init__(self):
        super().__init__(self.EVENTS_URL)

    def scrape(self) -> List[Dict]:
        try:
            soup = self.get_soup(self.EVENTS_URL)
            return self._parse_page(soup)
        except Exception as e:
            print(f"Error scraping Physics colloquia: {e}")
            return []

    def _parse_page(self, soup) -> List[Dict]:
        events = []
        seen_links = set()

        # Primary: Localist event detail links
        for a in soup.find_all("a", href=re.compile(r"/(?:home/)?events?/event/\d+")):
            href = a.get("href", "")
            link = href if href.startswith("http") else self.BASE_URL + href
            if link in seen_links:
                continue
            seen_links.add(link)

            container = a.find_parent(["p", "div", "li", "tr", "section"])
            title_raw = (container.find(["h2", "h3"]) if container else None)
            title_raw = title_raw.get_text(strip=True)[:200] if title_raw else a.get_text(strip=True)[:200]
            title = f"Physics Colloquium: {title_raw}" if title_raw else "Physics Colloquium"

            ev = self.scrape_localist_detail(link, title, source="Physics Department")
            events.append(ev)

        # Fallback: parse block text for TBD/plain-text entries (no links)
        if not events:
            for block in soup.find_all(["p", "li", "div"]):
                text = block.get_text(" ", strip=True)
                date_m = re.search(
                    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2},?\s*\d{4}",
                    text, re.I
                )
                if not date_m:
                    continue
                title_m = re.search(r"(?:Title:|Talk:)\s*(.+)", text, re.I)
                raw_title = title_m.group(1).strip()[:150] if title_m else text[:80]
                title = f"Physics Colloquium: {raw_title}"
                slug = re.sub(r"[^a-z0-9]", "-", raw_title.lower())[:30]
                link = f"{self.EVENTS_URL}#{slug}"
                if link in seen_links:
                    continue
                seen_links.add(link)
                events.append({
                    "title": title,
                    "date": date_m.group(0),
                    "description": text[:400],
                    "link": self.EVENTS_URL,
                    "source": "Physics Department",
                })

        return events
