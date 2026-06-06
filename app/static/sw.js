/**
 * KHANDHARS CHAT - Service Worker
 * PWA offline support and caching
 */

const CACHE_NAME = 'khandhars-chat-v1';
const STATIC_ASSETS = [
  '/',
  '/static/css/main.css',
  '/static/js/app.js',
  '/static/images/default-avatar.png',
  '/static/images/default-group.png',
  '/static/manifest.json',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (e) => {
  if (e.request.method !== 'GET') return;
  if (e.request.url.includes('/api/') || e.request.url.includes('/socket.io/')) return;

  e.respondWith(
    caches.match(e.request).then(cached => {
      const network = fetch(e.request).then(res => {
        if (res.ok && e.request.url.startsWith(self.location.origin)) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
        }
        return res;
      });
      return cached || network;
    })
  );
});

// Push notifications
self.addEventListener('push', (e) => {
  if (!e.data) return;
  const data = e.data.json();
  self.registration.showNotification(data.title || 'Khandhars Chat', {
    body: data.body || 'New message',
    icon: '/static/images/icon-192.png',
    badge: '/static/images/badge-72.png',
    data: data,
  });
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(clients.openWindow(e.notification.data?.url || '/chat/'));
});
