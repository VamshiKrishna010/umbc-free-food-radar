"""Scraper for myUMBC group event pages (e.g. /groups/isa/events)."""
import re
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
from urllib.parse import urljoin


class MyUMBCGroupScraper(BaseScraper):
    """Scrapes events from a myUMBC group's events page."""

    MYUMBC_BASE = "https://my3.my.umbc.edu"

    def __init__(self, group_url: str, source_name: str = "myUMBC"):
        events_url = group_url.rstrip("/")
        if not events_url.endswith("/events"):
            events_url += "/events"
        super().__init__(events_url)
        self.source_name = source_name

    def scrape(self) -> List[Dict]:
        events = []
        try:
            soup = self.get_soup(self.base_url)
        except Exception as e:
            print(f"Error scraping myUMBC group ({self.base_url}): {e}")
            return events

        seen = set()
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if not re.search(r"/events/\d+$", href):
                continue
            # Skip date-navigation URLs like /events/2026/3/2
            if re.search(r"/events/\d{4}/", href):
                continue

            abs_link = urljoin(self.MYUMBC_BASE, href)
            if abs_link in seen:
                continue
            seen.add(abs_link)

            container = a.find_parent("div", class_=lambda x: x and ("event" in str(x).lower() or "item" in str(x).lower()))
            if not container:
                container = a.find_parent("div")
            if not container:
                continue

            text_parts = container.get_text(separator="|", strip=True).split("|")

            title = ""
            heading = container.find(["h3", "h4", "strong"])
            if heading:
                title = heading.get_text(strip=True)
            else:
                title = a.get_text(strip=True)

            if not title or len(title) < 3:
                continue

            date = ""
            if text_parts:
                date = text_parts[0].strip()
                if len(text_parts) > 1 and re.search(r"(AM|PM)", text_parts[1], re.I):
                    date += " " + text_parts[1].strip()

            desc_parts = [p.strip() for p in text_parts if p.strip() != title and p.strip() != date]
            description = " ".join(desc_parts)[:500]

            events.append({
                "title": title[:200],
                "date": date or "TBA",
                "description": description,
                "link": abs_link,
                "source": self.source_name,
            })

        return events
