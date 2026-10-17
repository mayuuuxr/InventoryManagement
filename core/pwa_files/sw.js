/* nibba service worker v1 — installable-app shell.
 *
 * Strategy (deliberately boring, fits a server-rendered auth app):
 * - App pages (navigations): network-first, fall back to the last-seen
 *   copy when the site has no signal. Staff always see fresh balances
 *   when online; offline they at least get the shell, never a dead tab.
 * - Same-origin static + the 3 known CDN hosts (Tailwind/Inter/lucide):
 *   cache-first with background refresh. Everything else cross-origin
 *   (notably Cloudinary photo storage) is NEVER touched by this worker.
 * - Only GET requests are handled. POSTs (entries, deletes, login) always
 *   go straight to the network — the worker can neither complete nor
 *   safely replay them (offline entry queue is a separate future feature).
 */
var SHELL_CACHE = 'nibba-shell-v2';
var CDN_HOSTS = [
  'cdn.tailwindcss.com',
  'fonts.googleapis.com',
  'fonts.gstatic.com',
  'unpkg.com'
];
var PRECACHE = [
  '/sites/',
  '/manifest.webmanifest',
  '/pwa/icon-192.png',
  '/pwa/icon-512.png',
  '/pwa/icon-maskable-512.png',
  '/pwa/apple-touch-icon.png'
];

function offlinePage() {
  return new Response(
    '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<title>Offline — nibba</title></head>' +
    '<body style="font-family:system-ui,sans-serif;padding:32px 20px;text-align:center">' +
    '<h1>No signal</h1>' +
    '<p>Site network nahi hai. Signal aate hi page wapas load ho jayega.</p>' +
    '<button onclick="location.reload()" style="padding:12px 24px;font-size:16px">Retry</button>' +
    '</body></html>',
    { headers: { 'Content-Type': 'text/html' } }
  );
}

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then(function (cache) { return cache.addAll(PRECACHE).catch(function () {}); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys
          .filter(function (k) { return k !== SHELL_CACHE; })
          .map(function (k) { return caches.delete(k); }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var req = event.request;
  if (req.method !== 'GET') return;
  var url;
  try {
    url = new URL(req.url);
  } catch (e) { return; }
  var sameOrigin = url.origin === self.location.origin;
  if (!sameOrigin && CDN_HOSTS.indexOf(url.hostname) === -1) return;

  // App pages: fresh when online, last-seen copy when offline.
  // Only healthy (2xx) responses are cached — error pages must never
  // become the "offline copy". NOTE: cached pages are per-device, not
  // per-user: logout wipes this cache (see base.html) so a shared phone
  // can never offline-serve the previous member's balances.
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).then(function (res) {
        if (res && res.ok) {
          var copy = res.clone();
          caches.open(SHELL_CACHE)
            .then(function (c) { c.put(req, copy); })
            .catch(function () {});
        }
        return res;
      }).catch(function () {
        return caches.match(req).then(function (hit) { return hit || offlinePage(); });
      })
    );
    return;
  }

  // Static + known CDN: instant from cache, refresh behind the scenes.
  event.respondWith(
    caches.match(req).then(function (hit) {
      var net = fetch(req).then(function (res) {
        if (res && (res.ok || res.type === 'opaque')) {
          var copy = res.clone();
          caches.open(SHELL_CACHE)
            .then(function (c) { c.put(req, copy); })
            .catch(function () {});
        }
        return res;
      }).catch(function () { return hit; });
      return hit || net;
    })
  );
});

// nibba sends no push notifications (no VAPID, no push service), so this
// worker has no 'push' / 'notificationclick' handlers by design.
