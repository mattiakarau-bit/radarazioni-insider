'use strict';
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const usd=x=>Number.isFinite(x)?new Intl.NumberFormat('it-IT',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(x):'Non disponibile';
const price=x=>Number.isFinite(x)?new Intl.NumberFormat('it-IT',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:6}).format(x):'Non verificabile';
let radar=null, result=null, events=null, historyPromise=null, favorites=[], page='radar', params={...RadarCore.defaults};
function storageWarning(text){$('#storageStatus').textContent=text;$('#storageStatus').classList.remove('hidden');}
try{favorites=RadarCore.loadFavorites(localStorage);saveFavorites();}catch(e){storageWarning('Preferiti: '+e.message+'. I dati precedenti non vengono cancellati.');}
try{const p=JSON.parse(localStorage.getItem('radarazioni-filters-v1')||'null');if(p){RadarCore.evaluate(0,null,p);params={...RadarCore.defaults,...p};}}catch{}
function saveFavorites(){try{localStorage.setItem('radarazioni-favorites-v1',JSON.stringify({version:1,items:favorites}));}catch{storageWarning('Spazio locale insufficiente o salvataggio bloccato: le modifiche ai Preferiti restano solo in memoria. I dati precedenti sono conservati.');}}
function syncFilterInputs(){const ids={min_market_cap:'minCap',min_weekly_amount:'minAmount',proportional_pct:'proportion',proportional_cap:'maxRequired'};for(const [k,id]of Object.entries(ids))$('#'+id).value=params[k];}
function isFavorite(g){return favorites.some(f=>g.cik?f.cik===g.cik||(!f.cik&&f.symbol===g.symbol):f.symbol===g.symbol);}
function updateCount(){$('#favoriteCount').textContent=favorites.length;}
async function loadHistory(){
 if(events)return events;
 if(!historyPromise)historyPromise=fetch('./data/events_history.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('HTTP '+r.status);return r.json()}).then(d=>{events=d.filings||[];return events}).catch(e=>{historyPromise=null;throw e});
 return historyPromise;
}
async function toggleFavorite(g){
 const index=favorites.findIndex(f=>f.cik===g.cik||(!f.cik&&f.symbol===g.symbol));
 if(index>=0)favorites.splice(index,1);
 else{
  let rows=g.transactions||[];
  try{rows=(await loadHistory()).filter(x=>x.cik===g.cik);}catch{storageWarning('Storico completo non accessibile: salvate le operazioni attualmente disponibili.');}
  favorites.push({key:RadarCore.key(g),cik:g.cik,symbol:g.symbol,company:g.company,group:g,transactions:rows,saved_at:new Date().toISOString()});
 }
 saveFavorites();updateCount();renderRadar();if(page==='favorites')renderFavorites();
}
function setPage(name){page=name;$$('.page').forEach(el=>el.classList.toggle('hidden',el.id!==name+'Page'));$$('nav button').forEach(el=>{if(el.dataset.page===name)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')});if(name==='favorites'){renderFavorites();loadHistory().then(rows=>{favorites=RadarCore.hydrate(favorites,rows,radar?.groups||[]);saveFavorites();updateCount();renderFavorites();}).catch(()=>storageWarning('Storico SEC non accessibile: mostro i dati già salvati.'));}if(name==='history')renderHistory();window.scrollTo(0,0);}
function statusLabel(status){return {supera:'Conforme ai filtri · dati verificati',escluso:'Fuori dai filtri',non_verificabile:'Non verificabile · capitalizzazione assente'}[status];}
function card(g,{historic=false,favorite=false}={}){
 const el=document.createElement('article');el.className='card';el.dataset.cik=g.cik;
 const a=g.analysis||{},f=RadarCore.evaluate(g.amount,g.market_cap,params);
 el.innerHTML=`<div class="card-head"><button class="star" aria-label="${isFavorite(g)?'Rimuovi dai':'Aggiungi ai'} Preferiti ${esc(g.symbol)}" aria-pressed="${isFavorite(g)}">${isFavorite(g)?'★':'☆'}</button><div class="card-title"><span class="ticker">${esc(g.symbol)}</span><h3>${esc(g.company)}</h3><small>${esc(g.window_start)} — ${esc(g.window_end)}</small></div><div class="score"><strong>${esc(a.radar_score??'—')}</strong><small>Radar Score</small></div></div><div class="metrics"><div><strong>${esc(usd(g.amount))}</strong><small>${g.aggregation_verified?'Totale dichiarato in 7 giorni':'Stima prudenziale in 7 giorni'}</small></div><div><strong>${esc(g.transaction_count)}</strong><small>${g.aggregation_verified?'Transazioni':'Unità dopo dedup prudenziale'} · ${esc(g.reported_transaction_count)} righe SEC</small></div><div><strong>Non verificati</strong><small>Insider indipendenti</small></div></div><span class="badge">${historic?'Confronto prezzo non verificabile':statusLabel(f.status)}</span><p>${g.aggregation_verified?'':'Possibili co-dichiarazioni: importo e conteggio non sono un totale verificato. '}${historic?'Prezzi correnti, split e analisi aggiornata non disponibili.':`Capitalizzazione: ${esc(usd(g.market_cap))}. Soglia richiesta: ${f.required_amount==null?'non calcolabile':esc(usd(f.required_amount))}.`}</p><div class="card-actions"><button class="open-detail">Dettagli e operazioni</button><button class="score-explain text-button">Come funziona il punteggio?</button></div>`;
 el.querySelector('.star').addEventListener('click',()=>toggleFavorite(g));
 el.querySelector('.open-detail').addEventListener('click',()=>detail(g,favorite?favorites.find(f=>f.cik===g.cik)?.transactions:null));
 el.querySelector('.score-explain').addEventListener('click',()=>scoreHelp(g));
 return el;
}
function renderRadar(){
 const groups=radar?.groups||[];const q=$('#search').value.trim().toLowerCase(),visibility=$('#visibility').value;
 let list=groups.filter(g=>[g.company,g.symbol].some(v=>String(v).toLowerCase().includes(q))).filter(g=>{const f=RadarCore.evaluate(g.amount,g.market_cap,params);return visibility==='all'||(visibility==='verified'?f.status==='supera':f.status==='supera'||f.status==='non_verificabile'&&f.base_amount_pass)});
 list.sort((a,b)=>$('#sort').value==='amount'?b.amount-a.amount:(b.analysis?.radar_score||0)-(a.analysis?.radar_score||0));
 $('#windowStatus').textContent=radar?`Finestra mobile: ${radar.window_start} — ${radar.as_of}, secondo la data dell’operazione. Importi non cumulabili con finestre storiche sovrapposte.`:'';
 $('#resultsCount').textContent=`${list.length} società mostrate su ${groups.length} nella finestra SEC disponibile`;
 $('#results').replaceChildren(...list.map(g=>card(g)));
 if(!list.length)$('#results').innerHTML='<div class="panel"><h3>Nessuna società con questi filtri</h3><p>Prova “Tutte le società”. La capitalizzazione mancante non viene stimata e non può confermare i filtri.</p></div>';
 updateCount();
}
function renderFavorites(){
 const host=$('#favoriteItems');host.replaceChildren();
 for(const f of favorites){
  const group=(radar?.groups||[]).find(g=>g.cik===f.cik)||f.group;
  if(group){const el=card(group,{favorite:true});const info=document.createElement('p');info.className='muted';info.textContent=`Preferito · ${f.transactions?.length||0} righe SEC salvate, indipendentemente dai filtri. Finestra della scheda: ${group.window_start} — ${group.window_end}.`;el.append(info);host.append(el);}
  else{const el=document.createElement('article');el.className='card';el.innerHTML=`<h3>${esc(f.company||f.symbol)} · ${esc(f.symbol)}</h3><p>Nessuna finestra aggregata disponibile. ${f.transactions?.length||0} operazioni salvate.</p><button class="saved-detail">Operazioni salvate</button> <button class="remove">Rimuovi dai Preferiti</button>`;el.querySelector('.saved-detail').addEventListener('click',()=>savedDetail(f));el.querySelector('.remove').addEventListener('click',()=>{favorites=favorites.filter(x=>x!==f);saveFavorites();updateCount();renderFavorites();renderRadar();});host.append(el);}
 }
 if(!favorites.length)host.innerHTML='<div class="panel">Nessun Preferito. Usa la stellina nel radar o aggiungi un ticker.</div>';
}
function sourceRows(rows){return rows.length?`<ul class="source-list">${rows.map(x=>`<li><b>${esc(x.transaction_date)}</b> · ${esc(x.insider)} · ${esc(usd(x.amount))}<small>${esc(x.shares)} azioni · ${esc(price(x.unit_price))} dichiarati/azione · deposito ${esc(x.filed)} · ${esc(x.security_title||'Classe titolo non disponibile')}</small>${/^https:\/\/www\.sec\.gov\/Archives\//.test(x.form_url||'')?`<a href="${esc(x.form_url)}" target="_blank" rel="noopener noreferrer">Form 4 originale</a>`:''}</li>`).join('')}</ul>`:'<p>Nessuna operazione disponibile nello storico raccolto.</p>';}
function openDialog(html){$('#detailContent').innerHTML=html;const d=$('#detailDialog');if(typeof d.showModal==='function'){if(!d.open)d.showModal();}else d.setAttribute('open','');}
function savedDetail(f){openDialog(`<h2 id="detailName">${esc(f.company||f.symbol)}</h2><p>Righe SEC originali salvate. Non sommare automaticamente importi co-dichiarati.</p>${sourceRows(f.transactions||[])}`);}
async function detail(g,saved){
 let rows=saved||g.transactions;
 if(!rows){try{const ids=new Set(g.transaction_ids||[]);rows=(await loadHistory()).filter(x=>ids.has(x.id));}catch{rows=[];}}
 openDialog(`<h2 id="detailName">${esc(g.company)} · ${esc(g.symbol)}</h2><p>Finestra: ${esc(g.window_start)} — ${esc(g.window_end)} · Radar Score ${esc(g.analysis?.radar_score??'—')}/100.</p><p>Importo ${g.aggregation_verified?'dichiarato':'prudenziale'}: ${esc(usd(g.amount))}. Somma delle righe originali prima della verifica: ${esc(usd(g.reported_amount))}. Non è capitale indipendente verificato.</p><p>Prezzo medio ponderato: ${esc(price(g.weighted_price))}. I prezzi SEC originali non sono rettificati per split. Insider indipendenti: non verificabili.</p><p>Fondamentali disponibili alla data ${esc(g.fundamentals_as_of)}; non equivalgono a un controllo aggiornato degli eventi o delle ragioni del ribasso.</p><h3>Operazioni ${saved?'salvate (tutto lo storico)':'della finestra'}</h3>${sourceRows(rows||[])}<p>Nessun BUY o notifica di investimento.</p>`);
}
function scoreHelp(g){const a=g?.analysis;openDialog(`<h2 id="detailName">Come funziona il Radar Score?</h2><p>0–100, a regole: <b>70% qualità dell’opportunità + 30% forza insider</b>. Pesi iniziali da validare storicamente. Non è una probabilità di rendimento o una raccomandazione BUY.</p><p>Forza: importo fino a 50 punti e ruolo fino a 30. Nessun bonus per nomi multipli, fondi collegati o intestatari comuni senza verifica dell’indipendenza. Opportunità: fatturato, EPS e cassa; dati mancanti non danno punti.</p><p>Radar Score massimo 49 senza valutazione verificata, 39 con cassa insufficiente/non verificata, 29 con dati finanziari incompleti o problemi di cassa/EPS. Si applica il limite più basso.</p>${a?`<h3>${esc(g.company)}</h3><p>Opportunità ${a.opportunity_score}/100 · Forza ${a.insider_strength_score}/100. Media pesata prima dei limiti: ${a.radar_uncapped}. <b>Radar Score finale: ${a.radar_score}/100.</b></p><h3>Fattori positivi verificati</h3><ul class="factor-positive">${[...(a.insider_reasons||[]),...(a.reasons||[])].map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Nessuno disponibile</li>'}</ul><h3>Limiti e fattori negativi</h3><ul class="factor-negative">${[...(a.radar_caps||[]),...(a.warnings||[])].map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:'<p>Apri la spiegazione di una società per vedere componenti, fattori positivi/negativi e limiti applicati.</p>'}`);}
function renderHistory(){
 const months=Number($('#historyMonths').value),end=new Date((radar?.as_of||new Date().toISOString().slice(0,10))+'T00:00:00Z');
 const targetMonth=end.getUTCMonth()-months,day=end.getUTCDate();const start=new Date(Date.UTC(end.getUTCFullYear(),targetMonth,1));start.setUTCDate(Math.min(day,new Date(Date.UTC(start.getUTCFullYear(),start.getUTCMonth()+1,0)).getUTCDate()));
 const windows=(radar?.historical_windows||[]).filter(g=>g.window_end>=start.toISOString().slice(0,10));
 $('#historyStatus').textContent=`${windows.length} finestre osservate negli ultimi ${months} mesi; tutte non verificabili per il confronto prezzo. Nessuna revisione d’investimento attivata.`;
 $('#historyItems').replaceChildren(...windows.slice().reverse().map(g=>card(g,{historic:true})));
}
function renderCoverage(){const c=result?.coverage||{};$('#coverageSummary').textContent=c.known_indexed_forms==null?'Statistiche persistenti disponibili dopo la prossima scansione.':`${c.known_processed_forms}/${c.known_indexed_forms} Form 4 processati negli indici registrati; ${c.unprocessed_listed_forms} in coda. Non è copertura totale SEC. Form 4/A esclusi.`;$('#coverageDays').innerHTML=(c.by_day||[]).map(x=>`<p>${esc(x.day)} · ${esc(x.processed)}/${esc(x.indexed)} · ${esc(x.pending)} in coda · verificato ${esc(x.checked_utc)} ${/^https:\/\/www\.sec\.gov\/Archives\//.test(x.index_url||'')?`<a href="${esc(x.index_url)}" target="_blank" rel="noopener noreferrer">Indice SEC</a>`:''}</p>`).join('');}
async function load(){try{
 const fetchJSON=async path=>{const r=await fetch(path+'?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json()};
 [radar,result]=await Promise.all([fetchJSON('./data/radar.json'),fetchJSON('./data/results.json')]);
 $('#dataStatus').textContent=`SEC · Ultima scansione: ${result.last_scan_utc||'N/D'} · ${result.coverage?.unprocessed_listed_forms??'N/D'} documenti in coda. Fonti prezzi e capitalizzazioni non integrate; nessun dato mancante stimato.`;
 renderCoverage();renderRadar();if(page==='favorites')setPage('favorites');if(page==='history')renderHistory();
 }catch(e){$('#dataStatus').textContent='Dati SEC non accessibili: '+e.message+'. I Preferiti salvati restano consultabili.';renderRadar();}}
$$('nav button').forEach(b=>b.addEventListener('click',()=>setPage(b.dataset.page)));
$('#scoreHelp').addEventListener('click',()=>scoreHelp());$('#footerHelp').addEventListener('click',()=>scoreHelp());
$('#closeDetail').addEventListener('click',()=>{const d=$('#detailDialog');if(d.close)d.close();else d.removeAttribute('open')});
$('#filtersForm').addEventListener('submit',e=>{e.preventDefault();const p={min_market_cap:Number($('#minCap').value),min_weekly_amount:Number($('#minAmount').value),proportional_pct:Number($('#proportion').value),proportional_cap:Number($('#maxRequired').value)};try{RadarCore.evaluate(0,null,p);params=p;localStorage.setItem('radarazioni-filters-v1',JSON.stringify(params));$('#filterStatus').textContent='Filtri applicati e salvati su questo dispositivo.';}catch{$('#filterStatus').textContent='Parametri applicati solo in memoria oppure valori non validi.';}renderRadar();});
$('#resetFilters').addEventListener('click',()=>{params={...RadarCore.defaults};syncFilterInputs();renderRadar();try{localStorage.setItem('radarazioni-filters-v1',JSON.stringify(params));}catch{}});
for(const id of ['search','visibility','sort'])$('#'+id).addEventListener(id==='search'?'input':'change',renderRadar);
$('#historyMonths').addEventListener('change',renderHistory);$('#refreshBtn').addEventListener('click',load);
$('#favoriteForm').addEventListener('submit',e=>{e.preventDefault();const symbol=$('#favoriteTicker').value.trim().toUpperCase();if(!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(symbol))return;const g=(radar?.groups||[]).find(g=>g.symbol===symbol);if(g){if(!isFavorite(g))toggleFavorite(g);}else if(!favorites.some(f=>f.symbol===symbol)){favorites.push({key:'symbol:'+symbol,symbol,company:symbol,transactions:[]});saveFavorites();updateCount();setPage('favorites');}$('#favoriteTicker').value='';});
syncFilterInputs();updateCount();load();
