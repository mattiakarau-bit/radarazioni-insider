'use strict';
/* On-device price observations only. No API keys, quote networking or upload. */
const PersonalMarketUI=(()=>{
 const $=s=>document.querySelector(s);
 const fmt=number=>Number.isFinite(number)?Money.formatCompact(number):'Non inserita';
 const full=number=>Number.isFinite(number)?new Intl.NumberFormat('it-IT',{style:'currency',currency:'USD',maximumFractionDigits:4}).format(number):'Non disponibile';
 const protect=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const KEY='radarazioni-personal-market-v1';
 const quotes=Object.create(null);
 let listPromise=null;
 const status=message=>{$('#personalStatus').textContent=message};
 function read(){
  try{
   const raw=JSON.parse(localStorage.getItem(KEY)||'null');
   if(raw?.version===1&&Array.isArray(raw.items)){
    for(const item of raw.items){try{const q=PersonalMarket.validate(item);quotes[q.ticker]=q;}catch{}}
   }
  }catch{status('Non posso leggere i prezzi salvati in precedenza. Non ho modificato il salvataggio.');}
 }
 function save(){
  try{localStorage.setItem(KEY,JSON.stringify({version:1,items:Object.values(quotes)}));return true}
  catch{status('Salvataggio locale non consentito. I prezzi restano soltanto finché questa pagina rimane aperta.');return false}
 }
 async function companies(){
  if(!listPromise)listPromise=fetch('./data/pending_index.json',{cache:'no-store'})
   .then(async r=>{if(!r.ok)throw Error('Indice SEC non disponibile');return r.json()})
   .then(x=>x.companies||[]).catch(e=>{listPromise=null;throw e});
  return listPromise;
 }
 async function render(){
  const host=$('#personalResults'),all=Object.values(quotes).sort((a,b)=>a.ticker.localeCompare(b.ticker));
  $('#personalClear').classList.toggle('hidden',all.length===0);
  host.replaceChildren();
  if(!all.length){status('Nessun prezzo personale inserito. Compila i campi qui sopra oppure importa un CSV.');return}
  status('Abbino i prezzi che hai inserito alle società SEC…');
  let companiesFound=[];
  try{companiesFound=await companies()}catch{status('Indice SEC non disponibile. Prezzi personali ancora conservati: puoi riprovare con Ricarica.')}
  const map=new Map(companiesFound.map(g=>[String(g.symbol||'').toUpperCase(),g]));
  let matched=0,nearby=0;
  for(const q of all){
   const g=map.get(q.ticker);
   const calc=g?PersonalMarket.assess(g,q):null;
   if(g)matched++;if(calc?.nearby===true)nearby++;
   const gap=calc?.distance_pct;
   const gapText=gap==null?'Non confrontabile':(gap>0?'+':'')+new Intl.NumberFormat('it-IT',{maximumFractionDigits:2}).format(gap)+'%';
   const note=gap==null?'Serve conferma classe azionaria, split, data recente e prezzo SEC omogeneo.':
     calc.nearby?'Prezzo entro ±15% dal prezzo medio insider della settimana.':'Prezzo oltre ±15% dal prezzo medio insider della settimana.';
   const currentCap=q.market_cap==null?'Non inserita':fmt(q.market_cap)+(!calc?.current_cap_usable?' (data non attuale)':calc.current_cap_pass?' (sopra 500 Mln $)':' (sotto 500 Mln $)');
   const historicalCap=q.historical_cap==null?'Non inserita':fmt(q.historical_cap)+(calc?.historical_cap_usable?' (data nella settimana)':' (data fuori settimana)');
   const revenue=g?.sec_evidence?.annual?.revenue;
   const eps=g?.sec_evidence?.annual?.eps;
   const evidence=g?'Ricavi annuali SEC: '+(revenue?fmt(revenue.value)+' ('+protect(revenue.end)+')':'assenti')+
       '. EPS annuale SEC: '+(eps?full(eps.value)+' ('+protect(eps.end)+')':'assente')+'.':'';
   const el=document.createElement('article');el.className='personal-result';
   el.innerHTML=`<h3>${protect(q.ticker)} · ${protect(g?.company||'Nessuna corrispondenza nel Radar semestrale')}</h3>
   <div class="personal-grid">
    <div><small>Prezzo inserito · ${protect(q.date)}</small><strong>${full(q.price)}</strong></div>
    <div><small>Prezzo insider SEC (non rettificato)</small><strong>${full(g?.weighted_price)}</strong></div>
    <div><small>Differenza dal prezzo insider</small><strong class="${calc?.nearby===true?'personal-near':'personal-far'}">${protect(gapText)}</strong></div>
    <div><small>Acquisti insider nella settimana</small><strong>${fmt(g?.amount)}</strong></div>
   </div>
   <p><strong>${protect(note)}</strong></p>
   <p>Capitalizzazione attuale inserita: ${protect(currentCap)}. Storica: ${protect(historicalCap)}.
   ${calc?.weekly_pass==null?'Soglia proporzionale non verificata.':'Soglia proporzionale da dato personale: '+(calc.weekly_pass?'superata':'non superata')+' (non certificata).'}</p>
   <p>${evidence}</p>
   <p class="personal-warn">Fonte fornita da te, non verificata automaticamente: <a href="${protect(q.source_url)}" target="_blank" rel="noopener noreferrer">Apri la fonte</a>. Nessun Radar Score finanziario completo o previsione di rialzo.</p>
   <button class="remove-personal" type="button">Rimuovi dato personale</button>`;
   el.querySelector('.remove-personal').addEventListener('click',()=>{delete quotes[q.ticker];save();render()});
   host.append(el);
  }
  status(all.length+' prezzi personali · '+matched+' società abbinate · '+nearby+' vicine al prezzo insider quando il confronto è possibile. Non sono investimenti certificati.');
 }
 function submit(event){
  event.preventDefault();
  try{
   const q=PersonalMarket.validate({
    ticker:$('#personalTicker').value,price:$('#personalPrice').value,date:$('#personalDate').value,
    source_url:$('#personalSource').value,market_cap:$('#personalCap').value,
    market_cap_date:$('#personalCapDate').value,historical_cap:$('#personalHistoricCap').value,
    historical_cap_date:$('#personalHistoricCapDate').value,class_verified:$('#personalClass').checked
   });
   if(!Object.hasOwn(quotes,q.ticker)&&Object.keys(quotes).length>=150)throw Error('Massimo 150 aziende per dispositivo');
   quotes[q.ticker]=q;const saved=save();
   render();if(!saved)status('Prezzo usato per questa sessione, ma salvataggio sul dispositivo non riuscito.');
  }catch(e){status('Prezzo non salvato: '+e.message)}
 }
 async function importCSV(event){
  const file=event.target.files?.[0];if(!file)return;
  try{
   if(file.size>300000)throw Error('Dimensione massima del CSV: 300 KB');
   const incoming=PersonalMarket.parseCSV(await file.text());
   if(new Set([...Object.keys(quotes),...Object.keys(incoming)]).size>150)throw Error('Massimo 150 aziende per dispositivo');
   Object.assign(quotes,incoming);
   const ok=save();render();if(!ok)status('CSV letto, ma salvataggio sul dispositivo non riuscito.');
  }catch(e){status('Importazione non riuscita: '+e.message)}
  event.target.value='';
 }
 function template(){
  const url=URL.createObjectURL(new Blob([PersonalMarket.template],{type:'text/csv;charset=utf-8'}));
  const a=document.createElement('a');a.href=url;a.download='radarazioni-modello-prezzi-personali.csv';a.click();
  setTimeout(()=>URL.revokeObjectURL(url),3000);
 }
 function clear(){
  if(!confirm('Cancellare solo i prezzi personali su questo dispositivo? I Preferiti e i dati SEC non saranno eliminati.'))return;
  for(const key of Object.keys(quotes))delete quotes[key];
  save();render();
 }
 $('#personalDate').value=new Date().toISOString().slice(0,10);
 $('#personalQuoteForm').addEventListener('submit',submit);
 $('#personalCsvFile').addEventListener('change',importCSV);
 $('#personalCsvTemplate').addEventListener('click',template);
 $('#personalClear').addEventListener('click',clear);
 $('#personalMarketPanel').addEventListener('toggle',()=>{if($('#personalMarketPanel').open&&Object.keys(quotes).length)render()});
 read();if(Object.keys(quotes).length)render();
 return {render};
})();
