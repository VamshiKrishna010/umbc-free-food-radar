import os
from datetime import datetime
from scrapers.myumbc_scraper import MyUMBCScraper
from scrapers.registrar_scraper import RegistrarScraper
from scrapers.umbc_events_scraper import UMBCEventsScraper
from scrapers.campuslife_scraper import CampusLifeScraper
from scrapers.seb_scraper import SEBScraper
from scrapers.tickets_scraper import TicketsScraper
from scrapers.sbs_scraper import SBSScraper
from utils.notifier import DiscordNotifier
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
discord_notifier = DiscordNotifier(DISCORD_WEBHOOK_URL)

# URLs for event scrapers
FOOD_EVENT_URLS = [
    "https://my.umbc.edu/events/free-food",
    "https://my.umbc.edu/events",
]

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

# Category constants for filtering in DB and frontend
CATEGORY_IMPORTANT_DATE = "important_date"
CATEGORY_FOOD_EVENT = "food_event"
CATEGORY_CAMPUS_EVENT = "campus_event"


def load_seen_ids():
    if supabase is None:
        return set()
    try:
        response = supabase.table("events").select("id").execute()
        return set(row["id"] for row in response.data)
    except Exception as e:
        print(f"Error loading seen IDs: {e}")
    return set()


def load_existing_events():
    if supabase is None:
        return []
    try:
        response = supabase.table("events").select("*").execute()
        return response.data
    except Exception as e:
        print(f"Error loading events: {e}")
    return []


def save_events(events_list):
    if supabase is None:
        return
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        for event in events_list:
            row = {
                "id": event.get("link", event.get("id", "")),
                "title": event.get("title", ""),
                "date": event.get("date", ""),
                "description": event.get("description", ""),
                "link": event.get("link", ""),
                "food_keyword": event.get("food_keyword", ""),
                "source": event.get("source", ""),
                "category": event.get("category", CATEGORY_CAMPUS_EVENT),
                "updated_at": now_iso,
            }
            supabase.table("events").upsert(row).execute()
    except Exception as e:
        print(f"Error saving events: {e}")


