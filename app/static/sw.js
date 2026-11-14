// Offline support: app shell, the trips already opened, and the map tiles already seen stay readable without network.
const SHELL = "rp-shell-v1";
const DATA = "rp-data-v1";
const TILES = "rp-tiles-v1";
const MAX_TILES = 1500;
const SHELL_FILES = ["/", "/styles.css", "/app.js", "/vendor/leaflet.js", "/vendor/leaflet.css", "/manifest.webmanifest", "/icons/icon-192.png"];
// Read-only API answers worth keeping: who am I, my trips, one trip with places and routes
const CACHED_API = /^\/api\/(me|trips|trips\/\d+)$/;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES)));
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  const keep = [SHELL, DATA, TILES];
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => !keep.includes(k)).map((k) => caches.delete(k)))));
  self.clients.claim();
});

self.addEventListener("message", (e) => {
  if (e.data === "clear-data") caches.delete(DATA); // on logout
});

async function networkFirst(request, cacheName, timeoutMs) {
  const cache = await caches.open(cacheName);
  try {
    const ctrl = new AbortController();
    const timer = timeoutMs && setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(request, { cache: "no-cache", signal: ctrl.signal });
    clearTimeout(timer);
    if (res.ok) cache.put(request, res.clone());
    return res;
  } catch (err) {
    const hit = await cache.match(request);
    if (!hit) throw err;
    // Tell the app that this answer is the last known state, not a fresh one
    const headers = new Headers(hit.headers);
    headers.set("X-From-Cache", "1");
    return new Response(await hit.blob(), { status: hit.status, headers });
  }
}

async function cacheFirst(request, cacheName, max) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(request);
  if (hit) return hit;
  const res = await fetch(request);
  if (res.ok) {
    cache.put(request, res.clone());
    if (max && Math.random() < 0.02) trim(cache, max);
  }
  return res;
}

async function trim(cache, max) {
  const keys = await cache.keys();
  for (const key of keys.slice(0, Math.max(0, keys.length - max))) cache.delete(key);
}

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  if (url.hostname === "tile.openstreetmap.org" || url.hostname === "upload.wikimedia.org") {
    e.respondWith(cacheFirst(e.request, TILES, MAX_TILES));
  } else if (url.origin !== location.origin) {
    return;
  } else if (url.pathname.startsWith("/api/")) {
    if (CACHED_API.test(url.pathname)) e.respondWith(networkFirst(e.request, DATA, 6000));
  } else {
    e.respondWith(networkFirst(e.request, SHELL));
  }
});
