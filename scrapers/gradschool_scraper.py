"""Scraper for gradschool.umbc.edu and gsa.umbc.edu - Graduate School and GSA events."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class GradSchoolScraper(BaseScraper):
    """
    Scraper for UMBC Graduate School and Graduate Student Association (GSA) events.
    Tries multiple URL patterns since dedicated /events pages may not exist.
    """

    SOURCES = [
        {
            "urls": [
                "https://gradschool.umbc.edu/news-events/",
                "https://gradschool.umbc.edu/events/",
                "https://gradschool.umbc.edu/",
            ],
            "base": "https://gradschool.umbc.edu",
            "name": "Graduate School",
            "link_pattern": r"gradschool\.umbc\.edu/(?:events?|news)",
        },
        {
            "urls": [
                "https://gsa.umbc.edu/events/",
                "https://gsa.umbc.edu/",
            ],
            "base": "https://gsa.umbc.edu",
            "name": "Graduate Student Association",
            "link_pattern": r"gsa\.umbc\.edu/events?",
        },
    ]

    def __init__(self):
        super().__init__("https://gradschool.umbc.edu")

    def scrape(self) -> List[Dict]:
        all_events = []
        seen = set()

        for source in self.SOURCES:
            fetched = False
            for url in source["urls"]:
                try:
                    soup = self.get_soup(url)
                    events = self._parse_page(soup, source, url)
                    for ev in events:
                        if ev["link"] not in seen:
                            seen.add(ev["link"])
                            all_events.append(ev)
                    fetched = True
                    break  # stop trying URLs once one succeeds
                except Exception as e:
                    print(f"  {source['name']} ({url}): {e}")

            if not fetched:
                print(f"  Could not fetch any URL for {source['name']}")

        return all_events

    def _parse_page(self, soup, source: dict, page_url: str) -> List[Dict]:
        events = []
        seen_titles = set()
        seen_links = set()
        localist_re = re.compile(r"/events?/event/\d+")

        # Strategy 1: source-specific event links
        for a in soup.find_all("a", href=re.compile(source["link_pattern"])):
            href = a.get("href", "")
            link = href if href.startswith("http") else source["base"] + href
            if link in seen_links:
                continue
            title = a.get_text(strip=True)[:200]
            if not title or len(title) < 4 or title in seen_titles:
                continue
            if title.lower() in ("read more", "learn more", "more", "here", "events"):
                continue
            seen_titles.add(title)
            seen_links.add(link)

            container = a.find_parent(["article", "div", "li", "section"])
            title_el = container.find(["h2", "h3"]) if container else None
            title = title_el.get_text(strip=True) if title_el else title

            if localist_re.search(link):
                ev = self.scrape_localist_detail(link, title, source=source["name"])
                events.append(ev)
            else:
                desc_el = container.find("p") if container else None
                desc = desc_el.get_text(strip=True)[:400] if desc_el else ""
                date_text = self._extract_date(container) if container else ""
                events.append({
                    "title": title,
                    "date": date_text or "TBA",
                    "description": desc,
                    "link": link,
                    "source": source["name"],
                })

        # Strategy 2: Localist-style /events/event/ID links (fallback when Strategy 1 finds nothing)
        if not events:
            for a in soup.find_all("a", href=re.compile(r"/events?/event/\d+")):
                href = a.get("href", "")
                link = href if href.startswith("http") else source["base"] + href
                if link in seen_links:
                    continue
                seen_links.add(link)

                container = a.find_parent(["article", "div", "li"])
                title_el = container.find(["h2", "h3"]) if container else None
                title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)[:200]
                if not title or len(title) < 2:
                    continue

                ev = self.scrape_localist_detail(link, title, source=source["name"])
                events.append(ev)

        return events

    def _extract_date(self, container) -> str:
        if not container:
            return ""
        for node in container.find_all(string=True):
            t = str(node).strip()
            if re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}", t, re.I):
                return t[:100]
            if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", t):
                return t[:100]
        return ""
