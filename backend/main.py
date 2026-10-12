import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, cast

from dotenv import load_dotenv

from scrapers.athletics_scraper import AthleticsScraper
from scrapers.baltimoremag_scraper import BaltimoreMagScraper
from scrapers.biology_scraper import BiologyScraper
from scrapers.campuslife_scraper import CampusLifeScraper
from scrapers.careers_scraper import CareersScraper
from scrapers.department_seminar_scraper import DepartmentSeminarScraper
from scrapers.dining_scraper import DiningScraper
from scrapers.eventbrite_scraper import EventbriteScraper
from scrapers.gradschool_scraper import GradSchoolScraper
from scrapers.library_scraper import LibraryScraper
from scrapers.mathstat_scraper import MathStatScraper
from scrapers.meetup_scraper import MeetupScraper
from scrapers.myumbc_group_scraper import MyUMBCGroupScraper
from scrapers.myumbc_scraper import MyUMBCScraper
from scrapers.official_dates_scraper import OfficialDatesScraper
from scrapers.patch_scraper import PatchCalendarScraper
from scrapers.physics_scraper import PhysicsScraper
from scrapers.registrar_scraper import RegistrarScraper
from scrapers.sbs_scraper import SBSScraper
from scrapers.seb_scraper import SEBScraper
from scrapers.studentaffairs_scraper import StudentAffairsScraper
from scrapers.tickets_scraper import TicketsScraper
from scrapers.umbc_events_scraper import UMBCEventsScraper
from utils.notifier import DiscordNotifier

load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
discord_notifier = DiscordNotifier(DISCORD_WEBHOOK_URL)

# URLs for event scrapers
FOOD_EVENT_URLS = [
    "https://my.umbc.edu/events/free-food",
    "https://my.umbc.edu/events",
]

# Supabase Setup
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

supabase: Optional[Any] = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        from supabase import Client, create_client
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        supabase = supabase_client
        print("Successfully connected to Supabase")
    except Exception as e:
        print(f"Failed to connect to Supabase: {e}")
        supabase = None
else:
    print("Supabase credentials not configured.")

# Category constants for filtering in DB and frontend
CATEGORY_IMPORTANT_DATE = "important_date"
CATEGORY_FOOD_EVENT = "food_event"
CATEGORY_CAMPUS_EVENT = "campus_event"

_LOCALIST_EVENT_ID_RE = re.compile(r"/events?/event/(\d+)", re.I)


def normalize_event_id(link: str) -> str:
    """Normalize event IDs so shared Localist events and myUMBC events dedupe across UMBC sites."""
    if not link:
        return ""
    cleaned = re.sub(r"^https?://my3\.my\.umbc\.edu", "https://my.umbc.edu", link.strip()).rstrip("/")
    match = _LOCALIST_EVENT_ID_RE.search(cleaned)
    if match:
        return f"localist:{match.group(1)}"
    return cleaned


def load_seen_ids() -> Set[str]:
    if supabase is None:
        return set()
    try:
        response = supabase.table("events").select("id").execute()
        rows = cast(List[Dict[str, Any]], response.data or [])
        return {str(row["id"]) for row in rows if row.get("id")}
    except Exception as e:
        print(f"Error loading seen IDs: {e}")
    return set()


def load_existing_events() -> List[Dict[str, Any]]:
    if supabase is None:
        return []
    try:
        response = supabase.table("events").select("*").execute()
        return cast(List[Dict[str, Any]], response.data or [])
    except Exception as e:
        print(f"Error loading events: {e}")
    return []


_PLACEHOLDER_TITLES = {
    'no title', 'untitled', 'untitled event', 'event', '',
    'view more', 'featured events', 'weekend', 'today',
}

_PLACEHOLDER_DESCS = {
    'view more', 'featured events view more', 'weekend view more',
}


def _is_valid_event(event: dict) -> bool:
    """Reject placeholder / junk events before they reach Supabase."""
    if not event:
        return False
    eid = (event.get("id") or event.get("link") or "").strip()
    if not eid:
        return False
    title = (event.get("title") or "").strip()
    if title.lower() in _PLACEHOLDER_TITLES:
        return False
    if len(title) < 4:
        return False
    desc = (event.get("description") or "").strip().lower()
    if desc in _PLACEHOLDER_DESCS:
        return False
    if re.match(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun),?\s', title) and len(title) < 15:
        return False
    return True


