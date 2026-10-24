# Diagnosi dei rating · 0.6.0 · 24 ottobre 2026

Campione pubblicato 0.5.0: 13 società, 81 transazioni SEC, zero capitalizzazioni.
Punteggi: 6, 6, 8,4, 11,4, 12, 15, 15, 16,5, 23,5, 24,5, 29, 29, 46,3.
Media 18,66; massimo 46,3. Non è un campione selezionato con criteri finanziari verificati.
Copertura: 2.858 documenti ancora in coda nell’ultimo risultato disponibile; nessun backtest.

| Problema osservato | Diagnosi | Correzione |
|---|---|---|
| Combinazione 70/30 | Aritmetica corretta, ma opportunità già limitata a 49 prima della media e risultato nuovamente limitato | Punti evidenziati prima della media, limiti applicati al risultato una sola volta |
| Massimo strutturalmente basso | Valutazione non integrata; nessun percorso interno per evidenza completa favorevole | Contratto interno tipizzato per futuro adapter riconciliato; fixture completa = 94, non dato reale né approvazione di una fonte |
| EPS non monotoni | Mancata crescita trattata come perdita, anche con EPS positivi | Stato di crescita separato dal segno dell’ultimo EPS; limite per problemi effettivi solo con perdite/cassa negativa |
| Cassa su tre esercizi | Un anno passato negativo poteva essere letto come cassa corrente negativa | Separati storico triennale e segno dell’ultimo esercizio |
| Dati mancanti | Score parziale numerico scambiabile per cattivi fondamentali | `non_verificabile` senza voto pubblicato; `provvisorio` con fondamentali riconciliati ma valutazione assente |
| Ricavi parziali | Primo tag contrattuale disponibile non sempre rappresenta ricavi totali | Confronto tra serie candidate, tag/unità/date conservati, conflitti non promossi a ricavi totali |
| Snapshot precedenti | Serie salvate senza tag e date di fine periodo non dimostrano il perimetro | Valori conservati, indicatore ricavi sospeso fino a riconciliazione; riesame SEC prioritario nei prossimi scan |

## Controllo documentale concreto

RENT: la serie precedente termina con 43,8M USD. Il [documento SEC del 14 aprile 2026](https://www.sec.gov/Archives/edgar/data/1468327/000146832726000018/fy2025earningsrelease.htm)
riporta questa cifra come **altri ricavi**, mentre i ricavi totali sono 329,8M USD per
l’esercizio terminato il 31 gennaio 2026. Non sostituiamo automaticamente una serie
pluriennale con dati parziali trovati in ricerca: la crescita viene sospesa e la fonte
XBRL dovrà essere riconciliata. CHCO è un’attività bancaria: un tag contrattuale può
escludere gli interessi; il [bilancio dell’emittente](https://www.bankatcity.com/wp-content/uploads/2026/04/2025-Annual-Report.pdf)
mostra separatamente reddito da interessi e ricavi non da interessi.

La correzione non somma automaticamente tag potenzialmente sovrapposti. Fonte primaria
finanziaria resta [SEC companyfacts](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).
Nuova estrazione: tag, unità, date, cutoff point-in-time, controlli di durata e freschezza
(max 550 giorni dalla fine dell’esercizio, scelta conservativa a regole), segni EPS/cassa.
20-F/40-F annuali USD supportati; altre valute/tassonomie non vengono convertite inventando dati.

## Esito sui dati effettivamente disponibili

- 13 società osservate nella finestra di sette giorni.
- 0 capitalizzazioni verificate; 0 valutazioni favorevoli riconciliate.
- 13 snapshot finanziari precedenti da riconciliare: nessun rating attendibile pubblicato.
- 0 società selezionate; 5 sopra il minimo assoluto e in attesa di verifica.
- 8 sotto il minimo assoluto; le preferenze di ricerca non alterano questi conteggi.

I conteggi si riferiscono al campione salvato, non all’intero mercato USA. Se nuove scansioni
aggiungono evidenze, l’app li ricalcola. Storico/prezzi/eventi societari non sono improvvisati.
