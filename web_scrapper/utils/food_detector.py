import re

class FoodDetector:
    """Detects free food keywords in event titles and descriptions."""
    
    FOOD_KEYWORDS = [
        r'free\s+food', r'pizza', r'lunch', r'dinner', r'breakfast', 
        r'refreshments', r'snacks', r'catering', r'meal', r'buffet',
        r'provided', r'cookie', r'brownie', r'donut', r'bagel',
        r'taco', r'burger', r'pasta', r'soda', r'beverages'
    ]
    
    UNLIKELY_KEYWORDS = [
        r'bring\s+your\s+own', r'available\s+for\s+purchase', r'buy', 
        r'ticket\s+required', r'sold\s+out'
    ]

    def __init__(self):
        self.food_pattern = re.compile('|'.join(self.FOOD_KEYWORDS), re.IGNORECASE)
        self.unlikely_pattern = re.compile('|'.join(self.UNLIKELY_KEYWORDS), re.IGNORECASE)

    def contains_food(self, text: str) -> bool:
        if not text:
            return False
        
        # Check for food keywords
        has_food = self.food_pattern.search(text) is not None
        
        # Check for counter-indicators (like "available for purchase")
        has_exclusion = self.unlikely_pattern.search(text) is not None
        
        return has_food and not has_exclusion

    def get_matched_item(self, text: str) -> str:
        match = self.food_pattern.search(text)
        return match.group(0) if match else ""
