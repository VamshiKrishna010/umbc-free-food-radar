import os
import json
from datetime import datetime
from scrapers.myumbc_scraper import MyUMBCScraper
from utils.notifier import DiscordNotifier
from dotenv import load_dotenv

load_dotenv()

# Configuration
CALENDAR_URLS = [
    "https://my.umbc.edu/events/free-food", 
    "https://my.umbc.edu/events", # Main calendar to catch untagged free food
]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")
DATABASE_FILE = "seen_events.json"
EVENTS_DATA_FILE = "events_data.json"

def load_seen_events():
    if os.path.exists(DATABASE_FILE):
        with open(DATABASE_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_seen_events(seen_set):
    with open(DATABASE_FILE, 'w') as f:
        json.dump(list(seen_set), f)

def load_events_data():
    if os.path.exists(EVENTS_DATA_FILE):
        with open(EVENTS_DATA_FILE, 'r') as f:
            return json.load(f)
    return []

def save_events_data(events_list):
    # Sort events by date if possible before saving, or just save them
    with open(EVENTS_DATA_FILE, 'w') as f:
        json.dump(events_list, f, indent=4)

def main():
    print(f"[{datetime.now()}] Starting Scraper...")
    
    notifier = DiscordNotifier(DISCORD_WEBHOOK)
    seen_events = load_seen_events()
    saved_events_data = load_events_data()
    all_found_food = []

    # Iterate through target calendars
    for url in CALENDAR_URLS:
        scraper = MyUMBCScraper(url)
        all_events = scraper.scrape()
        # Since we are scraping the `/free-food` page, they ALL ostensibly have free food,
        # but the FoodDetector acts as a secondary verification step to fetch Keywords.
        food_events = scraper.filter_food_events(all_events)

        
        for event in food_events:
            event_id = event['link'] # Using link as unique ID
            
            # Update the event record in our saved data or append it
            # To avoid duplicates in events_data.json, we update if it exists
            existing_event = next((e for e in saved_events_data if e['link'] == event_id), None)
            if not existing_event:
                saved_events_data.append(event)
            else:
                # Update fields that might have changed
                existing_event.update(event)
                
            if event_id not in seen_events:
                print(f"New Food Event Found: {event['title']}")
                all_found_food.append(event)
                seen_events.add(event_id)
                # notify immediately
                notifier.notify(event)

    # Inject Retriever Essentials permanent locations into the database so they are always on the radar
    retriever_events = [
        {
            'title': 'The Essential Space (Free Grocery Store)',
            'date': 'Ongoing (Check RAC 235 Hours)',
            'description': 'A free grocery store located in the Retriever Activities Center, room 235. Pick up free groceries, toiletries, and baby items.',
            'link': 'https://retrieveressentials.umbc.edu',
            'food_keyword': 'free groceries',
            'source': 'Retriever Essentials'
        },
        {
            'title': 'Fresh Food Pop-Up',
            'date': 'Every Thursday 2:15 PM - 2:45 PM',
            'description': 'Located on the right side of the AOK Library. Get a variety of fresh food provided by So What Else.',
            'link': 'https://retrieveressentials.umbc.edu/#popup',
            'food_keyword': 'fresh food',
            'source': 'Retriever Essentials'
        }
    ]
    
    for re_event in retriever_events:
        existing_event = next((e for e in saved_events_data if e['link'] == re_event['link']), None)
        if not existing_event:
            saved_events_data.append(re_event)
            
    save_seen_events(seen_events)
    save_events_data(saved_events_data)
    print(f"Done. Found {len(all_found_food)} new events with free food. Total stored events: {len(saved_events_data)}")

if __name__ == "__main__":
    main()
