/* 크립토 레이더 서비스워커
   - 앱 껍데기는 캐시 우선 (지하철에서도 즉시 열림)
   - 데이터는 네트워크 우선 (항상 최신 시세, 실패 시 캐시)          */

const CACHE = "crypto-radar-v2";
const SHELL = ["./", "./index.html", "./manifest.json",
               "./icons/icon-192.png", "./icons/apple-touch-icon.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;

  // 데이터: 네트워크 우선
  if (url.pathname.includes("/data/")) {
    e.respondWith(
      fetch(e.request)
        .then((res) => {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(e.request, copy));
          return res;
        })
        .catch(() => caches.match(e.request))
    );
    return;
  }

  // 앱 껍데기: 캐시 우선
  e.respondWith(
    caches.match(e.request).then((hit) => hit || fetch(e.request))
  );
});
