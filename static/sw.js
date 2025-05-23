const CACHE_VERSION = Date.now(); // رقم فريد في كل مرة
const CACHE_NAME = `tareeqy-${CACHE_VERSION}`;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll([
        '/',
        '/static/css/welcome-page.css',
        '/static/js/app.js'
      ]))
      .then(() => self.skipWaiting()) // تخطي مرحلة الانتظار
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
