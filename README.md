# RadarAzioni – Insider Intelligence · 0.9.2

App statica PWA per screening di acquisti SEC Form 4. Nessun BUY, notifica d’investimento,
trading automatico o servizio a pagamento. Compatibile con navigazione touch e standalone;
Preferiti locali, nessuna sincronizzazione tra dispositivi.

## Funzioni pubblicate

- Radar Score = 70% opportunità + 30% forza insider; componenti visibili nella spiegazione.
  Limiti sul risultato: 49 senza valutazione, 39 con storico cassa non soddisfatto,
  29 con dati non verificati o perdite/cassa negativa effettive. Vale il limite più basso. Non è probabilità di rendimento.
- Radar per società, finestra `[data analisi − 6 giorni, data analisi]` secondo data operazione.
- Filtri modificabili: cap minima 500M USD, totale 7 giorni 100k USD, percentuale 0,002%,
  tetto proporzionale 2M USD. Importo richiesto `max(100k, min(2M, cap * 0.002 / 100))`.
  Sono ipotesi da validare storicamente. Senza cap i filtri restano non verificabili;
  la Ricerca può includere non verificabili; il Radar pubblica solo casi con evidenze complete.
- Stelle e Preferiti con migrazione di `radarazioni-watchlist-v2`. Vecchia chiave conservata,
  nuova `radarazioni-favorites-v1`. Operazioni salvate fuse per ID e non eliminate quando
  la società esce dal radar o dai filtri. Errori/quota storage segnalati; backup precedente
  non cancellato. Svuotare i dati del browser può comunque cancellare i Preferiti.
- Versione PWA e avviso aggiornamento: “Aggiorna e ricarica”, senza reinstallazione.

## Deduplicazione e aggregazione prudente

Accession + indice transazione deduplica gli alias URL. Righe distinte nel medesimo Form 4
restano distinte. Per termini economici uguali (data, titolo/classe dichiarata, quantità,
prezzo; proprietà diretta/indiretta non prova indipendenza) in depositi distinti, l’aggregatore conta il massimo numero
di righe riportato in un singolo deposito, anziché sommare tutte le co-dichiarazioni.
Questo può sottostimare acquisti indipendenti con gli stessi termini: la scheda indica
**stima prudenziale**, non un totale verificato. Tutte le righe e somme originali rimangono
nel dettaglio/storico. Classi dichiarate diverse non vengono fuse. Prezzo ponderato assente
quando classe o deduplicazione non sono verificabili. Nessun numero di insider indipendenti
è pubblicato senza verifica; nomi differenti o fondi collegati non assegnano punti cluster.

## Storico: cosa è predisposto e cosa manca

`scanner.radar.historical_windows` genera finestre mobili osservate negli ultimi 12 mesi;
l’interfaccia seleziona 6 o 12. Finestre sovrapposte non rappresentano capitale addizionale.
La disponibilità effettiva dipende dalla copertura SEC, oggi molto più breve di sei mesi.
Il comparatore matematico `price_band` testa ±5% su due prezzi già sulla medesima base split.
Il gate di revisione reale resta **chiuso**, anche se riceve flag arbitrari: nessun provider
redistribuibile è validato, né sono integrati eventi/motivi del ribasso o analisi aggiornata.
I prezzi SEC non vengono spacciati per prezzi correnti o rettificati. Nessuna opportunità
storica o avviso reale viene attivato. Vedi [fonti e diritti](research/free-data-sources.md).

## Scanner e pubblicazione

Coda persistente accession con 2/3 posti ai recenti e 1/3 ai più vecchi, prestito posti liberi,
ritentativi 1–7 giorni, recupero indici persi durante interruzioni, pausa del backfill se
la coda supera due lotti. Conteggi per giorno con fonti e timestamp. Form 4/A esclusi;
nessuna copertura totale/in tempo reale garantita. Storico SEC non troncato.

Le chiamate companyfacts sono ordinate per importo settimanale prudenziale, con massimo
30 emittenti nuovi per esecuzione (`MAX_FACTS_PER_RUN`, limite 100) e budget 18 minuti.
Dati differiti/mancanti non producono bonus. La capitalizzazione mancante non viene stimata.
`radar.json` contiene finestre correnti e riepiloghi storici; lo storico completo conserva
le transazioni. Il workflow salva tutti i JSON e pubblica Pages solo dopo test riusciti.
Nessuna modifica alle credenziali esistenti.

