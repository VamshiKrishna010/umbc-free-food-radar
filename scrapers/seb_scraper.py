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
        """Scrape SEB events with pagination. Check for food keywords."""
        all_events = []
        seen = set()
        page = 1
        max_pages = 8
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
                print(f"Error scraping SEB page {page}: {e}")
                break
        return all_events
    
    def _parse_page(self, soup) -> List[Dict]:
        events = []
        for a in soup.find_all("a", href=re.compile(r"/events/event/\d+")):
            href = a.get("href", "")
            link = href if href.startswith("http") else self.BASE_URL + href
            container = a.find_parent(["article", "div"], class_=lambda x: x and "event" in str(x).lower())
            if not container:
                container = a.find_parent(["article", "div"])
            if not container:
                continue
            title_el = container.find(["h2", "h3"])
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)[:100]
            if not title or len(title) < 2:
                continue
            desc_el = container.find("p")
            desc = desc_el.get_text(strip=True)[:400] if desc_el else ""
            date_text = ""
            for node in container.find_all(string=True):
                t = str(node).strip()
                if re.search(r"\d{4}.*\d{1,2}:\d{2}", t) or ("February" in t or "March" in t or "April" in t or "May" in t):
                    date_text = t[:80]
                    break
            events.append({
                "title": title[:200],
                "date": date_text or "TBA",
                "description": desc,
                "link": link,
                "source": "Student Events Board",
            })
        return events
