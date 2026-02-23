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

# Supabase Setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

try:
    from supabase import create_client, Client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("Successfully connected to Supabase")
except Exception as e:
    print(f"Failed to connect to Supabase: {e}")
    supabase = None

def load_seen_events():
    if supabase is not None:
        try:
            # We don't have a dedicated seen_events table in the new schema,
            # we can just pull all existing event IDs from the main table.
            response = supabase.table("events").select("id").execute()
            return set(row["id"] for row in response.data)
        except Exception as e:
            print(f"Error loading seen events from DB: {e}")
    return set()

def load_events_data():
    if supabase is not None:
        try:
            response = supabase.table("events").select("*").execute()
            return response.data
        except Exception as e:
            print(f"Error loading events data from DB: {e}")
    return []

def save_events_data(events_list):
    if supabase is not None:
        try:
            # Prepare data for upsert
            for event in events_list:
                supabase.table("events").upsert({
                    "id": event['link'], # Using URL as the primary key ID
                    "title": event.get('title', ''),
                    "date": event.get('date', ''),
                    "description": event.get('description', ''),
                    "link": event.get('link', ''),
                    "food_keyword": event.get('food_keyword', ''),
                    "source": event.get('source', '')
                }).execute()
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
        if not existing_event:
            saved_events_data.append(re_event)
            
    save_events_data(saved_events_data)
    print(f"Done. Found {len(all_found_food)} new events with free food. Total stored events: {len(saved_events_data)}")

if __name__ == "__main__":
    main()
