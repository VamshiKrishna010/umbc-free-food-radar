import re
from typing import List, Dict
from .base_scraper import BaseScraper

class BaltimoreMagScraper(BaseScraper):
    def __init__(self):
        super().__init__("https://events.baltimoremagazine.com/university_of_maryland_baltimore_county_umbc_177")

    def scrape(self) -> List[Dict]:
        events = []
        try:
            soup = self.get_soup(self.base_url)
        except Exception as e:
            print(f"BaltimoreMag fail: {e}")
            return events

        seen_links = set()
        # Look for event cards or links
        for article in soup.find_all(["article", "div"], class_=re.compile(r"event", re.I)):
            a_tag = article.find("a", href=True)
            if not a_tag:
                continue
                
            href = a_tag["href"]
            if "/event/" not in href:
                continue
                
            title_tag = article.find(["h2", "h3", "h4"])
            title = title_tag.get_text(strip=True) if title_tag else a_tag.get_text(strip=True)
            
            if len(title) < 4 or href in seen_links:
                continue
                
            seen_links.add(href)
            
            date_text = "TBA"
            # often class date or time or just another div/span
            date_tag = article.find(class_=re.compile(r"date|time", re.I))
            if date_tag:
                date_text = date_tag.get_text(separator=" ", strip=True)
                
            desc_tag = article.find(class_=re.compile(r"desc|summary|excerpt", re.I))
            description = desc_tag.get_text(separator=" ", strip=True) if desc_tag else title

            clean_link = href if href.startswith("http") else f"https://events.baltimoremagazine.com{href}"

            events.append({
                "title": title[:100],
                "link": clean_link,
                "date": date_text[:50],
                "description": description[:500],
                "source": "Baltimore Magazine",
            })
            
        return events
