'use strict';
const $=s=>document.querySelector(s), $$=s=>Array.from(document.querySelectorAll(s));
const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const usd=x=>Money.formatCompact(x);
const moneyButton=x=>Number.isFinite(x)?`<button type="button" class="money-toggle" data-amount="${x}" data-exact="false" aria-label="Importo abbreviato ${esc(Money.formatCompact(x))}. Tocca per vedere l'importo esatto" title="Tocca per vedere la cifra completa"><span class="money-value">${esc(Money.formatCompact(x))}</span><span class="money-hint" aria-hidden="true">↗</span></button>`:esc(Money.formatCompact(x));
function notify(message){const el=$('#toast');if(!el)return;el.textContent=message;el.classList.add('show');clearTimeout(notify.timer);notify.timer=setTimeout(()=>el.classList.remove('show'),2300);}
document.addEventListener('click',e=>{
 const button=e.target.closest('.money-toggle');if(!button)return;
 const exact=button.dataset.exact!=='true',value=Number(button.dataset.amount);
 button.dataset.exact=String(exact);
 button.querySelector('.money-value').textContent=exact?Money.formatExact(value):Money.formatCompact(value);
 button.setAttribute('aria-label',exact?'Importo completo '+Money.formatExact(value)+'. Tocca per abbreviare':'Importo abbreviato '+Money.formatCompact(value)+'. Tocca per vedere l’importo completo');
});
const price=x=>Number.isFinite(x)?new Intl.NumberFormat('it-IT',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:6}).format(x):'Non verificabile';
const displayRadar=a=>['verificato','provvisorio'].includes(a?.score_status)&&Number.isFinite(a.radar_score)?a.radar_score:'—';
let searchIndex=null,searchPromise=null,preliminaryIndex=null,preliminaryLimit=20;
let radar=null, result=null, events=null, historyPromise=null, favorites=[], page='radar', params={...RadarCore.defaults};
let searchApplied=false;
let uiTheme='dark';try{uiTheme=localStorage.getItem('radarazioni-ui-theme')==='light'?'light':'dark';}catch{}
function applyTheme(){document.documentElement.dataset.theme=uiTheme;const button=$('#themeToggle');if(button){button.textContent=uiTheme==='dark'?'☀ Chiaro':'☾ Scuro';button.setAttribute('aria-label','Passa al tema '+(uiTheme==='dark'?'chiaro':'scuro'));button.setAttribute('aria-pressed',String(uiTheme==='light'));}}
applyTheme();
$('#themeToggle').addEventListener('click',()=>{uiTheme=uiTheme==='dark'?'light':'dark';applyTheme();try{localStorage.setItem('radarazioni-ui-theme',uiTheme);}catch{}notify(uiTheme==='dark'?'Modalità scura attiva':'Modalità chiara attiva');});
function storageWarning(text){$('#storageStatus').textContent=text;$('#storageStatus').classList.remove('hidden');}
try{favorites=RadarCore.loadFavorites(localStorage);saveFavorites();}catch(e){storageWarning('Preferiti: '+e.message+'. I dati precedenti non vengono cancellati.');}
try{const p=JSON.parse(localStorage.getItem('radarazioni-filters-v1')||'null');if(p){RadarCore.evaluate(0,null,p);params={...RadarCore.defaults,...p};}}catch{}
function saveFavorites(){try{localStorage.setItem('radarazioni-favorites-v1',JSON.stringify({version:1,items:favorites}));}catch{storageWarning('Spazio locale insufficiente o salvataggio bloccato: le modifiche ai Preferiti restano solo in memoria. I dati precedenti sono conservati.');}}
function syncFilterInputs(){const ids={min_market_cap:'minCap',min_weekly_amount:'minAmount',proportional_pct:'proportion',proportional_cap:'maxRequired'};for(const [k,id]of Object.entries(ids))$('#'+id).value=params[k];}
function isFavorite(g){return favorites.some(f=>!f.legacy&&(g.cik?f.cik===g.cik||(!f.cik&&f.symbol===g.symbol):f.symbol===g.symbol));}
function updateCount(){$('#favoriteCount').textContent=favorites.filter(f=>!f.legacy).length;}
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
 const index=favorites.findIndex(f=>!f.legacy&&(f.cik===g.cik||(!f.cik&&f.symbol===g.symbol)));
 if(index>=0)favorites.splice(index,1);
 else{
  let rows=g.transactions||[];
  try{const d=await companyDetail(g);rows=RadarCore.mergeTransactions(rows,d?.transactions||(await loadHistory()).filter(x=>x.cik===g.cik));}catch{storageWarning('Storico completo non accessibile: salvate le operazioni attualmente disponibili.');}
  favorites.push({key:RadarCore.key(g),cik:g.cik,symbol:g.symbol,company:g.company,group:g.archive_only?null:g,transactions:rows,saved_at:new Date().toISOString()});
 }
 saveFavorites();updateCount();renderRadar();if(page==='favorites')renderFavorites();if(page==='custom')renderCustom();
 notify(index>=0?'Rimosso dai Preferiti':'Aggiunto ai Preferiti');
}
function setPage(name){
 if(!['radar','custom','favorites'].includes(name))return;
 page=name;
 $$('.page').forEach(el=>el.classList.toggle('hidden',el.id!==name+'Page'));
 $$('nav button').forEach(el=>{if(el.dataset.page===name)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current')});
 if(name==='favorites'){
  renderFavorites();
  loadHistory().then(rows=>{favorites=RadarCore.hydrate(favorites,rows,[...(radar?.groups||[]),...(radar?.preliminary_groups||[])]);saveFavorites();updateCount();renderFavorites();}).catch(()=>storageWarning('Storico SEC non accessibile: mostro i dati già salvati.'));
 }
 if(name==='custom'&&searchApplied)renderCustom();
 window.scrollTo(0,0);
}
function statusLabel(status){return {supera:'Conforme ai filtri · dati verificati',escluso:'Fuori dai filtri',non_verificabile:'Non verificabile · capitalizzazione assente'}[status];}
function card(g,{historic=false,favorite=false,custom=false}={}){
 const el=document.createElement('article');el.className='card';el.dataset.cik=g.cik;
 const a=g.analysis||{},f=custom?RadarCore.evaluate(g.amount,g.historical_market_cap,params):(g.filters||RadarCore.evaluate(g.amount,g.market_cap,RadarCore.defaults));
 const preliminary=!!g.preliminary;
 const label=preliminary?'Candidata preliminare · verifiche incomplete':historic?'Storico · dati da verificare':statusLabel(f.status);
 const score=preliminary?(g.amount_review_required?'—':a.insider_strength_score??'—'):displayRadar(a);
 const scoreLabel=preliminary?'Forza insider · preliminare':'Radar Score · '+(a.score_status==='verificato'?'Verificato':'Non verificato');
 const grade=Number(score),strengthTier=preliminary&&Number.isFinite(grade)?grade>=70?'high':grade>=40?'medium':'low':'none';
 const strengthLabel=strengthTier==='high'?'verde':strengthTier==='medium'?'gialla':strengthTier==='low'?'rossa':'non disponibile';
 const day=g.window_start&&g.window_end?`${esc(g.window_start)} — ${esc(g.window_end)}`:'Periodo non disponibile';
 const rationale=preliminary?`<p>${esc(g.amount_review_note||'')} Ruoli dichiarati: ${esc((g.insider_roles||[]).join(' · ')||'da verificare')}. Osservazioni SEC disponibili: ${esc(g.sec_observations??0)}/6; disponibilità non significa solidità. ${g.sec_risks?.length?'Rischi osservati: '+esc(g.sec_risks.join('; '))+'. ':''}Nessun Radar Score finanziario verificato.</p>`:'';
 const sec=g.sec_evidence||null;
 const fin=sec?.annual||{};
 const secValue=(row,eps=false)=>row&&Number.isFinite(row.value)?(eps?esc(price(row.value)):moneyButton(row.value)):'—';
 const secFacts=sec?`<div class="sec-facts" aria-label="Osservazioni annuali SEC">
 <div><small>Ricavi SEC</small><strong>${secValue(fin.revenue)}</strong></div>
 <div><small>EPS annuale</small><strong>${secValue(fin.eps,true)}</strong></div>
 <div><small>Flusso di cassa operativo</small><strong>${secValue(fin.operating_cashflow)}</strong></div>
 <div><small>Free cash flow</small><strong>${secValue(fin.free_cashflow)}</strong></div>
 </div><p class="sec-hint">Dati annuali SEC disponibili: ${esc(sec.available_count)}/5. Valori del rispettivo esercizio, non necessariamente dello stesso periodo né attuali.</p>`:'';
 const secSignals=sec?`<p><strong>Bilanci SEC:</strong> ${esc(sec.label)}. ${esc(sec.positive_observations?.length??0)} osservazioni favorevoli; ${esc(sec.observed_risks?.length??0)} segnali negativi riscontrati.</p>
 <p><strong>Osservazioni favorevoli:</strong> ${esc(sec.positive_observations?.join(' · ')||'Nessuna verificata.')}</p>
 <p><strong>Possibili rischi:</strong> ${esc(sec.observed_risks?.join(' · ')||'Nessun fattore negativo tra quelli analizzati; non equivale ad assenza di rischi.')}</p>
 <p>${esc(sec.note||'Mancano quotazioni e capitalizzazioni autorizzate per la verifica completa.')}</p>`:'';
 const note=g.aggregation_verified?'':'<p>Possibili co-dichiarazioni: importo e conteggio non sono un totale verificato.</p>';
 const details=`<details class="card-more"><summary>Verifiche, prezzi e dati mancanti</summary>
 ${note}${rationale}${secSignals}
 <p>Capitalizzazione corrente: ${moneyButton(g.market_cap)}. Capitalizzazione della settimana: ${moneyButton(g.historical_market_cap)}${g.historical_market_cap_as_of?' ('+esc(g.historical_market_cap_as_of)+')':''}. Soglia richiesta: ${moneyButton(f.required_amount)}.</p>
 <p>Prezzo corrente: ${esc(price(g.current_price))}${g.current_price_as_of?' · '+esc(g.current_price_as_of):''}. ${esc(g.significant_window_count??1)} finestre significative: non sommare periodi sovrapposti.</p>
 ${preliminary&&g.selection_reasons?.length?'<p>Controlli ancora necessari: '+esc(g.selection_reasons.join('; '))+'.</p>':''}
 </details>`;
 el.innerHTML=`<div class="card-head">
 <button class="star" aria-label="${isFavorite(g)?'Rimuovi dai':'Aggiungi ai'} Preferiti ${esc(g.symbol)}" aria-pressed="${isFavorite(g)}" title="Salva nei Preferiti">${isFavorite(g)?'★':'☆'}</button>
 <div class="card-title"><span class="ticker">${esc(g.symbol||'N/D')}</span><h3>${esc(g.company)}</h3><small>${day}</small></div>
 <div class="score ${preliminary?`score-strength-${strengthTier}`:""}" ${preliminary?`aria-label="Forza insider ${esc(score)} su 100; fascia ${strengthLabel}"`:""}><strong>${esc(score)}</strong><small>${esc(scoreLabel)}</small></div></div>
 <div class="metrics">
 <div><strong>${moneyButton(g.amount)}</strong><small>${g.amount_review_required?'Importo da riconciliare':g.aggregation_verified?'Acquisti dichiarati in 7 giorni':'Importo prudenziale in 7 giorni'}</small></div>
 <div><strong>${esc(g.transaction_count??'—')}</strong><small>Operazioni nella settimana</small></div>
 <div><strong>${esc(g.significant_window_count??1)}</strong><small>Finestre significative</small></div></div>
 <div class="card-meta"><span class="badge">${esc(label)}</span>${sec?.sec_documented_for_review?'<span class="badge badge-sec">Bilanci SEC da approfondire</span>':''}</div>
 ${secFacts}${details}<div class="card-actions"><button class="open-detail">Esplora azienda</button></div>`;
 el.querySelector('.star').addEventListener('click',()=>toggleFavorite(g));
 el.querySelector('.open-detail').addEventListener('click',()=>detail(g,favorite?favorites.find(f=>f.cik===g.cik)?.transactions:null));
 return el;
}
function renderRadar(){
 const groups=radar?.groups||[],selected=groups.filter(g=>RadarCore.homeDecision(g)==='selected').sort((a,b)=>b.analysis.radar_score-a.analysis.radar_score),stats=radar?.stats||{};
 const pending=stats.pending_base_candidates??groups.filter(g=>RadarCore.homeDecision(g)==='pending').length;
 $('#windowStatus').textContent=radar?`Universo degli ultimi sei mesi: ${radar.search_start||radar.window_start} — ${radar.as_of}. Ogni acquisto è aggregato in finestre mobili di sette giorni all’interno del semestre. Una scheda per società.`:'';
 $('#resultsCount').textContent=`${selected.length} società con tutti i criteri verificati`;
 $('#overviewCandidates').textContent=new Intl.NumberFormat('it-IT').format(stats.companies_weekly_base_pass??pending);
 $('#overviewVerified').textContent=new Intl.NumberFormat('it-IT').format(selected.length);
 $('#overviewObserved').textContent=new Intl.NumberFormat('it-IT').format(stats.companies_with_purchase_rows??0);
 $('#overviewDate').textContent=radar?.as_of||'—';
 $('#pendingStatus').textContent=`${stats.companies_with_purchase_rows??groups.length} aziende con righe di acquisto nel semestre; ${stats.companies_with_unambiguous_windows??0} con acquisti azionari utilizzabili, ${stats.companies_weekly_base_pass??0} sopra 100.000 USD dichiarati in almeno sette giorni. ${stats.companies_historical_cap_threshold_pass??0} superano capitalizzazione storica e soglia proporzionale; ${stats.companies_current_cap_pass??0} la capitalizzazione corrente; ${stats.companies_current_financials_verified??0} con bilanci/debito attuali verificati; ${stats.companies_current_prices_verified??0} con prezzi correnti verificati. ${stats.companies_without_usable_window??0} aziende senza finestre utilizzabili. Dati mancanti restano in attesa di verifica.`;
 const progress=radar?.financial_progress;if(progress)$('#pendingStatus').textContent+=` Cache finanziarie: ${progress.cached}/${progress.candidates}; osservazioni sulle azioni: ${progress.outstanding_share_observations}; indici societari: ${progress.corporate_indices}; ultimi tentativi falliti: ${progress.latest_attempt_errors}. Disponibilità di dati, non verifica finanziaria completa. Aggiornamento fino a 25 società per scansione.`;
 $('#results').replaceChildren(...selected.map(g=>card(g)));
 if(!selected.length)$('#results').innerHTML='<p>Nessuna opportunità completamente verificata al momento. Le candidate SEC sono consultabili qui sotto.</p>';
 renderPreliminary();
 updateCount();
}

function renderPreliminary(){
 const list=preliminaryIndex||radar?.preliminary_groups||[],total=radar?.preliminary_total??list.length;
 const visible=list.slice(0,preliminaryLimit);
 $('#preliminaryCount').textContent=`${visible.length} di ${total} aziende visualizzate · ${radar?.sec_screening?.candidates_with_usable_sec_observations??'—'} con osservazioni finanziarie SEC utili per approfondire; senza prezzi e capitalizzazioni verificati non sono investimenti selezionati.`;
 $('#preliminaryResults').replaceChildren(...visible.map(g=>card(g)));
 $('#morePreliminary').classList.toggle('hidden',visible.length>=total);
}
$('#morePreliminary').addEventListener('click',async()=>{
 const b=$('#morePreliminary');b.disabled=true;
 try{if(!preliminaryIndex){const r=await fetch('./data/pending_index.json',{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);const d=await r.json();if(d.as_of!==radar.as_of)throw Error('Dati aggiornati: ricarica il Radar');preliminaryIndex=d.companies;}preliminaryLimit+=20;renderPreliminary();}
 catch(e){$('#preliminaryCount').textContent='Impossibile caricare altre candidate: '+e.message;}finally{b.disabled=false;}
});

function renderCustom(){
 if(!radar||!searchApplied)return;
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
 // Previously migrated legacy watchlist entries remain stored but are not shown as
 // explicit starred favorites. Do not delete or rewrite historic user data.
 const starred=favorites.filter(f=>!f.legacy);
 for(const f of starred){
  const group=[...(radar?.groups||[]),...(preliminaryIndex||radar?.preliminary_groups||[])].find(g=>g.cik===f.cik)||f.group;
  if(group){
   const el=card(group,{favorite:true});
   host.append(el);
  }else{
   const el=document.createElement('article');el.className='card';
   el.innerHTML=`<div class="card-head"><span class="ticker">${esc(f.symbol)}</span><h3>${esc(f.company||f.symbol)}</h3></div><p>Questa società non è presente nell'ultima classifica, ma il tuo preferito resta salvato.</p><button class="saved-detail">Operazioni salvate</button> <button class="remove">Rimuovi dai Preferiti</button>`;
   el.querySelector('.saved-detail').addEventListener('click',()=>savedDetail(f));
   el.querySelector('.remove').addEventListener('click',()=>{favorites=favorites.filter(x=>x!==f);saveFavorites();updateCount();renderFavorites();renderRadar();notify('Rimosso dai Preferiti');});
   host.append(el);
  }
 }
 if(!starred.length)host.innerHTML='<div class="favorites-empty"><span aria-hidden="true">☆</span><h2>Nessuna azienda nei Preferiti</h2><p>Tocca la stellina ☆ su un’azienda del Radar per ritrovarla qui.</p></div>';
}
function sourceRows(rows){return rows.length?`<ul class="source-list">${rows.map(x=>`<li><b>${esc(x.transaction_date)}</b> · ${esc(x.insider)} · ${(x.currency==='unknown'?esc(new Intl.NumberFormat('it-IT').format(x.amount)+' (valuta non verificata)'):moneyButton(x.amount))}<small>${x.purchase_eligible===false?'Esclusa/in revisione · ':''}${esc(x.shares)} azioni · ${esc(x.currency==='unknown'?String(x.unit_price)+' in valuta non verificata':price(x.unit_price))} dichiarati/azione · deposito ${esc(x.filed)} · ${esc(x.security_title||'Classe titolo non disponibile')}</small>${/^https:\/\/www\.sec\.gov\/Archives\//.test(x.form_url||'')?`<a href="${esc(x.form_url)}" target="_blank" rel="noopener noreferrer">Form 4 originale</a>`:''}</li>`).join('')}</ul>`:'<p>Nessuna operazione disponibile nello storico raccolto.</p>';}
function openDialog(html){$('#detailContent').innerHTML=html;const d=$('#detailDialog');if(typeof d.showModal==='function'){if(!d.open)d.showModal();}else d.setAttribute('open','');}
function financialSnapshot(s){
 if(!s?.financials)return '<h3>Fondamentali attuali</h3><p>Estrazione SEC non ancora disponibile per questa società: verifica in coda, non giudizio negativo sui bilanci.</p>';
 const f=s.financials,b=s.balance||{},series=(name,rows,unit)=>`<li>${name}: ${(rows||[]).slice(-3).map(x=>esc(x.year)+': '+esc(unit==='eps'?price(x.value):usd(x.value))+' (fine '+esc(x.end)+', pubblico '+esc(x.filed)+')').join('; ')||'Non disponibile'}</li>`;
 return `<h3>Osservazioni finanziarie SEC</h3>${s.extractor_current===false?'<p>Estrazione precedente in coda di ricalcolo: le serie conservano le date originali e non certificano i fondamentali attuali.</p>':''}<p>Estrazione ${esc(s.fetched_on||'N/D')}; analisi ${esc(f.as_of)}. ${/^https:\/\/data\.sec\.gov\/api\/xbrl\/companyfacts\//.test(s.source_url||'')?`<a href="${esc(s.source_url)}" target="_blank" rel="noopener noreferrer">Fonte SEC companyfacts</a>`:''}</p><ul>${series('Ricavi'+(f.revenue_scope_verified?' riconciliati':' · perimetro non verificato'),f.revenue_years)}${series('EPS',f.eps_years,'eps')}${series('Flusso operativo annuale',f.cashflow_years)}</ul><p>Cassa osservata: ${moneyButton(b.cash?.val)} al ${esc(b.cash?.end||'N/D')}. Osservazione debito: ${moneyButton(b.debt_observation?.val)} al ${esc(b.debt_observation?.end||'N/D')}; non è un totale del debito riconciliato. ${esc(b.note||'Perimetro del debito da verificare.')}</p><p>Questi dati non certificano da soli solidità attuale, valutazione o assenza di eventi successivi.</p>`;
}
function additionalSEC(s){
 if(!s)return '';
 const shares=(s.shares_observations||[]).map(r=>`<li>${esc(r.val)} azioni · ${esc(r.tag)} · osservate ${esc(r.end)}, pubbliche ${esc(r.filed)}. Classe e split non riconciliati: non usate per stimare la capitalizzazione.</li>`).join('');
 const events=(s.corporate_filings?.filings||[]).map(r=>`<li>${esc(r.form)} · ${esc(r.filed)} · <a href="${esc(r.url)}" target="_blank" rel="noopener">Indice SEC</a></li>`).join('');
 return `<h3>Azioni in circolazione e depositi successivi</h3><ul>${shares||'<li>Osservazioni sulle azioni non disponibili.</li>'}</ul><p>Indice dei depositi dalla settimana mostrata: segnalazioni da leggere, non revisione dei cambiamenti societari. Copertura parziale; massimo 40 voci. ${s.corporate_filings_error?'Ultimo recupero indice non riuscito.':''}</p><ul>${events||'<li>Nessun deposito recuperato in questa cache; non implica assenza di eventi.</li>'}</ul>`;
}
function financialReview(r){
 if(!r)return '';
 const series=(label,row)=>`<li>${label}: ${row?moneyButton(row.value)+' · periodo '+esc(row.start)+' — '+esc(row.end)+' · pubblico '+esc(row.filed):'Non verificabile'}</li>`;
 const ratio=x=>x==null?'Non verificabile':new Intl.NumberFormat('it-IT',{maximumFractionDigits:2}).format(x)+'×';
 const observed=(label,row)=>`<li>${label}: ${row?moneyButton(row.val)+' · periodo '+esc(row.start||row.end)+' — '+esc(row.end)+' · pubblico '+esc(row.filed):'Non verificabile'}</li>`;
 return `<div class="financial-review"><h3>Verifica finanziaria e valutazione</h3><ul>${series('Utile annuale',r.annual?.net_income)}${series('Capex monetario',r.annual?.capex)}${series('Free cash flow',r.annual?.free_cashflow)}${observed('Ultimo utile periodico (non annualizzato)',r.balance_observations?.net_income)}${observed('Ultimo flusso operativo periodico (non annualizzato)',r.balance_observations?.operating_cashflow)}<li>P/E: ${esc(ratio(r.pe_last_fiscal_year))}; P/FCF: ${esc(ratio(r.price_to_fcf_last_fiscal_year))}</li></ul><p>${esc(r.multiple_basis)}. ${esc(r.fcf_definition)}.</p>${r.risks?.length?'<p>Fattori sfavorevoli osservati:</p><ul>'+r.risks.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':''}<p>Dati e verifiche ancora necessari:</p><ul>${(r.missing||[]).map(x=>'<li>'+esc(x)+'</li>').join('')}</ul></div>`;
}
function savedDetail(f){openDialog(`<h2 id="detailName">${esc(f.company||f.symbol)}</h2><p>Righe SEC originali salvate. Non sommare automaticamente importi co-dichiarati.</p>${sourceRows(f.transactions||[])}`);}
async function detail(g,saved){
 let rows=saved||g.transactions,data=null;
 try{data=await companyDetail(g);if(data){rows=RadarCore.mergeTransactions(rows||[],data.transactions||[]);g={...data.company,...g,analysis:data.company.analysis};}}catch(e){storageWarning('Dettaglio azienda non accessibile: '+e.message);}
 if(!rows){try{const ids=new Set(g.transaction_ids||[]);rows=(await loadHistory()).filter(x=>ids.has(x.id));}catch{rows=[];}}
 const windows=data?.significant_windows||[];
 openDialog(`<h2 id="detailName">${esc(g.company)} · ${esc(g.symbol)}</h2><p>Analisi attuale al ${esc(data?.as_of||radar?.as_of)}. Settimana mostrata: ${esc(g.window_start)} — ${esc(g.window_end)} · Radar Score ${esc(displayRadar(g.analysis))}/100.</p><p>Acquisti dichiarati in questa settimana: ${moneyButton(g.amount)}. Prezzo medio SEC: ${esc(price(g.weighted_price))}; base originale, non rettificata per split. Prezzo corrente: ${esc(price(g.current_price))}${g.current_price_as_of?' al '+esc(g.current_price_as_of):''}. Confronto rettificato: ${g.distance_from_insider_pct==null?'Non verificabile':esc(g.distance_from_insider_pct)+'%'}.</p><p>Capitalizzazione della settimana: ${moneyButton(g.historical_market_cap)} al ${esc(g.historical_market_cap_as_of||'N/D')}. Capitalizzazione corrente: ${moneyButton(g.market_cap)} al ${esc(g.current_valuation_as_of||'N/D')}. I due periodi non vengono sostituiti l’uno con l’altro. Insider indipendenti: non verificati.</p><p>Il Radar Score aziendale usa la migliore finestra del semestre ${esc(data?.company?.window_start||g.window_start)} — ${esc(data?.company?.window_end||g.window_end)} e le verifiche attuali. La ricerca può mostrare un’altra finestra; non ricalcola il punteggio globale.</p>${specificFactors(g)}${financialSnapshot(data?.financial_snapshot)}${financialReview(data?.financial_review)}${additionalSEC(data?.financial_snapshot)}<h3>Tutte le settimane significative del semestre (${windows.length})</h3><p>Finestre sovrapposte: non sommare importi o transazioni tra finestre.</p><ul>${windows.map(w=>`<li>${esc(w.window_start)} — ${esc(w.window_end)} · ${moneyButton(w.amount)} · ${esc(w.transaction_count)} transazioni · soglia proporzionale ${w.weekly_economic_verified?'verificata':'non verificata'}</li>`).join('')||'<li>Nessuna finestra significativa disponibile.</li>'}</ul><h3>Operazioni SEC della società (${rows?.length||0})</h3><p>Righe fonte dal ${esc(data?.transaction_period_start||data?.search_start||'N/D')} al ${esc(data?.transaction_period_end||data?.as_of||'N/D')}. Le operazioni prima del semestre restano consultabili ma non entrano nel Radar corrente.</p><p>Prezzi dichiarati in USD secondo l’istruzione 5 del Form 4; non sono quotazioni correnti. Le righe escluse o in revisione non sono sommate nelle soglie.</p>${sourceRows(rows||[])}<p>Nessun BUY o notifica di investimento.</p>`);
}

function specificFactors(g){const a=g.analysis||{};return `<h3>Motivazioni del punteggio</h3><p>Stato: ${esc(a.priority||'Non verificabile')}. Opportunità ${esc(a.opportunity_score??'—')}/100 · Forza insider ${esc(a.insider_strength_score??'—')}/100. Media 70/30 prima dei limiti: ${esc(a.radar_uncapped??'—')}. ${displayRadar(a)==='—'?'Punteggio non pubblicabile come rating attendibile; eventuale snapshot precedente resta conservato.':`Radar Score ${esc(a.radar_score)}/100 (${esc(a.score_status)}).`}</p><h3>Fattori favorevoli</h3><ul class="factor-positive">${[...(a.insider_reasons||[]),...(a.reasons||[])].map(x=>`<li>${esc(x)}</li>`).join('')||'<li>Nessuno verificato</li>'}</ul><h3>Rischi, dati mancanti e limiti</h3><ul class="factor-negative">${[...(a.radar_caps||[]),...(a.warnings||[])].map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`;}
function scoreHelp(){
 const secTime=result?.last_scan_utc;
 const parsed=secTime?new Date(secTime):null;
 const shown=parsed&&Number.isFinite(parsed.getTime())?parsed.toLocaleString('it-IT',{day:'numeric',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit'}):'Data non disponibile';
 const backlog=result?.coverage?.unprocessed_listed_forms;
 const secInfo=esc(shown);
 openDialog(`<h2 id="detailName">Informazioni su RadarAzioni</h2>
 <h3>Ultimo aggiornamento SEC</h3>
 <p>Ultima scansione registrata: <strong>${secInfo}</strong> (ora del dispositivo). ${backlog!=null?esc(new Intl.NumberFormat('it-IT').format(backlog))+' depositi Form 4 ancora in coda.':''} La raccolta recente può essere parziale e la data della scansione non garantisce completezza.</p>
 <h3>Come si calcola il Radar Score?</h3>
 <p>Quando tutti i dati sono verificati, il punteggio combina il <strong>70% di qualità finanziaria</strong> e il <strong>30% di forza degli acquisti insider</strong>. È una regola sperimentale, non una probabilità di rendimento né una raccomandazione BUY.</p>
 <p>La qualità finanziaria considera crescita dei ricavi, EPS, cassa e valutazione; la forza insider considera importo e ruolo dichiarato. I dati mancanti impediscono di attribuire un Radar Score completo.</p>
 <h3>Come si distinguono le classifiche?</h3>
 <p><strong>Le aziende selezionate dal Radar</strong> hanno superato tutti i controlli richiesti, inclusi prezzi, capitalizzazioni e fondamentali. <strong>Aziende con acquisti insider significativi</strong> significa solo che hanno superato il filtro iniziale degli acquisti negli ultimi sei mesi, raggruppati in finestre di 7 giorni.</p>
 <p>Capitalizzazione minima prevista: 500 milioni USD; acquisti minimi 100.000 USD in 7 giorni; soglia proporzionale 0,002% della capitalizzazione della settimana, fino a 2 milioni USD. Questi filtri non sono cambiati.</p>
 <p>La <strong>forza insider</strong> è una misura preliminare distinta dal Radar Score: verde da 70 a 100, giallo da 40 a 69, rosso sotto 40. Il colore non è un segnale BUY.</p>
 <p>Fonte: SEC Form 4 e SEC XBRL. Prezzi correnti e capitalizzazioni non ancora disponibili da una fonte gratuita autorizzata per la redistribuzione pubblica. Le aziende prive di queste verifiche non vengono promosse.</p>`);
}
function selectionHelp(){openDialog(`<h2 id="detailName">Criteri automatici e fonti</h2><p>Ricerca automatica su tutti gli acquisti degli ultimi sei mesi di calendario, aggiornata a ogni scansione. Una sola scheda per società se almeno una finestra mobile di sette giorni supera i criteri. Capitalizzazione verificata minima 500 milioni USD. Acquisti aggregati in sette giorni almeno 100.000 USD. Soglia aggiuntiva: 0,002% della capitalizzazione, massimo 2 milioni USD; importo richiesto = max(100.000, min(2.000.000, capitalizzazione × 0,00002)).</p><p>La soglia proporzionale usa la capitalizzazione della settimana dell’acquisto; la selezione oggi richiede anche capitalizzazione/valutazione correnti, confronto prezzo rettificato per split e revisione dei cambiamenti successivi. Dati storici e correnti mancanti restano distinti e non confermano opportunità.</p><p>Richiesti anche aggregazione senza ambiguità, fondamentali completi e riconciliati con ricavi/EPS in crescita, EPS positivi, cassa triennale positiva, valutazione favorevole verificata e Radar Score attendibile. Ordine: Radar Score decrescente. Sono criteri sperimentali, non soglie scientificamente validate.</p><p>Fonti attive: archivi trimestrali SEC già importati + depositi giornalieri raccolti, Form 4 originali, <a href="https://www.sec.gov/search-filings/edgar-application-programming-interfaces" target="_blank" rel="noopener noreferrer">SEC XBRL companyfacts</a>. Fonti prezzi/capitalizzazioni redistribuibili non ancora integrate (vedi anche il <a href="./data/source_policy.json" target="_blank" rel="noopener">registro fonti e soluzione richiesta</a>): i casi mancanti sono in attesa, non selezionati. Form 4/A in revisione ed esclusi dai segnali, copertura parziale. La Ricerca personalizzata non modifica questi criteri.</p>`);}



async function load(){try{
 const fetchJSON=async path=>{const r=await fetch(path+'?ts='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error('HTTP '+r.status);return r.json()};
 searchIndex=null;searchPromise=null;
 [radar,result]=await Promise.all([fetchJSON('./data/radar.json'),fetchJSON('./data/scan_status.json')]);
 preliminaryIndex=null;preliminaryLimit=20;searchIndex=null;searchPromise=null;
 renderRadar();updateSECStatus();if(page==='favorites')renderFavorites();
 }catch(e){$('#criticalStatus').textContent='Errore critico: dati SEC non accessibili. '+e.message+'. Preferiti salvati consultabili.';$('#criticalStatus').classList.remove('hidden');renderRadar();}}
$$('nav button').forEach(b=>b.addEventListener('click',()=>setPage(b.dataset.page)));
$('#appInfoBtn').addEventListener('click',scoreHelp);
$('#closeDetail').addEventListener('click',()=>{const d=$('#detailDialog');if(d.close)d.close();else d.removeAttribute('open')});
$('#filtersForm').addEventListener('submit',async e=>{
 e.preventDefault();
 const p={min_market_cap:Number($('#minCap').value),min_weekly_amount:Number($('#minAmount').value),proportional_pct:Number($('#proportion').value),proportional_cap:Number($('#maxRequired').value)};
 try{RadarCore.evaluate(0,null,p);}catch{$('#filterStatus').textContent='Controlla i filtri: valori non validi.';return;}
 params=p;searchApplied=true;$('#searchResults').classList.remove('hidden');
 $('#customStatus').textContent='Sto caricando i risultati della ricerca…';
 try{localStorage.setItem('radarazioni-filters-v1',JSON.stringify(params));$('#filterStatus').textContent='Filtri applicati.';}
 catch{$('#filterStatus').textContent='Filtri applicati; non è stato possibile salvarli sul dispositivo.';}
 try{await ensureSearchIndex();renderCustom();}catch(err){$('#customStatus').textContent='Impossibile caricare la ricerca: '+err.message;}
});
$('#resetFilters').addEventListener('click',()=>{
 params={...RadarCore.defaults};syncFilterInputs();
 $('#minScore').value=0;$('#searchPeriod').value='semester';$('#search').value='';
 $('#visibility').value='candidates';$('#sort').value='amount';
 searchApplied=false;$('#searchResults').classList.add('hidden');$('#customResults').replaceChildren();
 $('#customStatus').textContent='';$('#filterStatus').textContent='Filtri ripristinati. Premi Applica filtri per cercare.';
 try{localStorage.setItem('radarazioni-filters-v1',JSON.stringify(params));}catch{}
});
$('#filtersForm').addEventListener('input',()=>{
 if(!searchApplied)return;
 searchApplied=false;$('#searchResults').classList.add('hidden');
 $('#filterStatus').textContent='Filtri modificati: premi Applica filtri per aggiornare i risultati.';
});
$('#filtersForm').addEventListener('change',()=>{
 if(!searchApplied)return;
 searchApplied=false;$('#searchResults').classList.add('hidden');
 $('#filterStatus').textContent='Filtri modificati: premi Applica filtri per aggiornare i risultati.';
});
$('#refreshBtn').addEventListener('click',load);
syncFilterInputs();updateCount();load();


function updateSECStatus(){
 const stamp=Date.parse(result?.last_scan_utc||''),stale=!Number.isFinite(stamp)||Date.now()-stamp>48*3600000;
 const unavailable=!!result?.errors?.length && (result?.coverage?.days_checked||[]).length===0;
 $('#criticalStatus').classList.toggle('hidden',!stale&&!unavailable);
 if(stale||unavailable)$('#criticalStatus').textContent=unavailable?'Scansione SEC non riuscita: indici non accessibili. Controlla il pulsante informazioni ⓘ in alto.':'Scansione SEC obsoleta o data assente (oltre 48 ore): nessun dato deve essere interpretato come aggiornato.';
}

