"""Scraper for UMBC Registrar academic calendars - important dates and deadlines."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class RegistrarScraper(BaseScraper):
    """Scraper for UMBC Registrar academic calendars (registrar.umbc.edu)."""
    
    CALENDAR_URLS = [
        "https://registrar.umbc.edu/spring-undergraduate-academic-calendar",
        "https://registrar.umbc.edu/summer-academic-calendar",
        "https://registrar.umbc.edu/fall-undergraduate-academic-calendar/",
    ]
    
    def __init__(self):
        super().__init__(self.CALENDAR_URLS[0])
    
    def scrape(self) -> List[Dict]:
        """Scrape important dates from all registrar calendar pages."""
        all_dates = []
        seen = set()
        
        for url in self.CALENDAR_URLS:
            try:
                soup = self.get_soup(url)
                events = self._parse_calendar_page(soup, url)
                for event in events:
                    key = f"{event['date']}|{event['title']}"
                    if key not in seen:
                        seen.add(key)
                        all_dates.append(event)
            except Exception as e:
                print(f"Error scraping registrar ({url}): {e}")
        
        return all_dates
    
    def _parse_calendar_page(self, soup, base_url: str) -> List[Dict]:
        """Parse a registrar calendar page - extracts table rows with Date, Event, Details."""
        events = []
        
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            header = None
            date_col = 0
            event_col = 1
            details_col = 2
            
            for row in rows:
                cells = row.find_all(['th', 'td'])
                if not cells:
                    continue
                texts = [c.get_text(strip=True) for c in cells]
                
                if header is None and len(texts) >= 2:
                    lower_texts = [t.lower() for t in texts]
                    if 'event' in lower_texts:
                        event_col = lower_texts.index('event') if 'event' in lower_texts else 1
                        if 'details' in lower_texts:
                            details_col = lower_texts.index('details')
                        else:
                            details_col = min(event_col + 1, len(texts) - 1)
                        date_col = 0 if event_col > 0 else (1 if len(texts) > 3 else 0)
                        header = texts
                        continue
                
                if len(texts) >= 2:
                    date_str = texts[date_col] if date_col < len(texts) else texts[0]
                    event_col_actual = event_col if event_col < len(texts) else len(texts) - 2
                    details_col_actual = details_col if details_col < len(texts) else len(texts) - 1
                    title = texts[event_col_actual]
                    details = texts[details_col_actual] if details_col_actual != event_col_actual and details_col_actual < len(texts) else ''
                    if not re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}$', date_str.strip()):
                        date_str = texts[0] if len(texts) > 2 else date_str
                    if date_str and title and not title.lower().startswith('date') and not title.lower().startswith('event'):
                        event = {
                            'title': title,
                            'date': date_str,
                            'description': details,
                            'link': base_url,
                            'source': 'UMBC Registrar',
                        }
                        events.append(event)
        
        if not events:
            list_items = soup.find_all(['li', 'p'])
            for li in list_items:
                text = li.get_text(strip=True)
                date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})(?:\s*[–-]\s*(\d{1,2}/\d{1,2}/\d{2,4}))?\s*:\s*(.+)', text, re.I)
                if date_match:
                    start = date_match.group(1)
                    end = date_match.group(2)
                    rest = date_match.group(3)
                    date_str = f"{start} – {end}" if end else start
                    title_end = rest.find('.') if '.' in rest else len(rest)
                    title = rest[:title_end].strip()
                    events.append({
                        'title': title,
                        'date': date_str,
                        'description': rest,
                        'link': base_url,
                        'source': 'UMBC Registrar',
                    })
        
        return events
