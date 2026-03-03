import os
import re
from datetime import datetime
from scrapers.myumbc_scraper import MyUMBCScraper
from scrapers.registrar_scraper import RegistrarScraper
from scrapers.umbc_events_scraper import UMBCEventsScraper
from scrapers.campuslife_scraper import CampusLifeScraper
from scrapers.seb_scraper import SEBScraper
from scrapers.tickets_scraper import TicketsScraper
from scrapers.sbs_scraper import SBSScraper
# New scrapers
from scrapers.studentaffairs_scraper import StudentAffairsScraper
from scrapers.careers_scraper import CareersScraper
from scrapers.library_scraper import LibraryScraper
from scrapers.athletics_scraper import AthleticsScraper
from scrapers.physics_scraper import PhysicsScraper
from scrapers.biology_scraper import BiologyScraper
from scrapers.mathstat_scraper import MathStatScraper
from scrapers.department_seminar_scraper import DepartmentSeminarScraper
from scrapers.dining_scraper import DiningScraper
from scrapers.official_dates_scraper import OfficialDatesScraper
from scrapers.gradschool_scraper import GradSchoolScraper
from scrapers.myumbc_group_scraper import MyUMBCGroupScraper
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

_LOCALIST_EVENT_ID_RE = re.compile(r"/events?/event/(\d+)", re.I)


def normalize_event_id(link: str) -> str:
    """Normalize event IDs so shared Localist events dedupe across UMBC sites."""
    if not link:
        return ""
    match = _LOCALIST_EVENT_ID_RE.search(link)
    if match:
        return f"localist:{match.group(1)}"
    return link


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


_PLACEHOLDER_TITLES = {
    'no title', 'untitled', 'untitled event', 'event', '',
    'view more', 'featured events', 'weekend', 'today',
}


def _is_valid_event(event: dict) -> bool:
    """Reject placeholder / junk events before they reach Supabase."""
    title = (event.get("title") or "").strip()
    if title.lower() in _PLACEHOLDER_TITLES:
        return False
    if len(title) < 4:
        return False
    desc = (event.get("description") or "").strip()
    if desc.lower() in {'view more', 'featured events view more', 'weekend view more', ''}:
        return False
    if re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s', title) and len(title) < 15:
        return False
    return True


def _dedupe_events(events_list: list) -> list:
    """Final safety-net dedup: keep first occurrence by ID, then by title+date fingerprint."""
    seen_ids = set()
    seen_fingerprints = set()
    unique = []
    for ev in events_list:
        eid = ev.get("id") or ev.get("link", "")
        if eid in seen_ids:
            continue
        seen_ids.add(eid)
        title_norm = re.sub(r"\s+", " ", (ev.get("title") or "").strip().lower())
        date_norm = re.sub(r"\s+", " ", (ev.get("date") or "").strip().lower())
        fp = f"{title_norm}||{date_norm}"
        if fp in seen_fingerprints:
            continue
        seen_fingerprints.add(fp)
        unique.append(ev)
    dropped = len(events_list) - len(unique)
    if dropped:
        print(f"  Dedup pass removed {dropped} duplicate(s)")
    return unique


def _cleanup_stale_duplicates():
    """Remove old Supabase rows whose IDs are raw Localist URLs now covered by a normalized ID."""
    if supabase is None:
        return
    try:
        rows = supabase.table("events").select("id, link").execute().data
    except Exception as e:
        print(f"  [CLEANUP] Failed to read events: {e}")
        return

    normalized_ids = set()
    stale_ids = []
    for row in rows:
        rid = row.get("id", "")
        link = row.get("link", "")
        nid = normalize_event_id(link) if link else rid
        if nid != rid and nid.startswith("localist:"):
            if nid in normalized_ids:
                stale_ids.append(rid)
            else:
                normalized_ids.add(nid)
                stale_ids.append(rid)
        else:
            normalized_ids.add(rid)

    if not stale_ids:
        return
    print(f"  [CLEANUP] Removing {len(stale_ids)} stale duplicate row(s) from Supabase...")
    for sid in stale_ids:
        try:
            supabase.table("events").delete().eq("id", sid).execute()
        except Exception as e:
            print(f"  [CLEANUP] Failed to delete {sid}: {e}")


