document.addEventListener('DOMContentLoaded', () => {
    const eventsGrid = document.getElementById('events-grid');
    const searchInput = document.getElementById('searchInput');
    const tabBtns = document.querySelectorAll('.tab-btn');
    const sourceFilterEl = document.getElementById('source-filter');
    const lastUpdatedEl = document.getElementById('last-updated');
    const pullIndicator = document.getElementById('pull-indicator');
    const dateRangeEl = document.getElementById('date-range-filter');
    let allEvents = [];
    let activeTab = 'important_date';
    let selectedSource = 'all';
    let selectedDateRange = 'all';

    const FAVORITES_KEY = 'umbc_food_radar_favorites';
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
    let lastFetchTime = null;
    let touchStartY = 0;

    const SUPABASE_URL = 'https://thphtswaxlzpcipklhuy.supabase.co';
    const SUPABASE_KEY = 'sb_publishable_Dat2eljf5Zp07VSSjhzTDw_oOc6WOFD';

    function parseDateForSort(str) {
        if (!str) return Infinity;
        const s = String(str).toLowerCase();
        const months = { jan:0,feb:1,mar:2,apr:3,may:4,jun:5,jul:6,aug:7,sep:8,oct:9,nov:10,dec:11 };
        const m = s.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
        if (m) return new Date(parseInt(m[3]) > 50 ? 1900 + parseInt(m[3]) : 2000 + parseInt(m[3]), parseInt(m[1]) - 1, parseInt(m[2])).getTime();
        const m2 = s.match(/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})/i);
        if (m2) {
            const yr = (s.match(/\d{4}/) || [String(new Date().getFullYear())])[0];
            return new Date(parseInt(yr), months[m2[1].toLowerCase().slice(0,3)] || 0, parseInt(m2[2]) || 1).getTime();
        }
        const m3 = s.match(/(\d{1,2}):(\d{2})\s*(am|pm)?/i);
        if (m3) return Date.now();
        if (/ongoing|tba|check|every/i.test(s)) return 0;
        return Date.now();
    }

    function sortByDate(events) {
        return [...events].sort((a, b) => {
            const ta = parseDateForSort(a.date);
            const tb = parseDateForSort(b.date);
            if (ta === 0 && tb === 0) return 0;
            if (ta === 0) return 1;
            if (tb === 0) return -1;
            return ta - tb;
        });
    }

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

    function showSkeleton() {
        eventsGrid.innerHTML = '';
        for (let i = 0; i < 6; i++) {
            const sk = document.createElement('div');
            sk.className = 'skeleton-card';
            sk.innerHTML = '<div class="skeleton-line short"></div><div class="skeleton-line long"></div><div class="skeleton-line medium"></div>';
            eventsGrid.appendChild(sk);
        }
    }

    async function fetchEvents(showLoading = true) {
        if (showLoading) showSkeleton();
        try {
            const response = await fetch(`${SUPABASE_URL}/rest/v1/events?select=*`, {
                headers: { 'apikey': SUPABASE_KEY, 'Authorization': `Bearer ${SUPABASE_KEY}` }
            });
            if (!response.ok) throw new Error(`Failed to fetch: ${response.statusText}`);
            allEvents = await response.json();
            lastFetchTime = Date.now();
            updateLastUpdated();
            renderTabContent();
            updateTabBadges();
            renderSourceFilter();
        } catch (error) {
            console.error('Error:', error);
            eventsGrid.innerHTML = `<div class="loading">Error loading events: ${error.message}</div>`;
        }
    }

    function updateLastUpdated() {
        if (!lastUpdatedEl) return;
        lastUpdatedEl.textContent = 'Updated just now';
        lastUpdatedEl.style.opacity = '1';
        if (window._lastUpdatedInterval) clearInterval(window._lastUpdatedInterval);
        window._lastUpdatedInterval = setInterval(() => {
            if (!lastFetchTime) return;
            const mins = Math.floor((Date.now() - lastFetchTime) / 60000);
            lastUpdatedEl.textContent = mins < 1 ? 'Updated just now' : mins === 1 ? 'Updated 1 min ago' : `Updated ${mins} min ago`;
        }, 60000);
    }

    function getCategoryCounts() {
        return {
            important_date: allEvents.filter(e => (e.category || '') === 'important_date').length,
            food_event: allEvents.filter(e => (e.category || '') === 'food_event').length,
            campus_event: allEvents.filter(e => (e.category || '') === 'campus_event').length,
            favorites: getFavorites().size,
        };
    }

    function updateTabBadges() {
        const counts = getCategoryCounts();
        tabBtns.forEach(btn => {
            const tab = btn.dataset.tab;
            const n = counts[tab] ?? 0;
            let badge = btn.querySelector('.tab-badge');
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'tab-badge';
                btn.appendChild(badge);
            }
            badge.textContent = n;
        });
    }

    function getUniqueSources(category) {
        const list = allEvents.filter(e => (e.category || '') === category);
        const sources = [...new Set(list.map(e => e.source || 'Other').filter(Boolean))];
        return sources.sort();
    }

    function renderSourceFilter() {
        if (!sourceFilterEl) return;
        if (activeTab === 'favorites') {
            sourceFilterEl.style.display = 'none';
            return;
        }
        const sources = ['all', ...getUniqueSources(activeTab)];
        sourceFilterEl.innerHTML = '';
        sourceFilterEl.style.display = sources.length <= 1 ? 'none' : 'flex';
        sources.forEach(src => {
            const chip = document.createElement('button');
            chip.className = 'source-chip' + (selectedSource === src ? ' active' : '');
            chip.textContent = src === 'all' ? 'All' : src;
            chip.dataset.source = src;
            chip.addEventListener('click', () => {
                selectedSource = src;
                sourceFilterEl.querySelectorAll('.source-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                renderTabContent();
            });
            sourceFilterEl.appendChild(chip);
        });
    }

    function truncateText(text, maxLength = 120) {
        if (!text) return '';
        return text.length <= maxLength ? text : text.substr(0, maxLength) + '...';
    }

    function getFilteredEvents() {
        const term = (searchInput?.value || '').toLowerCase();
        let list = activeTab === 'favorites'
            ? allEvents.filter(e => isFavorite(e.link || e.id))
            : allEvents.filter(e => (e.category || 'campus_event') === activeTab);
        if (selectedSource !== 'all' && activeTab !== 'favorites') {
            list = list.filter(e => (e.source || 'Other') === selectedSource);
        }
        if (term) {
            list = list.filter(e => {
                const t = (e.title || '').toLowerCase();
                const d = (e.description || '').toLowerCase();
                const k = (e.food_keyword || '').toLowerCase();
                const s = (e.source || '').toLowerCase();
                return t.includes(term) || d.includes(term) || k.includes(term) || s.includes(term);
            });
        }
        if (selectedDateRange !== 'all') {
            const now = Date.now();
            const day = 86400000;
            let max = now + 7 * day;
            if (selectedDateRange === 'week') max = now + 7 * day;
            else if (selectedDateRange === '7days') max = now + 7 * day;
            else if (selectedDateRange === 'month') max = now + 30 * day;
            list = list.filter(e => {
                const t = parseDateForSort(e.date);
                return t > 0 && t < Infinity && t <= max;
            });
        }
        return sortByDate(list);
    }

    function renderTabContent() {
        const events = getFilteredEvents();
        eventsGrid.innerHTML = '';

        if (events.length === 0) {
            const msgs = {
                important_date: 'No important dates loaded yet.',
                food_event: 'No free food events spotted. Keep the radar on!',
                campus_event: 'No campus events match your search.',
                favorites: 'No favorites yet. Click the heart on any event to save it!',
            };
            eventsGrid.innerHTML = `<div class="no-results">${msgs[activeTab] || 'No events.'}</div>`;
            return;
        }

        events.forEach((event, index) => {
            const wrapper = document.createElement('div');
            wrapper.className = 'event-card-wrapper';
            const category = event.category || 'campus_event';
            const desc = truncateText(event.description);
            const foodKeyword = event.food_keyword || '';
            let badge = '';
            if (category === 'important_date') {
                badge = `<span class="date-badge">${event.source || 'Registrar'}</span>`;
            } else if (category === 'food_event' && foodKeyword) {
                badge = `<span class="keyword-badge">${foodKeyword.toUpperCase()}</span>`;
            } else {
                badge = `<span class="source-badge">${event.source || 'Event'}</span>`;
            }
            const addCalUrl = generateIcsUrl(event);
            const safeTitle = (event.title || 'event').replace(/[^\w\s\-]/g, '').slice(0, 30);
            const eventId = event.link || event.id || '';
            const fav = isFavorite(eventId);
            wrapper.innerHTML = `
                <div class="event-card" style="animation: fadeUp 0.5s ease backwards ${index * 0.08}s">
                    <div class="event-card-header">
                        <a href="${event.link || '#'}" target="_blank" rel="noopener" class="event-card-link">
                            <div class="event-date">${event.date || 'TBA'}</div>
                            <h2 class="event-title">${event.title || 'Untitled'}</h2>
                            <div class="event-desc">${desc}</div>
                        </a>
                        <button type="button" class="fav-btn ${fav ? 'active' : ''}" title="${fav ? 'Remove from favorites' : 'Add to favorites'}">♥</button>
                    </div>
                    <div class="event-footer">
                        ${badge}
                        <div class="event-actions">
                            <button type="button" class="share-btn" title="Share">Share</button>
                            <button type="button" class="add-cal-btn" title="Add to calendar">+ Cal</button>
                            <a href="${event.link || '#'}" target="_blank" rel="noopener" class="card-link-icon">↗</a>
                        </div>
                    </div>
                </div>
            `;
            const favBtn = wrapper.querySelector('.fav-btn');
            favBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                toggleFavorite(eventId);
                favBtn.classList.toggle('active');
                if (activeTab === 'favorites') renderTabContent();
                updateTabBadges();
            });
            const shareBtn = wrapper.querySelector('.share-btn');
            shareBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const text = `${event.title || 'Event'} - ${event.date || ''}`;
                const url = event.link || window.location.href;
                if (navigator.share) {
                    navigator.share({ title: event.title, text, url }).catch(() => {});
                } else {
                    navigator.clipboard.writeText(url).then(() => { shareBtn.textContent = 'Copied!'; setTimeout(() => shareBtn.textContent = 'Share', 1500); });
                }
            });
            const calBtn = wrapper.querySelector('.add-cal-btn');
            calBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const a = document.createElement('a');
                a.href = addCalUrl;
                a.download = safeTitle + '.ics';
                a.click();
            });
            eventsGrid.appendChild(wrapper);
        });
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeTab = btn.dataset.tab;
            selectedSource = 'all';
            renderSourceFilter();
            renderTabContent();
        });
    });

    searchInput?.addEventListener('input', () => renderTabContent());
    dateRangeEl?.addEventListener('change', (e) => {
        selectedDateRange = e.target.value;
        renderTabContent();
    });

    function setupPullToRefresh() {
        if (!pullIndicator) return;
        document.addEventListener('touchstart', e => { touchStartY = e.touches[0].clientY; }, { passive: true });
        document.addEventListener('touchmove', e => {
            if (window.scrollY === 0 && e.touches[0].clientY - touchStartY > 80) {
                pullIndicator.classList.add('visible');
            }
        }, { passive: true });
        document.addEventListener('touchend', () => {
            if (pullIndicator.classList.contains('visible')) {
                pullIndicator.classList.add('refreshing');
                fetchEvents(false).finally(() => {
                    pullIndicator.classList.remove('visible', 'refreshing');
                });
            } else {
                pullIndicator.classList.remove('visible', 'refreshing');
            }
        }, { passive: true });
    }
    setupPullToRefresh();

    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes shimmer { 0% { background-position: -200% 0; } 100% { background-position: 200% 0; } }
    `;
    document.head.appendChild(style);

    fetchEvents();
});
