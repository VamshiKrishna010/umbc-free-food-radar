import re
from typing import List, Dict
from bs4 import BeautifulSoup
from .base_scraper import BaseScraper

class PatchCalendarScraper(BaseScraper):
    def __init__(self):
        super().__init__("https://patch.com/maryland/baltimore/calendar")

    def scrape(self) -> List[Dict]:
        events = []
        try:
            soup = self.get_soup(self.base_url)
        except Exception as e:
            print(f"Patch fail: {e}")
            return events

        seen_links = set()
        # Events usually inside an article or specific div
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/calendar/event/" not in href:
                continue
                
            # Filter for UMBC if reasonable, but the user asked for Patch for UMBC related events.
            # Local Baltimore events might pass, maybe too noisy. Will grab all for now.
            
            title_tag = a.find(["h2", "h3", "h4"])
            title = title_tag.get_text(strip=True) if title_tag else a.get_text(strip=True)
            
            if len(title) < 5 or href in seen_links:
                continue
                
            seen_links.add(href)
            
            date_text = "TBA"
            card = a.find_parent("article") or a.find_parent("div", class_=re.compile(r"event", re.I))
            if card:
                time_t = card.find("time")
                if time_t:
                    date_text = time_t.get_text(strip=True)
                else:
                    for p in card.find_all(["p", "span", "div"]):
                        t = p.get_text(strip=True)
                        if " at " in t or re.search(r'(Mon|Tue|Wed|Thu|Fri|Sat|Sun),', t):
                            date_text = t
                            break

            desc = title
            if card:
                p_tags = card.find_all("p")
                if p_tags:
                    desc = max([p.get_text(strip=True) for p in p_tags], key=len, default=title)

            clean_link = href if href.startswith("http") else f"https://patch.com{href}"

            events.append({
                "title": title[:100],
                "link": clean_link,
                "date": date_text[:50],
                "description": desc[:500],
                "source": "Patch",
            })
            
        return events
