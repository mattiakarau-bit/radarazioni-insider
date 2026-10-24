/* Standalone tests against the local static app; no external service or credentials. */
const {chromium,webkit}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve('docs');
const server=http.createServer((req,res)=>{const pathname=new URL(req.url,'http://localhost').pathname;const file=path.join(root,pathname==='/'?'index.html':pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}fs.readFile(file,(e,body)=>{if(e){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.json')?'application/json':file.endsWith('.css')?'text/css':'text/html');res.end(body);});});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch({headless:true});
  try{for(const viewport of [{width:390,height:844},{width:768,height:1024},{width:320,height:568}]){
   const context=await browser.newContext({viewport,isMobile:true,hasTouch:true});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(()=>localStorage.setItem('radarazioni-watchlist-v2','["AAPL","CRBG"]'));
   await page.goto(base);await page.locator('#results .card').first().waitFor();
   assert.equal(await page.locator('nav button').count(),3);
   assert.equal(await page.getByRole('button',{name:'Da approfondire',exact:true}).count(),0);
   assert.equal(await page.locator('#favoriteCount').textContent(),'2');
   assert.ok(await page.locator('.score').first().textContent());
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'horizontal overflow');
   await page.locator('#scoreHelp').click();await page.locator('#detailDialog[open]').waitFor();
   assert.ok((await page.locator('#detailContent').textContent()).includes('70%'));await page.locator('#closeDetail').click();
   // Star a company, hide it with filters, then confirm favorites retain all operations.
   const first=page.locator('#results .card').filter({has:page.locator('.star[aria-pressed="false"]')}).first();const symbol=await first.locator('.ticker').textContent();
   await first.locator('.star').click();await page.waitForFunction(()=>JSON.parse(localStorage.getItem('radarazioni-favorites-v1')).items.length===3);
   await page.locator('#minAmount').fill('1000000000');await page.locator('#filtersForm button[type=submit]').click();
   await page.waitForFunction(()=>document.querySelectorAll('#results .card').length===0);
   assert.equal(await page.locator('#results .card').count(),0);
   await page.locator('nav [data-page=favorites]').click();await page.locator('#favoriteItems .card').first().waitFor();
   assert.ok((await page.locator('#favoriteItems').textContent()).includes(symbol));
   const before=await page.evaluate(()=>JSON.parse(localStorage.getItem('radarazioni-favorites-v1')).items.find(f=>f.cik)?.transactions.length);
   assert.ok(before>0);await page.reload();await page.locator('#resultsCount').waitFor();
   assert.equal(await page.locator('#favoriteCount').textContent(),'3');
   assert.equal(await page.evaluate(()=>localStorage.getItem('radarazioni-watchlist-v2')),'["AAPL","CRBG"]');
   await page.locator('nav [data-page=history]').click();await page.locator('#historyItems .card').first().waitFor();
   assert.ok((await page.locator('#historyStatus').textContent()).includes('non verificabili'));
   await page.locator('#historyMonths').selectOption('12');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.deepEqual(errors,[]);console.log(`${engine.name()} ${viewport.width}×${viewport.height}: passed`);
   await context.close();
  }}finally{await browser.close();}
 }
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>server.close());