```sh
python -m unittest discover -s tests -v
node --test tests/*.test.cjs
python -m scanner.migrate
```

La migrazione ricalcola dati locali, non chiama SEC o Telegram. Per i test browser:

```sh
npm install --ignore-scripts --no-package-lock
npx playwright install --with-deps chromium webkit
npm run test:ui
```

Test UI su WebKit/Chromium a 390×844, 768×1024 e 320×568: overflow, dettagli score,
migrazione, stelle, filtri, Preferiti persistenti e storico. Sono simulazioni browser,
non certificazione su hardware iPhone/iPad. Il workflow qualità viene eseguito sulla PR
prima dell’unione e nuovamente prima della pubblicazione su main.

## Aggiornamento 0.6.0

Radar automatico selettivo, senza form o ricerca avanzata. Parametri fissi 500M/100k/
0,002%/tetto 2M; aggregazione certa, capitalizzazione e valutazione verificate, fondamentali
riconciliati e criteri positivi, score attendibile. Le società prive di evidenze non sono
selezionate: contatore attese e stato vuoto corretto. Le fonti/criteri sono nell’icona ⓘ.

Ricerca personalizzata separata: cap, importo, percentuale, tetto, score minimo, testo,
periodo 7/30/90/180/365 giorni, ordinamento ed esito verifica. I parametri locali precedenti
migrano semanticamente nella ricerca, non alterano il Radar. Il periodo è la selezione
delle date finali delle finestre; ogni finestra di aggregazione resta sempre sette giorni.

Un solo pulsante globale sul punteggio; fattori favorevoli/rischi specifici nei Dettagli.
Stato SEC discreto nel pannello; errore dati/indici inaccessibili o scan oltre 48 ore sono
segnalati chiaramente. Preferiti e chiavi di salvataggio 0.5.0 conservati.

Scoring: rimosso il doppio limite prima/dopo la media; mancata crescita distinta da perdite
attuali. Nessun voto numerico quando i dati sono non verificabili. Gli snapshot finanziari
senza tag/perimetro restano conservati ma vengono sospesi dal rating attendibile e
riesaminati prioritariamente con SEC. Nessuna capitalizzazione integrata da fonti con
redistribuzione non autorizzata. Contratto di valutazione completa solo interno/preparatorio,
non attivato da un flag client; fixture solide testate a 94 e perdite/cassa negativa <=29.

[Diagnosi, distribuzione e conteggi effettivi](research/rating-diagnosis-0.6.0.md).
I test UI coprono anche home vuota, isolamento della ricerca, dettagli senza pulsanti
ripetuti, fixture selezionabile verificata e avviso critico SEC, oltre a Preferiti persistenti.

## Release 0.7.0 · Archivi strutturati e ricerca ML

Importatore ufficiale trimestrale 2021–2026, estendibile al 2006, separato dalla scansione
recente. Shard atomici e deterministici, manifest SHA256 e checkpoint per trimestre.
Form 4/A, alias/co-dichiarazioni, classi non ordinarie e conflitti vengono conservati in
revisione anziché produrre doppi acquisti o segnali. Corretto anche il controllo troppo
rigido dell’intestazione giornaliera SEC (case/spazi) che bloccava le scansioni.

La pagina Storico mostra copertura e candidati, carica un solo trimestre a richiesta e
separa gli archivi in verifica dai ritorni al prezzo insider (ancora non verificabili).
Preferiti compatibili anche per emittenti presenti solo negli archivi. Nessun rating aumentato.

Pipeline reale di ricerca SQLite, target 30/90/180, regressione logistica e gradient boosting
implementati ma bloccati senza prezzi/target verificati e campioni sufficienti. Nessuna
performance o modello fittizio. [Specifiche e limiti](research/sec-bulk-and-ml.md).

```sh
python -m scanner.bulk --max-quarters 1
python -m scanner.ml
```

