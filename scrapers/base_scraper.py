from abc import ABC, abstractmethod
from typing import List, Dict
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
