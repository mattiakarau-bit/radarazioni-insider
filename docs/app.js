'use strict';
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const usd=x=>Number.isFinite(x)?new Intl.NumberFormat('it-IT',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(x):'Non disponibile';
const price=x=>Number.isFinite(x)?new Intl.NumberFormat('it-IT',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:6}).format(x):'Non verificabile';
const displayRadar=a=>['verificato','provvisorio'].includes(a?.score_status)&&Number.isFinite(a.radar_score)?a.radar_score:'—';
let searchIndex=null,searchPromise=null;
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
async function companyDetail(g){
 if(!/^\.\/data\/companies\/\d+\.json$/.test(g.detail_url||''))return null;
 const r=await fetch(g.detail_url,{cache:'no-store'});if(!r.ok)throw Error('Dettaglio HTTP '+r.status);return r.json();
}
async function ensureSearchIndex(){
 if(searchIndex)return searchIndex;
 if(!searchPromise)searchPromise=fetch('./data/search_index.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('Indice ricerca HTTP '+r.status);return r.json()}).then(d=>searchIndex=d).catch(e=>{searchPromise=null;throw e});
 return searchPromise;
}
async function toggleFavorite(g){
 const index=favorites.findIndex(f=>f.cik===g.cik||(!f.cik&&f.symbol===g.symbol));
 if(index>=0)favorites.splice(index,1);
 else{
  let rows=g.transactions||[];
  try{const d=await companyDetail(g);rows=RadarCore.mergeTransactions(rows,d?.transactions||(await loadHistory()).filter(x=>x.cik===g.cik));}catch{storageWarning('Storico completo non accessibile: salvate le operazioni attualmente disponibili.');}
  favorites.push({key:RadarCore.key(g),cik:g.cik,symbol:g.symbol,company:g.company,group:g.archive_only?null:g,transactions:rows,saved_at:new Date().toISOString()});
 }
 saveFavorites();updateCount();renderRadar();if(page==='favorites')renderFavorites();if(page==='custom')renderCustom();
}
function setPage(name){page=name;$$('.page').forEach(el=>el.classList.toggle('hidden',el.id!==name+'Page'));$$('nav button').forEach(el=>{if(el.dataset.page===name)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')});if(name==='favorites'){renderFavorites();loadHistory().then(rows=>{favorites=RadarCore.hydrate(favorites,rows,radar?.groups||[]);saveFavorites();updateCount();renderFavorites();}).catch(()=>storageWarning('Storico SEC non accessibile: mostro i dati già salvati.'));}if(name==='custom'){renderCustom();ensureSearchIndex().then(renderCustom).catch(e=>$('#customStatus').textContent=e.message);}if(name==='history'){renderHistory();ensureSearchIndex().then(renderHistory).catch(()=>{});}window.scrollTo(0,0);}
function statusLabel(status){return {supera:'Conforme ai filtri · dati verificati',escluso:'Fuori dai filtri',non_verificabile:'Non verificabile · capitalizzazione assente'}[status];}
function card(g,{historic=false,favorite=false,custom=false}={}){
 const el=document.createElement('article');el.className='card';el.dataset.cik=g.cik;
 const a=g.analysis||{},f=custom?RadarCore.evaluate(g.amount,g.historical_market_cap,params):(g.filters||RadarCore.evaluate(g.amount,g.market_cap,RadarCore.defaults));
 el.innerHTML=`<div class="card-head"><button class="star" aria-label="${isFavorite(g)?'Rimuovi dai':'Aggiungi ai'} Preferiti ${esc(g.symbol)}" aria-pressed="${isFavorite(g)}">${isFavorite(g)?'★':'☆'}</button><div class="card-title"><span class="ticker">${esc(g.symbol)}</span><h3>${esc(g.company)}</h3><small>${esc(g.window_start)} — ${esc(g.window_end)}</small></div><div class="score"><strong>${esc(displayRadar(a))}</strong><small>Radar Score · ${esc(a.score_status==='verificato'?'Verificato':a.score_status==='provvisorio'?'Provvisorio':'Non verificabile')}</small></div></div><div class="metrics"><div><strong>${esc(usd(g.amount))}</strong><small>${g.aggregation_verified?'Totale dichiarato in 7 giorni':'Stima prudenziale in 7 giorni'}</small></div><div><strong>${esc(g.transaction_count)}</strong><small>${g.aggregation_verified?'Transazioni':'Unità dopo dedup prudenziale'} · ${esc(g.reported_transaction_count)} righe SEC</small></div><div><strong>Non verificati</strong><small>Insider indipendenti</small></div></div><span class="badge">${historic?'Confronto prezzo non verificabile':statusLabel(f.status)}</span><p>${g.aggregation_verified?'':'Possibili co-dichiarazioni: importo e conteggio non sono un totale verificato. '}${historic?'Prezzi correnti, split e analisi aggiornata non disponibili.':`Capitalizzazione corrente: ${esc(usd(g.market_cap))}. Capitalizzazione della settimana: ${esc(usd(g.historical_market_cap))}${g.historical_market_cap_as_of?' ('+esc(g.historical_market_cap_as_of)+')':''}. Soglia settimanale richiesta: ${f.required_amount==null?'non calcolabile':esc(usd(f.required_amount))}.`}</p><p>Prezzo corrente: ${esc(price(g.current_price))}${g.current_price_as_of?' · '+esc(g.current_price_as_of):''}. ${g.significant_window_count??1} finestre significative; non sommare finestre sovrapposte.</p><div class="card-actions"><button class="open-detail">Dettagli</button></div>`;
 el.querySelector('.star').addEventListener('click',()=>toggleFavorite(g));
 el.querySelector('.open-detail').addEventListener('click',()=>detail(g,favorite?favorites.find(f=>f.cik===g.cik)?.transactions:null));
 return el;
}
function renderRadar(){
 const groups=radar?.groups||[],selected=groups.filter(g=>RadarCore.homeDecision(g)==='selected').sort((a,b)=>b.analysis.radar_score-a.analysis.radar_score),stats=radar?.stats||{};
 const pending=stats.pending_base_candidates??groups.filter(g=>RadarCore.homeDecision(g)==='pending').length;
 $('#windowStatus').textContent=radar?`Universo degli ultimi sei mesi: ${radar.search_start||radar.window_start} — ${radar.as_of}. Ogni acquisto è aggregato in finestre mobili di sette giorni all’interno del semestre. Una scheda per società.`:'';
 $('#recentTrack').textContent=` · ${selected.length} società selezionate oggi da tutto il semestre.`;
 $('#pendingTrack').textContent=` · ${pending} società con almeno una settimana sopra il minimo, ma verifiche ancora incomplete.`;
 $('#resultsCount').textContent=`${selected.length} società con tutti i criteri verificati`;
 $('#pendingStatus').textContent=`${stats.companies_with_purchase_rows??groups.length} aziende con righe di acquisto nel semestre; ${stats.companies_with_unambiguous_windows??0} con acquisti azionari utilizzabili, ${stats.companies_weekly_base_pass??0} sopra 100.000 USD dichiarati in almeno sette giorni. ${stats.companies_historical_cap_threshold_pass??0} superano capitalizzazione storica e soglia proporzionale; ${stats.companies_current_cap_pass??0} la capitalizzazione corrente; ${stats.companies_current_financials_verified??0} con bilanci/debito attuali verificati; ${stats.companies_current_prices_verified??0} con prezzi correnti verificati. ${stats.companies_without_usable_window??0} aziende senza finestre utilizzabili. Dati mancanti restano in attesa di verifica.`;
 $('#results').replaceChildren(...selected.map(g=>card(g)));
 if(!selected.length)$('#results').innerHTML='<div class="panel"><h3>Nessuna società supera tutti i criteri verificati</h3><p>Il motore ha analizzato il semestre, non soltanto l’ultima settimana. Prezzi, capitalizzazioni, fondamentali e cambiamenti successivi devono essere verificati prima della selezione.</p></div>';
 updateCount();
}

function renderCustom(){
 if(!radar)return;
 if(!searchIndex){$('#customStatus').textContent='Caricamento indice compatto calcolato in Python; nessun archivio transazioni viene scaricato…';return;}
 const period=$('#searchPeriod').value,days=Number(period),minScore=Number($('#minScore').value),q=$('#search').value.trim().toLowerCase(),visibility=$('#visibility').value;
 const end=new Date(radar.as_of+'T00:00:00Z'),start=new Date(end);if(period!=='semester')start.setUTCDate(end.getUTCDate()-days+1);const first=period==='semester'?radar.search_start:start.toISOString().slice(0,10);
 let list=[];
 for(const record of searchIndex.issuers||[]){const c=record.company,a=c.analysis||{};
  if(![c.company,c.symbol].some(v=>String(v).toLowerCase().includes(q)))continue;
  if(visibility==='pending'&&c.selection_status!=='pending')continue;
  if(minScore>0&&(!Number.isFinite(a.radar_score)||a.radar_score<minScore))continue;
  const windows=(period==='semester'?(record.semester_windows||[]):(record.windows||[])).filter(w=>w.window_end>=first&&w.window_end<=radar.as_of).filter(w=>{
   const f=RadarCore.evaluate(w.amount,w.historical_market_cap,params);
   if(visibility==='all')return true;
   if(visibility==='verified')return f.status==='supera'&&w.aggregation_verified&&c.selection_status==='selected';
   return w.aggregation_verified&&(f.status==='supera'||f.status==='non_verificabile'&&f.base_amount_pass);
  });
  if(!windows.length)continue;
  windows.sort((a,b)=>b.amount-a.amount||b.window_end.localeCompare(a.window_end));
  const w=windows[0];list.push({...c,...w,filters:RadarCore.evaluate(w.amount,w.historical_market_cap,params)});
 }
 const sort=$('#sort').value;list.sort((a,b)=>sort==='amount'?b.amount-a.amount:sort==='date'?b.window_end.localeCompare(a.window_end):(b.analysis?.radar_score??-1)-(a.analysis?.radar_score??-1));
 $('#customStatus').textContent=`${list.length} società nel periodo cercato: ${period==='semester'?'sei mesi di calendario':days+' giorni'}; mostro fino a 80, una scheda per società. Settimane già aggregate lato Python: il periodo seleziona la data di fine finestra, non somma gli acquisti dell’intero periodo. Il punteggio aziendale usa la migliore finestra del semestre e i dati attuali. Usa la ricerca per restringere.`;
 $('#customResults').replaceChildren(...list.slice(0,80).map(g=>card(g,{custom:true})));
 if(!list.length)$('#customResults').innerHTML='<div class="panel">Nessuna società corrisponde ai criteri scelti. I dati mancanti non superano i filtri verificati.</div>';
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
function sourceRows(rows){return rows.length?`<ul class="source-list">${rows.map(x=>`<li><b>${esc(x.transaction_date)}</b> · ${esc(x.insider)} · ${esc(x.currency==='unknown'?new Intl.NumberFormat('it-IT').format(x.amount)+' (valuta non verificata)':usd(x.amount))}<small>${x.purchase_eligible===false?'Esclusa/in revisione · ':''}${esc(x.shares)} azioni · ${esc(x.currency==='unknown'?String(x.unit_price)+' in valuta non verificata':price(x.unit_price))} dichiarati/azione · deposito ${esc(x.filed)} · ${esc(x.security_title||'Classe titolo non disponibile')}</small>${/^https:\/\/www\.sec\.gov\/Archives\//.test(x.form_url||'')?`<a href="${esc(x.form_url)}" target="_blank" rel="noopener noreferrer">Form 4 originale</a>`:''}</li>`).join('')}</ul>`:'<p>Nessuna operazione disponibile nello storico raccolto.</p>';}
function openDialog(html){$('#detailContent').innerHTML=html;const d=$('#detailDialog');if(typeof d.showModal==='function'){if(!d.open)d.showModal();}else d.setAttribute('open','');}
function financialSnapshot(s){
 if(!s?.financials)return '<h3>Fondamentali attuali</h3><p>Estrazione SEC non ancora disponibile per questa società: verifica in coda, non giudizio negativo sui bilanci.</p>';
 const f=s.financials,b=s.balance||{},series=(name,rows,unit)=>`<li>${name}: ${(rows||[]).slice(-3).map(x=>esc(x.year)+': '+esc(unit==='eps'?price(x.value):usd(x.value))+' (fine '+esc(x.end)+', pubblico '+esc(x.filed)+')').join('; ')||'Non disponibile'}</li>`;
 return `<h3>Osservazioni finanziarie SEC</h3>${s.extractor_current===false?'<p>Estrazione precedente in coda di ricalcolo: le serie conservano le date originali e non certificano i fondamentali attuali.</p>':''}<p>Estrazione ${esc(s.fetched_on||'N/D')}; analisi ${esc(f.as_of)}. ${/^https:\/\/data\.sec\.gov\/api\/xbrl\/companyfacts\//.test(s.source_url||'')?`<a href="${esc(s.source_url)}" target="_blank" rel="noopener noreferrer">Fonte SEC companyfacts</a>`:''}</p><ul>${series('Ricavi'+(f.revenue_scope_verified?' riconciliati':' · perimetro non verificato'),f.revenue_years)}${series('EPS',f.eps_years,'eps')}${series('Flusso operativo annuale',f.cashflow_years)}</ul><p>Cassa osservata: ${esc(usd(b.cash?.val))} al ${esc(b.cash?.end||'N/D')}. Osservazione debito: ${esc(usd(b.debt_observation?.val))} al ${esc(b.debt_observation?.end||'N/D')}; non è un totale del debito riconciliato. ${esc(b.note||'Perimetro del debito da verificare.')}</p><p>Questi dati non certificano da soli solidità attuale, valutazione o assenza di eventi successivi.</p>`;
}
function savedDetail(f){openDialog(`<h2 id="detailName">${esc(f.company||f.symbol)}</h2><p>Righe SEC originali salvate. Non sommare automaticamente importi co-dichiarati.</p>${sourceRows(f.transactions||[])}`);}
async function detail(g,saved){
 let rows=saved||g.transactions,data=null;
 try{data=await companyDetail(g);if(data){rows=RadarCore.mergeTransactions(rows||[],data.transactions||[]);g={...data.company,...g,analysis:data.company.analysis};}}catch(e){storageWarning('Dettaglio azienda non accessibile: '+e.message);}
 if(!rows){try{const ids=new Set(g.transaction_ids||[]);rows=(await loadHistory()).filter(x=>ids.has(x.id));}catch{rows=[];}}
 const windows=data?.significant_windows||[];
 openDialog(`<h2 id="detailName">${esc(g.company)} · ${esc(g.symbol)}</h2><p>Analisi attuale al ${esc(data?.as_of||radar?.as_of)}. Settimana mostrata: ${esc(g.window_start)} — ${esc(g.window_end)} · Radar Score ${esc(displayRadar(g.analysis))}/100.</p><p>Acquisti dichiarati in questa settimana: ${esc(usd(g.amount))}. Prezzo medio SEC: ${esc(price(g.weighted_price))}; base originale, non rettificata per split. Prezzo corrente: ${esc(price(g.current_price))}${g.current_price_as_of?' al '+esc(g.current_price_as_of):''}. Confronto rettificato: ${g.distance_from_insider_pct==null?'Non verificabile':esc(g.distance_from_insider_pct)+'%'}.</p><p>Capitalizzazione della settimana: ${esc(usd(g.historical_market_cap))} al ${esc(g.historical_market_cap_as_of||'N/D')}. Capitalizzazione corrente: ${esc(usd(g.market_cap))} al ${esc(g.current_valuation_as_of||'N/D')}. I due periodi non vengono sostituiti l’uno con l’altro. Insider indipendenti: non verificati.</p><p>Il Radar Score aziendale usa la migliore finestra del semestre ${esc(data?.company?.window_start||g.window_start)} — ${esc(data?.company?.window_end||g.window_end)} e le verifiche attuali. La ricerca può mostrare un’altra finestra; non ricalcola il punteggio globale.</p>${specificFactors(g)}${financialSnapshot(data?.financial_snapshot)}<h3>Tutte le settimane significative del semestre (${windows.length})</h3><p>Finestre sovrapposte: non sommare importi o transazioni tra finestre.</p><ul>${windows.map(w=>`<li>${esc(w.window_start)} — ${esc(w.window_end)} · ${esc(usd(w.amount))} · ${esc(w.transaction_count)} transazioni · soglia proporzionale ${w.weekly_economic_verified?'verificata':'non verificata'}</li>`).join('')||'<li>Nessuna finestra significativa disponibile.</li>'}</ul><h3>Operazioni SEC della società (${rows?.length||0})</h3><p>Righe fonte dal ${esc(data?.transaction_period_start||data?.search_start||'N/D')} al ${esc(data?.transaction_period_end||data?.as_of||'N/D')}. Le operazioni prima del semestre restano consultabili ma non entrano nel Radar corrente.</p><p>Prezzi dichiarati in USD secondo l’istruzione 5 del Form 4; non sono quotazioni correnti. Le righe escluse o in revisione non sono sommate nelle soglie.</p>${sourceRows(rows||[])}<p>Nessun BUY o notifica di investimento.</p>`);
}

function specificFactors(g){const a=g.analysis||{};return `<h3>Motivazioni del punteggio</h3><p>Stato: ${esc(a.priority||'Non verificabile')}. Opportunità ${esc(a.opportunity_score??'—')}/100 · Forza insider ${esc(a.insider_strength_score??'—')}/100. Media 70/30 prima dei limiti: ${esc(a.radar_uncapped??'—')}. ${displayRadar(a)==='—'?'Punteggio non pubblicabile come rating attendibile; eventuale snapshot precedente resta conservato.':`Radar Score ${esc(a.radar_score)}/100 (${esc(a.score_status)}).`}</p><h3>Fattori favorevoli</h3><ul class="factor-positive">${[...(a.insider_reasons||[]),...(a.reasons||[])].map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Nessuno verificato</li>'}</ul><h3>Rischi, dati mancanti e limiti</h3><ul class="factor-negative">${[...(a.radar_caps||[]),...(a.warnings||[])].map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;}
function scoreHelp(){openDialog(`<h2 id="detailName">Come funziona il Radar Score?</h2><p>70% opportunità + 30% forza insider. Pesi iniziali non validati storicamente: non è una probabilità di rendimento né un BUY.</p><p>Opportunità: ricavi totali 25, EPS in crescita e positivi 25, cassa triennale 20, valutazione favorevole riconciliata 30. Forza: importo fino a 50 e ruolo fino a 30; nessun bonus per dichiaranti non indipendenti.</p><p>La media viene calcolata prima dei limiti: 49 per valutazione mancante, 39 per storico cassa non soddisfatto, 29 per dati non verificati o perdite/cassa negativa effettive. Mancata crescita non equivale a perdite. Fondamentali incompleti/non riconciliati: rating “Non verificabile”; senza valutazione verificata: “Provvisorio”.</p><p>Il Radar pubblica solo casi verificati. Nei Dettagli trovi componenti, fattori favorevoli, rischi e motivi specifici. Nessun BUY o notifica.</p>`);}
function selectionHelp(){openDialog(`<h2 id="detailName">Criteri automatici e fonti</h2><p>Ricerca automatica su tutti gli acquisti degli ultimi sei mesi di calendario, aggiornata a ogni scansione. Una sola scheda per società se almeno una finestra mobile di sette giorni supera i criteri. Capitalizzazione verificata minima 500 milioni USD. Acquisti aggregati in sette giorni almeno 100.000 USD. Soglia aggiuntiva: 0,002% della capitalizzazione, massimo 2 milioni USD; importo richiesto = max(100.000, min(2.000.000, capitalizzazione × 0,00002)).</p><p>La soglia proporzionale usa la capitalizzazione della settimana dell’acquisto; la selezione oggi richiede anche capitalizzazione/valutazione correnti, confronto prezzo rettificato per split e revisione dei cambiamenti successivi. Dati storici e correnti mancanti restano distinti e non confermano opportunità.</p><p>Richiesti anche aggregazione senza ambiguità, fondamentali completi e riconciliati con ricavi/EPS in crescita, EPS positivi, cassa triennale positiva, valutazione favorevole verificata e Radar Score attendibile. Ordine: Radar Score decrescente. Sono criteri sperimentali, non soglie scientificamente validate.</p><p>Fonti attive: archivi trimestrali SEC già importati + depositi giornalieri raccolti, Form 4 originali, <a href="https://www.sec.gov/search-filings/edgar-application-programming-interfaces" target="_blank" rel="noopener noreferrer">SEC XBRL companyfacts</a>. Fonti prezzi/capitalizzazioni redistribuibili non ancora integrate (vedi anche il <a href="./data/source_policy.json" target="_blank" rel="noopener">registro fonti e soluzione richiesta</a>): i casi mancanti sono in attesa, non selezionati. Form 4/A in revisione ed esclusi dai segnali, copertura parziale. La Ricerca personalizzata non modifica questi criteri.</p>`);}

function renderHistory(){
 const months=Number($('#historyMonths').value),end=new Date((radar?.as_of||new Date().toISOString().slice(0,10))+'T00:00:00Z'),start=new Date(end);start.setUTCMonth(start.getUTCMonth()-months);
 const windows=(searchIndex?.issuers||[]).flatMap(r=>(r.windows||[]).filter(w=>w.window_end>=start.toISOString().slice(0,10)).map(w=>({...r.company,...w})));
 $('#historyStatus').textContent=`${windows.length} finestre preaggregate osservate nel periodo; mostro fino a 80. Nessun ritorno al prezzo insider viene confermato senza prezzi e split verificati.`;
 $('#historyItems').replaceChildren(...windows.slice().sort((a,b)=>b.window_end.localeCompare(a.window_end)).slice(0,80).map(g=>card(g,{historic:true})));
}

function renderCoverage(){const c=result?.coverage||{};$('#coverageSummary').textContent=c.known_indexed_forms==null?'Statistiche persistenti disponibili dopo la prossima scansione.':`${c.known_processed_forms}/${c.known_indexed_forms} Form 4 processati negli indici registrati; ${c.unprocessed_listed_forms} in coda. Non è copertura totale SEC. Form 4/A in revisione ed esclusi dai segnali.`;$('#coverageDays').innerHTML=(c.by_day||[]).map(x=>`<p>${esc(x.day)} · ${esc(x.processed)}/${esc(x.indexed)} · ${esc(x.pending)} in coda · verificato ${esc(x.checked_utc)} ${/^https:\/\/www\.sec\.gov\/Archives\//.test(x.index_url||'')?`<a href="${esc(x.index_url)}" target="_blank" rel="noopener noreferrer">Indice SEC</a>`:''}</p>`).join('');}
async function load(){try{
 const fetchJSON=async path=>{const r=await fetch(path+'?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json()};
 searchIndex=null;searchPromise=null;
 [radar,result]=await Promise.all([fetchJSON('./data/radar.json'),fetchJSON('./data/scan_status.json')]);
 $('#dataStatus').textContent=`SEC · Ultima scansione: ${result.last_scan_utc||'N/D'} · ${result.coverage?.unprocessed_listed_forms??'N/D'} documenti in coda. Fonti prezzi e capitalizzazioni non integrate; nessun dato mancante stimato.`;
 renderCoverage();renderRadar();renderCustom();updateSECStatus();if(page==='favorites')setPage('favorites');if(page==='history')ensureSearchIndex().then(renderHistory);
 }catch(e){$('#criticalStatus').textContent='Errore critico: dati SEC non accessibili. '+e.message+'. Preferiti salvati consultabili.';$('#criticalStatus').classList.remove('hidden');renderRadar();}}
$$('nav button').forEach(b=>b.addEventListener('click',()=>setPage(b.dataset.page)));
$('#showPending').addEventListener('click',()=>{$('#visibility').value='pending';$('#searchPeriod').value='semester';setPage('custom');});
$('#scoreHelp').addEventListener('click',scoreHelp);$('#selectionHelp').addEventListener('click',selectionHelp);
$('#closeDetail').addEventListener('click',()=>{const d=$('#detailDialog');if(d.close)d.close();else d.removeAttribute('open')});
$('#filtersForm').addEventListener('submit',e=>{e.preventDefault();const p={min_market_cap:Number($('#minCap').value),min_weekly_amount:Number($('#minAmount').value),proportional_pct:Number($('#proportion').value),proportional_cap:Number($('#maxRequired').value)};try{RadarCore.evaluate(0,null,p);params=p;localStorage.setItem('radarazioni-filters-v1',JSON.stringify(params));$('#filterStatus').textContent='Filtri applicati e salvati su questo dispositivo.';}catch{$('#filterStatus').textContent='Parametri applicati solo in memoria oppure valori non validi.';}renderCustom();});
$('#resetFilters').addEventListener('click',()=>{params={...RadarCore.defaults};syncFilterInputs();renderCustom();try{localStorage.setItem('radarazioni-filters-v1',JSON.stringify(params));}catch{}});
for(const id of ['search','visibility','sort'])$('#'+id).addEventListener(id==='search'?'input':'change',renderCustom);
$('#historyMonths').addEventListener('change',renderHistory);$('#refreshBtn').addEventListener('click',load);
$('#favoriteForm').addEventListener('submit',e=>{e.preventDefault();const symbol=$('#favoriteTicker').value.trim().toUpperCase();if(!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(symbol))return;const g=(radar?.groups||[]).find(g=>g.symbol===symbol);if(g){if(!isFavorite(g))toggleFavorite(g);}else if(!favorites.some(f=>f.symbol===symbol)){favorites.push({key:'symbol:'+symbol,symbol,company:symbol,transactions:[]});saveFavorites();updateCount();setPage('favorites');}$('#favoriteTicker').value='';});
$('#minScore').addEventListener('change',renderCustom);$('#searchPeriod').addEventListener('change',renderCustom);
syncFilterInputs();updateCount();load();loadResearchState();

function updateSECStatus(){
 const stamp=Date.parse(result?.last_scan_utc||''),stale=!Number.isFinite(stamp)||Date.now()-stamp>48*3600000;
 const unavailable=!!result?.errors?.length && (result?.coverage?.days_checked||[]).length===0;
 $('#criticalStatus').classList.toggle('hidden',!stale&&!unavailable);
 if(stale||unavailable)$('#criticalStatus').textContent=unavailable?'Scansione SEC non riuscita: indici non accessibili. Copertura nel pannello informativo.':'Scansione SEC obsoleta o data assente (oltre 48 ore): nessun dato deve essere interpretato come aggiornato.';
}

let bulkSummary=null,bulkRows=[],bulkCache={};
async function loadResearchState(){
 try{const r=await fetch('./data/history_coverage.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('no history summary');bulkSummary=await r.json();
  $('#bulkCoverage').textContent=bulkSummary.status==='import_blocked'?'Importazione bloccata: '+bulkSummary.error:`${bulkSummary.completed_count||0}/${bulkSummary.published_count??'N/D'} trimestri SEC pubblicati importati (${bulkSummary.published_archive_coverage_pct??'N/D'}%). ${bulkSummary.unique_candidate_events??bulkSummary.counts?.retained_purchase_candidates??0} eventi candidati unici, ${bulkSummary.unique_issuers_purchase_candidates??0} emittenti unici; ${bulkSummary.unique_issuers_us_listing_current??0} con acquisti azionari riconciliati e listing USA corrente nella mappa SEC.`;
  $('#bulkLimits').textContent=`Dati riferiti ai depositi ${bulkSummary.period_filed_start||'N/D'} — ${bulkSummary.period_filed_end||'N/D'}. Listing corrente osservato ${bulkSummary.listing_observed_at||'N/D'}: non prova domicilio USA o listing storico. Emittenti verificabili finanziariamente: ${bulkSummary.financial_verified_issuers??0}; capitalizzazioni verificate: ${bulkSummary.market_cap_verified_issuers??0}. Copertura degli archivi, non copertura totale del mercato. Le date originali e le rettifiche restano separate.`;
  $('#bulkQuarter').innerHTML=(bulkSummary.completed_quarters||[]).slice().sort().reverse().map(q=>`<option value="${esc(q)}">${esc(q)}</option>`).join('');
 }catch{$('#bulkCoverage').textContent='Nessun archivio trimestrale importato disponibile in questa pubblicazione. La scansione recente rimane separata.';}
 try{const r=await fetch('./data/ml_status.json?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error();const m=await r.json();
 $('#mlStatus').textContent=m.trained?'Modello di ricerca addestrato: consultare il rapporto fuori campione. Non usato per BUY o Radar Score.':`NON addestrato. ${m.events_stored||0} eventi strutturati, ${m.point_in_time_feature_rows||0} righe di caratteristiche point-in-time. Target verificati: 30 giorni ${m.verified_targets?.['30']||0}, 90 giorni ${m.verified_targets?.['90']||0}, 180 giorni ${m.verified_targets?.['180']||0}. Mancano prezzi total-return autorizzati e identità storiche/split/dividendi/delisting. Performance: non disponibili.`;
 if(m.trained){$('#mlMetrics').innerHTML=Object.entries(m.horizons||{}).filter(([,r])=>r.trained).map(([h,r])=>`<h3>${esc(h)} giorni · test fuori campione</h3><p>Train ${esc(r.split_counts?.train)}, validazione ${esc(r.split_counts?.validation)}, test ${esc(r.split_counts?.test)}. Benchmark: ${esc(r.benchmark)}. Modello scelto in validazione: ${esc(r.chosen_on_validation)}.</p><ul>${Object.entries(r.metrics||{}).map(([name,v])=>`<li>${esc(name)}: ROC AUC ${esc(v.roc_auc)}, Brier ${esc(v.brier)}, intervallo 95% cluster ${esc(JSON.stringify(v.roc_auc_95_cluster_bootstrap))}</li>`).join('')}</ul><p>Baseline costante Brier ${esc(r.constant_baseline_brier)}; regole AUC ${esc(r.rules_baseline_auc??'non disponibile')}. ${esc(r.uncertainty)}.</p>`).join('');}else{$('#mlMetrics').textContent='Performance fuori campione e confronto con benchmark: non disponibili; nessun modello effettivamente addestrato.';}
 }catch{$('#mlStatus').textContent='Modelli predisposti, nessun addestramento o risultato verificato disponibile.';}
}
async function loadBulkQuarter(){const q=$('#bulkQuarter').value;if(!q){$('#bulkCount').textContent='Nessun trimestre completato disponibile.';return;}
 $('#loadBulk').disabled=true;$('#bulkCount').textContent='Caricamento dati SEC strutturati…';
 try{if(!bulkCache[q]){const r=await fetch('./data/bulk/'+encodeURIComponent(q)+'.json',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);bulkCache[q]=(await r.json()).events||[];while(Object.keys(bulkCache).length>2)delete bulkCache[Object.keys(bulkCache)[0]];}bulkRows=bulkCache[q];renderBulk();}catch(e){$('#bulkCount').textContent='Archivio non accessibile: '+e.message;}finally{$('#loadBulk').disabled=false;}}
function renderBulk(){const host=$('#bulkItems');host.replaceChildren();if($('#bulkMode').value==='returned'){$('#bulkCount').textContent='0 ritorni al prezzo insider verificati. Il confronto reale è bloccato finché prezzi rettificati e controlli aggiornati non sono disponibili.';return;}
 const q=$('#bulkSearch').value.toLowerCase(),all=$('#bulkReview').checked,byCik=new Map();
 for(const e of bulkRows){if(!all&&(!e.current_eligible||!e.us_listing_current))continue;if(![e.symbol,e.company].some(s=>String(s).toLowerCase().includes(q)))continue;if(!byCik.has(e.cik))byCik.set(e.cik,[]);byCik.get(e.cik).push(e);}
 $('#bulkCount').textContent=`${byCik.size} emittenti nel trimestre caricato; mostro fino a 80 società. Dati storici in verifica, non opportunità o importi settimanali. Usa la ricerca per restringere.`;
 for(const rows of [...byCik.values()].slice(0,80)){const latest=rows.slice().sort((a,b)=>b.filed.localeCompare(a.filed))[0],el=document.createElement('article');el.className='card';el.innerHTML=`<div class="card-head"><button class="star" aria-pressed="${isFavorite(latest)}" aria-label="Preferiti ${esc(latest.symbol)}">${isFavorite(latest)?'★':'☆'}</button><div><span class="ticker">${esc(latest.symbol)}</span><h3>${esc(latest.company)}</h3></div></div><p>${rows.length} righe di acquisti dichiarati nel trimestre · ultimo deposito ${esc(latest.filed)}. Categorie: ${esc([...new Set(rows.flatMap(e=>e.owner_categories||[]))].join(', '))}. Radar Score: Non verificabile. Insider indipendenti: non verificati.</p><button class="bulk-detail">Dettagli eventi SEC</button>`;
 const favorite={cik:latest.cik,symbol:latest.symbol,company:latest.company,transactions:rows,archive_only:true};
 el.querySelector('.star').addEventListener('click',async()=>{await toggleFavorite(favorite);renderBulk();});
 el.querySelector('.bulk-detail').addEventListener('click',()=>openDialog(`<h2 id="detailName">${esc(latest.company)}</h2><p>Archivio trimestrale as-filed: rettifiche/co-dichiarazioni non vengono sommate automaticamente. ${rows.length} righe; mostra fino a 100. Collegamenti indice SEC costruiti da CIK e accession, non verificati singolarmente. Le date di deposito sono diverse dalla data dell’operazione. Nessuna raccomandazione.</p>${sourceRows(rows.slice(0,100))}<h3>Stati di revisione</h3><ul>${[...new Set(rows.flatMap(e=>e.review_reasons||[]))].map(x=>`<li>${esc(x)}</li>`).join('')||'<li>In attesa di fondamentali, prezzi e valutazione verificati.</li>'}</ul>`));host.append(el);}}
$('#loadBulk').addEventListener('click',loadBulkQuarter);$('#bulkSearch').addEventListener('input',renderBulk);$('#bulkReview').addEventListener('change',renderBulk);$('#bulkMode').addEventListener('change',renderBulk);
