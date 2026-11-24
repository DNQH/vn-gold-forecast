/* Service worker.
 * - Vỏ ứng dụng (index.html, app.js, style.css, biểu tượng): stale-while-revalidate – mở ngay từ bộ nhớ máy
 *   (chạy được khi mất mạng), đồng thời tải bản mới về nền để lần mở sau dùng bản mới. Như vậy điện thoại
 *   không bị kẹt mãi ở bản cũ ngay cả khi quên đổi VERSION.
 * - Đổi VERSION khi sửa vỏ ứng dụng: service worker mới cài lại toàn bộ vỏ, kích hoạt ngay, và app.js tải lại
 *   trang một lần (controllerchange) để dùng bản mới ngay.
 * - data/latest.json: network-first, mất mạng thì dùng bản đã lưu (gắn X-From-Cache để hiện thông báo).
 * - CafeF và mọi địa chỉ bên ngoài: không đụng tới (đi thẳng mạng, không cache).
 */
const VERSION = "v2";
const SHELL = "vngold-shell-" + VERSION;
const DATA = "vngold-data";
const SHELL_FILES = ["./", "index.html", "app.js", "style.css", "manifest.webmanifest",
  "icons/icon-192.png", "icons/icon-512.png", "icons/maskable-512.png", "icons/apple-touch-icon-180.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(SHELL_FILES.map((u) => new Request(u, {cache: "reload"}))))
    .then(() => self.skipWaiting()));
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

// khoá cache của vỏ: bỏ phần ?query (vd. ?now=… để thử nghiệm); điều hướng vào thư mục gốc dùng "./"
function shellKey(url) {
  const u = new URL(url.href);
  u.search = ""; u.hash = "";
  return u.href;
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // CafeF và mọi bên ngoài: đi thẳng mạng, không cache
  const dataKey = new URL("data/latest.json", self.registration.scope).href;
  if (url.pathname.endsWith("/data/latest.json")) {
    e.respondWith((async () => {
      const cache = await caches.open(DATA);
      try {
        const res = await fetch(req);
        if (res.ok) await cache.put(dataKey, res.clone());
        return res;
      } catch (err) {
        const hit = await cache.match(dataKey);
        if (hit) return fromCacheCopy(hit);
        throw err;
      }
    })());
    return;
  }
  const key = shellKey(url);
  e.respondWith((async () => {
    const cache = await caches.open(SHELL);
    const save = async (res) => {
      if (res.ok && res.type === "basic" && !res.redirected) await cache.put(key, res.clone());
      return res;
    };
    const hit = await cache.match(key);
    if (hit) {
      // cập nhật nền cho lần mở sau (no-cache: hỏi lại máy chủ bằng ETag, rẻ)
      e.waitUntil(fetch(key, {cache: "no-cache", credentials: "same-origin"}).then(save).catch(() => {}));
      return hit;
    }
    try {
      return await save(await fetch(req));
    } catch (err) {
      if (req.mode === "navigate") {
        const idx = (await cache.match(new URL("./", self.registration.scope).href)) ||
          (await cache.match(new URL("index.html", self.registration.scope).href));
        if (idx) return idx;
      }
      throw err;
    }
  })());
});
