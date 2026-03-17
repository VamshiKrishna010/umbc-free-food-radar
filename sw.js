const CACHE_NAME = 'umbc-food-radar-v3';

self.addEventListener('install', (e) => {
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // API calls are always network-only to keep event data fresh.
  if (url.origin === self.location.origin && url.pathname.startsWith('/api/')) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' }).catch(() =>
        new Response(
          JSON.stringify({ error: 'Offline and no live data available' }),
          {
            status: 503,
            headers: {
              'Content-Type': 'application/json',
              'Cache-Control': 'no-store',
            },
          }
        )
      )
    );
    return;
  }

  // Network-first for scripts/styles to avoid stale client code.
  if (e.request.destination === 'script' || e.request.destination === 'style') {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          if (res.ok) {
            const clone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(e.request, clone));
          }
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  if (e.request.mode === 'navigate' || e.request.destination === 'document') {
    e.respondWith(
      fetch(e.request).catch(() =>
        caches.match('/').then((r) => r || caches.match(e.request))
      )
    );
    return;
  }
  e.respondWith(
    caches.match(e.request).then((r) => r || fetch(e.request))
  );
});
