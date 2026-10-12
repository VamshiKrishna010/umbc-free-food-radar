/* Prototype renderer. State comes from URL params so every screen is linkable:
   ?view=food|events|deadlines|saved  &theme=light|dark  &open=<eventId>
   &popover=sources  &state=loading|error|offline|empty  &now=<ISO datetime>  */
(function () {
  const P = new URLSearchParams(location.search);
  const VIEW = P.get("view") || "food";
  const THEME = P.get("theme") || "light";
  const OPEN = P.get("open");
  const POPOVER = P.get("popover");
  const STATE = P.get("state");
  const NOW = new Date(P.get("now") || "2026-10-12T12:20:00");
  const SAVED = new Set((P.get("saved") || "f4,d5,c3").split(",").filter(Boolean));
  const MIN = 60000, DAY = 86400000;

  document.documentElement.dataset.theme = THEME;
  if (STATE === "loading") document.getElementById("freshness").textContent = "Checking for new listings";
  if (STATE === "offline" || STATE === "error") document.getElementById("freshness").textContent = "Last updated 11:52 AM";
  const all = window.SAMPLE_EVENTS.map(e => ({
    ...e,
    start: e.start_at ? new Date(e.start_at) : null,
    end: e.end_at ? new Date(e.end_at) : null,
  }));

  /* ---------- helpers ---------- */
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const icon = (id, cls = "") => `<svg class="icon ${cls}" aria-hidden="true"><use href="#i-${id}"/></svg>`;
  const startOfDay = d => new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const dayDiff = d => Math.round((startOfDay(d) - startOfDay(NOW)) / DAY);
  const hm = d => {
    let h = d.getHours(), m = d.getMinutes(); const ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
    return { t: m ? `${h}:${String(m).padStart(2, "0")}` : `${h}:00`, ap };
  };
  const timeStr = d => { const x = hm(d); return `${x.t} ${x.ap}`; };
  const weekday = d => d.toLocaleDateString("en-US", { weekday: "long" });
  const longDate = d => d.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
  const shortDate = d => d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
  const dayName = d => { const n = dayDiff(d); return n === 0 ? "Today" : n === 1 ? "Tomorrow" : weekday(d); };
  const isLive = e => e.start && e.end && e.start <= NOW && NOW < e.end;
  const minsUntil = d => Math.round((d - NOW) / MIN);
  const dur = mins => mins < 60 ? `${mins} min` : `${Math.floor(mins / 60)} hr${mins % 60 ? ` ${mins % 60} min` : ""}`;
  const pct = e => Math.min(100, Math.max(0, ((NOW - e.start) / (e.end - e.start)) * 100));

  const food = all.filter(e => e.category === "food_event" && e.kind === "one_time" && (e.end || e.start) > NOW).sort((a, b) => a.start - b.start);
  const resources = all.filter(e => e.category === "food_event" && e.kind !== "one_time");
  const events = all.filter(e => e.category === "campus_event" && e.end > NOW).sort((a, b) => a.start - b.start);
  const deadlines = all.filter(e => e.category === "important_date" && dayDiff(e.start) >= 0).sort((a, b) => a.start - b.start);

  function statusTag(e) {
    if (isLive(e)) return `<span class="tag live"><span class="dot"></span>Happening now</span>`;
    const m = minsUntil(e.start);
    if (m > 0 && m <= 90) return `<span class="tag soon">Starts in ${dur(m)}</span>`;
    return "";
  }
  function countdown(d) {
    const n = dayDiff(d);
    const cls = n <= 3 ? "urgent" : n <= 7 ? "soon" : "later";
    const big = n === 0 ? "Today" : n;
    const small = n === 0 ? "" : n === 1 ? "day" : "days";
    return `<div class="countdown ${cls}">${big}${small ? `<small>${small}</small>` : ""}</div>`;
  }

  /* ---------- nav ---------- */
  const NAV = [
    { id: "food", label: "Free food", icon: "food", n: food.length },
    { id: "events", label: "Events", icon: "ticket", n: events.length },
    { id: "deadlines", label: "Deadlines", icon: "alarm", n: deadlines.length },
    { id: "saved", label: "Saved", icon: "bookmark", n: STATE === "empty" ? 0 : SAVED.size },
  ];
  const keep = extra => { const q = new URLSearchParams({ theme: THEME, ...extra }); return "?" + q.toString(); };
  document.getElementById("primaryNav").innerHTML = NAV.map(n =>
    `<a href="${keep({ view: n.id })}" ${n.id === VIEW ? 'aria-current="page"' : ""}>${icon(n.icon, "icon-sm")}${n.label}<span class="count">${n.n}</span></a>`).join("");
  document.getElementById("bottomNav").innerHTML = NAV.map(n =>
    `<a href="${keep({ view: n.id })}" ${n.id === VIEW ? 'aria-current="page"' : ""}><span class="pill">${icon(n.icon)}</span>${n.label}</a>`).join("");
  document.getElementById("themeBtn").innerHTML = icon(THEME === "dark" ? "sun" : "moon");
  document.getElementById("themeBtn").onclick = () => { location.search = keep({ view: VIEW, theme: THEME === "dark" ? "light" : "dark" }); };

  /* ---------- pieces ---------- */
  function nowBand() {
    if (STATE === "loading") {
      return `<section class="now-band"><div class="wrap">
        <div class="now-head"><h1>Free food right now</h1><p>Checking campus listings</p></div>
        <div class="now-cards">${[0, 1, 2].map(() => `<div class="now-card" style="height:170px;background:rgba(255,253,246,.6)"></div>`).join("")}</div></div></section>`;
    }
    const live = food.filter(isLive);
    const soon = food.filter(e => !isLive(e) && minsUntil(e.start) > 0 && minsUntil(e.start) <= 90);
    const later = food.filter(e => !live.includes(e) && !soon.includes(e));
    const cards = [...live, ...soon, ...later].slice(0, 3);
    const sub = [live.length && `${live.length} serving now`, soon.length && `${soon.length} starting within the hour`].filter(Boolean).join(", ");
    return `<section class="now-band" aria-labelledby="nowTitle"><div class="wrap">
      <div class="now-head">
        <h1 id="nowTitle">Free food right now</h1>
        <p>${sub ? sub + "." : "Nothing is serving right now."} Tap a card for the room and details.</p>
        <span class="clock">${icon("clock", "icon-sm")}As of ${timeStr(NOW)}</span>
      </div>
      <div class="now-cards">${cards.map(e => {
        if (isLive(e)) {
          const left = minsUntil(e.end);
          return `<a class="now-card" href="${keep({ view: VIEW, open: e.id })}">
            <span class="status"><span class="dot pulse"></span>Serving now</span>
            <span class="remaining">${dur(left).replace(/ (min|hr)/, "<small>$1</small>").replace(/<small>hr<\/small> (\d+) min/, "<small>hr</small> $1<small>min</small>")}<small>left</small></span>
            <h3>${esc(e.title)}</h3>
            <span class="where">${icon("pin", "icon-sm")}${esc(e.location)}</span>
            <div class="progress" aria-label="${Math.round(pct(e))}% elapsed"><span style="width:${pct(e)}%"></span></div></a>`;
        }
        const m = minsUntil(e.start);
        const isSoon = m <= 90;
        return `<a class="now-card ${isSoon ? "" : "later"}" href="${keep({ view: VIEW, open: e.id })}">
          <span class="status soon">${isSoon ? "Starts soon" : `Next up, ${dayDiff(e.start) <= 1 ? dayName(e.start).toLowerCase() : dayName(e.start)}`}</span>
          <span class="remaining">${isSoon ? `in ${m}<small>min</small>` : `${hm(e.start).t}<small>${hm(e.start).ap}</small>`}</span>
          <h3>${esc(e.title)}</h3>
          <span class="where">${icon("pin", "icon-sm")}${esc(e.location)}</span></a>`;
      }).join("")}</div></div></section>`;
  }

  function toolbar() {
    const chip = (label, on, extra = "") => `<button class="chip" aria-pressed="${on}">${label}${extra}</button>`;
    let left = "";
    if (VIEW === "food" || VIEW === "events") {
      left = `<div class="seg" role="group" aria-label="When">
        ${chip("Upcoming", true)}${chip("Today", false)}${chip("Tomorrow", false)}${chip("This week", false)}
        <button class="chip menu">${icon("calendar", "icon-sm")}Pick a date</button></div>
        <span class="divider-v"></span>`;
      if (VIEW === "food") {
        left += `<div class="dropdown"><button class="chip menu ${POPOVER ? "has-value" : ""}" aria-expanded="${!!POPOVER}">Sources${POPOVER ? '<span class="n">3 of 6</span>' : ""}${icon("chev-down", "icon-sm")}</button>${POPOVER === "sources" ? sourcesPopover() : ""}</div>
          <button class="chip menu">Food type${icon("chev-down", "icon-sm")}</button>`;
      } else {
        left += `<button class="chip menu">Type${icon("chev-down", "icon-sm")}</button>
          <button class="toggle" role="switch" aria-checked="false"><span class="switch"></span>Free food only</button>`;
      }
    } else if (VIEW === "deadlines") {
      left = `<div class="seg" role="group" aria-label="Kind">${chip("All", true, `<span class="n">${deadlines.length}</span>`)}${chip("Registration", false)}${chip("Billing", false)}${chip("Breaks and exams", false)}</div>`;
    } else {
      left = `<div class="seg">${chip("All", true)}${chip("Food", false)}${chip("Events", false)}${chip("Deadlines", false)}</div>`;
    }
    const count = VIEW === "food" ? `${food.length} upcoming` : VIEW === "events" ? `${events.length} upcoming` : VIEW === "deadlines" ? `${deadlines.length} this semester` : "";
    return `<div class="toolbar"><div class="wrap">${left}<span class="result-count">${count}</span></div></div>`;
  }

  function sourcesPopover() {
    const src = [["myUMBC", 2, true], ["Student Events Board", 2, true], ["UMBC Events", 1, true], ["Career Center", 1, false], ["Graduate School", 1, false], ["Departments", 2, false]];
    return `<div class="popover" role="dialog" aria-label="Filter by source"><h4>Show food from</h4>
      ${src.map(([n, c, on]) => `<div class="check-row ${on ? "on" : ""}"><span class="box">${on ? icon("check", "icon-sm") : ""}</span>${n}<span class="n">${c}</span></div>`).join("")}
      <div class="popover-foot"><button class="text-btn">Clear</button><button class="text-btn strong">Show 5 results</button></div></div>`;
  }

  function row(e, opts = {}) {
    const t = hm(e.start);
    const tags = [statusTag(e), ...(e.food_items || []).map(f => `<span class="tag food">${esc(f)}</span>`)];
    if (e.category === "campus_event" && e.event_type) tags.push(`<span class="tag">${esc(e.event_type)}</span>`);
    const saved = SAVED.has(e.id);
    return `<article class="row ${OPEN === e.id ? "selected" : ""}" tabindex="0" onclick="location.search='${keep({ view: VIEW, open: e.id }).slice(1)}'">
      <div class="time">${t.t}<span style="font-size:.7em;font-weight:650"> ${t.ap}</span><small>${e.end ? `to ${hm(e.end).ap === t.ap ? hm(e.end).t : timeStr(e.end)}` : ""}</small></div>
      <div>
        <h3>${esc(e.title)}</h3>
        <div class="meta"><span>${icon("pin", "icon-sm")}${esc(e.location)}</span><span class="src">${esc(e.source)}</span></div>
        ${tags.filter(Boolean).length ? `<div class="tags">${tags.filter(Boolean).join("")}</div>` : ""}
      </div>
      <button class="save ${saved ? "on" : ""}" aria-label="${saved ? "Remove from saved" : "Save"}" onclick="event.stopPropagation()">${icon("bookmark")}</button>
    </article>`;
  }

  function timeline(list) {
    if (STATE === "loading") {
      return [0, 1].map(g => `<section class="day"><div class="day-head"><div class="skeleton" style="width:140px;height:26px"></div></div>
        ${[0, 1, 2].map(() => `<div class="row" style="cursor:default"><div class="skeleton" style="height:22px;width:64px;margin-left:8px"></div>
        <div><div class="skeleton" style="height:18px;width:70%"></div><div class="skeleton" style="height:13px;width:40%;margin-top:10px"></div></div><span></span></div>`).join("")}</section>`).join("");
    }
    const groups = new Map();
    list.forEach(e => { const k = startOfDay(e.start).getTime(); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(e); });
    return [...groups.entries()].map(([k, items]) => {
      const d = new Date(k);
      return `<section class="day" aria-label="${longDate(d)}"><div class="day-head"><h2>${dayName(d)}</h2>
        <span class="date">${dayDiff(d) <= 1 ? longDate(d) : d.toLocaleDateString("en-US", { month: "long", day: "numeric" })}</span>
        <span class="n">${items.length} ${items.length === 1 ? "event" : "events"}</span></div>
        ${items.map(e => row(e)).join("")}</section>`;
    }).join("");
  }

  function miniCal() {
    const y = NOW.getFullYear(), m = NOW.getMonth();
    const first = new Date(y, m, 1).getDay(), days = new Date(y, m + 1, 0).getDate();
    const foodDays = new Set(all.filter(e => e.category === "food_event" && e.start).map(e => e.start.toDateString()));
    const dlDays = new Set(all.filter(e => e.category === "important_date").map(e => e.start.toDateString()));
    let cells = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"].map(w => `<div class="wd">${w}</div>`).join("");
    const prevDays = new Date(y, m, 0).getDate();
    for (let i = first - 1; i >= 0; i--) cells += `<div class="d muted">${prevDays - i}</div>`;
    for (let d = 1; d <= days; d++) {
      const dt = new Date(y, m, d);
      const dots = (foodDays.has(dt.toDateString()) ? "<i></i>" : "") + (dlDays.has(dt.toDateString()) ? '<i class="deadline"></i>' : "");
      cells += `<div class="d ${dt.toDateString() === NOW.toDateString() ? "today" : ""}">${d}${dots}</div>`;
    }
    const tail = (7 - ((first + days) % 7)) % 7;
    for (let d = 1; d <= tail; d++) cells += `<div class="d muted">${d}</div>`;
    return `<div class="panel mini-cal"><div class="mini-cal-head">${NOW.toLocaleDateString("en-US", { month: "long", year: "numeric" })}
      <div><button aria-label="Previous month">${icon("chev-left", "icon-sm")}</button><button aria-label="Next month">${icon("chev-right", "icon-sm")}</button></div></div>
      <div class="cal-grid">${cells}</div>
      <div class="cal-legend"><span><i></i>Free food</span><span><i class="deadline"></i>Deadline</span></div></div>`;
  }

  function deadlinesPanel(n = 3) {
    return `<section class="rail-section"><h2>Deadlines coming up <a href="${keep({ view: "deadlines" })}">See all</a></h2>
      <div class="panel list-tight">${deadlines.slice(0, n).map(d => `<a class="mini-row" href="${keep({ view: VIEW, open: d.id })}">${countdown(d.start)}
        <div><strong>${esc(d.title)}</strong><span>${shortDate(d.start)}, ${esc(d.source)}</span></div></a>`).join("")}</div></section>`;
  }

  function resourcesPanel() {
    return `<section class="rail-section"><h2>Always on campus</h2><div class="panel list-tight">
      ${resources.map(r => `<a class="resource" href="${keep({ view: VIEW, open: r.id })}" style="text-decoration:none"><span class="ico">${icon(r.kind === "ongoing" ? "bag" : "leaf")}</span>
        <div><strong>${esc(r.title)}</strong><span>${esc(r.recurrence_text)}</span><span>${esc(r.location)}</span></div></a>`).join("")}</div></section>`;
  }

  function alertsPanel() {
    return `<section class="rail-section"><div class="panel alert-card">
      <h2 style="margin:0;font-size:var(--fs-15);display:flex;gap:8px;align-items:center">${icon("bell", "icon-sm")}Get pinged when food shows up</h2>
      <p>New free-food listings are posted to the Food Radar Discord within 30 minutes of appearing.</p>
      <a class="btn block" href="#">Join the Discord channel</a></div></section>`;
  }

  function banner() {
    if (STATE === "offline") return `<div class="banner offline" style="margin-top:20px">${icon("wifi-off")}You're offline. Showing listings saved at 11:52 AM.</div>`;
    if (STATE === "error") return `<div class="banner error" style="margin-top:20px">${icon("refresh")}Couldn't refresh listings. Showing results from 11:52 AM.<button class="btn">Try again</button></div>`;
    return "";
  }

  function deadlinePeek() {
    const d = deadlines[0];
    return `<a class="panel deadline-peek" href="${keep({ view: "deadlines" })}" style="text-decoration:none">${countdown(d.start)}
      <div><strong>${esc(d.title)}</strong><span>Next deadline, ${shortDate(d.start)}</span></div>${icon("chev-right", "icon-sm")}</a>`;
  }

  /* ---------- views ---------- */
  function viewFood() {
    return nowBand() + toolbar() + `<div class="wrap page"><main id="main">${banner()}${deadlinePeek()}${timeline(food)}
      <div class="mobile-only" style="margin-top:28px">${resourcesPanel()}</div></main>
      <aside class="rail" aria-label="Calendar and deadlines">${miniCal()}${STATE === "loading" ? "" : deadlinesPanel() + resourcesPanel() + alertsPanel()}</aside></div>`;
  }

  function viewEvents() {
    return `<div class="wrap page-intro"><h1>Campus events</h1><p>Talks, games, workshops and shows from ${"20"} UMBC calendars, merged into one list.</p></div>`
      + toolbar() + `<div class="wrap page"><main id="main">${timeline(events)}</main>
      <aside class="rail">${miniCal()}${deadlinesPanel(2)}</aside></div>`;
  }

  function viewDeadlines() {
    const groups = [];
    const push = (name, items) => items.length && groups.push([name, items]);
    const thisWeek = deadlines.filter(d => dayDiff(d.start) <= 7);
    const rest = deadlines.filter(d => dayDiff(d.start) > 7);
    push("Next 7 days", thisWeek);
    const byMonth = new Map();
    rest.forEach(d => { const k = d.start.toLocaleDateString("en-US", { month: "long" }); if (!byMonth.has(k)) byMonth.set(k, []); byMonth.get(k).push(d); });
    byMonth.forEach((v, k) => push(k === NOW.toLocaleDateString("en-US", { month: "long" }) ? `Later in ${k}` : k, v));
    const body = groups.map(([name, items]) => `<section class="dl-group"><h2>${name}</h2>${items.map(d => `
      <article class="dl-row" onclick="location.search='${keep({ view: VIEW, open: d.id }).slice(1)}'">${countdown(d.start)}
        <div><h3>${esc(d.title)}</h3><div class="meta"><span>${d.end ? `${shortDate(d.start)} to ${shortDate(d.end)}` : longDate(d.start)}</span><span style="color:var(--ink-3)">${esc(d.source)}</span></div></div>
        <button class="save ${SAVED.has(d.id) ? "on" : ""}" aria-label="Save" onclick="event.stopPropagation()">${icon("bookmark")}</button></article>`).join("")}</section>`).join("");
    return `<div class="wrap page-intro"><h1>Deadlines</h1><p>Registrar and billing dates for Fall 2026, counted down from today.</p></div>`
      + toolbar() + `<div class="wrap page"><main id="main">${body}</main>
      <aside class="rail">${miniCal()}<section class="rail-section"><div class="panel alert-card">
        <h2 style="margin:0;font-size:var(--fs-15);display:flex;gap:8px;align-items:center">${icon("calendar", "icon-sm")}Put every deadline in your calendar</h2>
        <p>Subscribe once and new Registrar and billing dates appear in Google Calendar, Outlook or Apple Calendar automatically.</p>
        <a class="btn primary block" href="#">Subscribe to deadlines</a></div></section></aside></div>`;
  }

  function viewSaved() {
    if (STATE === "empty") {
      return `<div class="wrap page-intro"><h1>Saved</h1></div><div class="wrap page single"><main><div class="empty">
        <span class="ico">${icon("bookmark")}</span><h3>Nothing saved yet</h3>
        <p>Tap the bookmark on any food listing, event or deadline to keep it here. Saved items stay on this device.</p>
        <a class="btn primary" href="${keep({ view: "food" })}">Browse free food</a></div></main></div>`;
    }
    const items = all.filter(e => SAVED.has(e.id)).sort((a, b) => a.start - b.start);
    return `<div class="wrap page-intro"><h1>Saved</h1><p>Kept on this device. Past items clear themselves after a week.</p></div>` + toolbar()
      + `<div class="wrap page"><main>${timeline(items.filter(e => e.category !== "important_date"))}
      <section class="dl-group"><h2>Deadlines</h2>${items.filter(e => e.category === "important_date").map(d => `<article class="dl-row">${countdown(d.start)}<div><h3>${esc(d.title)}</h3><div class="meta">${longDate(d.start)}</div></div><button class="save on">${icon("bookmark")}</button></article>`).join("")}</section>
      </main><aside class="rail">${miniCal()}</aside></div>`;
  }

  /* ---------- drawer ---------- */
  function drawer(e) {
    if (!e) return "";
    const isDeadline = e.category === "important_date";
    const live = isLive(e);
    const when = isDeadline
      ? (e.end ? `${longDate(e.start)} to ${longDate(e.end)}` : longDate(e.start))
      : e.start ? `${dayName(e.start)}, ${e.start.toLocaleDateString("en-US", { month: "long", day: "numeric" })}<br>${timeStr(e.start)} to ${timeStr(e.end)}` : esc(e.recurrence_text);
    const sameDay = e.category !== "food_event" ? [] : all.filter(x => x.id !== e.id && x.category === "food_event" && x.start && e.start && x.start.toDateString() === e.start.toDateString()).slice(0, 3);
    return `<div class="scrim" onclick="location.search='${keep({ view: VIEW }).slice(1)}'"></div>
    <aside class="drawer" role="dialog" aria-modal="true" aria-labelledby="dTitle">
      <div class="drawer-top"><div class="crumbs">${isDeadline ? '<span class="tag urgent">Deadline</span>' : e.category === "food_event" ? '<span class="tag food">Free food</span>' : `<span class="tag">${esc(e.event_type || "Event")}</span>`}<span class="tag">${esc(e.source)}</span></div>
        <a class="icon-btn" href="${keep({ view: VIEW })}" aria-label="Close">${icon("x")}</a></div>
      <div class="drawer-body">
        <h2 class="title" id="dTitle">${esc(e.title)}</h2>
        ${live ? `<div class="live-strip"><span class="dot pulse"></span>Serving now, ${dur(minsUntil(e.end))} left<div class="progress"><span style="width:${pct(e)}%"></span></div></div>` : ""}
        ${isDeadline ? `<div class="live-strip" style="background:var(--urgent-wash);color:var(--urgent)">${icon("alarm", "icon-sm")}Due in ${dayDiff(e.start)} days</div>` : ""}
        <dl class="facts">
          <div class="fact">${icon("clock")}<div><dt>When</dt><dd>${when}</dd></div></div>
          ${e.location ? `<div class="fact">${icon("pin")}<div><dt>Where</dt><dd>${esc(e.location)}<br><a href="#">Open in UMBC campus map</a></dd></div></div>` : ""}
          ${(e.food_items || []).length ? `<div class="fact">${icon("food")}<div><dt>Food</dt><dd><div class="tags" style="margin-top:4px">${e.food_items.map(f => `<span class="tag food">${esc(f)}</span>`).join("")}</div>
            <span class="note">Picked up from the listing text. Supplies usually run out, so arrive early.</span></dd></div></div>` : ""}
        </dl>
        ${e.description ? `<p class="about">${esc(e.description)}</p>` : ""}
        <p style="margin-top:14px"><a href="${esc(e.link)}" style="font-size:var(--fs-13);font-weight:600;color:var(--ink-2);display:inline-flex;gap:6px;align-items:center">${icon("external", "icon-sm")}View the original listing on ${esc(e.source)}</a></p>
        ${sameDay.length ? `<div class="also"><h4>More free food ${dayDiff(e.start) <= 1 ? dayName(e.start).toLowerCase() : "on " + dayName(e.start)}</h4>${sameDay.map(x => `<a href="${keep({ view: VIEW, open: x.id })}"><b>${timeStr(x.start)}</b><span>${esc(x.title)}<br><span style="color:var(--ink-3)">${esc(x.location)}</span></span></a>`).join("")}</div>` : ""}
      </div>
      <div class="drawer-actions">
        <button class="btn primary">${icon("calendar", "icon-sm")}Add to calendar<span class="desktop-only" style="display:inline-flex">${icon("chev-down", "icon-sm")}</span></button>
        <button class="btn ${SAVED.has(e.id) ? "" : ""}">${icon("bookmark", "icon-sm")}${SAVED.has(e.id) ? "Saved" : "Save"}</button>
        <button class="btn" aria-label="Share">${icon("share", "icon-sm")}<span class="desktop-only">Share</span></button>
      </div>
    </aside>`;
  }

  const views = { food: viewFood, events: viewEvents, deadlines: viewDeadlines, saved: viewSaved };
  document.getElementById("app").innerHTML = (views[VIEW] || viewFood)() + drawer(all.find(e => e.id === OPEN));
  if (OPEN) document.body.style.overflow = "hidden";

  // "/" focuses search, Esc closes drawer
  document.addEventListener("keydown", ev => {
    if (ev.key === "/" && document.activeElement.tagName !== "INPUT") { ev.preventDefault(); document.querySelector(".search input")?.focus(); }
    if (ev.key === "Escape" && OPEN) location.search = keep({ view: VIEW }).slice(1);
  });
})();
