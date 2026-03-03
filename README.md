# UMBC Food Radar

Automated dashboard for UMBC: important dates, free food events, and campus activities.

## Features
- **Important Dates:** Registrar academic calendar + SBS billing deadlines
- **Free Food:** myUMBC, Retriever Essentials, Student Events Board (SEB)
- **Campus Events:** myUMBC, umbc.edu/events, Campus Life (RAC), SEB, UMBC Tickets (athletics/arts)
- **Discord Alerts:** New food events posted to Discord when `DISCORD_WEBHOOK_URL` is set
- **PWA:** Installable on mobile; works offline with cached data (after at least one online load to warm API cache)
- **Favorites, Share, Date filter:** Save events to favorites, share via Web Share API, filter by date range
- **Auto-update:** GitHub Actions runs every 30 minutes

*Note: Handshake requires student login and cannot be scraped. Career events may appear via myUMBC groups.*

## Setup

1. **Environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1   # or: source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Supabase:**
   - Create a project at [supabase.com](https://supabase.com)
   - Create an `events` table with: `id` (text primary key), `title`, `date`, `description`, `link`, `food_keyword`, `source`, `category`
   - Or run the migration: `supabase_migration.sql` in Supabase SQL Editor

3. **Configuration:**
   - Copy `.env.example` to `.env`
   - For the Python scraper, add `SUPABASE_URL`, `SUPABASE_KEY` (service role), and optionally `DISCORD_WEBHOOK_URL`
   - For Vercel frontend proxy, set `SUPABASE_URL` and `SUPABASE_ANON_KEY` in Project Settings -> Environment Variables

## Usage
```bash
cd web_scrapper
python main.py
```

## Project Structure
- `scrapers/`: myumbc_scraper, registrar_scraper, umbc_events_scraper
- `utils/`: food_detector, notifier
- `main.py`: Orchestrates all scrapers and saves to Supabase
