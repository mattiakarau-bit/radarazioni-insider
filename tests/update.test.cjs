const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {APP_VERSION,isNewVersion}=require('../docs/update.js');
test('version manifest, interface and worker agree',()=>{
 assert.equal(JSON.parse(fs.readFileSync('docs/version.json')).version,APP_VERSION);
 assert.ok(fs.readFileSync('docs/sw.js','utf8').includes(`radarazioni-${APP_VERSION}-static`));
 assert.ok(fs.readFileSync('docs/index.html','utf8').includes('data-app-version'));
});
test('version detection ignores malformed and unchanged manifests',()=>{
 assert.equal(isNewVersion(APP_VERSION,APP_VERSION),false);
 assert.equal(isNewVersion('0.5.0',APP_VERSION),true);
 for(const v of [null,undefined,{},'bad'])assert.equal(isNewVersion(v,APP_VERSION),false);
});
test('worker excludes live data and version, activates only on request',()=>{
 const handlers={}; let skipped=0;
 vm.runInNewContext(fs.readFileSync('docs/sw.js','utf8'),{URL,self:{location:{origin:'https://example.com'},addEventListener:(n,f)=>handlers[n]=f,skipWaiting:()=>skipped++}});
 for(const path of ['/data/results.json','/version.json']) {
  handlers.fetch({request:{url:'https://example.com'+path,method:'GET'},respondWith:()=>assert.fail('live data must bypass cache')});
 }
 handlers.message({data:{type:'OTHER'}});assert.equal(skipped,0);
 handlers.message({data:{type:'SKIP_WAITING'}});assert.equal(skipped,1);
});
test('client displays update and button reloads without reinstalling',async()=>{
 const events={};let offered=false,reloads=0;
 const button={addEventListener:(n,f)=>events[n]=f};
 vm.runInNewContext(fs.readFileSync('docs/update.js','utf8'),{
  document:{querySelectorAll:()=>[],querySelector:s=>s==='#updateApp'?button:{classList:{remove:()=>offered=true}}},
  navigator:{},location:{protocol:'https:',reload:()=>reloads++},
  window:{addEventListener:()=>{}},setInterval:()=>{},Date,
  fetch:async()=>({ok:true,json:async()=>({version:'0.5.0'})})
 });
 await new Promise(r=>setImmediate(r));
 assert.equal(offered,true);await events.click();assert.equal(reloads,1);
 assert.equal(isNewVersion('0.3.0',APP_VERSION),false);
});
test('release assets bypass stale browser HTTP caches',()=>{
 const html=fs.readFileSync('docs/index.html','utf8'),sw=fs.readFileSync('docs/sw.js','utf8');
 for(const asset of ['app.js','update.js','style.css']){
  assert.ok(html.includes(`./${asset}?v=${APP_VERSION}`));
  assert.ok(sw.includes(`./${asset}?v=${APP_VERSION}`));
 }
});
