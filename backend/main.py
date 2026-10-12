import hashlib
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, cast

# Ensure UTF-8 output on all environments (prevents Windows cp1252 charmap crashes)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

_EVENT_NUMERIC_ID_RE = re.compile(r"(?:/events?/event/|/events/|localist:|umbc:)(\d+)", re.I)

MONTHS_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def extract_calendar_date(s: str) -> str:
    """Normalize date strings into a canonical YYYY-MM-DD day key.
    Ensures 'October 15, 2026, 11:30 am' and 'Oct 15 11:30 AM' produce identical date keys.
    """
    if not s:
        return "no-date"
    s_low = s.lower().strip()
    # 1. ISO format: 2026-10-15
    m_iso = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m_iso:
        return f"{int(m_iso.group(1)):04d}-{int(m_iso.group(2)):02d}-{int(m_iso.group(3)):02d}"
    # 2. Month name + day: 'October 15, 2026' or 'Oct 15 11:30 AM'
    m_name = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:,?\s*(\d{4}))?", s_low)
    if m_name:
        mo = MONTHS_MAP[m_name.group(1)[:3]]
        day = int(m_name.group(2))
        yr = int(m_name.group(3)) if m_name.group(3) else datetime.now().year
        return f"{yr:04d}-{mo:02d}-{day:02d}"
    # 3. Slash format: 10/15/2026
    m_slash = re.search(r"(\d{1,2})/(\d{1,2})/(?:\d{2,4})", s)
    if m_slash:
        return f"{datetime.now().year:04d}-{int(m_slash.group(1)):02d}-{int(m_slash.group(2)):02d}"
    if "ongoing" in s_low or "check" in s_low:
        return "ongoing"
    return re.sub(r"[^a-z0-9]+", "", s_low)[:15]


def extract_numeric_event_id(link: str) -> str:
    """Extract UMBC's underlying numeric event ID if present in the link or ID string."""
    m = _EVENT_NUMERIC_ID_RE.search(link or "")
    return m.group(1) if m else ""


def compute_event_fingerprint_hash(title: str, date: str) -> str:
    """Assign a deterministic 16-hex SHA-256 hash to an event title + calendar date.
    Eliminates cross-website deduplication hassle by giving identical events from different
    websites the exact same hash fingerprint.
    """
    clean_title = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
    clean_date = extract_calendar_date(date)
    fingerprint = f"{clean_title}||{clean_date}"
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]


def get_event_id(ev: dict) -> str:
    """Return the deterministic title+date fingerprint hash ID for an event.
    Guarantees cross-website deduplication across all feeds.
    """
    title = (ev.get("title") or "").strip()
    date = (ev.get("date") or "").strip()
    if title:
        return f"ev_{compute_event_fingerprint_hash(title, date)}"
    link = (ev.get("link") or "").strip()
    nid = extract_numeric_event_id(link)
    if nid:
        return f"umbc:{nid}"
    return link


def normalize_event_id(link: str, title: str = "", date: str = "") -> str:
    """Normalize event ID using title+date fingerprint hash or numeric ID."""
    if title:
        return f"ev_{compute_event_fingerprint_hash(title, date)}"
    if not link:
        return ""
    cleaned = re.sub(r"^https?://my3\.my\.umbc\.edu", "https://my.umbc.edu", link.strip()).rstrip("/")
    nid = extract_numeric_event_id(cleaned)
    if nid:
        return f"umbc:{nid}"
    return cleaned


def load_seen_ids() -> Set[str]:
    if supabase is None:
        return set()
    seen = set()
    page_size = 1000
    start = 0
    try:
        while True:
            response = supabase.table("events").select("id").range(start, start + page_size - 1).execute()
            rows = cast(List[Dict[str, Any]], response.data or [])
            for r in rows:
                if r.get("id"):
                    seen.add(str(r["id"]))
            if len(rows) < page_size:
                break
            start += page_size
    except Exception as e:
        print(f"Error loading seen IDs: {e}")
    return seen


