"""Scraper for careers.umbc.edu - Career fairs, recruitment events, and workshops."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
import re


class CareersScraper(BaseScraper):
    """Scraper for UMBC Career Center events: career fairs, workshops, and hiring events."""

    BASE_URL = "https://careers.umbc.edu"
    URLS = [
        ("https://careers.umbc.edu/employers/career-fairs-events/", "Career Center"),
        ("https://careers.umbc.edu/tools/workshops/", "Career Center Workshops"),
    ]

    def __init__(self):
        super().__init__(self.URLS[0][0])

    def scrape(self) -> List[Dict]:
        all_events = []
        seen = set()

        for url, source_label in self.URLS:
            try:
                soup = self.get_soup(url)
                events = self._parse_page(soup, source_label, url)
                for ev in events:
                    if ev["link"] not in seen:
                        seen.add(ev["link"])
                        all_events.append(ev)
            except Exception as e:
                print(f"Error scraping Career Center ({url}): {e}")

        return all_events

    def _parse_page(self, soup, source_label: str, page_url: str) -> List[Dict]:
        events = []
        seen_titles = set()
        event_link_pattern = re.compile(
            r"/events?/event/\d+|/event/|/events/|/workshops?/|career-fair|handshake|joinhandshake\.com",
            re.I,
        )

        # Strategy 1: Localist-style event links
        for a in soup.find_all("a", href=event_link_pattern):
            href = a.get("href", "")
            link = href if href.startswith("http") else self.BASE_URL + href
            container = a.find_parent(["article", "div", "li"])
            title_el = container.find(["h2", "h3", "h4"]) if container else None
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)[:200]
            if not title or len(title) < 3 or title in seen_titles:
                continue
            seen_titles.add(title)
            desc_el = container.find("p") if container else None
            desc = desc_el.get_text(strip=True)[:400] if desc_el else ""
            date_text = self._extract_date(container) if container else ""
            body_text = f"{title} {desc}".strip().lower()
            if any(skip in body_text for skip in ["menu", "search", "breadcrumb", "skip to content"]):
                continue
            events.append({
                "title": title[:200],
                "date": date_text or "TBA",
                "description": desc,
                "link": link,
                "source": source_label,
            })

        # Strategy 2: Bold/strong titles with surrounding text (simple HTML pages)
        if not events:
            content_root = (
                soup.select_one("main")
                or soup.select_one("article")
                or soup.select_one(".entry-content")
                or soup.select_one(".post-content")
                or soup
            )
            for strong in content_root.find_all(["strong", "b", "h3", "h4"]):
                title = strong.get_text(strip=True)
                if not title or len(title) < 5 or title in seen_titles:
                    continue
                # Skip navigation/boilerplate items
                if any(skip in title.lower() for skip in [
                    "menu", "search", "home", "contact", "login",
                    "apply now", "quick links", "footer", "navigation"
                ]):
                    continue
                seen_titles.add(title)
                parent = strong.find_parent(["p", "li", "div", "section"])
                desc = parent.get_text(strip=True)[:400] if parent else ""
                date_text = self._extract_date(parent) if parent else ""
                has_event_terms = bool(re.search(r"(event|workshop|career|fair|recruit|session)", f"{title} {desc}", re.I))
                if len(desc) < 30 and not date_text:
                    continue
                if not date_text and not has_event_terms:
                    continue
                link_el = (parent or strong).find("a") if parent else strong.find("a")
                link = ""
                if link_el:
                    href = link_el.get("href", "")
                    link = href if href.startswith("http") else self.BASE_URL + href
                link = link or page_url
                events.append({
                    "title": title[:200],
                    "date": date_text or "TBA",
                    "description": desc,
                    "link": link,
                    "source": source_label,
                })

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