Usano l’identità SEC già configurata nei Secrets. Non impostare credenziali nel codice.
Dipendenze opzionali per training: `pip install -r research-requirements.txt` (solo librerie,
nessuna API o sottoscrizione). La PWA 0.7.0 si aggiorna senza cancellare i Preferiti locali.

## 0.8.0 — il Radar cerca nel semestre, non nell’ultima settimana

`python -m scanner.universe` riutilizza gli shard SEC già importati e li riconcilia
con `events_history.json`. L’universo si basa sulla **data dell’operazione negli ultimi
sei mesi di calendario**, con deposito già pubblico alla data del calcolo. Le finestre
mobili restano di sette giorni: una società entra nella classifica solo se almeno una
finestra supera i criteri economici e tutti i controlli attuali. Una scheda per CIK;
tutte le settimane significative restano nel dettaglio azienda caricato su richiesta.

`docs/data/semester_report.json` riporta universo, righe, conteggi indipendenti per
ogni evidenza e funnel cumulativo. Non usare il totale emittenti 2021–2026 come
universo semestrale. La copertura di ottobre dipende dalla coda giornaliera, resta
parziale e viene mostrata separatamente. Le vecchie righe senza classe/swap verificati
restano conservate ma non certificano il superamento delle soglie.

La soglia proporzionale usa la capitalizzazione storica della settimana; quella
corrente è un controllo diverso. Mancanze non sono sostituite con l’altra data.
SEC Form 4, istruzione 5, prescrive prezzi dichiarati in USD: questo chiarisce la
base degli importi SEC, senza rendere verificati i prezzi di mercato. Gli shard 0.7
sono immutati; il nuovo adapter documenta la base valutaria senza inventare conversioni.

La produzione non ha un provider prezzi/capitalizzazioni approvato. Il registro
`docs/data/source_policy.json` contiene fonti, condizioni verificate, fonti escluse
e passaggi concreti ancora richiesti. Nessuna raccomandazione è confermata senza
prezzi, split, valutazione, debito/cassa attuali e revisione dei cambiamenti dopo gli
acquisti. Il cache SEC `data/analysis` contiene estrazioni e osservazioni finanziarie
con provenienza; osservazioni del debito non riconciliate non sono una verifica del
perimetro. Refresh fino a 25 emittenti per scansione, TTL sette giorni, priorità agli
acquisti sopra soglia e rotazione dei mancanti. Errori conservano snapshot datati.

La homepage scarica una classifica JSON compatta e uno stato scansione senza righe
transazione; indice Ricerca e dettagli sono scaricati solo su richiesta. Parametri
personali e periodo 7/30/90/180/365 non cambiano il semestre della homepage.
Preferiti e chiavi locali non vengono cancellati, nessuna sincronizzazione dichiarata.

Verifiche: test di accettazione maggio/giugno/settembre → ottobre con evidenze
fittizie complete; una sola scheda con più settimane; soglie, correzioni, co-report,
separazione capitalizzazioni storiche/correnti, prezzi mancanti e cassa negativa.
`python tests/verify_semester.py` controlla la pipeline sui veri archivi checkout,
riconta gli emittenti indipendentemente e riconcilia gli importi dei dettagli.
Actions esegue questa verifica e i test mobile Chromium/WebKit prima di Pages.
ML e segnali BUY restano disabilitati senza target/validazione reali.

### 0.8.1 — confine del semestre nelle schede

La Ricerca in modalità “6 mesi · semestre Radar” usa ora le finestre semestrali
clippate lato Python, senza riprendere importi da una finestra annuale che inizi
prima del limite. Test specifico: un acquisto il 22 aprile non incrementa la
settimana del 27 aprile nel semestre che inizia il 25 aprile. L’indice annuale resta
separato per la ricerca personalizzata sugli altri periodi.

### 0.8.2 — serie finanziarie SEC non obsolete

L’estrattore sceglie il concetto annuale con fine periodo più recente, usando la
priorità dei tag solo a parità di data. Un vecchio tag `Revenues` fermo al 2017 non
nasconde più una serie 2023–2025. Non mescola concetti tra anni e mantiene i blocchi
per ricavi parziali o discordanti. Le estrazioni precedenti vengono declassate e
messe in coda di ricalcolo con priorità, senza attribuire loro validità corrente.

