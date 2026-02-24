"""Scraper for tickets.umbc.edu - Athletics, Arts & Culture events."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
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
            soup = self.get_soup(self.EVENTS_URL)
            for a in soup.find_all("a", href=re.compile(r"event\.aspx\?id=\d+")):
                href = a.get("href", "")
                if href.startswith("http"):
                    link = href
                elif href.startswith("/"):
                    link = self.BASE_URL + href
                else:
                    link = self.BASE_URL + "/w/" + href.lstrip("/")
                if link in seen:
                    continue
                seen.add(link)
                container = a.find_parent(["div", "li", "article"])
                if not container:
                    container = a
                title = a.get_text(strip=True)
                if not title or len(title) < 3:
                    continue
                date_str = ""
                for sib in container.find_next_siblings() + list(container.previous_siblings or []):
                    if hasattr(sib, "get_text"):
                        t = sib.get_text(strip=True)
                        if re.search(r"\w+,?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", t):
                            date_str = t[:60]
                            break
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
