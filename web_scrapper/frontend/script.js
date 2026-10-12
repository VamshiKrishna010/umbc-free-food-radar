/**
 * UMBC Food Radar - Redesigned Production Application Logic
 * Integrates live Supabase data, date engine, responsive drawer, side rail, and PWA caching.
 */

(function () {
  'use strict';

  // --- Constants & Config ---
  const API_URL = '/api/events';
  const STORAGE_KEY_SAVED = 'umbc_food_radar_favorites';
  const STORAGE_KEY_THEME = 'umbc_food_radar_theme';
  const STORAGE_KEY_CACHE = 'umbc_food_radar_cache_v2';
  const MIN = 60000;
  const HOUR = 3600000;
  const DAY = 86400000;

  // --- URL & Session State ---
  const urlParams = new URLSearchParams(window.location.search);
  let activeView = urlParams.get('view') || 'food'; // 'food' | 'events' | 'deadlines' | 'saved'
  let activeTheme = localStorage.getItem(STORAGE_KEY_THEME) || urlParams.get('theme') || 'light';
  let openEventId = urlParams.get('open') || null;
  let activeDateFilter = urlParams.get('when') || 'upcoming'; // 'upcoming' | 'today' | 'tomorrow' | 'week' | YYYY-MM-DD
  let selectedSources = new Set();
  let showSourcesPopover = false;
  let showDatePopover = false;
  let freeFoodOnlyFilter = false;
  let searchQuery = '';
  let calendarMonthOffset = 0; // 0 = current month
  let lastFetchTime = null;

  // Raw and processed events
  let allEvents = [];
  let savedEventIds = new Set();

  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY_SAVED) || '[]');
    savedEventIds = new Set(Array.isArray(stored) ? stored : []);
  } catch (e) {
    savedEventIds = new Set();
  }

  // Set initial theme
  document.documentElement.dataset.theme = activeTheme;

  // --- Utility Functions ---
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = (id, cls = '') => `<svg class="icon ${cls}" aria-hidden="true"><use href="#i-${id}"/></svg>`;
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dayDiff = (d, base = new Date()) => Math.round((startOfDay(d) - startOfDay(base)) / DAY);

  const hm = (d) => {
    let h = d.getHours();
    const m = d.getMinutes();
    const ap = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    return { t: m ? `${h}:${String(m).padStart(2, '0')}` : `${h}:00`, ap };
  };

  const timeStr = (d) => {
    const x = hm(d);
    return `${x.t} ${x.ap}`;
  };

  const weekday = (d) => d.toLocaleDateString('en-US', { weekday: 'long' });
  const longDate = (d) => d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  const shortDate = (d) => d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
  const dayName = (d, base = new Date()) => {
    const n = dayDiff(d, base);
    return n === 0 ? 'Today' : n === 1 ? 'Tomorrow' : n === -1 ? 'Yesterday' : weekday(d);
  };

  const dur = (mins) => {
    if (mins < 60) return `${mins} min`;
    const h = Math.floor(mins / 60);
    const m = mins % 60;
    return `${h} hr${m ? ` ${m} min` : ''}`;
  };

  function updateUrlParams() {
    const q = new URLSearchParams();
    if (activeView !== 'food') q.set('view', activeView);
    if (activeTheme !== 'light') q.set('theme', activeTheme);
    if (openEventId) q.set('open', openEventId);
    if (activeDateFilter !== 'upcoming') q.set('when', activeDateFilter);
    const newSearch = q.toString() ? `?${q.toString()}` : window.location.pathname;
    window.history.replaceState({}, '', newSearch);
  }

  function toggleSaveEvent(id, ev) {
    if (ev) ev.stopPropagation();
    if (savedEventIds.has(id)) {
      savedEventIds.delete(id);
      showToast('Removed from saved items');
    } else {
      savedEventIds.add(id);
      showToast('Saved to your bookmarks');
    }
    localStorage.setItem(STORAGE_KEY_SAVED, JSON.stringify([...savedEventIds]));
    renderApp();
  }

  function toggleTheme() {
    activeTheme = activeTheme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = activeTheme;
    localStorage.setItem(STORAGE_KEY_THEME, activeTheme);
    document.getElementById('themeBtn').innerHTML = icon(activeTheme === 'dark' ? 'sun' : 'moon');
    updateUrlParams();
  }

  function showToast(msg) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();
    const t = document.createElement('div');
    t.className = 'toast';
    t.innerHTML = `${icon('check', 'icon-sm')}<span>${esc(msg)}</span>`;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2800);
  }

  // --- Date & Content Normalization Engine ---
  const FOOD_KEYWORDS_MAP = [
    'pizza', 'cookies', 'coffee', 'tea', 'bagels', 'tacos', 'pancakes', 'popcorn',
    'candy', 'donuts', 'soda', 'snacks', 'groceries', 'produce', 'lunch', 'breakfast',
    'samosa', 'burrito', 'ice cream', 'bbq', 'refreshments'
  ];

  function extractFoodItems(text, keyword) {
    const found = new Set();
    const combined = `${keyword || ''} ${text || ''}`.toLowerCase();
    for (const item of FOOD_KEYWORDS_MAP) {
      if (combined.includes(item)) {
        found.add(item.charAt(0).toUpperCase() + item.slice(1));
      }
    }
    if (found.size === 0 && keyword) {
      found.add(keyword.charAt(0).toUpperCase() + keyword.slice(1));
    }
    return [...found];
  }

  function extractLocation(text, rawLocation) {
    if (rawLocation && rawLocation.trim()) return rawLocation.trim();
    if (!text) return 'UMBC Campus';
    const locMatch = text.match(/\b(ITE \d+|RAC \d+|Commons [A-Za-z0-9 ]+|Skylight Room|AOK Library[A-Za-z0-9, ]*|Lecture Hall \d+|Physics \d+|Math & Psychology \d+|University Center \d+|Retriever Activities Center)\b/i);
    if (locMatch) return locMatch[1].trim();
    return 'UMBC Campus';
  }

  function parseEventDate(rawDateStr) {
    if (!rawDateStr) return { start: null, end: null, kind: 'ongoing', recurrence_text: 'Check website for times' };
    const s = String(rawDateStr).trim();

    if (/ongoing|tba|check rac/i.test(s)) {
      return { start: null, end: null, kind: 'ongoing', recurrence_text: s };
    }
    if (/every (monday|tuesday|wednesday|thursday|friday|saturday|sunday)/i.test(s)) {
      return { start: null, end: null, kind: 'recurring', recurrence_text: s };
    }

    // Standard date parsing
    const now = new Date();
    let start = null;
    let end = null;
    let kind = 'one_time';

    // 1. Try ISO or native parse
    const isoTry = new Date(s);
    if (!isNaN(isoTry.getTime()) && s.length > 9 && s.includes('-')) {
      start = isoTry;
      end = new Date(start.getTime() + HOUR);
      return { start, end, kind, recurrence_text: null };
    }

    // 2. Format: MM/DD/YYYY or MM/DD/YY
    const slashMatch = s.match(/(\d{1,2})\/(\d{1,2})\/(\d{2,4})/);
    if (slashMatch) {
      const yrRaw = parseInt(slashMatch[3], 10);
      const yr = yrRaw < 100 ? (yrRaw > 50 ? 1900 + yrRaw : 2000 + yrRaw) : yrRaw;
      const mo = parseInt(slashMatch[1], 10) - 1;
      const day = parseInt(slashMatch[2], 10);
      start = new Date(yr, mo, day);

      // Check for time: e.g. 2:15 PM
      const timeMatch = s.match(/(\d{1,2}):(\d{2})\s*(am|pm)/i);
      if (timeMatch) {
        let hrs = parseInt(timeMatch[1], 10);
        const mins = parseInt(timeMatch[2], 10);
        const ap = timeMatch[3].toLowerCase();
        if (ap === 'pm' && hrs < 12) hrs += 12;
        if (ap === 'am' && hrs === 12) hrs = 0;
        start.setHours(hrs, mins, 0, 0);
      } else {
        start.setHours(9, 0, 0, 0);
      }
      end = new Date(start.getTime() + HOUR);
      return { start, end, kind, recurrence_text: null };
    }

    // 3. Format: Month Name Day, e.g. "Oct 12, 2026 12:00 PM - 1:30 PM"
    const monthNames = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 };
    const monthMatch = s.match(/(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:,?\s*(\d{4}))?/i);
    if (monthMatch) {
      const mo = monthNames[monthMatch[1].toLowerCase().slice(0, 3)];
      const day = parseInt(monthMatch[2], 10);
      const yr = monthMatch[3] ? parseInt(monthMatch[3], 10) : now.getFullYear();
      start = new Date(yr, mo, day);

      const timeMatches = [...s.matchAll(/(\d{1,2})(?::(\d{2}))?\s*(am|pm)/gi)];
      if (timeMatches.length > 0) {
        let hrs = parseInt(timeMatches[0][1], 10);
        const mins = parseInt(timeMatches[0][2] || '0', 10);
        const ap = timeMatches[0][3].toLowerCase();
        if (ap === 'pm' && hrs < 12) hrs += 12;
        if (ap === 'am' && hrs === 12) hrs = 0;
        start.setHours(hrs, mins, 0, 0);

        if (timeMatches.length > 1) {
          let eHrs = parseInt(timeMatches[1][1], 10);
          const eMins = parseInt(timeMatches[1][2] || '0', 10);
          const eAp = timeMatches[1][3].toLowerCase();
          if (eAp === 'pm' && eHrs < 12) eHrs += 12;
          if (eAp === 'am' && eHrs === 12) eHrs = 0;
          end = new Date(yr, mo, day, eHrs, eMins, 0, 0);
        }
      }
      if (!end) end = new Date(start.getTime() + HOUR);
      return { start, end, kind, recurrence_text: null };
    }

    return { start: null, end: null, kind: 'ongoing', recurrence_text: s };
  }

  function normalizeEvent(item) {
    const rawDate = item.date || item.start_at || '';
    const dateParsed = parseEventDate(rawDate);
    const textAll = `${item.title || ''} ${item.description || ''}`;
    const foodItems = extractFoodItems(textAll, item.food_keyword);
    const location = extractLocation(item.description, item.location);

    return {
      id: item.id || item.link || String(Math.random()),
      category: item.category || 'campus_event',
      source: item.source || 'UMBC Campus',
      title: item.title || 'Untitled Event',
      description: item.description || '',
      link: item.link || 'https://my.umbc.edu',
      location: location,
      food_keyword: item.food_keyword || (foodItems.length ? foodItems[0] : ''),
      food_items: foodItems,
      start: dateParsed.start,
      end: dateParsed.end,
      kind: dateParsed.kind,
      recurrence_text: dateParsed.recurrence_text,
      event_type: item.event_type || (item.category === 'important_date' ? 'Deadline' : 'Campus Event'),
      updated_at: item.updated_at || null,
    };
  }

  // --- Data Fetching ---
  async function loadData() {
    const appEl = document.getElementById('app');
    const freshnessEl = document.getElementById('freshness');
    freshnessEl.textContent = 'Checking campus...';

    // Show skeleton view immediately
    appEl.innerHTML = renderSkeleton();

    try {
      const res = await fetch(API_URL, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      allEvents = (Array.isArray(data) ? data : []).map(normalizeEvent);
      lastFetchTime = new Date();
      localStorage.setItem(STORAGE_KEY_CACHE, JSON.stringify(allEvents));
      updateFreshnessLabel();
    } catch (err) {
      console.warn('API fetch failed, reading from cache:', err);
      try {
        const cached = JSON.parse(localStorage.getItem(STORAGE_KEY_CACHE) || '[]');
        if (cached && cached.length) {
          allEvents = cached.map((e) => ({
            ...e,
            start: e.start ? new Date(e.start) : null,
            end: e.end ? new Date(e.end) : null,
          }));
          freshnessEl.textContent = 'Offline (cached data)';
        } else {
          freshnessEl.textContent = 'Could not load data';
        }
      } catch (e) {
        freshnessEl.textContent = 'Offline';
      }
    }

    renderApp();
  }

  function updateFreshnessLabel() {
    const el = document.getElementById('freshness');
    if (!el || !lastFetchTime) return;
    const diffMins = Math.round((new Date() - lastFetchTime) / MIN);
    if (diffMins <= 1) el.textContent = 'Updated just now';
    else el.textContent = `Updated ${diffMins} min ago`;
  }
  setInterval(updateFreshnessLabel, 60000);

  // --- Filtering & Selection ---
  function getFilteredEvents() {
    const now = new Date();
    const query = searchQuery.trim().toLowerCase();

    return allEvents.filter((e) => {
      // 1. View / Category Match
      if (activeView === 'food') {
        if (e.category !== 'food_event') return false;
      } else if (activeView === 'events') {
        if (e.category !== 'campus_event') return false;
        if (freeFoodOnlyFilter && (!e.food_items || e.food_items.length === 0)) return false;
      } else if (activeView === 'deadlines') {
        if (e.category !== 'important_date') return false;
      } else if (activeView === 'saved') {
        if (!savedEventIds.has(e.id)) return false;
      }

      // 2. Source filter
      if (selectedSources.size > 0 && !selectedSources.has(e.source)) {
        return false;
      }

      // 3. Search query
      if (query) {
        const matchTitle = e.title.toLowerCase().includes(query);
        const matchDesc = e.description.toLowerCase().includes(query);
        const matchLoc = e.location.toLowerCase().includes(query);
        const matchSrc = e.source.toLowerCase().includes(query);
        const matchFood = (e.food_items || []).some((f) => f.toLowerCase().includes(query));
        if (!matchTitle && !matchDesc && !matchLoc && !matchSrc && !matchFood) return false;
      }

      // 4. Date filter (When)
      if (activeDateFilter !== 'upcoming' && e.start) {
        const nDays = dayDiff(e.start, now);
        if (activeDateFilter === 'today' && nDays !== 0) return false;
        if (activeDateFilter === 'tomorrow' && nDays !== 1) return false;
        if (activeDateFilter === 'week' && (nDays < 0 || nDays > 7)) return false;
        if (activeDateFilter.startsWith('20') && e.start.toISOString().slice(0, 10) !== activeDateFilter) {
          return false;
        }
      }

      return true;
    });
  }

  // --- Calendar Export (.ics & Google) ---
  function exportIcsFile(ev) {
    const title = (ev.title || 'Event').replace(/[^\w\s\-.,]/g, '');
    const desc = (ev.description || '').replace(/\n/g, '\\n').slice(0, 600);
    const loc = (ev.location || 'UMBC').replace(/[^\w\s\-.,]/g, '');
    const now = new Date();
    const start = ev.start || now;
    const end = ev.end || new Date(start.getTime() + HOUR);
    const fmt = (d) => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '').slice(0, 15);
    const icsContent = [
      'BEGIN:VCALENDAR',
      'VERSION:2.0',
      'PRODID:-//UMBC Food Radar//EN',
      'BEGIN:VEVENT',
      `UID:${ev.id}@foodradar.umbc`,
      `DTSTAMP:${fmt(now)}`,
      `DTSTART:${fmt(start)}`,
      `DTEND:${fmt(end)}`,
      `SUMMARY:${title}`,
      `LOCATION:${loc}`,
      `DESCRIPTION:${desc}\\n\\nOriginal link: ${ev.link}`,
      'END:VEVENT',
      'END:VCALENDAR',
    ].join('\r\n');

    const blob = new Blob([icsContent], { type: 'text/calendar;charset=utf-8' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${title.slice(0, 30).toLowerCase().replace(/\s+/g, '_')}.ics`;
    link.click();
    showToast('Downloaded calendar file (.ics)');
  }

  function getGoogleCalendarUrl(ev) {
    const title = encodeURIComponent(ev.title || 'Event');
    const desc = encodeURIComponent(`${ev.description || ''}\n\nLink: ${ev.link || ''}`);
    const loc = encodeURIComponent(ev.location || 'UMBC');
    const start = ev.start || new Date();
    const end = ev.end || new Date(start.getTime() + HOUR);
    const fmt = (d) => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '').slice(0, 15) + 'Z';
    return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${fmt(start)}/${fmt(end)}&details=${desc}&location=${loc}`;
  }

  // --- Rendering Functions ---

  function renderSkeleton() {
    return `
      <section class="now-band">
        <div class="wrap">
          <div class="now-head">
            <h1>Free food right now</h1>
            <p>Scanning campus listings...</p>
          </div>
          <div class="now-cards">
            ${[1, 2, 3].map(() => `<div class="now-card skeleton" style="height:160px;opacity:.8;"></div>`).join('')}
          </div>
        </div>
      </section>
      <div class="wrap page">
        <main>
          <div style="margin-top:24px;">
            ${[1, 2, 3].map(() => `
              <div class="skeleton" style="height:26px;width:180px;margin-bottom:12px;"></div>
              <div class="skeleton" style="height:70px;margin-bottom:12px;"></div>
              <div class="skeleton" style="height:70px;margin-bottom:24px;"></div>
            `).join('')}
          </div>
        </main>
      </div>
    `;
  }

  function renderNowBand(eventsList) {
    const now = new Date();
    const foodOneTime = eventsList.filter((e) => e.category === 'food_event' && e.kind === 'one_time' && e.start);

    const live = foodOneTime.filter((e) => e.start <= now && e.end && now < e.end);
    const soon = foodOneTime.filter((e) => e.start > now && (e.start - now) <= 90 * MIN).sort((a, b) => a.start - b.start);
    const upcoming = foodOneTime.filter((e) => e.start > now && !soon.includes(e)).sort((a, b) => a.start - b.start);

    const cards = [...live, ...soon, ...upcoming].slice(0, 3);
    const isQuiet = live.length === 0 && soon.length === 0;

    let subText = 'Nothing is currently serving. Check upcoming listings below.';
    if (live.length > 0 && soon.length > 0) {
      subText = `${live.length} serving now, ${soon.length} starting within the hour.`;
    } else if (live.length > 0) {
      subText = `${live.length} serving right now. Arrive early while food lasts.`;
    } else if (soon.length > 0) {
      subText = `${soon.length} starting soon.`;
    }

    return `
      <section class="now-band ${isQuiet && cards.length === 0 ? 'quiet' : ''}" aria-labelledby="nowTitle">
        <div class="wrap">
          <div class="now-head">
            <h1 id="nowTitle">Free food right now</h1>
            <p>${subText}</p>
            <span class="clock">${icon('clock', 'icon-sm')} As of ${timeStr(now)}</span>
          </div>
          <div class="now-cards">
            ${cards.map((e) => {
              const isEventLive = e.start <= now && e.end && now < e.end;
              if (isEventLive) {
                const minsLeft = Math.max(0, Math.round((e.end - now) / MIN));
                const totalDur = Math.max(1, (e.end - e.start));
                const pctElapsed = Math.min(100, Math.max(0, ((now - e.start) / totalDur) * 100));
                return `
                  <div class="now-card" role="button" tabindex="0" onclick="window.app.openEvent('${e.id}')">
                    <span class="status"><span class="dot pulse"></span>Serving now</span>
                    <span class="remaining">${dur(minsLeft).replace(/ (min|hr)/, '<small>$1</small>')}<small>left</small></span>
                    <h3>${esc(e.title)}</h3>
                    <span class="where">${icon('pin', 'icon-sm')}${esc(e.location)}</span>
                    <div class="progress" aria-label="${Math.round(pctElapsed)}% elapsed"><span style="width:${pctElapsed}%"></span></div>
                  </div>
                `;
              }
              const minsToStart = Math.max(0, Math.round((e.start - now) / MIN));
              const isSoon = minsToStart <= 90;
              return `
                <div class="now-card ${isSoon ? '' : 'later'}" role="button" tabindex="0" onclick="window.app.openEvent('${e.id}')">
                  <span class="status soon">${isSoon ? 'Starts soon' : `Next up, ${dayName(e.start)}`}</span>
                  <span class="remaining">${isSoon ? `in ${minsToStart}<small>min</small>` : `${hm(e.start).t}<small>${hm(e.start).ap}</small>`}</span>
                  <h3>${esc(e.title)}</h3>
                  <span class="where">${icon('pin', 'icon-sm')}${esc(e.location)}</span>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </section>
    `;
  }

  function renderToolbar(count) {
    const chip = (id, label, active) => `
      <button class="chip" data-when="${id}" aria-pressed="${active ? 'true' : 'false'}" onclick="window.app.setDateFilter('${id}')">${label}</button>
    `;

    // Available sources for popover
    const sourceCounts = new Map();
    allEvents.forEach((e) => {
      if (activeView === 'food' && e.category !== 'food_event') return;
      if (activeView === 'events' && e.category !== 'campus_event') return;
      if (activeView === 'deadlines' && e.category !== 'important_date') return;
      sourceCounts.set(e.source, (sourceCounts.get(e.source) || 0) + 1);
    });

    let left = '';
    if (activeView === 'food' || activeView === 'events') {
      left = `
        <div class="seg" role="group" aria-label="When">
          ${chip('upcoming', 'Upcoming', activeDateFilter === 'upcoming')}
          ${chip('today', 'Today', activeDateFilter === 'today')}
          ${chip('tomorrow', 'Tomorrow', activeDateFilter === 'tomorrow')}
          ${chip('week', 'This week', activeDateFilter === 'week')}
          <button class="chip menu ${activeDateFilter.startsWith('20') ? 'has-value' : ''}" onclick="window.app.toggleDatePopover(event)">
            ${icon('calendar', 'icon-sm')}${activeDateFilter.startsWith('20') ? activeDateFilter : 'Pick a date'}
          </button>
        </div>
        <span class="divider-v"></span>
        <div class="dropdown">
          <button class="chip menu ${selectedSources.size ? 'has-value' : ''}" onclick="window.app.toggleSourcesPopover(event)">
            ${icon('sliders', 'icon-sm')}Sources${selectedSources.size ? `<span class="n">${selectedSources.size}</span>` : ''}${icon('chev-down', 'icon-sm')}
          </button>
          ${showSourcesPopover ? renderSourcesPopover(sourceCounts) : ''}
        </div>
      `;

      if (activeView === 'events') {
        left += `
          <button class="toggle" role="switch" aria-checked="${freeFoodOnlyFilter}" onclick="window.app.toggleFreeFoodFilter()">
            <span class="switch"></span>Free food only
          </button>
        `;
      }
    } else if (activeView === 'deadlines') {
      left = `
        <div class="seg" role="group" aria-label="Kind">
          ${chip('upcoming', `All <span class="n">${count}</span>`, activeDateFilter === 'upcoming')}
          ${chip('week', 'Next 7 days', activeDateFilter === 'week')}
        </div>
      `;
    } else {
      left = `
        <div class="seg">
          <span style="font-weight:600;font-size:var(--fs-13);color:var(--ink-2);">${count} saved items</span>
        </div>
      `;
    }

    const countLabel = activeView === 'food' ? `${count} free food listings` : activeView === 'events' ? `${count} campus events` : activeView === 'deadlines' ? `${count} deadlines` : `${count} saved`;

    return `
      <div class="toolbar">
        <div class="wrap">
          ${left}
          <span class="result-count">${countLabel}</span>
        </div>
      </div>
    `;
  }

  function renderSourcesPopover(sourceCounts) {
    return `
      <div class="popover" role="dialog" aria-label="Filter by source" onclick="event.stopPropagation()">
        <h4>Filter by campus source</h4>
        ${[...sourceCounts.entries()].map(([srcName, srcCount]) => {
          const isSelected = selectedSources.has(srcName);
          return `
            <div class="check-row ${isSelected ? 'on' : ''}" onclick="window.app.toggleSourceSelection('${srcName}')">
              <span class="box">${isSelected ? icon('check', 'icon-sm') : ''}</span>
              ${esc(srcName)}
              <span class="n">${srcCount}</span>
            </div>
          `;
        }).join('')}
        <div class="popover-foot">
          <button class="text-btn" onclick="window.app.clearSources()">Clear all</button>
          <button class="text-btn strong" onclick="window.app.toggleSourcesPopover()">Apply</button>
        </div>
      </div>
    `;
  }

  function renderRow(e) {
    const isSaved = savedEventIds.has(e.id);
    let timeText = 'TBA';
    let endText = '';

    if (e.start) {
      const t = hm(e.start);
      timeText = `${t.t} <span style="font-size:.7em;font-weight:650">${t.ap}</span>`;
      if (e.end) {
        const et = hm(e.end);
        endText = `<small>to ${et.ap === t.ap ? et.t : timeStr(e.end)}</small>`;
      }
    } else if (e.recurrence_text) {
      timeText = `<span style="font-size:var(--fs-12);font-weight:600;">${esc(e.recurrence_text)}</span>`;
    }

    // Status Tags
    const now = new Date();
    const tags = [];
    if (e.start && e.end && e.start <= now && now < e.end) {
      tags.push(`<span class="tag live"><span class="dot"></span>Happening now</span>`);
    } else if (e.start && e.start > now && (e.start - now) <= 90 * MIN) {
      const m = Math.round((e.start - now) / MIN);
      tags.push(`<span class="tag soon">Starts in ${m} min</span>`);
    }

    (e.food_items || []).forEach((f) => {
      tags.push(`<span class="tag food">${esc(f)}</span>`);
    });

    if (e.category === 'campus_event' && e.event_type) {
      tags.push(`<span class="tag">${esc(e.event_type)}</span>`);
    }

    return `
      <article class="row ${openEventId === e.id ? 'selected' : ''}" tabindex="0" role="button" onclick="window.app.openEvent('${e.id}')">
        <div class="time">${timeText}${endText}</div>
        <div>
          <h3>${esc(e.title)}</h3>
          <div class="meta">
            <span>${icon('pin', 'icon-sm')}${esc(e.location)}</span>
            <span class="src">${esc(e.source)}</span>
          </div>
          ${tags.length ? `<div class="tags">${tags.join('')}</div>` : ''}
        </div>
        <button class="save ${isSaved ? 'on' : ''}" aria-label="${isSaved ? 'Remove from saved' : 'Save'}" onclick="window.app.toggleSave('${e.id}', event)">
          ${icon('bookmark')}
        </button>
      </article>
    `;
  }

  function renderTimeline(eventsList) {
    if (eventsList.length === 0) {
      return `
        <div class="empty">
          <span class="ico">${icon('search')}</span>
          <h3>No events found</h3>
          <p>No listings matched your current filters. Try resetting the search or picking another date.</p>
          <button class="btn primary" onclick="window.app.resetFilters()">Reset filters</button>
        </div>
      `;
    }

    const now = new Date();
    const groups = new Map();

    eventsList.forEach((e) => {
      const groupKey = e.start ? startOfDay(e.start).getTime() : 0;
      if (!groups.has(groupKey)) groups.set(groupKey, []);
      groups.get(groupKey).push(e);
    });

    return [...groups.entries()].map(([keyTime, items]) => {
      if (keyTime === 0) {
        return `
          <section class="day">
            <div class="day-head">
              <h2>Ongoing Campus Resources</h2>
              <span class="n">${items.length} listings</span>
            </div>
            ${items.map(renderRow).join('')}
          </section>
        `;
      }

      const d = new Date(keyTime);
      return `
        <section class="day" aria-label="${longDate(d)}">
          <div class="day-head">
            <h2>${dayName(d, now)}</h2>
            <span class="date">${shortDate(d)}</span>
            <span class="n">${items.length} ${items.length === 1 ? 'event' : 'events'}</span>
          </div>
          ${items.map(renderRow).join('')}
        </section>
      `;
    }).join('');
  }

  function renderDeadlinesView(deadlinesList) {
    if (deadlinesList.length === 0) {
      return `<div class="empty"><h3>No deadlines found</h3><p>No academic deadlines matched your filters.</p></div>`;
    }

    const now = new Date();
    const urgent = deadlinesList.filter((d) => d.start && dayDiff(d.start, now) <= 7);
    const later = deadlinesList.filter((d) => !d.start || dayDiff(d.start, now) > 7);

    const renderRowDl = (d) => {
      const n = d.start ? dayDiff(d.start, now) : 0;
      const cls = n <= 3 ? 'urgent' : n <= 7 ? 'soon' : 'later';
      const big = n === 0 ? 'Today' : n < 0 ? 'Past' : n;
      const small = n === 0 ? '' : n === 1 ? 'day' : 'days';
      const isSaved = savedEventIds.has(d.id);

      return `
        <article class="dl-row" onclick="window.app.openEvent('${d.id}')">
          <div class="countdown ${cls}">${big}${small ? `<small>${small}</small>` : ''}</div>
          <div>
            <h3>${esc(d.title)}</h3>
            <div class="meta">
              <span>${d.start ? longDate(d.start) : 'TBA'}</span>
              <span>${esc(d.source)}</span>
            </div>
          </div>
          <button class="save ${isSaved ? 'on' : ''}" aria-label="Save" onclick="window.app.toggleSave('${d.id}', event)">
            ${icon('bookmark')}
          </button>
        </article>
      `;
    };

    return `
      <div class="wrap page-intro">
        <h1>Academic & Billing Deadlines</h1>
        <p>Registrar deadlines, semester dates, and billing schedules counted down from today.</p>
      </div>
      ${renderToolbar(deadlinesList.length)}
      <div class="wrap page">
        <main>
          ${urgent.length ? `<section class="dl-group"><h2>Next 7 days</h2>${urgent.map(renderRowDl).join('')}</section>` : ''}
          ${later.length ? `<section class="dl-group"><h2>Upcoming this semester</h2>${later.map(renderRowDl).join('')}</section>` : ''}
        </main>
        <aside class="rail">
          ${renderMiniCalendar()}
          <section class="rail-section">
            <div class="panel alert-card">
              <h2>${icon('calendar', 'icon-sm')} Add to Google or Outlook</h2>
              <p>Keep these deadlines on your calendar so you never miss registration or payment dates.</p>
              <button class="btn primary block" onclick="window.app.exportAllDeadlinesIcs()">Download all deadlines (.ics)</button>
            </div>
          </section>
        </aside>
      </div>
    `;
  }

  function renderSavedView(savedList) {
    if (savedList.length === 0) {
      return `
        <div class="wrap page-intro"><h1>Saved Items</h1></div>
        <div class="wrap page single">
          <main>
            <div class="empty">
              <span class="ico">${icon('bookmark')}</span>
              <h3>Nothing saved yet</h3>
              <p>Tap the bookmark icon on any food listing, event, or deadline to save it for easy access.</p>
              <button class="btn primary" onclick="window.app.setView('food')">Browse free food</button>
            </div>
          </main>
        </div>
      `;
    }

    return `
      <div class="wrap page-intro">
        <h1>Saved Items</h1>
        <p>Your bookmarked food events, campus gatherings, and deadlines stored locally on this device.</p>
      </div>
      ${renderToolbar(savedList.length)}
      <div class="wrap page">
        <main>
          ${renderTimeline(savedList.filter((e) => e.category !== 'important_date'))}
          ${savedList.some((e) => e.category === 'important_date') ? `
            <section class="dl-group">
              <h2>Saved Deadlines</h2>
              ${savedList.filter((e) => e.category === 'important_date').map((d) => `
                <article class="dl-row" onclick="window.app.openEvent('${d.id}')">
                  <div class="countdown urgent">${d.start ? dayDiff(d.start) : 0}<small>days</small></div>
                  <div><h3>${esc(d.title)}</h3><div class="meta">${d.start ? longDate(d.start) : 'TBA'}</div></div>
                  <button class="save on" onclick="window.app.toggleSave('${d.id}', event)">${icon('bookmark')}</button>
                </article>
              `).join('')}
            </section>
          ` : ''}
        </main>
        <aside class="rail">
          ${renderMiniCalendar()}
        </aside>
      </div>
    `;
  }

  function renderMiniCalendar() {
    const base = new Date();
    const curr = new Date(base.getFullYear(), base.getMonth() + calendarMonthOffset, 1);
    const yr = curr.getFullYear();
    const mo = curr.getMonth();
    const firstDay = new Date(yr, mo, 1).getDay();
    const totalDays = new Date(yr, mo + 1, 0).getDate();
    const prevDays = new Date(yr, mo, 0).getDate();

    const foodDays = new Set(allEvents.filter((e) => e.category === 'food_event' && e.start).map((e) => e.start.toDateString()));
    const dlDays = new Set(allEvents.filter((e) => e.category === 'important_date' && e.start).map((e) => e.start.toDateString()));

    let cells = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((w) => `<div class="wd">${w}</div>`).join('');

    for (let i = firstDay - 1; i >= 0; i--) {
      cells += `<div class="d muted">${prevDays - i}</div>`;
    }

    for (let d = 1; d <= totalDays; d++) {
      const dt = new Date(yr, mo, d);
      const dtStr = dt.toDateString();
      const isoStr = dt.toISOString().slice(0, 10);
      const isToday = dtStr === base.toDateString();
      const isFilterActive = activeDateFilter === isoStr;
      const hasFood = foodDays.has(dtStr);
      const hasDl = dlDays.has(dtStr);

      const dots = (hasFood ? '<i></i>' : '') + (hasDl ? '<i class="deadline"></i>' : '');
      cells += `
        <div class="d ${isToday ? 'today' : ''} ${isFilterActive ? 'active-filter' : ''}" onclick="window.app.setDateFilter('${isoStr}')">
          ${d}${dots}
        </div>
      `;
    }

    const tail = (7 - ((firstDay + totalDays) % 7)) % 7;
    for (let d = 1; d <= tail; d++) {
      cells += `<div class="d muted">${d}</div>`;
    }

    return `
      <div class="panel mini-cal">
        <div class="mini-cal-head">
          ${curr.toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
          <div>
            <button aria-label="Previous month" onclick="window.app.navCalendar(-1)">${icon('chev-left', 'icon-sm')}</button>
            <button aria-label="Next month" onclick="window.app.navCalendar(1)">${icon('chev-right', 'icon-sm')}</button>
          </div>
        </div>
        <div class="cal-grid">${cells}</div>
        <div class="cal-legend">
          <span><i></i>Free food</span>
          <span><i class="deadline"></i>Deadline</span>
        </div>
      </div>
    `;
  }

  function renderSideRail() {
    const deadlinesUpcoming = allEvents
      .filter((e) => e.category === 'important_date' && e.start && dayDiff(e.start) >= 0)
      .sort((a, b) => a.start - b.start)
      .slice(0, 3);

    const resources = allEvents.filter((e) => e.category === 'food_event' && e.kind !== 'one_time');

    return `
      <aside class="rail" aria-label="Calendar and deadlines">
        ${renderMiniCalendar()}
        ${deadlinesUpcoming.length ? `
          <section class="rail-section">
            <h2>Deadlines coming up <a onclick="window.app.setView('deadlines')">See all</a></h2>
            <div class="panel list-tight">
              ${deadlinesUpcoming.map((d) => `
                <div class="mini-row" role="button" tabindex="0" onclick="window.app.openEvent('${d.id}')">
                  <div class="countdown ${dayDiff(d.start) <= 3 ? 'urgent' : 'soon'}">
                    ${dayDiff(d.start) === 0 ? 'Today' : dayDiff(d.start)}<small>${dayDiff(d.start) === 0 ? '' : 'days'}</small>
                  </div>
                  <div>
                    <strong>${esc(d.title)}</strong>
                    <span>${shortDate(d.start)}, ${esc(d.source)}</span>
                  </div>
                </div>
              `).join('')}
            </div>
          </section>
        ` : ''}

        ${resources.length ? `
          <section class="rail-section">
            <h2>Always on campus</h2>
            <div class="panel list-tight">
              ${resources.map((r) => `
                <div class="resource" role="button" tabindex="0" onclick="window.app.openEvent('${r.id}')">
                  <span class="ico">${icon(r.kind === 'ongoing' ? 'bag' : 'leaf')}</span>
                  <div>
                    <strong>${esc(r.title)}</strong>
                    <span>${esc(r.recurrence_text)}</span>
                    <span>${esc(r.location)}</span>
                  </div>
                </div>
              `).join('')}
            </div>
          </section>
        ` : ''}

        <section class="rail-section">
          <div class="panel alert-card">
            <h2>${icon('bell', 'icon-sm')} Discord Food Alerts</h2>
            <p>New free-food listings are posted to the UMBC Food Radar Discord channel within minutes of appearing.</p>
            <a class="btn block" href="https://discord.gg/" target="_blank" rel="noopener">Join Discord notifications</a>
          </div>
        </section>
      </aside>
    `;
  }

  function renderDrawer(ev) {
    if (!ev) return '';
    const now = new Date();
    const isDeadline = ev.category === 'important_date';
    const isFood = ev.category === 'food_event';
    const isLive = ev.start && ev.end && ev.start <= now && now < ev.end;
    const isSaved = savedEventIds.has(ev.id);

    let whenText = 'Date announced on original listing';
    if (isDeadline) {
      whenText = ev.start ? longDate(ev.start) : 'TBA';
    } else if (ev.start) {
      whenText = `${dayName(ev.start)}, ${longDate(ev.start)}<br>${timeStr(ev.start)}${ev.end ? ` to ${timeStr(ev.end)}` : ''}`;
    } else if (ev.recurrence_text) {
      whenText = esc(ev.recurrence_text);
    }

    const sameDayFood = !ev.start ? [] : allEvents.filter((x) =>
      x.id !== ev.id && x.category === 'food_event' && x.start && x.start.toDateString() === ev.start.toDateString()
    ).slice(0, 3);

    return `
      <div class="scrim" onclick="window.app.closeDrawer()"></div>
      <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="dTitle">
        <div class="drawer-top">
          <div class="crumbs">
            ${isDeadline ? '<span class="tag urgent">Deadline</span>' : isFood ? '<span class="tag food">Free food</span>' : `<span class="tag">${esc(ev.event_type || 'Event')}</span>`}
            <span class="tag">${esc(ev.source)}</span>
          </div>
          <button class="icon-btn" onclick="window.app.closeDrawer()" aria-label="Close">
            ${icon('x')}
          </button>
        </div>

        <div class="drawer-body">
          <h2 class="title" id="dTitle">${esc(ev.title)}</h2>

          ${isLive ? `
            <div class="live-strip">
              <span class="dot pulse"></span>Serving now, ${dur(Math.max(0, Math.round((ev.end - now) / MIN)))} remaining
              <div class="progress"><span style="width:${Math.min(100, Math.max(0, ((now - ev.start) / (ev.end - ev.start)) * 100))}%"></span></div>
            </div>
          ` : ''}

          ${isDeadline && ev.start ? `
            <div class="live-strip" style="background:var(--urgent-wash);color:var(--urgent)">
              ${icon('alarm', 'icon-sm')}Due in ${dayDiff(ev.start)} days (${shortDate(ev.start)})
            </div>
          ` : ''}

          <dl class="facts">
            <div class="fact">
              ${icon('clock')}
              <div><dt>When</dt><dd>${whenText}</dd></div>
            </div>
            ${ev.location ? `
              <div class="fact">
                ${icon('pin')}
                <div>
                  <dt>Where</dt>
                  <dd>
                    ${esc(ev.location)}<br>
                    <a href="https://map.umbc.edu/?id=1941#!s/?q=${encodeURIComponent(ev.location)}" target="_blank" rel="noopener">
                      Open in UMBC campus map &rarr;
                    </a>
                  </dd>
                </div>
              </div>
            ` : ''}
            ${(ev.food_items || []).length ? `
              <div class="fact">
                ${icon('food')}
                <div>
                  <dt>Food items detected</dt>
                  <dd>
                    <div class="tags" style="margin-top:4px">
                      ${ev.food_items.map((f) => `<span class="tag food">${esc(f)}</span>`).join('')}
                    </div>
                    <span class="note">Detected from announcement text. Food supplies are limited, arrive promptly.</span>
                  </dd>
                </div>
              </div>
            ` : ''}
          </dl>

          ${ev.description ? `<p class="about">${esc(ev.description)}</p>` : ''}

          <p style="margin-top:20px;">
            <a href="${esc(ev.link)}" target="_blank" rel="noopener" style="font-size:var(--fs-13);font-weight:600;color:var(--ink-2);display:inline-flex;gap:6px;align-items:center;">
              ${icon('external', 'icon-sm')} View original event page on ${esc(ev.source)}
            </a>
          </p>

          ${sameDayFood.length ? `
            <div class="also">
              <h4>More free food ${dayName(ev.start).toLowerCase()}</h4>
              ${sameDayFood.map((x) => `
                <a onclick="window.app.openEvent('${x.id}')">
                  <b>${x.start ? timeStr(x.start) : 'TBA'}</b>
                  <span>${esc(x.title)}<br><span style="color:var(--ink-3)">${esc(x.location)}</span></span>
                </a>
              `).join('')}
            </div>
          ` : ''}
        </div>

        <div class="drawer-actions">
          <button class="btn primary" onclick="window.app.exportIcs('${ev.id}')">
            ${icon('calendar', 'icon-sm')} Add to calendar
          </button>
          <button class="btn ${isSaved ? 'gold' : ''}" onclick="window.app.toggleSave('${ev.id}', event)">
            ${icon('bookmark', 'icon-sm')} ${isSaved ? 'Saved' : 'Save'}
          </button>
          <button class="btn" onclick="window.app.shareEvent('${ev.id}')">
            ${icon('share', 'icon-sm')} <span class="desktop-only">Share</span>
          </button>
        </div>
      </aside>
    `;
  }

  // --- Main View Renderer ---
  function renderApp() {
    const appEl = document.getElementById('app');
    const filtered = getFilteredEvents();
    const openedEvent = openEventId ? allEvents.find((e) => e.id === openEventId) : null;

    // Primary & bottom nav update
    const NAV = [
      { id: 'food', label: 'Free food', icon: 'food', n: allEvents.filter((e) => e.category === 'food_event').length },
      { id: 'events', label: 'Events', icon: 'ticket', n: allEvents.filter((e) => e.category === 'campus_event').length },
      { id: 'deadlines', label: 'Deadlines', icon: 'alarm', n: allEvents.filter((e) => e.category === 'important_date').length },
      { id: 'saved', label: 'Saved', icon: 'bookmark', n: savedEventIds.size },
    ];

    document.getElementById('primaryNav').innerHTML = NAV.map((n) => `
      <button data-view="${n.id}" ${n.id === activeView ? 'aria-current="page"' : ''} onclick="window.app.setView('${n.id}')">
        ${icon(n.icon, 'icon-sm')}${n.label}
        <span class="count">${n.n}</span>
      </button>
    `).join('');

    document.getElementById('bottomNav').innerHTML = NAV.map((n) => `
      <button data-view="${n.id}" ${n.id === activeView ? 'aria-current="page"' : ''} onclick="window.app.setView('${n.id}')">
        <span class="pill">${icon(n.icon)}</span>
        ${n.label}
      </button>
    `).join('');

    let contentHtml = '';

    if (activeView === 'deadlines') {
      contentHtml = renderDeadlinesView(filtered);
    } else if (activeView === 'saved') {
      contentHtml = renderSavedView(filtered);
    } else if (activeView === 'events') {
      contentHtml = `
        <div class="wrap page-intro">
          <h1>Campus Events</h1>
          <p>Talks, games, workshops, and student meetings across UMBC gathered into one place.</p>
        </div>
        ${renderToolbar(filtered.length)}
        <div class="wrap page">
          <main id="main">
            ${renderTimeline(filtered)}
          </main>
          ${renderSideRail()}
        </div>
      `;
    } else {
      // Default: Food View
      contentHtml = `
        ${renderNowBand(allEvents)}
        ${renderToolbar(filtered.length)}
        <div class="wrap page">
          <main id="main">
            ${renderTimeline(filtered)}
          </main>
          ${renderSideRail()}
        </div>
      `;
    }

    appEl.innerHTML = contentHtml + renderDrawer(openedEvent);
    if (openedEvent) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    updateUrlParams();
  }

  // --- Public App Interface for Event Handlers ---
  window.app = {
    setView(v) {
      activeView = v;
      activeDateFilter = 'upcoming';
      renderApp();
      window.scrollTo({ top: 0, behavior: 'smooth' });
    },

    setDateFilter(w) {
      if (activeDateFilter === w && w !== 'upcoming') {
        activeDateFilter = 'upcoming';
      } else {
        activeDateFilter = w;
      }
      showDatePopover = false;
      renderApp();
    },

    toggleSourcesPopover(ev) {
      if (ev) ev.stopPropagation();
      showSourcesPopover = !showSourcesPopover;
      renderApp();
    },

    toggleDatePopover(ev) {
      if (ev) ev.stopPropagation();
      showDatePopover = !showDatePopover;
      renderApp();
    },

    toggleSourceSelection(srcName) {
      if (selectedSources.has(srcName)) selectedSources.delete(srcName);
      else selectedSources.add(srcName);
      renderApp();
    },

    clearSources() {
      selectedSources.clear();
      showSourcesPopover = false;
      renderApp();
    },

    toggleFreeFoodFilter() {
      freeFoodOnlyFilter = !freeFoodOnlyFilter;
      renderApp();
    },

    resetFilters() {
      searchQuery = '';
      activeDateFilter = 'upcoming';
      selectedSources.clear();
      freeFoodOnlyFilter = false;
      const sInput = document.getElementById('searchInput');
      if (sInput) sInput.value = '';
      renderApp();
    },

    navCalendar(delta) {
      calendarMonthOffset += delta;
      renderApp();
    },

    openEvent(id) {
      openEventId = id;
      renderApp();
    },

    closeDrawer() {
      openEventId = null;
      renderApp();
    },

    toggleSave(id, ev) {
      toggleSaveEvent(id, ev);
    },

    exportIcs(id) {
      const ev = allEvents.find((e) => e.id === id);
      if (ev) exportIcsFile(ev);
    },

    exportAllDeadlinesIcs() {
      const deadlines = allEvents.filter((e) => e.category === 'important_date');
      if (!deadlines.length) return;
      const fmt = (d) => d.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '').slice(0, 15);
      const eventsBlock = deadlines.map((d) => {
        const start = d.start || new Date();
        const end = d.end || new Date(start.getTime() + HOUR);
        return [
          'BEGIN:VEVENT',
          `UID:${d.id}@foodradar.umbc`,
          `SUMMARY:${(d.title || '').replace(/[^\w\s\-.,]/g, '')}`,
          `DTSTART:${fmt(start)}`,
          `DTEND:${fmt(end)}`,
          `DESCRIPTION:${(d.description || '').slice(0, 300)}`,
          'END:VEVENT',
        ].join('\r\n');
      }).join('\r\n');

      const ics = `BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//UMBC Food Radar//EN\r\n${eventsBlock}\r\nEND:VCALENDAR`;
      const blob = new Blob([ics], { type: 'text/calendar;charset=utf-8' });
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'umbc_academic_deadlines.ics';
      link.click();
      showToast('Downloaded all academic deadlines');
    },

    async shareEvent(id) {
      const ev = allEvents.find((e) => e.id === id);
      if (!ev) return;
      const shareUrl = `${window.location.origin}${window.location.pathname}?view=${activeView}&open=${encodeURIComponent(id)}`;
      if (navigator.share) {
        try {
          await navigator.share({
            title: ev.title,
            text: `Free food & campus event at UMBC: ${ev.title}`,
            url: shareUrl,
          });
          return;
        } catch (e) {
          // Fall back to clipboard if user dismissed or unsupported
        }
      }
      try {
        await navigator.clipboard.writeText(shareUrl);
        showToast('Link copied to clipboard!');
      } catch (e) {
        prompt('Copy link:', shareUrl);
      }
    },
  };

  // --- Document Event Listeners ---
  document.addEventListener('DOMContentLoaded', () => {
    // Theme button
    const themeBtn = document.getElementById('themeBtn');
    if (themeBtn) {
      themeBtn.innerHTML = icon(activeTheme === 'dark' ? 'sun' : 'moon');
      themeBtn.addEventListener('click', toggleTheme);
    }

    // Brand click returns to food home
    const brandHome = document.getElementById('brandHome');
    if (brandHome) {
      brandHome.addEventListener('click', (e) => {
        e.preventDefault();
        window.app.setView('food');
      });
    }

    // Search inputs
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
      searchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value;
        renderApp();
      });
    }

    const mobileSearchBtn = document.getElementById('mobileSearchBtn');
    const mobileSearchBar = document.getElementById('mobileSearchBar');
    const closeMobileSearchBtn = document.getElementById('closeMobileSearchBtn');
    const mobileSearchInput = document.getElementById('mobileSearchInput');

    if (mobileSearchBtn && mobileSearchBar) {
      mobileSearchBtn.addEventListener('click', () => {
        const isHidden = mobileSearchBar.style.display === 'none';
        mobileSearchBar.style.display = isHidden ? 'flex' : 'none';
        if (isHidden && mobileSearchInput) mobileSearchInput.focus();
      });
    }

    if (closeMobileSearchBtn && mobileSearchBar) {
      closeMobileSearchBtn.addEventListener('click', () => {
        mobileSearchBar.style.display = 'none';
        searchQuery = '';
        if (mobileSearchInput) mobileSearchInput.value = '';
        renderApp();
      });
    }

    if (mobileSearchInput) {
      mobileSearchInput.addEventListener('input', (e) => {
        searchQuery = e.target.value;
        renderApp();
      });
    }

    // Global keyboard shortcuts: '/' focuses search, 'Escape' closes drawer
    document.addEventListener('keydown', (e) => {
      if (e.key === '/' && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        e.preventDefault();
        const input = document.getElementById('searchInput');
        if (input && window.innerWidth >= 960) input.focus();
        else if (mobileSearchBtn) mobileSearchBtn.click();
      } else if (e.key === 'Escape') {
        if (openEventId) {
          window.app.closeDrawer();
        }
        if (showSourcesPopover) {
          showSourcesPopover = false;
          renderApp();
        }
      }
    });

    // Close popovers when clicking outside
    document.addEventListener('click', (e) => {
      if (showSourcesPopover && !e.target.closest('.dropdown')) {
        showSourcesPopover = false;
        renderApp();
      }
    });

    // Initial data fetch
    loadData();
  });
})();