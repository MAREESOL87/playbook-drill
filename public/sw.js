/* Playbook Drill, service worker. Bumper VERSION à chaque publication. */
const VERSION = 'playbook-drill-2026-11-09a';
const SHELL = ['./', 'index.html', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(VERSION).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== VERSION && k !== VERSION + '-ext').map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;                 // les écritures /api passent directement
  const url = new URL(e.request.url);
  if (url.pathname.includes('/api/')) return;             // l'API est toujours réseau
  if (url.origin !== location.origin) {                   // polices : cache opportuniste
    e.respondWith(caches.open(VERSION + '-ext').then(async c => {
      const hit = await c.match(e.request);
      const net = fetch(e.request).then(r => { c.put(e.request, r.clone()); return r; }).catch(() => hit);
      return hit || net;
    }));
    return;
  }
  const isShellEntry = e.request.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('index.html');
  if (isShellEntry) {                                      // page : réseau d'abord, cache en secours (hors ligne)
    e.respondWith(fetch(e.request).then(r => { caches.open(VERSION).then(c => c.put('index.html', r.clone())); return r; }).catch(() => caches.match('index.html')));
    return;
  }
  e.respondWith(caches.match(e.request).then(hit => hit || fetch(e.request).then(r => { caches.open(VERSION).then(c => c.put(e.request, r.clone())); return r; })));
});