def _dedupe_events(events_list: list) -> list:
    """Final safety-net dedup: keep best occurrence by normalized ID and title+date fingerprint."""
    groups: Dict[str, Dict[str, Any]] = {}
    for ev in events_list:
        raw_id = ev.get("id") or ev.get("link", "")
        eid = normalize_event_id(raw_id)
        if not eid:
            continue
        title_norm = re.sub(r"[^a-z0-9]+", " ", (ev.get("title") or "").strip().lower()).strip()
        date_norm = re.sub(r"[^a-z0-9]+", " ", (ev.get("date") or "").strip().lower()).strip()

        # Canonical key
        if eid.startswith("localist:"):
            key = eid
        elif "my.umbc.edu" in eid:
            m_my = re.search(r"my\.umbc\.edu/(?:groups/[^/]+/)?events/(\d+)", eid)
            key = f"myumbc:{m_my.group(1)}||{date_norm}" if m_my else f"{title_norm}||{date_norm}"
        else:
            key = f"{title_norm}||{date_norm}" if title_norm else eid

        if key not in groups:
            ev_copy = dict(ev)
            ev_copy["id"] = eid
            if ev_copy.get("link"):
                ev_copy["link"] = re.sub(r"^https?://my3\.my\.umbc\.edu", "https://my.umbc.edu", ev_copy["link"].strip())
            groups[key] = ev_copy
        else:
            existing = groups[key]
            # Merge food keyword
            if ev.get("food_keyword") and not existing.get("food_keyword"):
                existing["food_keyword"] = ev["food_keyword"]
            # Promote category
            if ev.get("category") == CATEGORY_FOOD_EVENT:
                existing["category"] = CATEGORY_FOOD_EVENT
            # Prefer longer description
            if len(ev.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = ev["description"]
            # Prefer non-my3 link
            if "my3." in str(existing.get("link", "")) and "my3." not in str(ev.get("link", "")):
                existing["link"] = ev["link"]

    unique = list(groups.values())
    dropped = len(events_list) - len(unique)
    if dropped:
        print(f"  Dedup pass removed {dropped} duplicate(s)")
    return unique


def _cleanup_stale_duplicates():
    """Remove old Supabase rows:
    1. Raw Localist URLs superseded by localist:<id>.
    2. Stale my3.my.umbc.edu rows superseded by my.umbc.edu rows.
    3. Duplicate rows with identical (clean_title, clean_date).
    """
    if supabase is None:
        return
    try:
        response = supabase.table("events").select("*").execute()
        rows = cast(List[Dict[str, Any]], response.data or [])
    except Exception as e:
        print(f"  [CLEANUP] Failed to read events: {e}")
        return

    all_ids = {str(row.get("id", "")) for row in rows}
    stale_ids = set()

    # 1. Localist stale URLs
    for row in rows:
        rid = str(row.get("id", ""))
        link = str(row.get("link", ""))
        nid = normalize_event_id(link) if link else rid
        if nid != rid and nid.startswith("localist:") and nid in all_ids:
            stale_ids.add(rid)

    # 2. Semantic title + date duplicate clusters
    by_fingerprint: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        rid = str(row.get("id", ""))
        if rid in stale_ids:
            continue
        title_norm = re.sub(r"[^a-z0-9]+", " ", str(row.get("title", "")).lower()).strip()
        date_norm = re.sub(r"[^a-z0-9]+", " ", str(row.get("date", "")).lower()).strip()
        if not title_norm:
            continue
        fp = f"{title_norm}||{date_norm}"
        by_fingerprint.setdefault(fp, []).append(row)

    for fp, cluster in by_fingerprint.items():
        if len(cluster) > 1:
            def score(x: Dict[str, Any]):
                return (
                    1 if x.get("category") == CATEGORY_FOOD_EVENT else 0,
                    0 if "my3." in str(x.get("id", "")) else 1,
                    len(str(x.get("description", ""))),
                    str(x.get("updated_at") or x.get("created_at") or "")
                )
            sorted_cluster = sorted(cluster, key=score, reverse=True)
            for discard in sorted_cluster[1:]:
                stale_ids.add(str(discard.get("id", "")))

    if not stale_ids:
        print("  [CLEANUP] No stale duplicates found in Supabase.")
        return

    print(f"  [CLEANUP] Removing {len(stale_ids)} stale duplicate row(s) from Supabase...")
    for sid in stale_ids:
        try:
            supabase.table("events").delete().eq("id", sid).execute()
        except Exception as e:
            print(f"  [CLEANUP] Failed to delete {sid}: {e}")


def save_events(events_list: list):
    if supabase is None:
        return
    events_list = _dedupe_events(events_list)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    skipped = 0
    valid_rows = []
    seen_row_ids = set()
    for event in events_list:
        if not _is_valid_event(event):
            skipped += 1
            continue
        row_id = event.get("id") or event.get("link", "")
        if not row_id or row_id in seen_row_ids:
            continue
        seen_row_ids.add(row_id)
        row = {
            "id": row_id,
            "title": event.get("title", ""),
            "date": event.get("date", ""),
            "description": event.get("description", ""),
            "link": event.get("link", ""),
            "food_keyword": event.get("food_keyword", ""),
            "source": event.get("source", ""),
            "category": event.get("category", CATEGORY_CAMPUS_EVENT),
            "updated_at": now_iso,
        }
        valid_rows.append(row)

    # Batch upsert in chunks of 100 for dramatic speedup and reliability
    chunk_size = 100
    for i in range(0, len(valid_rows), chunk_size):
        chunk = valid_rows[i:i + chunk_size]
        try:
            supabase.table("events").upsert(chunk).execute()
        except Exception as e:
            print(f"Error saving events batch {i // chunk_size + 1}: {e}")
            # Fallback to single-row upsert so one malformed row does not drop the entire chunk
            for row in chunk:
                try:
                    supabase.table("events").upsert(row).execute()
                except Exception as row_e:
                    print(f"Failed to upsert event {row.get('id')}: {row_e}")

    if skipped:
        print(f"  Skipped {skipped} invalid/placeholder events")
    _cleanup_stale_duplicates()


def main():
    print(f"[{datetime.now()}] Starting UMBC Scraper...")

    seen_ids = load_seen_ids()
    all_events = []

    def notify_food_event(ev: dict):
        eid = ev.get("id")
        if eid and eid not in seen_ids and _is_valid_event(ev):
            seen_ids.add(eid)
            discord_notifier.notify(ev)

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
    myumbc_cached_events = []

    for url in FOOD_EVENT_URLS:
        try:
            scraper = MyUMBCScraper(url)
            all_from_page = scraper.scrape()
            if url == "https://my.umbc.edu/events":
                myumbc_cached_events = all_from_page
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
                notify_food_event(ev)

    # Dining events (filter for food)
    try:
        dining = DiningScraper()
        for ev in dining.filter_food_events(dining.scrape()):
            ev["category"] = CATEGORY_FOOD_EVENT
            ev["id"] = normalize_event_id(ev.get("link", ""))
            if ev["id"] not in food_links:
                food_links.add(ev["id"])
                all_events.append(ev)
                notify_food_event(ev)
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
    for ev in retriever_events:
        food_links.add(ev["id"])
        all_events.append(ev)

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
                notify_food_event(ev)
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

    # Reuse myUMBC events already scraped in Section 2 to avoid redundant network fetch
    if not myumbc_cached_events:
        try:
            myumbc_cached_events = MyUMBCScraper("https://my.umbc.edu/events").scrape()
        except Exception as e:
            print(f"  [ERROR] myUMBC campus fallback failed: {e}")

    for ev in myumbc_cached_events:
        ev["id"] = normalize_event_id(ev.get("link", ""))
        if ev["id"] in food_links:
            continue
        ev["category"] = CATEGORY_CAMPUS_EVENT
        if ev["id"] not in campus_seen:
            campus_seen.add(ev["id"])
            all_events.append(ev)

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
        (EventbriteScraper,        "Eventbrite (UMBC)"),
        (MeetupScraper,            "Meetup (UMBC)"),
        (BaltimoreMagScraper,      "Baltimore Magazine (UMBC)"),
        (PatchCalendarScraper,     "Patch Calendar (Baltimore)"),
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
                        notify_food_event(ev)
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