## 0.8.3 — analisi finanziaria senza inventare dati mancanti

Analisi offline delle cache SEC esistenti: utili periodici, liquidità e debito
osservato datati; FCF soltanto con CFO/capex coerenti, multipli soltanto con
evidenze di mercato verificate. I nuovi campi annuali vengono estratti dal
medesimo refresh ordinario, senza invalidare/riscaricare cache per completarli.
Nello snapshot 25 ottobre: 881 candidate insider, 60 cache esaminate, zero
società prequalificate su prezzi/cap, zero società verificate in homepage.
Dettagli finanziari estesi nel layout esistente; Preferiti e scoring conservati.
La pubblicazione su push è offline, gli aggiornamenti programmati restano attivi.
[Metodi, risultati e limiti](research/financial-review-0.8.3.md).

## 0.9.0 — interfaccia monocromatica e importi chiari

Restyling frontend bianco/nero (modalità scura predefinita, modalità chiara opzionale),
schede finanziarie alleggerite, riepilogo del semestre, microinterazioni su pulsanti
e Preferiti, miglioramenti responsive per iPad e iPhone.

Gli importi numerici si leggono in italiano come `4,43 Mln $` o `4,43 Mld $`;
toccando la cifra si visualizza il valore esatto con separatori italiani.
I dati sorgente, le soglie, la selezione e il punteggio rimangono invariati.
Il valore intero non va perso dalla formattazione; i mancanti restano marcati come tali.

Tema salvato in `radarazioni-ui-theme`, senza cambiare l'archivio Preferiti.
L'interfaccia rispetta `prefers-reduced-motion` e la PWA aggiorna la versione
e la cache statica a 0.9.0. Test Money + controlli WebKit/Chromium.

## 0.9.1 — navigazione e filtraggio semplici

Tre schede a tutta larghezza sempre visibili in basso: Radar, Ricerca,
Preferiti. Storico eliminato dall'interfaccia, ma archivi SEC e dati
personali precedenti conservati. Le classifiche sono chiaramente separate
tra societa selezionate dopo tutti i controlli e acquisti insider significativi
ancora da verificare. I valori Forza insider usano verde 70–100,
giallo 40–69 e rosso sotto 40; non sono rating di investimento.

Pulsante ⓘ in testata con metodologia e ultima scansione SEC. Ricerca mostra
aziende soltanto dopo 'Applica filtri', senza caricare indici in anticipo.
Preferiti mostra esclusivamente le societa salvate con stellina; le
vecchie liste migrate sono conservate, non visualizzate come selezioni esplicite.

## 0.9.2 — bilanci SEC più visibili, selezione preliminare più documentata

Le società con acquisti insider significativi vengono ordinate per **priorità
di approfondimento**: prima i documenti SEC annuali con segnali favorevoli,
poi le osservazioni disponibili, il punteggio insider preliminare e gli
importi. Operazioni con importi estremi restano in revisione. La priorità
NON equivale al Radar Score di investimento; missing = sconosciuto, non
negativo.

Quando verificabili nei file SEC, le schede mostrano ricavi, EPS, flusso di
cassa operativo e FCF con note sui periodi. Gli importi di ciascun indicatore
possono riferirsi a esercizi diversi; la provenienza dettagliata e i controlli
rimangono nei dettagli societari. I segnali finanziari positivi e le criticità
osservate sono espliciti, non interpretazioni BUY.

Il recupero SEC Companyfacts + indice depositi è incrementale e autorizzato
per un massimo di 50 candidate per scansione (in precedenza 25); manteniamo
cache, source URL, throttling, test e backoff dopo errori. La funzione
scarta dati futuri o obsoleti e non inventa debito/capitalizzazioni.

**Limite fondamentale:** prezzi e capitalizzazioni storici e attuali,
rettifiche split, P/E, P/FCF e controlli post-acquisto restano non verificati
finché non è disponibile un fornitore con diritti di pubblicazione compatibili.
Nessuna quota API non autorizzata, nessun provider di prezzi fittizio.
