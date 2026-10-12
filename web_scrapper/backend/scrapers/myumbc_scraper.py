import re
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
from urllib.parse import urljoin

# Pseudo-event URL segments that are navigation/category pages, not real events
_SKIP_SEGMENTS = {'featured', 'weekend', 'today', 'upcoming', 'past', 'free-food'}

_JUNK_TITLES = {
    'no title', 'untitled', 'view more', 'featured events',
    'weekend', 'today', 'upcoming events', '',
}


class MyUMBCScraper(BaseScraper):
    """Scraper for the myUMBC Events calendar (https://my.umbc.edu/events)."""

    @staticmethod
    def _is_real_event_url(href: str) -> bool:
        """Return True only for links pointing to a specific numeric event ID."""
        parts = href.rstrip('/').split('/')
        last = parts[-1] if parts else ''
        if last.lower() in _SKIP_SEGMENTS:
            return False
        return bool(re.search(r'\d', last))

    @staticmethod
    def _is_valid_title(title: str) -> bool:
        stripped = title.strip().lower()
        if stripped in _JUNK_TITLES:
            return False
        if len(stripped) < 4:
            return False
        if re.match(r'^(mon|tue|wed|thu|fri|sat|sun),?\s', stripped):
            return False
        return True

    def scrape(self) -> List[Dict]:
        events = []
        try:
            soup = self.get_soup_authenticated(self.base_url, wait_selector="a[href*='/events/']")

            for a in soup.find_all('a', href=True):
                href = a['href']
                if '/events/' not in href:
                    continue
                if not self._is_real_event_url(href):
                    continue

                abs_link = urljoin("https://my.umbc.edu", href)

                if any(e['link'] == abs_link for e in events):
                    continue

                container = a.find_parent('div', class_=lambda x: x and ('event' in x.lower() or 'item' in x.lower()))
                if not container:
                    continue

                text_parts = container.get_text(separator='|', strip=True).split('|')

                title = ""
                date = ""
                description = ""

                heading = container.find(['h3', 'h4', 'strong'])
                if heading:
                    title = heading.get_text(strip=True)
                elif len(text_parts) > 2:
                    title = text_parts[2]

                if not self._is_valid_title(title):
                    continue

                if len(text_parts) > 0:
                    date = text_parts[0]
                    if len(text_parts) > 1 and ("AM" in text_parts[1] or "PM" in text_parts[1]):
                        date += " " + text_parts[1]

                raw_desc = " ".join(text_parts)
                description = re.sub(r'\s*(View More|Read More|See More)\s*', ' ', raw_desc, flags=re.IGNORECASE).strip()

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
