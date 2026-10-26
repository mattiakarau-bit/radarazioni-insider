'use strict';
const APP_VERSION = '0.9.0';
function isNewVersion(remote, current) {
  if (typeof remote !== 'string' || !/^\d+\.\d+\.\d+$/.test(remote)) return false;
  const a=remote.split('.').map(Number), b=current.split('.').map(Number);
  for (let i=0;i<3;i++) {if(a[i]!==b[i]) return a[i]>b[i]}
  return false;
}
if (typeof module !== 'undefined') module.exports = {APP_VERSION, isNewVersion};
if (typeof document !== 'undefined') {
  document.querySelectorAll('[data-app-version]').forEach(el=>{el.textContent=APP_VERSION});
  const banner=document.querySelector('#updateBanner'), button=document.querySelector('#updateApp');
  let registration, reloading=false;
  async function checkVersion() {
    try {
      const response=await fetch('./version.json?ts='+Date.now(),{cache:'no-store'});
      if (!response.ok) return;
      const remote=await response.json();
      if (isNewVersion(remote.version,APP_VERSION)) banner.classList.remove('hidden');
      if (registration) await registration.update();
    } catch {} // Offline use remains available; never claim a successful update.
  }
  button.addEventListener('click',async()=>{
    button.disabled=true;
    try {
      if (registration) await registration.update();
      if (registration?.waiting) {
        reloading=true;
        registration.waiting.postMessage({type:'SKIP_WAITING'});
        return;
      }
      location.reload();
    } catch {button.disabled=false;}
  });
  if ('serviceWorker' in navigator && location.protocol==='https:') {
    navigator.serviceWorker.addEventListener('controllerchange',()=>{if(reloading) location.reload()});
    navigator.serviceWorker.register('./sw.js',{updateViaCache:'none'}).then(reg=>{
      registration=reg;
      const show=()=>{if(reg.waiting && navigator.serviceWorker.controller) banner.classList.remove('hidden')};
      show();
      reg.addEventListener('updatefound',()=>{const worker=reg.installing;worker?.addEventListener('statechange',show)});
      checkVersion();
    }).catch(()=>{});
  }
  checkVersion();
  setInterval(checkVersion,5*60*1000);
  window.addEventListener('focus',checkVersion);
  window.addEventListener('online',checkVersion);
}
