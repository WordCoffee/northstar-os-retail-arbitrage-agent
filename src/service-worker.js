// src/service-worker.js
const CACHE_NAME = 'northstar-os-v1';
const urlsToCache = [
  '/',
  '/index.html',
  '/src/styles/design-tokens.css',
  '/src/styles/glassmorphism.css',
  'https://fonts.googleapis.com/css2?family=Exo+2:wght@400;500;600;700&family=Inter:wght@300;400;500;600&display=swap',
  '/src/components/Layout/Layout.html',
  '/src/components/Layout/Layout.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request);
      })
  );
});

self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});