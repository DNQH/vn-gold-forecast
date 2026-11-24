/* Service worker: vỏ ứng dụng cache-first (có đánh số phiên bản); data/latest.json network-first; không bao giờ cache CafeF. */
const VERSION = "v1";
const SHELL = "vngold-shell-" + VERSION;
const DATA = "vngold-data-" + VERSION;
const SHELL_FILES = ["./", "index.html", "app.js", "style.css", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png", "icons/apple-touch-icon-180.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES.map((u) => new Request(u, {cache: "reload"})))).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== SHELL && k !== DATA).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

function fromCacheCopy(res) {
  const h = new Headers(res.headers);
  h.set("X-From-Cache", "1");
  return res.blob().then((b) => new Response(b, {status: res.status, statusText: res.statusText, headers: h}));
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // CafeF và mọi bên ngoài: đi thẳng mạng, không cache
  if (url.pathname.endsWith("/data/latest.json")) {
    e.respondWith((async () => {
      const cache = await caches.open(DATA);
      try {
        const res = await fetch(req);
        if (res.ok) await cache.put(new Request(new URL("data/latest.json", self.registration.scope).href), res.clone());
        return res;
      } catch (err) {
        const hit = await cache.match(new URL("data/latest.json", self.registration.scope).href);
        if (hit) return fromCacheCopy(hit);
        throw err;
      }
    })());
    return;
  }
  e.respondWith((async () => {
    const hit = await caches.match(req, {ignoreSearch: true, cacheName: SHELL});
    if (hit) return hit;
    try {
      return await fetch(req);
    } catch (err) {
      if (req.mode === "navigate") { const idx = await caches.match("index.html", {cacheName: SHELL}); if (idx) return idx; }
      throw err;
    }
  })());
});
