const CACHE='radarazioni-0.6.0-static';
const FILES=['./','./index.html','./style.css?v=0.6.0','./app.js?v=0.6.0','./radar-core.js?v=0.6.0','./update.js?v=0.6.0','./icon.svg','./icon-192.png','./icon-512.png','./manifest.webmanifest'];
self.addEventListener('install',event=>{event.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES)))});
self.addEventListener('message',event=>{if(event.data?.type==='SKIP_WAITING') self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('radarazioni-')&&k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()))});
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  if(url.origin!==self.location.origin || url.pathname.includes('/data/') || url.pathname.endsWith('/version.json') || event.request.method!=='GET') return;
  event.respondWith(fetch(event.request).then(async response=>{
    if(response.ok&&response.type==='basic'){const cp=response.clone();await caches.open(CACHE).then(c=>c.put(event.request,cp)).catch(()=>{})}
    return response;
  }).catch(()=>caches.match(event.request)));
});
