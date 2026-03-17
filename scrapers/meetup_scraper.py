import re
import time
from typing import List, Dict
from .base_scraper import BaseScraper

class MeetupScraper(BaseScraper):
    def __init__(self):
        super().__init__("https://www.meetup.com/find/?keywords=umbc&location=us--md--Baltimore&source=EVENTS")

    def scrape(self) -> List[Dict]:
        events = []
        try:
            # wait_selector for Meetup's event card wrapper
            soup = self.get_soup_js(self.base_url, wait_selector="a[data-event-label]", timeout=30000)
        except Exception as e:
            print(f"Meetup fail: {e}")
            # If wait_selector failed, try to parse anyway, it might have loaded partially
            soup = self.get_soup(self.base_url)

        seen_links = set()
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/events/" not in href or "meetup.com" not in href:
                continue
                
            title = "TBA"
            card = a.find_parent("div")
            if card:
                h3 = card.find("h3")
                if h3:
                    title = h3.get_text(strip=True)
                    
            if len(title) < 5 or title == "TBA":
                # Maybe no inner h3, fallback to checking deep text
                text_elements = [h.get_text(strip=True) for h in (card.find_all(["h2", "h3"]) if card else [])]
                if text_elements:
                    title = text_elements[0]
                else:
                    text = a.get_text(strip=True)
                    if len(text) > 5 and not "attendees" in text.lower():
                        title = text

            if len(title) < 5 or title == "TBA":
                continue
                
            if href in seen_links:
                continue
            seen_links.add(href)
            
            date_text = "TBA"
            time_tag = card.find("time") if card else a.find("time")
            if time_tag:
                date_text = time_tag.get_text(strip=True)
            
            clean_link = href.split("?")[0]

            events.append({
                "title": title[:100],
                "link": clean_link,
                "date": date_text[:50],
                "description": title,
                "source": "Meetup",
            })
            
        return events
