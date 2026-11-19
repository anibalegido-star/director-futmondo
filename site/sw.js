// Guarda la app para abrirla sin conexión. Los datos (data.enc) siempre se piden
// frescos y, si no hay red, se usa la última copia guardada.
const CACHE = "director-v1";
const SHELL = ["./", "index.html", "manifest.webmanifest", "icon.svg", "icon-192.png"];
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener("activate", e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))); self.clients.claim(); });
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (url.origin !== location.origin) return;
  e.respondWith(fetch(e.request).then(r => {
    const copy = r.clone();
    if (r.ok) caches.open(CACHE).then(c => c.put(url.pathname.endsWith("data.enc") ? "data.enc" : e.request, copy));
    return r;
  }).catch(() => caches.match(url.pathname.endsWith("data.enc") ? "data.enc" : e.request)));
});
