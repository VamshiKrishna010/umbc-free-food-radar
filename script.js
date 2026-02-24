document.addEventListener('DOMContentLoaded', () => {
    const eventsGrid = document.getElementById('events-grid');
    const searchInput = document.getElementById('searchInput');
    const tabBtns = document.querySelectorAll('.tab-btn');
    let allEvents = [];
    let activeTab = 'important_date';

    const SUPABASE_URL = 'https://thphtswaxlzpcipklhuy.supabase.co';
    const SUPABASE_KEY = 'sb_publishable_Dat2eljf5Zp07VSSjhzTDw_oOc6WOFD';

    async function fetchEvents() {
        try {
            const response = await fetch(`${SUPABASE_URL}/rest/v1/events?select=*`, {
                headers: {
                    'apikey': SUPABASE_KEY,
                    'Authorization': `Bearer ${SUPABASE_KEY}`
                }
            });
            if (!response.ok) throw new Error(`Failed to fetch: ${response.statusText}`);
            allEvents = await response.json();
            renderTabContent();
        } catch (error) {
            console.error('Error:', error);
            eventsGrid.innerHTML = `<div class="loading">Error loading events: ${error.message}</div>`;
        }
    }

    function truncateText(text, maxLength = 120) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }

    function getFilteredEvents() {
        const term = (searchInput?.value || '').toLowerCase();
        let list = allEvents.filter(e => (e.category || 'campus_event') === activeTab);
        if (term) {
            list = list.filter(e => {
                const t = (e.title || '').toLowerCase();
                const d = (e.description || '').toLowerCase();
                const k = (e.food_keyword || '').toLowerCase();
                const s = (e.source || '').toLowerCase();
                return t.includes(term) || d.includes(term) || k.includes(term) || s.includes(term);
            });
        }
        return list;
    }

    function renderTabContent() {
        const events = getFilteredEvents();
        eventsGrid.innerHTML = '';

        if (events.length === 0) {
            const msgs = {
                important_date: 'No important dates loaded yet.',
                food_event: 'No free food events spotted. Keep the radar on!',
                campus_event: 'No campus events match your search.'
            };
            eventsGrid.innerHTML = `<div class="no-results">${msgs[activeTab] || 'No events.'}</div>`;
            return;
        }

        events.forEach((event, index) => {
            const card = document.createElement('a');
            card.href = event.link || '#';
            card.target = '_blank';
            card.className = 'event-card';
            card.style.animation = `fadeUp 0.5s ease backwards ${index * 0.08}s`;

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

            card.innerHTML = `
                <div class="event-date">${event.date || 'TBA'}</div>
                <h2 class="event-title">${event.title || 'Untitled'}</h2>
                <div class="event-desc">${desc}</div>
                <div class="event-footer">
                    ${badge}
                    <div class="card-link-icon">↗</div>
                </div>
            `;
            eventsGrid.appendChild(card);
        });
    }

    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeTab = btn.dataset.tab;
            renderTabContent();
        });
    });

    searchInput?.addEventListener('input', () => renderTabContent());

    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);

    fetchEvents();
});
