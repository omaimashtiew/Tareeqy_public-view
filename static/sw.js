const CACHE_VERSION = Date.now();
const CACHE_NAME = `tareeqy-${CACHE_VERSION}`;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll([
        '/',
        '/static/css/styles.css',
        '/static/css/welcome-page.css',
        '/static/js/map_config.js',
        '/static/js/ui_interactions.js',
        '/static/js/data_handler.js',
        '/static/js/location.js',
        '/static/js/search.js',
        '/static/js/route_planner.js',
        '/static/js/main_map.js',
        '/static/icons/cover1.png',  // صححت اسم الصورة
        '/static/manifest.json'      // أضفت / في البداية
      ]))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});
