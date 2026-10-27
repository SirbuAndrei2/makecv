// Monetag was removed on 2026-10-27. Browsers that registered its push service worker keep
// re-fetching this file; this version unregisters itself (which also drops the push subscription)
// and reloads open tabs, so those visitors stop getting Monetag notifications.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    await self.registration.unregister();
    const tabs = await self.clients.matchAll({ type: 'window' });
    tabs.forEach(tab => tab.navigate(tab.url));
  })());
});