def main():
    print(f"[{datetime.now()}] Starting UMBC Scraper...")

    seen_ids = load_seen_ids()
    all_events = []

    # 1. Important dates (Registrar + SBS billing)
    print("Scraping important dates (Registrar, SBS)...")
    try:
        registrar = RegistrarScraper()
        important_dates = registrar.scrape()
        for date_item in important_dates:
            date_item["category"] = CATEGORY_IMPORTANT_DATE
            date_item["id"] = date_item.get("link", "") + "#" + date_item.get("title", "")[:50]
            all_events.append(date_item)
    except Exception as e:
        print(f"  [ERROR] Registrar scraper failed: {e}")
    try:
        sbs = SBSScraper()
        for date_item in sbs.scrape():
            date_item["category"] = CATEGORY_IMPORTANT_DATE
            date_item["id"] = date_item.get("link", "") + "#" + date_item.get("date", "") + date_item.get("title", "")[:30]
            all_events.append(date_item)
    except Exception as e:
        print(f"  [ERROR] SBS scraper failed: {e}")

    # 2. Food events from myUMBC and Retriever Essentials
    print("Scraping food events...")
    food_links = set()
    for url in FOOD_EVENT_URLS:
        try:
            scraper = MyUMBCScraper(url)
            all_from_page = scraper.scrape()
            food_events = scraper.filter_food_events(all_from_page)
        except Exception as e:
            print(f"  [ERROR] myUMBC scraper ({url}) failed: {e}")
            continue
        for ev in food_events:
            ev["category"] = CATEGORY_FOOD_EVENT
            ev["id"] = ev.get("link", "")
            if ev["id"] not in food_links:
                food_links.add(ev["id"])
                all_events.append(ev)
                if ev["id"] not in seen_ids:
                    discord_notifier.notify(ev)

    # Retriever Essentials (permanent)
    retriever_events = [
        {
            "id": "https://retrieveressentials.umbc.edu",
            "title": "The Essential Space (Free Grocery Store)",
            "date": "Ongoing (Check RAC 235 Hours)",
            "description": "A free grocery store located in the Retriever Activities Center, room 235.",
            "link": "https://retrieveressentials.umbc.edu",
            "food_keyword": "free groceries",
            "source": "Retriever Essentials",
            "category": CATEGORY_FOOD_EVENT,
        },
        {
            "id": "https://retrieveressentials.umbc.edu/#popup",
            "title": "Fresh Food Pop-Up",
            "date": "Every Thursday 2:15 PM - 2:45 PM",
            "description": "Located on the right side of the AOK Library.",
            "link": "https://retrieveressentials.umbc.edu/#popup",
            "food_keyword": "fresh food",
            "source": "Retriever Essentials",
            "category": CATEGORY_FOOD_EVENT,
        },
    ]
    all_events.extend(retriever_events)

    # 3. SEB events (Student Events Board) - check for food
    campus_seen = set()
    print("Scraping SEB events...")
    try:
        seb_scraper = SEBScraper()
        seb_events = seb_scraper.scrape()
        seb_food = seb_scraper.filter_food_events(seb_events)
    except Exception as e:
        print(f"  [ERROR] SEB scraper failed: {e}")
        seb_events = []
        seb_food = []
    for ev in seb_events:
        ev["id"] = ev.get("link", "")
        if ev in seb_food:
            ev["category"] = CATEGORY_FOOD_EVENT
            ev["food_keyword"] = ev.get("food_keyword", "free food")
            if ev["id"] not in food_links:
                food_links.add(ev["id"])
                all_events.append(ev)
                if ev["id"] not in seen_ids:
                    discord_notifier.notify(ev)
        else:
            ev["category"] = CATEGORY_CAMPUS_EVENT
            if ev["id"] not in campus_seen:
                campus_seen.add(ev["id"])
                all_events.append(ev)
    campus_seen.update(e.get("link") for e in all_events if e.get("category") == CATEGORY_CAMPUS_EVENT)

    # 4. Campus events from myUMBC, umbc.edu, campuslife, tickets
    print("Scraping campus events (myUMBC, UMBC events, Campus Life, Tickets)...")
    for url in ["https://my.umbc.edu/events"]:
        try:
            scraper = MyUMBCScraper(url)
            for ev in scraper.scrape():
                if ev.get("link") in food_links:
                    continue
                ev["category"] = CATEGORY_CAMPUS_EVENT
                ev["id"] = ev.get("link", "")
                if ev["id"] not in campus_seen:
                    campus_seen.add(ev["id"])
                    all_events.append(ev)
        except Exception as e:
            print(f"  [ERROR] myUMBC campus ({url}) failed: {e}")
    for scraper_class, name in [(UMBCEventsScraper, "UMBC Events"), (CampusLifeScraper, "Campus Life"), (TicketsScraper, "Tickets")]:
        try:
            for ev in scraper_class().scrape():
                ev["category"] = CATEGORY_CAMPUS_EVENT
                ev["id"] = ev.get("link", "")
                if ev["id"] not in campus_seen:
                    campus_seen.add(ev["id"])
                    all_events.append(ev)
        except Exception as e:
            print(f"  [ERROR] {name} scraper failed: {e}")

    save_events(all_events)
    counts = {
        CATEGORY_IMPORTANT_DATE: sum(1 for e in all_events if e.get("category") == CATEGORY_IMPORTANT_DATE),
        CATEGORY_FOOD_EVENT: sum(1 for e in all_events if e.get("category") == CATEGORY_FOOD_EVENT),
        CATEGORY_CAMPUS_EVENT: sum(1 for e in all_events if e.get("category") == CATEGORY_CAMPUS_EVENT),
    }
    print(f"Done. Saved {len(all_events)} total: {counts}")


if __name__ == "__main__":
    main()
