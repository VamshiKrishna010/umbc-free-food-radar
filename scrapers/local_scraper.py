from scrapers.base_scraper import BaseScraper
from typing import List, Dict

class LocalistScraper(BaseScraper):
    """Scraper for university calendars powered by Localist (Concept3D)."""
    
    def scrape(self) -> List[Dict]:
        """
        Implementation for Localist calendars.
        Localist usually has a list of events in a predictable HTML structure.
        """
        events = []
        try:
            soup = self.get_soup(self.base_url)
            # Typical Localist event list item selector
            event_items = soup.select('.lw_event_item, .event-card, .list-event-item')
            
            for item in event_items:
                title_elem = item.select_one('.lw_event_title, h3, .title')
                date_elem = item.select_one('.lw_event_date, .date')
                desc_elem = item.select_one('.lw_event_description, .description, .summary')
                link_elem = item.select_one('a')
                
                event = {
                    'title': title_elem.get_text(strip=True) if title_elem else 'No Title',
                    'date': date_elem.get_text(strip=True) if date_elem else 'No Date',
                    'description': desc_elem.get_text(strip=True) if desc_elem else '',
                    'link': link_elem['href'] if link_elem and link_elem.has_attr('href') else self.base_url,
                    'source': 'Localist'
                }
                
                # Resolve relative URLs
                if event['link'].startswith('/'):
                    event['link'] = self.base_url.rstrip('/') + event['link']
                    
                events.append(event)
        except Exception as e:
            print(f"Error scraping Localist ({self.base_url}): {e}")
            
        return events
