from utils.food_detector import FoodDetector
from scrapers.local_scraper import LocalistScraper

def test_food_detector():
    detector = FoodDetector()
    texts = [
        "Free pizza at the union!",
        "Workshop on AI (Refreshments provided)",
        "Lunch and Learn: New Research",
        "Bring your own lunch to the meeting",
        "Tickets available for purchase at $10"
    ]
    
    print("Testing Food Detector:")
    for t in texts:
        result = detector.contains_food(t)
        match = detector.get_matched_item(t)
        print(f"[{'YES' if result else ' NO'}] '{t}' (Matched: {match})")

def test_imports():
    try:
        import requests
        from bs4 import BeautifulSoup
        import playwright
        print("\nImports check: SUCCESS")
    except ImportError as e:
        print(f"\nImports check: FAILED - {e}")

if __name__ == "__main__":
    test_imports()
    test_food_detector()
