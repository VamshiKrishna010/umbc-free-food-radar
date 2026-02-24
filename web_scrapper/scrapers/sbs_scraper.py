"""Scraper for SBS billing deadlines - important dates for students."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict


class SBSScraper(BaseScraper):
    """Scraper for Student Business Services billing schedule (sbs.umbc.edu)."""
    
    URL = "https://sbs.umbc.edu/billing/e-billing-schedule/"
    
    def __init__(self):
        super().__init__(self.URL)
    
    def scrape(self) -> List[Dict]:
        """Scrape e-billing due dates and late fee dates as important dates."""
        events = []
        seen_keys = set()
        current_term = "Term"
        try:
            soup = self.get_soup(self.URL)
            for tag in soup.find_all(["h4", "h5", "h6", "table"]):
                if tag.name in ("h4", "h5", "h6"):
                    text = tag.get_text(strip=True)
                    if text in ("Fall", "Winter", "Spring", "Summer"):
                        current_term = text
                    continue
                rows = tag.find_all("tr")
                for row in rows[1:]:
                    cells = row.find_all(["th", "td"])
                    if len(cells) < 3:
                        continue
                    texts = [c.get_text(strip=True) for c in cells]
                    due_date = texts[2] if len(texts) > 2 else texts[0]
                    late_date = texts[3] if len(texts) > 3 else ""
                    key = f"{current_term}|{due_date}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    title = f"E-Bill Due ({current_term})"
                    desc = f"Payment due. Late fee charged {late_date}." if late_date else "Payment due."
                    events.append({
                        "title": title,
                        "date": due_date,
                        "description": desc,
                        "link": self.URL,
                        "source": "Student Business Services",
                    })
        except Exception as e:
            print(f"Error scraping SBS: {e}")
        return events
