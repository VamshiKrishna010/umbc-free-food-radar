"""Scraper for tickets.umbc.edu - Athletics, Arts & Culture events."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
from urllib.parse import urljoin
import re


class TicketsScraper(BaseScraper):
    """Scraper for UMBC tickets (umbctickets.universitytickets.com)."""
    
    BASE_URL = "https://umbctickets.universitytickets.com"
    EVENTS_URL = "https://umbctickets.universitytickets.com/w/default.aspx"
    
    def __init__(self):
        super().__init__(self.EVENTS_URL)
    
    def scrape(self) -> List[Dict]:
        """Scrape athletics and arts events from UMBC tickets."""
        events = []
        seen = set()
        try:
            soup = self.get_soup_js(
                self.EVENTS_URL,
                wait_selector="main, a[href*='event.aspx?id='], a[href*='event.aspx?Id=']",
            )
            for a in soup.find_all("a", href=re.compile(r"event\.aspx\?id=\d+", re.I)):
                href = str(a.get("href", ""))
                link = urljoin(f"{self.BASE_URL}/w/", href)
                if link in seen:
                    continue
                seen.add(link)
                container = a.find_parent(["div", "li", "article"])
                if not container:
                    container = a
                title = a.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                date_str = self._extract_date(container)
                if not date_str:
                    parent = container.find_parent(["div", "li", "article", "section"])
                    if parent:
                        date_str = self._extract_date(parent)
                desc = ""
                parent = container.find_parent()
                if parent:
                    desc = parent.get_text(strip=True)[:300]
                events.append({
                    "title": title[:200],
                    "date": date_str or "TBA",
                    "description": desc,
                    "link": link,
                    "source": "UMBC Tickets",
                })
        except Exception as e:
            print(f"Error scraping UMBC tickets: {e}")
        return events

    def _extract_date(self, container) -> str:
        if not container:
            return ""

        patterns = [
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*[,]?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}(?:,\s*\d{4})?",
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}(?:,\s*\d{4})?",
            r"\d{1,2}/\d{1,2}/\d{2,4}",
        ]

        for node in container.find_all(string=True):
            text = str(node).strip()
            if not text:
                continue
            for pattern in patterns:
                match = re.search(pattern, text, re.I)
                if match:
                    return match.group(0)[:80]

        return ""
