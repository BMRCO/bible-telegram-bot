const CACHE_NAME = 'labible-v42';

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/offline.html',
  '/styles.css?v=4',
  '/app.v2.js',
  '/footer.js',
  '/header.js',
  '/data/explications.json',
  '/manifest.webmanifest',
  '/a-propos.html',
  '/contact.html',
  '/legal.html',
  '/installer.html',
  '/liens.html',
  '/icons/icon-192x192.png',
  '/icons/icon-512x512.png',
];

const BIBLE_DATA = '/data/lsg1910.json';

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(async cache => {
      await Promise.allSettled(
        STATIC_ASSETS.map(url =>
          fetch(url, { cache: 'reload' }).then(res => {
            if (res.ok) return cache.put(url, res);
          }).catch(() => {})
        )
      );
      try {
        const res = await fetch(BIBLE_DATA, { cache: 'reload' });
        if (res.ok) await cache.put(BIBLE_DATA, res);
        console.log('[SW] Bible JSON mis en cache ✓');
      } catch (e) {
        console.warn('[SW] Bible JSON non disponible:', e);
      }
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => {
            console.log('[SW] Suppression ancien cache:', key);
            return caches.delete(key);
          })
      )
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  if (request.method !== 'GET') return;
  if (!url.origin.includes(self.location.origin) && !url.hostname.includes('fonts.googleapis') && !url.hostname.includes('fonts.gstatic')) return;

  if (url.pathname === BIBLE_DATA) {
    event.respondWith(cacheFirst(request));
    return;
  }

  if (url.hostname.includes('fonts.googleapis') || url.hostname.includes('fonts.gstatic')) {
    event.respondWith(cacheFirst(request));
    return;
  }

  if (request.mode === 'navigate' || request.destination === 'document' || url.pathname.endsWith('.html') || url.pathname === '/') {
    event.respondWith(networkFirst(request));
    return;
  }

  event.respondWith(staleWhileRevalidate(request));
});

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Contenu non disponible hors ligne.', { status: 503 });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request, { cache: 'reload' });
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return caches.match('/offline.html');
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);

  const fetchPromise = fetch(request).then(response => {
    if (response.ok) cache.put(request, response.clone());
    return response;
  }).catch(() => null);

  return cached || fetchPromise || new Response('Hors ligne', { status: 503 });
}