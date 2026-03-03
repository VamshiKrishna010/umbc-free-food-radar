"""Scraper for library.umbc.edu - Albin O. Kuhn Library events and workshops."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class LibraryScraper(BaseScraper):
    """Scraper for AOK Library events, workshops, and gallery exhibitions."""

    BASE_URL = "https://library.umbc.edu"
    MYUMBC_BASE = "https://my3.my.umbc.edu"
    URLS = [
        ("https://library.umbc.edu/events", "AOK Library"),
        ("https://library.umbc.edu/workshops/index.php", "Library Workshops"),
    ]

    def __init__(self):
        super().__init__(self.URLS[0][0])

    def scrape(self) -> List[Dict]:
        all_events = []
        seen = set()

        for url, source_label in self.URLS:
            try:
                soup = self.get_soup(url)
                events = self._parse_page(soup, source_label)
                for ev in events:
                    if ev["link"] not in seen:
                        seen.add(ev["link"])
                        all_events.append(ev)
            except Exception as e:
                print(f"Error scraping Library ({url}): {e}")

        return all_events

    def _parse_page(self, soup, source_label: str) -> List[Dict]:
        events = []

        # Library event links go to my.umbc.edu/groups/library/events/ID
        for a in soup.find_all("a", href=re.compile(r"(library/events/\d+|my\.umbc\.edu/groups/library)")):
            href = a.get("href", "").lstrip("/")
            link = href if href.startswith("http") else "https://" + href
            title = a.get_text(strip=True)[:200]
            if not title or len(title) < 2:
                continue

            container = a.find_parent(["li", "div", "article", "section"])
            date_text = ""
            desc = ""

            if container:
                texts = [t.strip() for t in container.find_all(string=True) if t.strip()]
                for t in texts:
                    if re.search(r"(Date:|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)", t, re.I) \
                            and re.search(r"\d", t):
                        date_text = t[:100]
                    elif re.search(r"(Summary:|Abstract:|Description:)", t, re.I):
                        desc = t.replace("Summary:", "").replace("Abstract:", "").strip()[:400]

                if not date_text:
                    date_text = self._extract_date(container)

            events.append({
                "title": title,
                "date": date_text or "TBA",
                "description": desc,
                "link": link,
                "source": source_label,
            })

        # Fallback: look for h3 headings with nearby event metadata
        if not events:
            for h in soup.find_all(["h3", "h2"]):
                a = h.find("a")
                if not a:
                    continue
                href = a.get("href", "").lstrip("/")
                link = href if href.startswith("http") else "https://" + href
                title = h.get_text(strip=True)[:200]
                if not title or len(title) < 2:
                    continue
                parent = h.find_parent(["li", "div", "article"])
                date_text = self._extract_date(parent) if parent else ""
                events.append({
                    "title": title,
                    "date": date_text or "TBA",
                    "description": "",
                    "link": link,
                    "source": source_label,
                })

        return events

    def _extract_date(self, container) -> str:
        if not container:
            return ""
        for node in container.find_all(string=True):
            t = str(node).strip()
            if re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}", t, re.I):
                return t[:100]
            if re.search(r"\d{1,2}(st|nd|rd|th)\s+at\s+\d{1,2}:\d{2}", t, re.I):
                return t[:100]
        return ""
