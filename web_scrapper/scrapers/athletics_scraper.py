"""Scraper for umbcretrievers.com - UMBC Retrievers athletics schedules."""
from scrapers.base_scraper import BaseScraper
from typing import List, Dict
from urllib.parse import urljoin
import json
import re


class AthleticsScraper(BaseScraper):
    """Scraper for UMBC athletics game schedules (basketball, soccer, lacrosse, etc.)."""

    BASE_URL = "https://umbcretrievers.com"
    COMPOSITE_URL = f"{BASE_URL}/calendar"

    # (sport_code, display_name) pairs matching Sidearm URL slugs
    SPORTS = [
        ("mbball", "Men's Basketball"),
        ("wbball", "Women's Basketball"),
        ("msoc", "Men's Soccer"),
        ("wsoc", "Women's Soccer"),
        ("wvball", "Volleyball"),
        ("mlax", "Men's Lacrosse"),
        ("wlax", "Women's Lacrosse"),
        ("baseball", "Baseball"),
        ("softball", "Softball"),
        ("mswim", "Men's Swimming & Diving"),
        ("wswim", "Women's Swimming & Diving"),
        ("mtrack", "Men's Track & Field"),
        ("wtrack", "Women's Track & Field"),
        ("mxc", "Men's Cross Country"),
        ("wxc", "Women's Cross Country"),
    ]

    def __init__(self):
        super().__init__(self.BASE_URL)

    def scrape(self) -> List[Dict]:
        all_events = []
        seen = set()

        # Sidearm's composite calendar usually contains all upcoming athletics events.
        try:
            composite_soup = self.get_soup_js(
                self.COMPOSITE_URL,
                wait_selector="main, .sidearm-schedule-game, a[href*='calendar']",
            )
            self._extend_unique(all_events, self._parse_composite_calendar(composite_soup), seen)
        except Exception as e:
            print(f"  Athletics (composite calendar): {e}")

        # Fallback: if composite parsing fails/returns nothing, parse per-sport schedule pages.
        if not all_events:
            for sport_code, sport_name in self.SPORTS:
                url = f"{self.BASE_URL}/sports/{sport_code}/schedule"
                try:
                    soup = self.get_soup_js(url, wait_selector="main, body")
                    events = self._parse_schedule(soup, sport_name, sport_code)
                    self._extend_unique(all_events, events, seen)
                except Exception as e:
                    print(f"  Athletics ({sport_name}): {e}")

        return all_events

    def _extend_unique(self, all_events: List[Dict], new_events: List[Dict], seen: set) -> None:
        for ev in new_events:
            key = f"{ev.get('link', '')}|{ev.get('title', '')}|{ev.get('date', '')}"
            if key not in seen:
                seen.add(key)
                all_events.append(ev)

    def _parse_composite_calendar(self, soup) -> List[Dict]:
        events = self._parse_json_ld_events(soup, self.COMPOSITE_URL)
        if events:
            return events

        return self._parse_event_containers(
            soup,
            default_title="Athletics Event",
            fallback_link=self.COMPOSITE_URL,
        )

    def _parse_schedule(self, soup, sport_name: str, sport_code: str) -> List[Dict]:
        schedule_url = f"{self.BASE_URL}/sports/{sport_code}/schedule"
        events = self._parse_json_ld_events(soup, schedule_url, sport_name=sport_name)
        if events:
            return events

        return self._parse_event_containers(
            soup,
            default_title=sport_name,
            fallback_link=schedule_url,
            sport_name=sport_name,
        )

    def _parse_event_containers(
        self,
        soup,
        default_title: str,
        fallback_link: str,
        sport_name: str = "",
    ) -> List[Dict]:
        events = []
        selectors = [
            ".sidearm-schedule-game",
            "li[class*='schedule-game']",
            "tr[class*='schedule-game']",
            "div[class*='schedule-game']",
            "article[class*='schedule-game']",
            "li[class*='event']",
            "article[class*='event']",
        ]

        containers = []
        for selector in selectors:
            matches = soup.select(selector)
            if matches:
                containers = matches
                break

        for item in containers:
            text = item.get_text(" ", strip=True)
            if not text or len(text) < 12:
                continue

            date_text = self._extract_date(text)
            if not date_text:
                continue

            opponent_match = re.search(r"(?:vs\.?|at)\s+[A-Z][A-Za-z0-9&'().\- ]+", text)
            opponent = opponent_match.group(0).strip() if opponent_match else ""
            title = f"{sport_name}: {opponent}" if sport_name and opponent else (opponent or default_title)

            location = "Home" if re.search(r"\bvs\.?\b", text, re.I) else "Away"
            description = f"UMBC {sport_name or 'Athletics'} — {location}. {text[:220]}"

            link = fallback_link
            a = item.find("a", href=True)
            if a:
                link = urljoin(self.BASE_URL, a.get("href", ""))

            events.append({
                "title": title[:200],
                "date": date_text,
                "description": description,
                "link": link,
                "source": "UMBC Athletics",
            })

        return events

    def _parse_json_ld_events(self, soup, fallback_link: str, sport_name: str = "") -> List[Dict]:
        events = []
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = (script.string or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            stack = data if isinstance(data, list) else [data]
            while stack:
                item = stack.pop()
                if isinstance(item, list):
                    stack.extend(item)
                    continue
                if not isinstance(item, dict):
                    continue

                for key in ["@graph", "itemListElement", "events", "subEvents"]:
                    if key in item and isinstance(item[key], (list, dict)):
                        stack.append(item[key])

                event_type = item.get("@type", "")
                event_types = event_type if isinstance(event_type, list) else [event_type]
                if not any(t in ("Event", "SportsEvent") for t in event_types):
                    continue

                title = str(item.get("name", "")).strip()
                if not title:
                    continue

                start_date = str(item.get("startDate", "")).strip()
                date_text = start_date[:100] if start_date else "TBA"
                link = item.get("url") or fallback_link
                description = str(item.get("description", "")).strip()[:350]
                if sport_name and sport_name.lower() not in title.lower():
                    title = f"{sport_name}: {title}"

                events.append({
                    "title": title[:200],
                    "date": date_text,
                    "description": description,
                    "link": urljoin(self.BASE_URL, link),
                    "source": "UMBC Athletics",
                })

        return events

    def _extract_date(self, text: str) -> str:
        patterns = [
            r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\w*[,]?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}(?:,\s*\d{4})?",
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\.?\s+\d{1,2}(?:,\s*\d{4})?",
            r"\d{1,2}/\d{1,2}/\d{2,4}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                return match.group(0).strip()
        return ""