def load_existing_events() -> List[Dict[str, Any]]:
    if supabase is None:
        return []
    all_rows = []
    page_size = 1000
    start = 0
    try:
        while True:
            response = supabase.table("events").select("*").range(start, start + page_size - 1).execute()
            rows = cast(List[Dict[str, Any]], response.data or [])
            all_rows.extend(rows)
            if len(rows) < page_size:
                break
            start += page_size
    except Exception as e:
        print(f"Error loading events: {e}")
    return all_rows


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
    """Automatic cross-website deduplication using title+date fingerprint hashes
    and UMBC numeric event IDs. Merges metadata (food keywords, descriptions, links).
    """
    groups: Dict[str, Dict[str, Any]] = {}
    key_aliases: Dict[str, str] = {}

    for ev in events_list:
        raw_link = ev.get("link") or ev.get("id", "")
        clean_link = re.sub(r"^https?://my3\.my\.umbc\.edu", "https://my.umbc.edu", str(raw_link).strip())
        h = compute_event_fingerprint_hash(ev.get("title", ""), ev.get("date", ""))
        nid = extract_numeric_event_id(clean_link)

        # Look up if either the numeric ID or the title+date hash was already seen
        canon_key = None
        if nid and f"num:{nid}" in key_aliases:
            canon_key = key_aliases[f"num:{nid}"]
        elif f"hash:{h}" in key_aliases:
            canon_key = key_aliases[f"hash:{h}"]

        if not canon_key:
            canon_key = f"ev_{h}"
            if nid:
                key_aliases[f"num:{nid}"] = canon_key
            key_aliases[f"hash:{h}"] = canon_key

            ev_copy = dict(ev)
            ev_copy["id"] = canon_key
            ev_copy["link"] = clean_link
            groups[canon_key] = ev_copy
        else:
            existing = groups[canon_key]
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
            if "my3." in str(existing.get("link", "")) and "my3." not in str(clean_link):
                existing["link"] = clean_link
            # Prefer more detailed date if current is short
            if len(str(ev.get("date", ""))) > len(str(existing.get("date", ""))):
                existing["date"] = ev["date"]

    unique = list(groups.values())
    dropped = len(events_list) - len(unique)
    if dropped:
        print(f"  [DEDUPE] Automatically collapsed {dropped} cross-website duplicate event(s) via hash & ID matching")
    return unique


