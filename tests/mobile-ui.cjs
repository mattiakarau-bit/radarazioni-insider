/* Local application tests; production SEC data are not altered by fixtures. */
const {chromium,webkit}=require('playwright');
const http=require('node:http'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const root=path.resolve('docs');
const server=http.createServer((req,res)=>{const pathname=new URL(req.url,'http://localhost').pathname;const file=path.join(root,pathname==='/'?'index.html':pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}fs.readFile(file,(e,body)=>{if(e){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.json')?'application/json':file.endsWith('.css')?'text/css':'text/html');res.end(body);});});
const fits=async page=>{const x=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,overflow:Array.from(document.querySelectorAll('body *')).filter(e=>e.getBoundingClientRect().right>innerWidth+1||e.scrollWidth>e.clientWidth+2).slice(0,8).map(e=>({tag:e.tagName,id:e.id,scroll:e.scrollWidth,client:e.clientWidth}))}));assert.ok(x.scroll<=x.width+1,JSON.stringify(x));};
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
 for(const engine of [chromium,webkit]){
  const browser=await engine.launch({headless:true});
  try{for(const viewport of [{width:390,height:844},{width:768,height:1024},{width:320,height:568}]){
   const context=await browser.newContext({viewport,isMobile:true,hasTouch:true});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(()=>localStorage.setItem('radarazioni-watchlist-v2','["AAPL","CRBG"]'));
   await page.goto(base);await page.waitForFunction(()=>document.querySelector('#resultsCount').textContent.includes('società'));
   assert.equal(await page.locator('nav button').count(),4);
   assert.equal(await page.locator('#radarPage form').count(),0);
   assert.equal(await page.locator('#radarPage select').count(),0);
   assert.equal(await page.locator('#radarPage input').count(),0);
   assert.equal(await page.getByRole('button',{name:'Come funziona il punteggio?',exact:false}).count(),1);
   assert.equal(await page.locator('#favoriteCount').textContent(),'2');
   assert.equal(await page.locator('#results .card').count(),0);
   const homeStatus=await page.locator('#resultsCount').textContent();
   assert.ok((await page.locator('#pendingStatus').textContent()).includes('in attesa'));
   await fits(page);
   await page.locator('#scoreHelp').click();await page.locator('#detailDialog[open]').waitFor();assert.ok((await page.locator('#detailContent').textContent()).includes('70%'));await page.locator('#closeDetail').click();
   await page.locator('#selectionHelp').click();assert.ok((await page.locator('#detailContent').textContent()).includes('500 milioni'));await page.locator('#closeDetail').click();
   await page.locator('nav [data-page=custom]').click();await page.locator('#visibility').selectOption('all');await page.locator('#customResults .card').first().waitFor();
   assert.equal(await page.locator('.score-explain').count(),0);
   await fits(page);
   const first=page.locator('#customResults .card').filter({has:page.locator('.star[aria-pressed="false"]')}).first();const symbol=await first.locator('.ticker').textContent();
   await first.locator('.open-detail').click();await page.getByRole('heading',{name:'Fattori favorevoli',exact:true}).waitFor();assert.ok((await page.locator('#detailContent').textContent()).includes('Fattori favorevoli'));assert.ok((await page.locator('#detailContent').textContent()).includes('Rischi'));await page.locator('#closeDetail').click();
   await first.locator('.star').click();await page.waitForFunction(()=>JSON.parse(localStorage.getItem('radarazioni-favorites-v1')).items.length===3);
   for(const days of ['7','30','90','180','365'])await page.locator('#searchPeriod').selectOption(days);
   await page.locator('#minAmount').fill('1000000000');await page.locator('#visibility').selectOption('candidates');await page.locator('#filtersForm button[type=submit]').click();await page.waitForFunction(()=>document.querySelectorAll('#customResults .card').length===0);
   await page.locator('nav [data-page=radar]').click();assert.equal(await page.locator('#resultsCount').textContent(),homeStatus);assert.equal(await page.locator('#results .card').count(),0);
   await page.locator('nav [data-page=favorites]').click();await page.locator('#favoriteItems .card').first().waitFor();assert.ok((await page.locator('#favoriteItems').textContent()).includes(symbol));
   assert.ok(await page.evaluate(()=>JSON.parse(localStorage.getItem('radarazioni-favorites-v1')).items.find(f=>f.cik)?.transactions.length>0));
   await page.reload();await page.waitForFunction(()=>document.querySelector('#resultsCount').textContent.includes('società'));assert.equal(await page.locator('#favoriteCount').textContent(),'3');
   assert.equal(await page.evaluate(()=>localStorage.getItem('radarazioni-watchlist-v2')),'["AAPL","CRBG"]');
   await page.locator('nav [data-page=history]').click();await page.locator('#historyItems .card').first().waitFor();await fits(page);assert.deepEqual(errors,[]);
   await context.close();console.log(`${engine.name()} ${viewport.width}×${viewport.height}: passed`);
  }
  // A verified fixture must appear; changing custom criteria must not move this gate.
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const page=await context.newPage();
  const data=JSON.parse(fs.readFileSync('docs/data/radar.json'));const fixture={...data.groups[0],cik:999999,symbol:'FIXTURE',company:'Società fittizia di test',amount:1e6,aggregation_verified:true,market_cap:1e9,market_cap_verified:true,analysis:{...data.groups[0].analysis,radar_score:94,score_status:'verificato',fundamentals_verified:true,valuation_verified:true,quality_pass:true}};
  await page.route('**/data/radar.json*',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({...data,groups:[fixture],historical_windows:[fixture]})}));
  await page.route('**/data/results.json*',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({last_scan_utc:'2020-01-01T00:00:00Z',coverage:{days_checked:[]},errors:['fixture failure']})}));
  await page.goto(base);await page.locator('#results .card').waitFor();assert.ok((await page.locator('#results').textContent()).includes('FIXTURE'));await page.locator('#criticalStatus:not(.hidden)').waitFor();
  await page.locator('nav [data-page=custom]').click();await page.locator('#minAmount').fill('1000000000');await page.locator('#filtersForm button[type=submit]').click();await page.locator('nav [data-page=radar]').click();assert.equal(await page.locator('#results .card').count(),1);
  await context.close();console.log(engine.name()+': verified fixture, independent defaults and critical SEC status passed');
  const archiveContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const archivePage=await archiveContext.newPage();
  const historyFixture={completed_count:1,published_count:23,published_archive_coverage_pct:4.35,counts:{retained_purchase_candidates:1},unique_issuers_purchase_candidates:1,unique_issuers_us_listing_current:1,completed_quarters:['2021q1'],period_filed_start:'2021-01-04',period_filed_end:'2021-01-04'};
  const eventFixture={id:'fixture-archive-row',cik:999999,symbol:'FIXTURE',company:'Emittente archivio fittizio',filed:'2021-01-04',transaction_date:'2021-01-01',amount:1000,shares:10,unit_price:100,current_eligible:true,us_listing_current:true,owner_categories:['OFFICER'],review_reasons:[],form_url:'https://www.sec.gov/Archives/edgar/data/1/fixture-index.html'};
  await archivePage.route('**/data/history_coverage.json*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify(historyFixture)}));
  await archivePage.route('**/data/ml_status.json*',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({trained:false,events_stored:1,point_in_time_feature_rows:1,verified_targets:{30:0,90:0,180:0}})}));
  await archivePage.route('**/data/bulk/2021q1.json',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({events:[eventFixture]})}));
  await archivePage.goto(base);await archivePage.locator('nav [data-page=history]').click();await archivePage.waitForFunction(()=>document.querySelector('#bulkQuarter').options.length===1);
  await archivePage.locator('#loadBulk').click();await archivePage.locator('#bulkItems .card').waitFor();assert.ok((await archivePage.locator('#mlStatus').textContent()).includes('NON addestrato'));
  await archivePage.locator('#bulkItems .star').click();await archivePage.waitForFunction(()=>JSON.parse(localStorage.getItem('radarazioni-favorites-v1')).items.length===1);
  await archivePage.locator('#bulkMode').selectOption('returned');assert.equal(await archivePage.locator('#bulkItems .card').count(),0);assert.ok((await archivePage.locator('#bulkCount').textContent()).includes('0 ritorni'));
  await archivePage.locator('nav [data-page=favorites]').click();await archivePage.locator('.saved-detail').click();assert.ok((await archivePage.locator('#detailContent').textContent()).includes('2021-01-01'));
  await archivePage.locator('#closeDetail').click();await fits(archivePage);await archiveContext.close();console.log(engine.name()+': structured archive, blocked ML, returned-price gate and archive favorites passed');

  }finally{await browser.close();}
 }
})().catch(e=>{console.error(e);process.exitCode=1}).finally(()=>server.close());
