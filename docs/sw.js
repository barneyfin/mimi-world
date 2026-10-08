// Mimi World offline copy.
// Change VERSION whenever any file below changes, so tablets pick up the new copy.
const VERSION = 'mimi-world-v0.1.2';
const FILES = ['./', './index.html', './manifest.json', './icon-192.png', './icon-512.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    // cache: 'reload' skips the browser's own short-term cache, so a new version saves new files
    caches.open(VERSION)
      .then((cache) => cache.addAll(FILES.map((f) => new Request(f, { cache: 'reload' }))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// Open from the saved copy straight away, then refresh the saved copy in the background.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== self.location.origin) return;
  event.respondWith(
    caches.open(VERSION).then((cache) =>
      cache.match(req, { ignoreSearch: true }).then((saved) => {
        // no-cache: always ask the server if there's something newer
        const fresh = fetch(req.url, { cache: 'no-cache', credentials: 'same-origin' })
          .then((res) => {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          })
          .catch(() => saved);
        if (saved) {
          event.waitUntil(fresh);
          return saved;
        }
        return fresh;
      })
    )
  );
});
