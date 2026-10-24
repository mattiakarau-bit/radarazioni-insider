'use strict';
const RadarCore = (()=>{
 const defaults={min_market_cap:500000000,min_weekly_amount:100000,proportional_pct:0.002,proportional_cap:2000000};
 function evaluate(amount,cap,p=defaults){
  if(Object.values(p).some(v=>!Number.isFinite(v)||v<0))throw Error('Parametri non validi');
  if(!Number.isFinite(cap)||cap<=0)return {status:'non_verificabile',required_amount:null,base_amount_pass:amount>=p.min_weekly_amount};
  const threshold=Math.max(p.min_weekly_amount,Math.min(p.proportional_cap,cap*p.proportional_pct/100));
  return {status:cap>=p.min_market_cap&&amount>=threshold?'supera':'escluso',required_amount:threshold,base_amount_pass:amount>=p.min_weekly_amount};
 }
 const key=x=>x.cik?'cik:'+x.cik:'symbol:'+x.symbol.toUpperCase();
 function loadFavorites(storage){
  const current=storage.getItem('radarazioni-favorites-v1');
  if(current){const p=JSON.parse(current);if(p.version===1&&Array.isArray(p.items))return p.items;throw Error('Archivio Preferiti non valido; copia precedente conservata');}
  const old=JSON.parse(storage.getItem('radarazioni-watchlist-v2')||'[]');
  if(!Array.isArray(old))throw Error('Watchlist precedente non valida; dati conservati');
  const items=[...new Set(old.filter(x=>typeof x==='string'))].map(symbol=>({key:'symbol:'+symbol.toUpperCase(),symbol:symbol.toUpperCase(),company:symbol.toUpperCase(),transactions:[],legacy:true}));
  try{storage.setItem('radarazioni-favorites-v1',JSON.stringify({version:1,items}));}catch{} // Keep migrated items in memory even when storage is full.
  return items;
 }
 function mergeTransactions(a,b){return [...new Map([...a,...b].map(x=>[x.id,x])).values()].sort((x,y)=>y.transaction_date.localeCompare(x.transaction_date));}
 function hydrate(favorites,events,groups){return favorites.map(f=>{
  const rows=events.filter(x=>f.cik?x.cik===f.cik:x.symbol===f.symbol);
  if(!rows.length)return f;
  const latest=[...rows].sort((a,b)=>b.filed.localeCompare(a.filed))[0];
  return {...f,cik:latest.cik,key:key(latest),company:latest.company,symbol:latest.symbol,
    transactions:mergeTransactions(f.transactions||[],rows),group:groups.find(g=>g.cik===latest.cik)||f.group};
 });}
 return {defaults,evaluate,key,loadFavorites,mergeTransactions,hydrate};
})();
if(typeof module!=='undefined')module.exports=RadarCore;
