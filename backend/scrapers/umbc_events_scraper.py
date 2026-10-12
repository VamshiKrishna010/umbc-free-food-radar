"""Scraper for UMBC main featured events (umbc.edu/events).

Uses the official WordPress The Events Calendar REST API (https://umbc.edu/wp-json/tribe/events/v1/events)
with an automated fallback to the HTML list view (https://umbc.edu/events/list/).
"""
import html
import re
from datetime import datetime
from typing import Dict, List
import requests
from bs4 import BeautifulSoup
from scrapers.base_scraper import BaseScraper


class UMBCEventsScraper(BaseScraper):
    """Scraper for UMBC featured events (umbc.edu/events, events.umbc.edu)."""

    API_URL = "https://umbc.edu/wp-json/tribe/events/v1/events?per_page=50"
    FALLBACK_LIST_URL = "https://umbc.edu/events/list/"

    def __init__(self):
        super().__init__("https://umbc.edu/events/")

    def scrape(self) -> List[Dict]:
        """Scrape campus events from UMBC Events API with HTML fallback."""
        events = self._scrape_api()
        if not events:
            print("  [UMBC Events] REST API returned 0 events; attempting HTML list view fallback...")
            events = self._scrape_fallback_html()
        return events

    def _scrape_api(self) -> List[Dict]:
        events = []
        seen_links = set()
        next_url = self.API_URL
        max_pages = 4  # Scrape up to 200 events

        for _ in range(max_pages):
            if not next_url:
                break
            try:
                resp = requests.get(next_url, headers=self.headers, timeout=12)
                if resp.status_code != 200:
                    break
                data = resp.json()
            except Exception as e:
                print(f"  [UMBC Events] API request failed ({next_url}): {e}")
                break

            items = data.get("events", [])
            if not items:
                break

            for item in items:
                link = (item.get("url") or "").strip()
                if not link or link in seen_links:
                    continue
                seen_links.add(link)

                # Clean Title
                raw_title = item.get("title") or ""
                clean_title = html.unescape(raw_title).replace("\ufffd", "—").strip()
                if not clean_title or len(clean_title) < 3:
                    continue

                # Format Date
                start_str = item.get("start_date") or ""
                date_str = start_str
                if start_str:
                    try:
                        dt = datetime.strptime(start_str, "%Y-%m-%d %H:%M:%S")
                        date_str = dt.strftime("%b %d, %Y %I:%M %p").replace(" 0", " ")
                    except Exception:
                        date_str = start_str

                # Extract Venue / Location
                venue_name = ""
                venue_data = item.get("venue")
                if isinstance(venue_data, dict):
                    venue_name = venue_data.get("venue") or ""

                # Extract Clean Description
                raw_desc = item.get("excerpt") or item.get("description") or ""
                desc_text = BeautifulSoup(raw_desc, "html.parser").get_text(separator=" ", strip=True)
                desc_text = html.unescape(desc_text).replace("\ufffd", "—").strip()

                if venue_name and venue_name not in desc_text:
                    full_desc = f"{venue_name} — {desc_text}" if desc_text else venue_name
                else:
                    full_desc = desc_text

                event = {
                    "title": clean_title[:200],
                    "date": date_str or "TBA",
                    "description": full_desc[:500] if full_desc else "",
                    "link": link,
                    "source": "UMBC Events",
                }
                events.append(event)

            next_url = data.get("next_rest_url")

        return events

    def _scrape_fallback_html(self) -> List[Dict]:
        events = []
        seen_links = set()
        try:
            soup = self.get_soup(self.FALLBACK_LIST_URL)
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/event/" not in href:
                    continue
                link = href if href.startswith("http") else "https://umbc.edu" + href
                if link in seen_links:
                    continue
                seen_links.add(link)

                container = a.find_parent(["article", "div"], class_=lambda x: x and ("event" in str(x).lower() or "tribe" in str(x).lower()))
                if not container:
                    continue

                title_elem = container.select_one("h2, h3, .tribe-events-calendar-list__event-title")
                title = title_elem.get_text(strip=True) if title_elem else a.get_text(strip=True)
                title = html.unescape(title).replace("\ufffd", "—").strip()
                if not title or len(title) < 4:
                    continue

                date_elem = container.select_one("time, .tribe-events-calendar-list__event-datetime, .tribe-event-date-start")
                date_str = date_elem.get_text(strip=True) if date_elem else "TBA"

                desc_elem = container.select_one("p, .tribe-events-calendar-list__event-description")
                desc = desc_elem.get_text(strip=True) if desc_elem else ""

                events.append({
                    "title": title[:200],
                    "date": date_str or "TBA",
                    "description": desc[:500] if desc else "",
                    "link": link,
                    "source": "UMBC Events",
                })
        except Exception as e:
            print(f"  [UMBC Events] Fallback HTML scrape failed: {e}")

        return events
