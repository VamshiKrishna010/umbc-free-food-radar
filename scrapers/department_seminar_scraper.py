"""Generic scraper for UMBC department seminar pages: CS/EE, GES, and Research Division."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class DepartmentSeminarScraper(BaseScraper):
    """
    Generic scraper for WordPress-style UMBC department seminar / talk pages.
    Handles: CS/EE colloquia, Geography & Environmental Sciences, Research Division.
    """

    SOURCES = [
        {
            "url": "https://news.cs.umbc.edu/csee-colloquia-and-talks/",
            "base": "https://news.cs.umbc.edu",
            "name": "CS/EE Department",
            "link_pattern": r"news\.cs\.umbc\.edu/\d{4}/\d{2}/\d{2}/|/\d{4}/\d{2}/\d{2}/",
        },
        {
            "url": "https://ges.umbc.edu/home/seminars/",
            "base": "https://ges.umbc.edu",
            "name": "Geography & Environmental Sciences",
            "link_pattern": r"ges\.umbc\.edu/events?/event/\d+|ges\.umbc\.edu/home/seminars",
        },
        {
            "url": "https://research.umbc.edu/seminars-and-workshops/",
            "base": "https://research.umbc.edu",
            "name": "Research Division",
            "link_pattern": r"research\.umbc\.edu/events?/event/\d+|/seminars",
        },
    ]

    def __init__(self):
        super().__init__("https://umbc.edu")

    def scrape(self) -> List[Dict]:
        all_events = []
        seen = set()

        for source in self.SOURCES:
            try:
                soup = self.get_soup(source["url"])
                events = self._parse_page(soup, source)
                for ev in events:
                    if ev["link"] not in seen:
                        seen.add(ev["link"])
                        all_events.append(ev)
            except Exception as e:
                print(f"Error scraping {source['name']}: {e}")

        return all_events

    def _parse_page(self, soup, source: dict) -> List[Dict]:
        events = []
        seen_titles = set()
        seen_links = set()
        localist_re = re.compile(r"/events?/event/\d+")

        # Strategy 1: match source-specific link patterns
        for a in soup.find_all("a", href=re.compile(source["link_pattern"])):
            href = a.get("href", "")
            link = href if href.startswith("http") else source["base"] + href
            if link in seen_links:
                continue
            title = a.get_text(strip=True)[:200]
            if not title or len(title) < 5:
                continue
            if title.lower() in ("read more", "view details", "more", "here", "click here"):
                continue
            if title in seen_titles:
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

        # Strategy 2: headings with nearby date context (when no pattern links found)
        if not events:
            for heading in soup.find_all(["h2", "h3", "h4"]):
                title = heading.get_text(strip=True)[:200]
                if not title or len(title) < 5 or title in seen_titles:
                    continue
                if any(skip in title.lower() for skip in ["menu", "search", "navigation", "footer", "sidebar"]):
                    continue
                seen_titles.add(title)

                parent = heading.find_parent(["article", "div", "section"])
                date_text = self._extract_date(parent) if parent else ""
                a_el = heading.find("a") or (parent.find("a") if parent else None)
                link = source["url"]
                if a_el:
                    href = a_el.get("href", "")
                    link = href if href.startswith("http") else source["base"] + href

                if localist_re.search(link) and link not in seen_links:
                    seen_links.add(link)
                    ev = self.scrape_localist_detail(link, title, source=source["name"])
                    events.append(ev)
                else:
                    events.append({
                        "title": title,
                        "date": date_text or "TBA",
                        "description": "",
                        "link": link,
                        "source": source["name"],
                    })

        return events

    def _extract_date(self, container) -> str:
        if not container:
            return ""
        for node in container.find_all(string=True):
            t = str(node).strip()
            if re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}", t, re.I):
                return t[:100]
            if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", t):
                return t[:100]
        return ""
