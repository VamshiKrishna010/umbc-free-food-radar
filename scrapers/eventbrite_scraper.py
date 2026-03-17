import re
from typing import List, Dict
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper

class EventbriteScraper(BaseScraper):
    def __init__(self):
        super().__init__("https://www.eventbrite.com/d/md--baltimore/umbc/")

    def scrape(self) -> List[Dict]:
        events = []
        try:
            soup = self.get_soup_js(self.base_url, wait_selector=".search-main-content", timeout=20000)
        except Exception as e:
            print(f"Eventbrite fail: {e}")
            return events
            
        seen_links = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/e/" not in href:
                continue
                
            title = a.get_text(strip=True)
            if len(title) < 5:
                # sometimes image contains heading
                h3 = a.find("h3") or (a.find_parent("div") and a.find_parent("div").find("h3"))
                if h3:
                    title = h3.get_text(strip=True)
                    
            if len(title) < 5 or href in seen_links:
                continue
                
            seen_links.add(href)
            
            # Find date text
            date_text = "TBA"
            card = a.find_parent("section") or a.find_parent("div", class_=re.compile(r"event-card", re.I))
            if card:
                for p in card.find_all("p"):
                    text = p.get_text(strip=True)
                    if re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),', text) or re.search(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', text):
                        date_text = text
                        break
            
            clean_link = href.split("?")[0]
            if not clean_link.startswith("http"):
                clean_link = "https://www.eventbrite.com" + clean_link

            events.append({
                "title": title[:100],
                "link": clean_link,
                "date": date_text[:50],
                "description": title,
                "source": "Eventbrite",
            })
            
        return events


