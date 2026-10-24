const {test}=require('node:test'),assert=require('node:assert/strict');
const C=require('../docs/radar-core.js');
const store=(seed={})=>{const d={...seed};return {getItem:k=>d[k]??null,setItem:(k,v)=>d[k]=v,d}};
test('legacy favorites migrate once without deletion or resurrection',()=>{
 const s=store({'radarazioni-watchlist-v2':'["AAPL","MSFT","AAPL"]'});
 assert.equal(C.loadFavorites(s).length,2);
 assert.equal(s.getItem('radarazioni-watchlist-v2'),'["AAPL","MSFT","AAPL"]');
 s.setItem('radarazioni-favorites-v1',JSON.stringify({version:1,items:[]}));
 assert.equal(C.loadFavorites(s).length,0);
});
test('saved history survives disappearance and merges by transaction id',()=>{
 const favorites=[{key:'cik:1',cik:1,symbol:'TEST',transactions:[{id:'old',transaction_date:'2026-01-01'}]}];
 assert.deepEqual(C.hydrate(favorites,[],[]),favorites);
 const f=C.hydrate(favorites,[{id:'new',cik:1,symbol:'NEW',company:'Renamed',filed:'2026-10-24',transaction_date:'2026-10-21'}],[])[0];
 assert.equal(f.transactions.length,2);assert.equal(f.symbol,'NEW');
 assert.equal(C.mergeTransactions(f.transactions,f.transactions).length,2);
});
test('filters match monetary and percentage units',()=>{
 assert.equal(C.evaluate(100000,500e6).status,'supera');
 assert.equal(C.evaluate(1999999,200e9).required_amount,2e6);
 assert.equal(C.evaluate(1e6,null).status,'non_verificabile');
 assert.throws(()=>C.evaluate(1,null,{...C.defaults,min_weekly_amount:NaN}));
});
