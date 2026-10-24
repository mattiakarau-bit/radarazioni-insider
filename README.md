# RadarAzioni – Insider Intelligence

Scanner SEC EDGAR e interfaccia statica. Solo screening: nessun trading automatico.

## Verifica locale

```sh
python -m unittest discover -s tests -v
node --check docs/app.js
```

Nessuna dipendenza Python esterna. Il workflow esegue i test prima della pubblicazione.
Le credenziali esistenti restano nei GitHub Actions secrets.

## Correzioni dati v2

Identità evento: accession SEC + indice transazione, indipendente dal CIK nella URL.
Transazioni diverse nello stesso deposito restano separate. Depositi distinti con importi
uguali non vengono automaticamente cancellati: potrebbero rappresentare operazioni reali.
Date di deposito e operazione in ISO; prezzi dichiarati visualizzati fino a sei decimali,
separatamente dall'importo complessivo. Il prezzo dichiarato può essere una media ponderata.

Migrazione offline ripetibile (senza notifiche o chiamate SEC):

```sh
python -m scanner.migrate
```

Lo scoring viene ricalcolato sullo storico. Con indicatori finanziari mancanti è limitato
a 49/100 e non attiva notifiche. Il conteggio insider esclude depositi successivi alla data
valutata. Nessun punteggio è una probabilità di rendimento o un segnale di acquisto.

## Sviluppo ML successivo

Prima dell'addestramento servono prezzi storici reali rettificati, titoli delistati,
identificativi stabili e fondamentali disponibili alla data del deposito. Definire rendimenti
futuri a 30/90/180 giorni rispetto a un benchmark e costi di negoziazione. Separare train,
validazione e test cronologicamente, con intervalli di esclusione per target sovrapposti;
confrontare con regole e benchmark. Non usare lo storico attuale come prova di efficacia:
è troppo breve. Verificare copertura e licenze delle fonti gratuite prima di scegliere il
fornitore. Nessun servizio a pagamento o esecuzione automatica di ordini.

## Due punteggi v3

Forza insider: importo 0–50, ruolo 0–30; 20 punti cluster riservati e non
assegnati finché non esiste una verifica documentata dell’indipendenza. Nomi distinti,
fondi collegati e comproprietari non dimostrano decisioni indipendenti.
Opportunità: fatturato 25, EPS 25, cassa operativa 20; valutazione ancora assente,
quindi massimo 49. Cassa negativa o dati insufficienti: massimo 39. Cassa operativa
positiva non dimostra adeguatezza del free cashflow o convenienza del prezzo.
I due punteggi non si sommano. Tutte le notifiche sono disabilitate nello scoring v3;
nessun BUY validato. Lo storico viene ricalcolato con la migrazione offline.

## Release 0.4.0: coda e aggiornamenti

Coda persistente per accession: 2/3 della capacità ai depositi recenti, 1/3 ai più vecchi,
con prestito dei posti inutilizzati. Errori ritentati con attesa crescente (1–7 giorni),
mai cancellati per scadenza della finestra. Ogni esecuzione aggiorna gli indici recenti,
recupera un giorno precedente e ritenta fino a tre indici falliti. Budget di elaborazione
18 minuti; con arrivi superiori alla capacità l’arretrato può crescere: nessuna garanzia
di copertura totale o latenza. Form 4/A ancora esclusi e dichiarati come tali.

`state.json` conserva coda, accession processate, indici verificati e cursore storico.
`results.json.coverage.by_day` permette di riconciliare indicizzati = processati + in coda
per ogni giorno e riporta URL originale e ora della verifica. I conteggi preesistenti non
vengono inventati: si popolano con le scansioni effettive. Storico transazioni non troncato.
La scrittura JSON è atomica per file; dati storici salvati prima delle accession processate.

Versione visibile anche su mobile, manifest `docs/version.json`, controllo ogni 5 minuti,
al ritorno in primo piano e al ripristino della rete. “Aggiorna e ricarica” applica il nuovo
service worker e ricarica l’app, senza reinstallazione. Offline il controllo non dichiara
aggiornamenti riusciti. Per la prossima release aggiornare insieme update.js, version.json,
index.html e nome cache sw.js; i test verificano la coerenza.

Test: `python -m unittest discover -s tests -v` e `node --test tests/update.test.cjs`.
Ricognizione fonti e requisiti finanziari: [research/free-data-sources.md](research/free-data-sources.md).
