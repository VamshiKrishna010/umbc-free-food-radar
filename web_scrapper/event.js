/* event.js — UMBC Food Radar Event Detail Page */
(function () {
    const API_BASE = '/api';
    const FAVORITES_KEY = 'umbc_food_radar_favorites';

    // --- Helpers ---
    function getFavorites() {
        try { return new Set(JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]')); }
        catch { return new Set(); }
    }
    function toggleFavorite(id) {
        const fav = getFavorites();
        if (fav.has(id)) fav.delete(id); else fav.add(id);
        localStorage.setItem(FAVORITES_KEY, JSON.stringify([...fav]));
    }
    function isFavorite(id) { return getFavorites().has(id); }

    function generateIcsUrl(event) {
        const title = (event.title || 'Event').replace(/[^\w\s\-.,]/g, '');
        const desc = (event.description || '').replace(/\n/g, '\\n').slice(0, 500);
        const link = event.link || '';
        let start = new Date();
        let end = new Date(start.getTime() + 3600000);
        const d = event.date || '';
        const dm = d.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
        if (dm) {
            const y = parseInt(dm[3]) > 50 ? 1900 + parseInt(dm[3]) : 2000 + parseInt(dm[3]);
            start = new Date(y, parseInt(dm[1]) - 1, parseInt(dm[2]) || 1);
            end = new Date(start);
            end.setHours(end.getHours() + 1);
        }
        const fmt = d => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '').slice(0, 15);
        const ics = `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nDTSTART:${fmt(start)}\r\nDTEND:${fmt(end)}\r\nSUMMARY:${title}\r\nDESCRIPTION:${desc}\r\nURL:${link}\r\nEND:VEVENT\r\nEND:VCALENDAR`;
        return 'data:text/calendar;charset=utf-8,' + encodeURIComponent(ics);
    }

    // Try to extract a location from description text
    function extractLocation(description) {
        if (!description) return null;
        // Common patterns: "at [Location]", "in [Room/Building]", "Location: ..."
        const patterns = [
            /\bat\s+([A-Z][A-Za-z0-9\s,&\-\.]{3,60}(?:Hall|Center|Building|Room|Library|Stadium|Commons|Gym|Auditorium|Theater|Theatre|Lounge|Lab|Labs|Arena|Field|Park|Union|House|College|Cafe|Caf[eé]|RAC|AOK|UC|ITE|ILSB|Sondheim|Math|Physics|Chesapeake|Baltimore|UMBC)[A-Za-z0-9\s,\.]*)/i,
            /(?:^|\.\s)([A-Z][A-Za-z0-9\s,&\-\.]{2,50}(?:Hall|Room|Center|Building|Library|Commons|Gym|Arena|Stadium|Field|Union|RAC|AOK|UC|ITE|ILSB|Sondheim)[\w\s,\.]*)/m,
            /Location[:\-]\s*(.+)/i,
            /Where[:\-]\s*(.+)/i,
            /held at\s+(.+?)(?:\.|,|$)/i,
        ];
        for (const pattern of patterns) {
            const m = description.match(pattern);
            if (m && m[1]) return m[1].trim().slice(0, 100);
        }
        return null;
    }

    function showError() {
        document.getElementById('detail-loading').style.display = 'none';
        document.getElementById('detail-error').style.display = 'block';
    }

    function renderEvent(event) {
        document.title = `${event.title || 'Event'} – UMBC Food Radar`;

        const category = event.category || 'campus_event';
        const eventId = event.link || event.id || '';

        // Badge
        const badgeEl = document.getElementById('detail-badge');
        if (category === 'food_event' && event.food_keyword) {
            badgeEl.className = 'detail-badge keyword-badge';
            badgeEl.textContent = event.food_keyword.toUpperCase();
        } else if (category === 'important_date') {
            badgeEl.className = 'detail-badge date-badge';
            badgeEl.textContent = 'Important Date';
        } else {
            badgeEl.style.display = 'none';
        }

        // Source
        const sourceEl = document.getElementById('detail-source');
        sourceEl.textContent = event.source || 'UMBC';

        // Title
        document.getElementById('detail-title').textContent = event.title || 'Untitled Event';

        // --- Metadata Parsing ---
        let cleanDescription = event.description || '';
        let extractedLocation = extractLocation(cleanDescription);
        let extractedDate = event.date || 'Date TBA';

        // Often scraped descriptions dump everything: "Off Campus — Location Off Campus Date March 16... Description ..."
        // Let's systematically rip out the headers and extract.
        const descText = cleanDescription;
        
        let foundLocation = null;
        let foundDate = null;
        let foundDesc = null;

        // Extract "Location ..."
        const locRegex = /Location\s+(.*?)\s+(?=Date|Description|$)/i;
        const locMatch = descText.match(locRegex);
        if (locMatch) foundLocation = locMatch[1].trim();

        // Extract "Date ..." or "Date & Time ..."
        const dateRegex = /Date\s+(?:&\s*Time\s+)?(.*?)(?:\s+Description|\s*$)/i;
        const dateMatch = descText.match(dateRegex);
        if (dateMatch) foundDate = dateMatch[1].trim();

        // Extract "Description ..."
        const descRegex = /Description\s+(.*)/i;
        const descMatch = descText.match(descRegex);
        if (descMatch) {
            foundDesc = descMatch[1].trim();
        } else if (!locMatch && !dateMatch) {
            // If it doesn't have the explicit labels, use the raw string.
            foundDesc = cleanDescription;
        } else {
             // Fallback if it had Location/Date but missing 'Description' label for some reason
            foundDesc = cleanDescription.replace(/Location\s+.*?(?=Date|Description|$)/i, '')
                                        .replace(/Date\s+.*?(?=Description|$)/i, '')
                                        .replace(/Off Campus — /i, '')
                                        .trim();
        }

        const finalLocation = foundLocation || extractedLocation || null;
        const finalDate = foundDate || extractedDate;
        const finalDesc = foundDesc || 'No additional details available.';

        // --- DOM Population ---

        // Date
        const dateEl = document.getElementById('detail-date');
        dateEl.textContent = finalDate;

        // Location
        if (finalLocation) {
            document.getElementById('detail-location').textContent = finalLocation;
            document.getElementById('detail-location-row').style.display = 'flex';
        } else {
             document.getElementById('detail-location-row').style.display = 'none';
        }

        // Description
        const descEl = document.getElementById('detail-description');
        descEl.textContent = finalDesc;

        // External link
        const extLink = document.getElementById('detail-external-link');
        if (event.link) {
            extLink.href = event.link;
        } else {
            extLink.style.display = 'none';
        }

        // Favorite button
        const favBtn = document.getElementById('detail-fav-btn');
        if (isFavorite(eventId)) favBtn.classList.add('active');
        favBtn.addEventListener('click', () => {
            toggleFavorite(eventId);
            favBtn.classList.toggle('active');
        });

        // Calendar button
        const calBtn = document.getElementById('detail-cal-btn');
        calBtn.addEventListener('click', () => {
            const a = document.createElement('a');
            a.href = generateIcsUrl(event);
            a.download = (event.title || 'event').replace(/[^\w\s\-]/g, '').slice(0, 30) + '.ics';
            a.click();
        });

        // Share button
        const shareBtn = document.getElementById('detail-share-btn');
        shareBtn.addEventListener('click', () => {
            const url = window.location.href;
            const text = `${event.title || 'Event'} – ${finalDate}`;
            if (navigator.share) {
                navigator.share({ title: event.title, text, url }).catch(() => { });
            } else {
                navigator.clipboard.writeText(url).then(() => {
                    shareBtn.textContent = 'Copied!';
                    setTimeout(() => shareBtn.textContent = 'Share', 1500);
                });
            }
        });

        // Show content
        document.getElementById('detail-loading').style.display = 'none';
        document.getElementById('detail-content').style.display = 'block';
    }

    // --- Main: parse ID from URL and fetch ---
    async function init() {
        const params = new URLSearchParams(window.location.search);
        const rawId = params.get('id');

        if (!rawId) { showError(); return; }

        const eventId = decodeURIComponent(rawId);

        // First try sessionStorage cache (set by main page before navigating)
        const cached = sessionStorage.getItem('umbc_event_detail');
        if (cached) {
            try {
                const ev = JSON.parse(cached);
                if ((ev.link || ev.id || '') === eventId) {
                    renderEvent(ev);
                    return;
                }
            } catch (_) { }
        }

        // Fetch from Supabase by matching link or id column
        try {
            const url = `${API_BASE}/events?id=${encodeURIComponent(eventId)}`;
            const response = await fetch(url, {
                cache: 'no-store',
            });
            if (!response.ok) throw new Error('Fetch failed');
            const data = await response.json();
            if (!data || data.length === 0) throw new Error('Not found');
            renderEvent(data[0]);
        } catch (err) {
            console.error('Could not load event:', err);
            showError();
        }
    }

    document.addEventListener('DOMContentLoaded', init);
})();
