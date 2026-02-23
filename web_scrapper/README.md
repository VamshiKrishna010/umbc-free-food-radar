# Campus Event & Free Food Scraper

Automated tool to scan university event calendars for free food.

## Features
- **Smart Detection:** Filters events based on keywords (pizza, lunch, etc.) and avoids false positives.
- **Modular Scrapers:** Easily extensible base class for different calendar platforms (Localist, Trumba, etc.).
- **Notifications:** Integrated Discord webhook support.
- **Deduplication:** Keeps track of "seen" events in a local JSON database.

## Setup
1. **Environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   python -m playwright install chromium
   ```

2. **Configuration:**
   - Copy `.env.example` to `.env` and add your Discord Webhook URL.
   - Edit `main.py` to add your university's calendar URL to the `CALENDAR_URLS` list.

## Usage
Run the scraper:
```bash
python main.py
```

## Project Structure
- `scrapers/`: Individual site scrapers.
- `utils/`: Notification and food detection logic.
- `seen_events.json`: Local storage to prevent duplicate alerts.