def save_events(events_list):
    if supabase is None:
        return
    events_list = _dedupe_events(events_list)
    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    skipped = 0
    try:
        for event in events_list:
            if not _is_valid_event(event):
                skipped += 1
                continue
            row = {
                "id": event.get("id") or event.get("link", ""),
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
    if skipped:
        print(f"  Skipped {skipped} invalid/placeholder events")
    _cleanup_stale_duplicates()


def main():
    print(f"[{datetime.now()}] Starting UMBC Scraper...")

    seen_ids = load_seen_ids()
    all_events = []

    # 1. Important dates (Registrar + SBS billing + Official Dates)
    print("Scraping important dates (Registrar, SBS, Official Dates)...")
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
    try:
        official_dates = OfficialDatesScraper()
        for date_item in official_dates.scrape():
            date_item["category"] = CATEGORY_IMPORTANT_DATE
            date_item["id"] = date_item.get("link", "") + "#" + date_item.get("title", "")[:50]
            all_events.append(date_item)
    except Exception as e:
        print(f"  [ERROR] Official Dates scraper failed: {e}")

    # 2. Food events from myUMBC, Dining, and Retriever Essentials
    print("Scraping food events (myUMBC, Dining)...")
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
            ev["id"] = normalize_event_id(ev.get("link", ""))
            if ev["id"] not in food_links:
                food_links.add(ev["id"])
                all_events.append(ev)
                if ev["id"] not in seen_ids:
                    discord_notifier.notify(ev)

    # Dining events (filter for food)
    try:
        dining = DiningScraper()
        for ev in dining.filter_food_events(dining.scrape()):
            ev["category"] = CATEGORY_FOOD_EVENT
            ev["id"] = normalize_event_id(ev.get("link", ""))
            if ev["id"] not in food_links:
                food_links.add(ev["id"])
                all_events.append(ev)
                if ev["id"] not in seen_ids:
                    discord_notifier.notify(ev)
    except Exception as e:
        print(f"  [ERROR] Dining scraper failed: {e}")

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
    seb_food_ids = {normalize_event_id(e.get("link", "")) for e in seb_food}
    for ev in seb_events:
        ev["id"] = normalize_event_id(ev.get("link", ""))
        if ev["id"] in seb_food_ids:
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
    campus_seen.update(
        e.get("id")
        for e in all_events
        if e.get("category") == CATEGORY_CAMPUS_EVENT and e.get("id")
    )

    # 4. Campus events from myUMBC, umbc.edu, campuslife, tickets + all new sources
    print("Scraping campus events (myUMBC, UMBC Events, Campus Life, Tickets, Student Affairs,")
    print("  Careers, Library, Athletics, Physics, Biology, Math/Stat, Dept Seminars, Grad School)...")
    for url in ["https://my.umbc.edu/events"]:
        try:
            scraper = MyUMBCScraper(url)
            for ev in scraper.scrape():
                ev["id"] = normalize_event_id(ev.get("link", ""))
                if ev["id"] in food_links:
                    continue
                ev["category"] = CATEGORY_CAMPUS_EVENT
                if ev["id"] not in campus_seen:
                    campus_seen.add(ev["id"])
                    all_events.append(ev)
        except Exception as e:
            print(f"  [ERROR] myUMBC campus ({url}) failed: {e}")

    campus_scrapers = [
        (UMBCEventsScraper,        "UMBC Events"),
        (CampusLifeScraper,        "Campus Life"),
        (TicketsScraper,           "Tickets"),
        (StudentAffairsScraper,    "Student Affairs"),
        (CareersScraper,           "Career Center"),
        (LibraryScraper,           "Library"),
        (AthleticsScraper,         "Athletics"),
        (PhysicsScraper,           "Physics"),
        (BiologyScraper,           "Biology"),
        (MathStatScraper,          "Math & Statistics"),
        (DepartmentSeminarScraper, "Dept Seminars (CS/GES/Research)"),
        (GradSchoolScraper,        "Grad School / GSA"),
    ]
    for scraper_class, name in campus_scrapers:
        try:
            for ev in scraper_class().scrape():
                ev["category"] = CATEGORY_CAMPUS_EVENT
                ev["id"] = normalize_event_id(ev.get("link", ""))
                if ev["id"] not in campus_seen:
                    campus_seen.add(ev["id"])
                    all_events.append(ev)
        except Exception as e:
            print(f"  [ERROR] {name} scraper failed: {e}")

    # myUMBC student org groups
    MYUMBC_GROUPS = [
        ("https://my3.my.umbc.edu/groups/isa", "ISA (Indian Student Association)"),
    ]
    for group_url, name in MYUMBC_GROUPS:
        try:
            scraper = MyUMBCGroupScraper(group_url, source_name=name)
            group_events = scraper.scrape()
            food_from_group = scraper.filter_food_events(group_events)
            food_from_group_ids = {normalize_event_id(e.get("link", "")) for e in food_from_group}
            for ev in group_events:
                ev["id"] = normalize_event_id(ev.get("link", ""))
                if ev["id"] in food_from_group_ids:
                    ev["category"] = CATEGORY_FOOD_EVENT
                    if ev["id"] not in food_links:
                        food_links.add(ev["id"])
                        all_events.append(ev)
                else:
                    ev["category"] = CATEGORY_CAMPUS_EVENT
                    if ev["id"] not in campus_seen:
                        campus_seen.add(ev["id"])
                        all_events.append(ev)
        except Exception as e:
            print(f"  [ERROR] myUMBC group ({name}) failed: {e}")

    save_events(all_events)
    counts = {
        CATEGORY_IMPORTANT_DATE: sum(1 for e in all_events if e.get("category") == CATEGORY_IMPORTANT_DATE),
        CATEGORY_FOOD_EVENT: sum(1 for e in all_events if e.get("category") == CATEGORY_FOOD_EVENT),
        CATEGORY_CAMPUS_EVENT: sum(1 for e in all_events if e.get("category") == CATEGORY_CAMPUS_EVENT),
    }
    print(f"Done. Saved {len(all_events)} total: {counts}")


if __name__ == "__main__":
    main()