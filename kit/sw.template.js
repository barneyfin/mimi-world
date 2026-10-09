// Mimi World offline copy. Written by tools/build.py: don't edit docs/sw.js by hand.
// VERSION changes with every build that changes a file, so tablets pick up the new copy. A tablet saves the new
// copy in the background the next time Mimi World opens, then switches to it at the start screen (never mid-round).
const VERSION = '__CACHE__';
const FILES = __FILES__;

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
    caches.keys().then((keys) => {
      // only Mimi World's own saved copies: other apps on the same site keep theirs
      const old = keys.filter((k) => k !== VERSION && k.indexOf('mimi-world-') === 0);
      // The phase 0 tablet test page (offline copies named mimi-world-v0.1.*) can't hear the message below,
      // so a tablet still showing it is moved straight to the new page.
      const fromTestPage = old.some((k) => /^mimi-world-v0\.1\./.test(k));
      return Promise.all(old.map((k) => caches.delete(k)))
        .then(() => self.clients.claim())
        .then(() => self.clients.matchAll({ type: 'window' }))
        .then((windows) => windows.forEach((w) => {
          const page = w.url.split(/[?#]/)[0];
          if (page !== self.registration.scope && page !== self.registration.scope + 'index.html') return; // not the game (e.g. the recording page)
          if (fromTestPage) w.navigate(w.url);
          else if (old.length) w.postMessage({ type: 'mw-updated', version: VERSION });
        }));
    })
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
