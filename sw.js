// Kill switch for an old third-party push service worker removed on 2026-10-27: browsers that
// registered it keep re-fetching this file; this version unregisters itself (dropping the push
// subscription) and reloads open tabs. Delete this file and its _headers entry after 2026-11-26.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    await self.registration.unregister();
    const tabs = await self.clients.matchAll({ type: 'window' });
    tabs.forEach(tab => tab.navigate(tab.url));
  })());
});
