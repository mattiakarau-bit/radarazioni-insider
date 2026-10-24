const CACHE='radarazioni-v3-static';
const FILES=['./','./index.html','./style.css','./app.js','./icon.svg','./icon-192.png','./icon-512.png','./manifest.webmanifest'];
self.addEventListener('install', event => {event.waitUntil(caches.open(CACHE).then(c=>c.addAll(FILES)).catch(()=>{}));self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))));self.clients.claim()});
self.addEventListener('fetch',event=>{const url=new URL(event.request.url);
  if(url.pathname.includes('/data/') || event.request.method!=='GET')return;
  event.respondWith(fetch(event.request).then(response=>{if(response.ok&&response.type==='basic'){const cp=response.clone();caches.open(CACHE).then(c=>c.put(event.request,cp))}return response}).catch(()=>caches.match(event.request)));
});
