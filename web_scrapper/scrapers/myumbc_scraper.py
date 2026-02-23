from scrapers.base_scraper import BaseScraper
from typing import List, Dict

class MyUMBCScraper(BaseScraper):
    """Scraper for the myUMBC Events calendar (https://my.umbc.edu/events)."""
    
    def scrape(self) -> List[Dict]:
        """
        Implementation for myUMBC calendar.
        myUMBC has a specific structure where event cards contain all the summary information.
        """
        events = []
        try:
            # We fetch from the base URL provided. 
            # myUMBC has a handy /free-food filter specifically!
            soup = self.get_soup(self.base_url)
            
            # Find all event containers directly.
            # Using a generic event class selector that handles myUMBC's CSS
            # Examples: 'my-events-item', 'event-card', 'ui-list__item'
            
            # myUMBC usually uses anchor tags linking directly to the event ID
            for a in soup.find_all('a', href=True):
                # Look for links like /events/123456 or /groups/name/events/12345
                href = a['href']
                if '/events/' in href and any(c.isdigit() for c in href):
                    
                    # Ensure the link is absolute
                    if href.startswith('/'):
                        abs_link = 'https://my3.my.umbc.edu' + href
                    else:
                        abs_link = href
                    
                    # Avoid duplicate processing of the same link on the page
                    if any(e['link'] == abs_link for e in events):
                        continue
                    
                    # Find the containing HTML block for this event
                    container = a.find_parent('div', class_=lambda x: x and ('event' in x.lower() or 'item' in x.lower()))
                    if not container:
                        continue
                    
                    # Extract text using a separator to split fields
                    text_parts = container.get_text(separator='|', strip=True).split('|')
                    
                    # The text parts usually follow: [Month Day, Time, Title, Location, Description...]
                    # Since it can vary, we will just join them for description, but try to extract the title
                    
                    title = "No Title"
                    date = ""
                    description = ""
                    
                    # Try to extract exact title from heading tags if possible
                    heading = container.find(['h3', 'h4', 'strong'])
                    if heading:
                        title = heading.get_text(strip=True)
                    elif len(text_parts) > 2:
                        title = text_parts[2] # Fallback
                        
                    # Date is usually the first part 
                    if len(text_parts) > 0:
                        date = text_parts[0]
                        if len(text_parts) > 1 and "AM" in text_parts[1] or "PM" in text_parts[1]:
                            date += " " + text_parts[1]
                            
                    description = " ".join(text_parts)
                    
                    event = {
                        'title': title,
                        'date': date,
                        'description': description,
                        'link': abs_link,
                        'source': 'myUMBC'
                    }
                    
                    events.append(event)
                    
        except Exception as e:
            print(f"Error scraping myUMBC ({self.base_url}): {e}")
            
        return events
