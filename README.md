# RadarAzioni – Insider Intelligence · 0.6.0

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
