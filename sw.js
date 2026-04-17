const CACHE = 'ci-charts-v3';
const ASSETS = ['/', '/manifest.json', '/icons/icon-192.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys =>
    Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))
  ));
  self.clients.claim();
});

self.addEventListener('fetch', e => {
  const url = e.request.url;
  if (!url.startsWith('http')) return;
  if (e.request.method !== 'GET') return;
  if (url.includes('kworb.net') || url.includes('groq.com') || url.includes('allorigins') || url.includes('corsproxy')) return;

  e.respondWith(
    fetch(e.request)
      .then(r => {
        if (r && r.status === 200 && r.type !== 'opaque') {
          caches.open(CACHE).then(c => c.put(e.request, r.clone()));
        }
        return r;
      })
      .catch(() => caches.match(e.request))
  );
});
