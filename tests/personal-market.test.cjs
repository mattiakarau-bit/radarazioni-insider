const {test}=require('node:test');const assert=require('node:assert/strict');
const P=require('../docs/personal-market.js');
const today='2026-11-07', base={ticker:'UBER',price:74,date:'2026-11-06',
 source_url:'https://www.nasdaq.com/market-activity/stocks/uber',class_verified:true};
const company={symbol:'UBER',amount:250000,window_start:'2026-10-02',
 window_end:'2026-10-08',weighted_price:72.5,aggregation_verified:true,amount_review_required:false};
test('USD market prices require dated evidence and https user-source, never public API keys',()=>{
 assert.equal(P.validate(base,today).price,74);
 for(const bad of [{price:0},{price:-3},{price:'abc'},{date:'2026-11-08'},
  {date:'2026-02-30'},{source_url:'http://not-secure.test'},
  {source_url:'https://user:secret@example.com/'},{currency:'EUR'}]){
  assert.throws(()=>P.validate({...base,...bad},today));
 }
});
test('without explicit same class and split basis never compare insider to last close',()=>{
 const a=P.assess(company,{...base,class_verified:false},today);
 assert.equal(a.distance_pct,null);assert.equal(a.nearby,null);
 assert.equal(a.complete_investment_review,false);
});
test('near price comparable only when fresh, reconciled and unambiguous',()=>{
 const a=P.assess(company,base,today);
 assert.equal(a.nearby,true);assert.ok(a.distance_pct>0);assert.equal(a.current_cap_pass,null);
 assert.equal(P.assess(company,{...base,date:'2026-10-19'},today).distance_pct,null);
 assert.equal(P.assess({...company,aggregation_verified:false},base,today).distance_pct,null);
 assert.equal(P.assess({...company,amount_review_required:true},base,today).distance_pct,null);
});
test('historical cap must fall in matching insider week; current cap separately dated',()=>{
 const priced={...base,market_cap:'1200000000',market_cap_date:'2026-11-06',
  historical_cap:800000000,historical_cap_date:'2026-10-05'};
 const a=P.assess(company,priced,today);
 assert.equal(a.current_cap_pass,true);assert.equal(a.weekly_pass,true);
 assert.equal(a.required_amount,100000);
 assert.equal(P.assess(company,{...priced,historical_cap_date:'2026-09-01'},today).weekly_pass,null);
 assert.equal(P.assess(company,{...priced,market_cap_date:'2026-09-01'},today).current_cap_pass,null);
});
test('CSV import rejects duplicate tickers and missing provenance, supports quotes',()=>{
 const head=P.columns.join(',');
 const row='UBER,74,2026-11-06,https://example.com/uber,yes,1200000000,2026-11-06,800000000,2026-10-05';
 const r=P.parseCSV(head+'\n'+row+'\n',today);
 assert.equal(r.UBER.market_cap,1200000000);
 assert.equal(r.UBER.class_verified,true);
 assert.throws(()=>P.parseCSV(head+'\n'+row+'\n'+row,today),/duplicato/);
 assert.throws(()=>P.parseCSV(head+'\n'+'UBER,74,2026-11-06,,yes,,,,\n',today),/fonte/);
});
