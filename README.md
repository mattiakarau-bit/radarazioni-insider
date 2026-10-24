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
