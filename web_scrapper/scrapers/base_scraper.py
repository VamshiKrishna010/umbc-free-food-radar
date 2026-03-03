import os
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
from utils.food_detector import FoodDetector

class BaseScraper(ABC):
    """Abstract base class for all campus event scrapers."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.detector = FoodDetector()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_soup(self, url: str) -> BeautifulSoup:
        """Fetches a page and returns a BeautifulSoup object."""
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')

    def get_soup_js(self, url: str, wait_selector: str = "body", timeout: int = 15000) -> BeautifulSoup:
        """Fetches a JS-rendered page using Playwright and returns BeautifulSoup."""
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
        except ModuleNotFoundError:
            # Keep scrapers functional in environments without Playwright.
            return self.get_soup(url)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.headers["User-Agent"])
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                    try:
                        page.wait_for_selector(wait_selector, timeout=timeout)
                    except PlaywrightTimeoutError:
                        # Some pages never expose stable selectors; keep best-effort HTML.
                        try:
                            page.wait_for_load_state("networkidle", timeout=timeout)
                        except PlaywrightTimeoutError:
                            pass
                    html = page.content()
                finally:
                    browser.close()
            return BeautifulSoup(html, "html.parser")
        except Exception:
            return self.get_soup(url)

    def get_soup_authenticated(
        self,
        url: str,
        wait_selector: str = "body",
        timeout: int = 30000,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> BeautifulSoup:
        """Fetches a page after logging in with myUMBC/Shibboleth credentials from env."""
        user = username or os.getenv("MYUMBC_USER", "").strip()
        pw = password or os.getenv("MYUMBC_PASS", "").strip()
        if not user or not pw:
            return self.get_soup_js(url, wait_selector, timeout)

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright
        except ModuleNotFoundError:
            return self.get_soup(url)

        headed = os.getenv("MYUMBC_HEADED", "").lower() in ("1", "true", "yes")
        session_file = os.getenv("MYUMBC_SESSION_FILE", ".auth/myumbc_storage_state.json").strip()
        session_path = Path(session_file or ".auth/myumbc_storage_state.json")
        session_path.parent.mkdir(parents=True, exist_ok=True)
        auth_timeout = max(timeout, 120000)
        user_selector = 'input[name="j_username"], input#username, input[type="text"][name*="user"]'
        pass_selector = 'input[name="j_password"], input#password, input[type="password"]'
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=not headed)
                context_kwargs = {"user_agent": self.headers["User-Agent"]}
                if session_path.exists():
                    context_kwargs["storage_state"] = str(session_path)
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                    try:
                        page.wait_for_load_state("networkidle", timeout=timeout)
                    except PlaywrightTimeoutError:
                        pass

                    # Shibboleth login form
                    user_input = page.query_selector(user_selector)
                    pw_input = page.query_selector(pass_selector)
                    if user_input and pw_input:
                        user_input.fill(user)
                        pw_input.fill(pw)
                        page.keyboard.press("Enter")
                        # Duo/MFA handoff can take longer than normal page loads.
                        try:
                            page.wait_for_load_state("networkidle", timeout=auth_timeout)
                        except PlaywrightTimeoutError:
                            pass

                    page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                    try:
                        page.wait_for_selector(wait_selector, timeout=min(timeout, 10000))
                    except PlaywrightTimeoutError:
                        pass
                    # Persist cookies/session so next run reuses authenticated state.
                    context.storage_state(path=str(session_path))
                    html = page.content()
                finally:
                    context.close()
                    browser.close()
            return BeautifulSoup(html, "html.parser")
        except Exception as e:
            print(f"  [AUTH] Login failed, falling back to unauthenticated: {e}")
            return self.get_soup_js(url, wait_selector, timeout)

    def scrape_localist_detail(self, link: str, fallback_title: str = "", source: str = "") -> Dict:
        """Fetch a UMBC Localist event detail page and extract date/time/location/description.

        All UMBC Localist sites (SEB, Campus Life, Student Affairs, Math/Stat, Biology, etc.)
        share the same detail-page markup: <p class="event-details-header"> label followed by <p> value.
        """
        result = {"title": fallback_title, "date": "TBA", "description": "", "link": link, "source": source}
        try:
            soup = self.get_soup(link)
        except Exception:
            return result

        heading = soup.find("h1", class_="event-title") or soup.find("h1")
        if heading:
            result["title"] = heading.get_text(strip=True) or fallback_title

        date_text = ""
        location = ""
        description = ""

        for hdr in soup.find_all("p", class_="event-details-header"):
            label = hdr.get_text(strip=True).lower()
            value_p = hdr.find_next_sibling("p")
            if not value_p:
                continue
            value = value_p.get_text(separator=" ", strip=True)
            if "date" in label or "time" in label:
                date_text = value
            elif "location" in label:
                location = value
            elif "description" in label:
                description = value[:500]

        if not description:
            info = soup.find("div", class_="event-info")
            if info:
                description = info.get_text(separator=" ", strip=True)[:500]

        if location and description:
            description = f"{location} — {description}"
        elif location:
            description = location

        result["date"] = date_text or "TBA"
        result["description"] = description
        return result

    @abstractmethod
    def scrape(self) -> List[Dict]:
        """Scrapes events from the source and returns a list of event objects."""
        return []

    def filter_food_events(self, events: List[Dict]) -> List[Dict]:
        """Filters a list of events down to those likely to have free food."""
        food_events = []
        for event in events:
            # Check title and description
            all_text = f"{event.get('title', '')} {event.get('description', '')}"
            if self.detector.contains_food(all_text):
                event['food_keyword'] = self.detector.get_matched_item(all_text)
                food_events.append(event)
        return food_events
