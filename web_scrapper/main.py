import os
import json
from datetime import datetime
from scrapers.myumbc_scraper import MyUMBCScraper
from utils.notifier import DiscordNotifier
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

load_dotenv()

# Configuration
CALENDAR_URLS = [
    "https://my.umbc.edu/events/free-food", 
    "https://my.umbc.edu/events", # Main calendar to catch untagged free food
]
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

# MongoDB Setup
MONGO_URI = os.getenv("MONGO_URI")
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, tlsCAFile=certifi.where())
    db = client.umbc_food_radar
    events_collection = db.events
    seen_events_collection = db.seen_events
    # Test connection
    client.server_info()
    print("Successfully connected to MongoDB")
except Exception as e:
    print(f"Failed to connect to MongoDB: {e}")
    # Fallback to local lists if connection fails
    db = None

def load_seen_events():
    if db is not None:
        try:
            return set(doc['_id'] for doc in seen_events_collection.find({}, {'_id': 1}))
        except Exception as e:
            print(f"Error loading seen events from DB: {e}")
    return set()

def save_seen_events(seen_set):
    if db is not None:
        try:
            # Upsert each seen event ID
            for event_id in seen_set:
                seen_events_collection.update_one(
                    {'_id': event_id}, 
                    {'$set': {'_id': event_id}}, 
                    upsert=True
                )
        except Exception as e:
            print(f"Error saving seen events to DB: {e}")

def load_events_data():
    if db is not None:
        try:
            return list(events_collection.find({}, {'_id': 0}))
        except Exception as e:
            print(f"Error loading events data from DB: {e}")
    return []

def save_events_data(events_list):
    if db is not None:
        try:
            for event in events_list:
                # Use the 'link' as a unique identifier for upserts
                events_collection.update_one(
                    {'link': event['link']},
                    {'$set': event},
                    upsert=True
                )
        except Exception as e:
            print(f"Error saving events data to DB: {e}")

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
