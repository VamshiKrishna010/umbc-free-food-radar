// Sample data for the UI prototype. Shape follows the proposed data contract in
// UI_REDESIGN_SPEC.md section 9 (start_at / end_at / location / food_items / kind).
// Titles, rooms and dates are illustrative only.
window.SAMPLE_EVENTS = [
  // ---------- Free food ----------
  {
    id: "f1", category: "food_event", source: "myUMBC", kind: "one_time",
    title: "Pizza and pair programming night",
    start_at: "2026-10-12T12:00:00", end_at: "2026-10-12T13:30:00",
    location: "ITE 104", food_items: ["Pizza", "Soda"],
    description: "Bring a laptop and a problem you are stuck on. Peer mentors will pair up with anyone who drops in. Pizza will be provided while it lasts.",
    link: "https://my.umbc.edu/"
  },
  {
    id: "f2", category: "food_event", source: "UMBC Events", kind: "one_time",
    title: "International coffee hour",
    start_at: "2026-10-12T12:00:00", end_at: "2026-10-12T13:00:00",
    location: "The Commons, Skylight Room", food_items: ["Coffee", "Snacks"],
    description: "Meet students from around the world over coffee, tea and snacks. Everyone is welcome.",
    link: "https://umbc.edu/events/"
  },
  {
    id: "f3", category: "food_event", source: "Graduate School", kind: "one_time",
    title: "Lunch and learn: planning your thesis proposal",
    start_at: "2026-10-12T13:00:00", end_at: "2026-10-12T14:00:00",
    location: "AOK Library, Room 767", food_items: ["Lunch"],
    description: "A one-hour session on scoping a proposal, building a timeline with your advisor and avoiding common delays. Lunch is provided for registered attendees.",
    link: "https://gradschool.umbc.edu/"
  },
  {
    id: "f4", category: "food_event", source: "Student Events Board", kind: "one_time",
    title: "SEB movie night with free popcorn",
    start_at: "2026-10-12T20:00:00", end_at: "2026-10-12T22:15:00",
    location: "Lecture Hall 5", food_items: ["Popcorn", "Candy"],
    description: "This week's pick is a campus-voted favorite. Free popcorn and candy at the door while supplies last.",
    link: "https://seb.umbc.edu/"
  },
  {
    id: "f5", category: "food_event", source: "Career Center", kind: "one_time",
    title: "Bagel breakfast with recruiters",
    start_at: "2026-10-13T09:30:00", end_at: "2026-10-13T10:30:00",
    location: "Career Center, Math & Psychology 2nd floor", food_items: ["Bagels", "Coffee"],
    description: "Informal breakfast before the fall tech fair. Bring a printed resume.",
    link: "https://careers.umbc.edu/"
  },
  {
    id: "f6", category: "food_event", source: "Physics Department", kind: "one_time",
    title: "Physics colloquium: dark matter detectors",
    start_at: "2026-10-13T15:30:00", end_at: "2026-10-13T16:45:00",
    location: "Physics 401", food_items: ["Refreshments"],
    description: "Refreshments are served 15 minutes before the talk.",
    link: "https://physics.umbc.edu/"
  },
  {
    id: "f7", category: "food_event", source: "myUMBC", kind: "one_time",
    title: "Commuter student taco night",
    start_at: "2026-10-13T17:30:00", end_at: "2026-10-13T19:00:00",
    location: "Commuter Lounge, The Commons", food_items: ["Tacos"],
    description: "Tacos, games and a chance to meet other commuters. Vegetarian options available.",
    link: "https://my.umbc.edu/"
  },
  {
    id: "f8", category: "food_event", source: "Math & Statistics", kind: "one_time",
    title: "Math and stat tea with cookies",
    start_at: "2026-10-14T15:45:00", end_at: "2026-10-14T16:30:00",
    location: "Math & Psychology 401", food_items: ["Cookies", "Tea"],
    description: "Weekly department tea before the Wednesday seminar.",
    link: "https://mathstat.umbc.edu/"
  },
  {
    id: "f9", category: "food_event", source: "Student Events Board", kind: "one_time",
    title: "Late-night pancakes",
    start_at: "2026-10-16T22:00:00", end_at: "2026-10-16T23:30:00",
    location: "True Grit's Dining Hall", food_items: ["Pancakes"],
    description: "Pancakes flipped by SEB volunteers. Bring your student ID.",
    link: "https://seb.umbc.edu/"
  },
  // ---------- Recurring / ongoing food resources ----------
  {
    id: "r1", category: "food_event", source: "Retriever Essentials", kind: "ongoing",
    title: "The Essential Space (free grocery store)",
    recurrence_text: "Open weekdays, check posted hours",
    location: "RAC 235", food_items: ["Groceries"],
    description: "A free grocery store for any UMBC student. No sign-up or proof of need required.",
    link: "https://retrieveressentials.umbc.edu/"
  },
  {
    id: "r2", category: "food_event", source: "Retriever Essentials", kind: "recurring",
    title: "Fresh food pop-up",
    recurrence_text: "Every Thursday, 2:15 to 2:45 PM",
    start_at: "2026-10-15T14:15:00", end_at: "2026-10-15T14:45:00",
    location: "Commons Main Street", food_items: ["Produce"],
    description: "Free fresh produce. Bring a bag.",
    link: "https://retrieveressentials.umbc.edu/"
  },

  // ---------- Campus events ----------
  { id: "c1", category: "campus_event", source: "UMBC Events", event_type: "Workshop", kind: "one_time",
    title: "Zotero basics for research papers", start_at: "2026-10-12T14:00:00", end_at: "2026-10-12T15:00:00",
    location: "AOK Library, Room 160", description: "Hands-on workshop.", link: "#" },
  { id: "c2", category: "campus_event", source: "UMBC Athletics", event_type: "Sports", kind: "one_time",
    title: "Men's soccer vs. Albany", start_at: "2026-10-12T19:00:00", end_at: "2026-10-12T21:00:00",
    location: "Retriever Soccer Park", description: "Home game. Free for students with ID.", link: "#" },
  { id: "c3", category: "campus_event", source: "Career Center", event_type: "Career", kind: "one_time",
    title: "Fall tech and engineering career fair", start_at: "2026-10-13T11:00:00", end_at: "2026-10-13T15:00:00",
    location: "Chesapeake Employers Insurance Arena", description: "Over 80 employers.", link: "#", food_items: [] },
  { id: "c4", category: "campus_event", source: "UMBC Tickets", event_type: "Arts", kind: "one_time",
    title: "Theatre: opening night of the fall production", start_at: "2026-10-15T19:30:00", end_at: "2026-10-15T21:30:00",
    location: "Proscenium Theatre, PAHB", description: "Student tickets available.", link: "#" },
  { id: "c5", category: "campus_event", source: "Department Seminars", event_type: "Talk", kind: "one_time",
    title: "CSEE seminar: trustworthy retrieval for LLMs", start_at: "2026-10-14T13:00:00", end_at: "2026-10-14T14:00:00",
    location: "ITE 325B", description: "Seminar talk.", link: "#" },
  { id: "c6", category: "campus_event", source: "Campus Life", event_type: "Social", kind: "one_time",
    title: "Board game night at the RAC", start_at: "2026-10-14T19:00:00", end_at: "2026-10-14T22:00:00",
    location: "RAC Lounge", description: "Bring friends.", link: "#" },

  // ---------- Important dates ----------
  { id: "d1", category: "important_date", source: "Registrar", kind: "one_time", all_day: true,
    title: "Spring 2027 schedule of classes published", start_at: "2026-10-14T00:00:00", link: "#",
    description: "Browse spring sections and plan with your advisor before registration opens." },
  { id: "d2", category: "important_date", source: "Student Business Services", kind: "one_time", all_day: true,
    title: "October billing statement due", start_at: "2026-10-15T00:00:00", link: "#",
    description: "Pay through the student account portal to avoid a late fee." },
  { id: "d3", category: "important_date", source: "Registrar", kind: "one_time", all_day: true,
    title: "Last day to change a course to pass/fail", start_at: "2026-10-23T00:00:00", link: "#", description: "" },
  { id: "d4", category: "important_date", source: "Registrar", kind: "one_time", all_day: true,
    title: "Spring 2027 registration opens for seniors", start_at: "2026-11-02T00:00:00", link: "#", description: "" },
  { id: "d5", category: "important_date", source: "Registrar", kind: "one_time", all_day: true,
    title: "Last day to drop a class with a W", start_at: "2026-11-09T00:00:00", link: "#", description: "" },
  { id: "d6", category: "important_date", source: "Student Business Services", kind: "one_time", all_day: true,
    title: "November billing statement due", start_at: "2026-11-15T00:00:00", link: "#", description: "" },
  { id: "d7", category: "important_date", source: "Registrar", kind: "one_time", all_day: true,
    title: "Thanksgiving break, no classes", start_at: "2026-11-26T00:00:00", end_at: "2026-11-29T00:00:00", link: "#", description: "" },
  { id: "d8", category: "important_date", source: "Registrar", kind: "one_time", all_day: true,
    title: "Last day of classes", start_at: "2026-12-10T00:00:00", link: "#", description: "" },
  { id: "d9", category: "important_date", source: "Registrar", kind: "one_time", all_day: true,
    title: "Final exams", start_at: "2026-12-12T00:00:00", end_at: "2026-12-18T00:00:00", link: "#", description: "" }
];
