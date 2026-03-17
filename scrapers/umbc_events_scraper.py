"""Scraper for UMBC main events (umbc.edu/events)."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict


class UMBCEventsScraper(BaseScraper):
    """Scraper for UMBC featured events (umbc.edu/events, events.umbc.edu)."""
    
    EVENTS_URLS = [
        "https://umbc.edu/events/",
        "https://umbc.edu/events/month/",
    ]
    
    def __init__(self):
        super().__init__(self.EVENTS_URLS[0])
    
    def scrape(self) -> List[Dict]:
        """Scrape campus events from UMBC main events pages."""
        all_events = []
        seen_links = set()
        
        for url in self.EVENTS_URLS:
            try:
                soup = self.get_soup(url)
                events = self._parse_events_page(soup)
                for event in events:
                    if event['link'] not in seen_links:
                        seen_links.add(event['link'])
                        all_events.append(event)
            except Exception as e:
                print(f"Error scraping UMBC events ({url}): {e}")
        
        return all_events
    
    def _parse_events_page(self, soup) -> List[Dict]:
        """Parse umbc.edu/events page - events have descriptions and links to full details."""
        events = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/event/' in href and href.startswith('http'):
                link = href
            elif '/event/' in href:
                link = 'https://umbc.edu' + href if href.startswith('/') else 'https://umbc.edu/' + href
            else:
                continue
            
            container = a.find_parent(['article', 'div'], class_=lambda x: x and ('event' in str(x).lower() or 'tribe' in str(x).lower()))
            if not container:
                container = a.find_parent(['article', 'div'])
            
            if not container:
                continue
            
            title_elem = container.select_one('h2, h3, h4, .tribe-events-calendar-list__event-title')
            title = title_elem.get_text(strip=True) if title_elem else a.get_text(strip=True)[:100]
            
            desc_elem = container.select_one('p, .tribe-events-list-event-description')
            description = desc_elem.get_text(strip=True) if desc_elem else ''
            
            date_elem = container.select_one('time, .tribe-event-date-start, .event-date')
            date_str = ''
            if date_elem:
                date_str = date_elem.get('datetime', '') or date_elem.get_text(strip=True)
            if not date_str and container:
                date_str = container.get_text(strip=True)[:80]
            
            if not title or len(title) < 3:
                continue
            
            event = {
                'title': title[:200],
                'date': date_str or 'TBA',
                'description': description[:500] if description else '',
                'link': link,
                'source': 'UMBC Events',
            }
            events.append(event)
        
        if not events:
            for article in soup.find_all(['article', 'div'], class_=lambda x: x and 'tribe' in str(x).lower()):
                link_elem = article.find('a', href=lambda h: h and '/event/' in str(h))
                if not link_elem:
                    continue
                link = link_elem['href']
                if not link.startswith('http'):
                    link = 'https://umbc.edu' + (link if link.startswith('/') else '/' + link)
                title = link_elem.get_text(strip=True) or 'Event'
                desc = article.find('p')
                date_el = article.select_one('time, .date, [class*="date"]')
                events.append({
                    'title': title[:200],
                    'date': date_el.get_text(strip=True) if date_el else 'TBA',
                    'description': desc.get_text(strip=True)[:500] if desc else '',
                    'link': link,
                    'source': 'UMBC Events',
                })
        
        return events
