document.addEventListener('DOMContentLoaded', () => {
    const eventsGrid = document.getElementById('events-grid');
    const searchInput = document.getElementById('searchInput');
    let allEvents = [];

    // Supabase credentials
    const SUPABASE_URL = 'https://thphtswaxlzpcipklhuy.supabase.co';
    const SUPABASE_KEY = 'sb_publishable_Dat2eljf5Zp07VSSjhzTDw_oOc6WOFD';

    // Fetch events directly from Supabase REST API
    async function fetchEvents() {
        try {
            const response = await fetch(`${SUPABASE_URL}/rest/v1/events?select=*`, {
                headers: {
                    'apikey': SUPABASE_KEY,
                    'Authorization': `Bearer ${SUPABASE_KEY}`
                }
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch events: ${response.statusText}`);
            }

            allEvents = await response.json();

            // Temporary check for empty data while testing
            if (allEvents.length === 0) {
                eventsGrid.innerHTML = '<div class="no-results">No free food events spotted on campus yet. Keep the radar on!</div>';
                return;
            }

            renderEvents(allEvents);
        } catch (error) {
            console.error('Error:', error);
            eventsGrid.innerHTML = `<div class="loading">Error loading events: ${error.message}</div>`;
        }
    }

    // Function to truncate text nicely
    function truncateText(text, maxLength = 120) {
        if (!text) return '';
        if (text.length <= maxLength) return text;
        return text.substr(0, maxLength) + '...';
    }

    // Render events to the grid
    function renderEvents(eventsToRender) {
        eventsGrid.innerHTML = ''; // Clear current

        if (eventsToRender.length === 0) {
            eventsGrid.innerHTML = '<div class="no-results">No events match your search. Try different keywords!</div>';
            return;
        }

        eventsToRender.forEach((event, index) => {
            // Create the card element
            const card = document.createElement('a');
            card.href = event.link || '#';
            card.target = '_blank';
            card.className = 'event-card';

            // Staggered animation delay for rendering
            card.style.animation = `fadeUp 0.5s ease backwards ${index * 0.1}s`;

            // Clean up description
            const desc = truncateText(event.description);
            const foodKeyword = event.food_keyword || 'free food';

            card.innerHTML = `
                <div class="event-date">${event.date || 'TBA'}</div>
                <h2 class="event-title">${event.title || 'Untitled Event'}</h2>
                <div class="event-desc">${desc}</div>
                <div class="event-footer">
                    <span class="keyword-badge">Contains: ${foodKeyword.toUpperCase()}</span>
                    <div class="card-link-icon">↗</div>
                </div>
            `;

            eventsGrid.appendChild(card);
        });
    }

    // Dynamic Search Filtering
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();

        const filtered = allEvents.filter(event => {
            const titleMatch = (event.title || '').toLowerCase().includes(searchTerm);
            const descMatch = (event.description || '').toLowerCase().includes(searchTerm);
            const keywordMatch = (event.food_keyword || '').toLowerCase().includes(searchTerm);

            return titleMatch || descMatch || keywordMatch;
        });

        renderEvents(filtered);
    });

    // Add animation styles dynamically
    const style = document.createElement('style');
    style.textContent = `
        @keyframes fadeUp {
            from {
                opacity: 0;
                transform: translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
    `;
    document.head.appendChild(style);

    // Initial fetch
    fetchEvents();
});