def _cleanup_stale_duplicates():
    """Remove old / duplicate Supabase rows across different feeds using hash fingerprints and numeric IDs."""
    if supabase is None:
        return
    rows = load_existing_events()
    if not rows:
        return

    clusters: Dict[str, List[Dict[str, Any]]] = {}
    key_aliases: Dict[str, str] = {}
    stale_ids: Set[str] = set()

    for row in rows:
        rid = str(row.get("id", ""))
        link = str(row.get("link", ""))
        title = str(row.get("title", ""))
        date = str(row.get("date", ""))

        h = compute_event_fingerprint_hash(title, date)
        nid = extract_numeric_event_id(rid) or extract_numeric_event_id(link)

        canon_key = None
        if nid and f"num:{nid}" in key_aliases:
            canon_key = key_aliases[f"num:{nid}"]
        elif f"hash:{h}" in key_aliases:
            canon_key = key_aliases[f"hash:{h}"]

        if not canon_key:
            canon_key = f"ev_{h}"
            if nid:
                key_aliases[f"num:{nid}"] = canon_key
            key_aliases[f"hash:{h}"] = canon_key

        clusters.setdefault(canon_key, []).append(row)

    for canon_key, cluster in clusters.items():
        if len(cluster) > 1:
            def score(x: Dict[str, Any]):
                x_id = str(x.get("id", ""))
                return (
                    1 if x.get("category") == CATEGORY_FOOD_EVENT else 0,
                    1 if x_id.startswith("ev_") else 0,
                    0 if "my3." in x_id else 1,
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
    stale_list = list(stale_ids)
    batch_size = 100
    for i in range(0, len(stale_list), batch_size):
        batch = stale_list[i : i + batch_size]
        try:
            supabase.table("events").delete().in_("id", batch).execute()
        except Exception as e:
            print(f"  [CLEANUP] Batch delete failed, falling back to single delete: {e}")
            for sid in batch:
                try:
                    supabase.table("events").delete().eq("id", sid).execute()
                except Exception as row_e:
                    print(f"  [CLEANUP] Failed to delete {sid}: {row_e}")


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
        row_id = event.get("id") or f"ev_{compute_event_fingerprint_hash(event.get('title', ''), event.get('date', ''))}"
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
            date_item["id"] = get_event_id(date_item)
            all_events.append(date_item)
    except Exception as e:
        print(f"  [ERROR] Registrar scraper failed: {e}")
    try:
        sbs = SBSScraper()
        for date_item in sbs.scrape():
            date_item["category"] = CATEGORY_IMPORTANT_DATE
            date_item["id"] = get_event_id(date_item)
            all_events.append(date_item)
    except Exception as e:
        print(f"  [ERROR] SBS scraper failed: {e}")
    try:
        official_dates = OfficialDatesScraper()
        for date_item in official_dates.scrape():
            date_item["category"] = CATEGORY_IMPORTANT_DATE
            date_item["id"] = get_event_id(date_item)
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
            ev["id"] = get_event_id(ev)
            if ev["id"] not in food_links:
                food_links.add(ev["id"])
                all_events.append(ev)
                notify_food_event(ev)

    # Dining events (filter for food)
    try:
        dining = DiningScraper()
        for ev in dining.filter_food_events(dining.scrape()):
            ev["category"] = CATEGORY_FOOD_EVENT
            ev["id"] = get_event_id(ev)
            if ev["id"] not in food_links:
                food_links.add(ev["id"])
                all_events.append(ev)
                notify_food_event(ev)
    except Exception as e:
        print(f"  [ERROR] Dining scraper failed: {e}")

    # Retriever Essentials (permanent)
    retriever_events = [
        {
            "title": "The Essential Space (Free Grocery Store)",
            "date": "Ongoing (Check RAC 235 Hours)",
            "description": "A free grocery store located in the Retriever Activities Center, room 235.",
            "link": "https://retrieveressentials.umbc.edu",
            "food_keyword": "free groceries",
            "source": "Retriever Essentials",
            "category": CATEGORY_FOOD_EVENT,
        },
        {
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
        ev["id"] = get_event_id(ev)
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
    seb_food_ids = {get_event_id(e) for e in seb_food}
    for ev in seb_events:
        ev["id"] = get_event_id(ev)
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
        ev["id"] = get_event_id(ev)
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
            scraper_inst = scraper_class()
            for ev in scraper_inst.scrape():
                eid = get_event_id(ev)
                if not eid:
                    continue
                ev["id"] = eid

                # Check for food keywords across campus events
                all_text = f"{ev.get('title', '')} {ev.get('description', '')}"
                is_food = getattr(scraper_inst, "detector", None) and scraper_inst.detector.contains_food(all_text)
                if is_food:
                    ev["category"] = CATEGORY_FOOD_EVENT
                    ev["food_keyword"] = scraper_inst.detector.get_matched_item(all_text)
                    if eid not in food_links:
                        food_links.add(eid)
                        all_events.append(ev)
                        notify_food_event(ev)
                else:
                    ev["category"] = CATEGORY_CAMPUS_EVENT
                    if eid not in campus_seen:
                        campus_seen.add(eid)
                        all_events.append(ev)
        except Exception as e:
            print(f"  [ERROR] {name} scraper failed: {e}")

    # myUMBC high-activity student org and campus office groups
    MYUMBC_GROUPS = [
        ("https://my3.my.umbc.edu/groups/ocss", "Off-Campus Student Services"),
        ("https://my3.my.umbc.edu/groups/gsa", "Graduate Student Association"),
        ("https://my3.my.umbc.edu/groups/womenscenter", "Women's Center"),
        ("https://my3.my.umbc.edu/groups/sga", "Student Government Association"),
        ("https://my3.my.umbc.edu/groups/seb", "Student Events Board"),
        ("https://my3.my.umbc.edu/groups/retrieveressentials", "Retriever Essentials"),
        ("https://my3.my.umbc.edu/groups/bsu", "Black Student Union"),
        ("https://my3.my.umbc.edu/groups/isa", "Indian Student Association"),
        ("https://my3.my.umbc.edu/groups/nsbe", "National Society of Black Engineers"),
        ("https://my3.my.umbc.edu/groups/hackumbc", "HackUMBC"),
        ("https://my3.my.umbc.edu/groups/swe", "Society of Women Engineers"),
        ("https://my3.my.umbc.edu/groups/shpe", "Society of Hispanic Professional Engineers"),
        ("https://my3.my.umbc.edu/groups/ieee", "IEEE UMBC Student Branch"),
    ]
    for group_url, name in MYUMBC_GROUPS:
        try:
            scraper = MyUMBCGroupScraper(group_url, source_name=name)
            group_events = scraper.scrape()
            food_from_group = scraper.filter_food_events(group_events)
            food_from_group_ids = {get_event_id(e) for e in food_from_group}
            for ev in group_events:
                eid = get_event_id(ev)
                ev["id"] = eid
                if eid in food_from_group_ids:
                    ev["category"] = CATEGORY_FOOD_EVENT
                    if eid not in food_links:
                        food_links.add(eid)
                        all_events.append(ev)
                        notify_food_event(ev)
                else:
                    ev["category"] = CATEGORY_CAMPUS_EVENT
                    if eid not in campus_seen:
                        campus_seen.add(eid)
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