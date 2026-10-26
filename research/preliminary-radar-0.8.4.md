# Radar 0.8.4: due livelli, dati SEC progressivi

Il Radar mostra opportunità completamente verificate e candidate insider preliminari in sezioni distinte. Il periodo resta sei mesi; sette giorni è la sola finestra di aggregazione. Una scheda per CIK, migliore settimana per importo; tutte le altre finestre nei Dettagli. I criteri di selezione verificata e il Radar Score non cambiano.

Le candidate sono ordinate per importo dichiarato nella migliore settimana, poi forza insider e quantità di osservazioni annuali disponibili. La disponibilità non certifica solidità. Importi almeno 1 miliardo USD o prezzo medio almeno 10.000 USD sono segnalati e messi in fondo per riconciliazione delle unità/note: è una regola prudenziale di controllo dati, non una stima corretta né una nuova soglia d'investimento. Valori SEC originali e documenti rimangono conservati. Il conteggio di insider indipendenti rimane non verificato.

Il primo JSON contiene 20 candidate; altre schede si caricano su richiesta. I dettagli restano separati per società. Preferiti e chiavi localStorage conservati. Le candidate hanno Radar Score nullo; l'eventuale forza insider è preliminare, non una probabilità o BUY. Quando il motore riceve tutte le evidenze richieste, una società selezionata esce automaticamente dal gruppo preliminare e compare una sola volta nel gruppo verificato.

## Acquisizione

Scansione incrementale Form 4 esistente e aggiornamento massimo 25 società per esecuzione, incluse le pubblicazioni. Archivi trimestrali mai riscaricati. Cache persistenti di bilancio, sette giorni di riuso e backoff anche per errori; vecchie osservazioni conservate se il recupero fallisce. Priorità alle società quotate nell'indice esistente, senza tentativi precedenti, poi importi maggiori. Un companyfacts e, se riuscito, un indice submissions per società: massimo 50 richieste logiche, oltre la scansione Form 4 preesistente, con throttling/retry SEC esistenti.

L'estrazione aggiunge osservazioni datate sulle azioni in circolazione e fino a 40 indici dei depositi successivi alla settimana mostrata. Le azioni entity-wide non certificano classi, ADS, split o consistenza corrente; non vengono moltiplicate per un prezzo ipotetico. Gli indici 8-K/10-Q/10-K/6-K/20-F sono documenti da esaminare, non una revisione sostanziale degli eventi. Ricavi, EPS, utili, CFO, capex e FCF restano datati e verificati secondo i contratti esistenti. Assenza non equivale a zero.

## Fonti rivalutate il 25 ottobre 2026

- [SEC API ufficiali](https://www.sec.gov/search-filings/edgar-application-programming-interfaces): companyfacts e submissions senza API key. Standard entity-wide, non una serie di quotazioni di borsa; dimensioni di classe non garantite.
- [SEC riutilizzo](https://www.sec.gov/about/webmaster-frequently-asked-questions): contenuti governativi e filing pubblici liberamente accessibili e riutilizzabili. Identità SEC già configurata e limiti di accesso rispettati.
- [Twelve Data](https://twelvedata.com/terms): display esterno/redistribuzione solo con add-on o accordo scritto; nessuna concessione gratuita per questo progetto verificata.
- [Tiingo](https://app.tiingo.com/tos/): API per consumo interno; redistribuzione richiede permesso e costi aggiuntivi.
- [SimFin](https://www.simfin.com/en/commercial-license/): FREE/BASIC per ricerca propria, non condivisibile con terzi.
- [Market Data](https://www.marketdata.app/docs/api/cors/): CORS non autorizza app pubbliche; piani self-service personali, redistribuzione non consentita.

Il registro source_policy.json conserva anche le altre fonti già valutate. Nessun nuovo provider prezzi approvato: non si afferma che nessuna fonte gratuita possa esistere. Serve un dataset aggiornato con provenienza e licenza esplicita compatibile con JSON pubblici, oppure concessione gratuita scritta. Nessuna richiesta a terzi, account, credenziale o abbonamento attivato. I prezzi dei Form 4 restano corrispettivi dichiarati, non quotazioni correnti.

## Conteggi verificabili

I conteggi aggiornati sono in docs/data/radar.json e docs/data/companies/financial/report.json, generati dalla stessa elaborazione pubblicata. Prima della scansione di rilascio: 1.656 società nel semestre, 881 candidate, 60 cache finanziarie, 0 società completamente verificate. Questi non sono conteggi finali della nuova scansione. Il report distingue osservazioni annuali disponibili, criteri verificati, candidate visibili iniziali e totale consultabile.

Test automatici: regressioni Python/JavaScript, accettazione su archivi SEC autentici, WebKit e Chromium a 390×844, 768×1024 e 320×568. Verificati distinzione dei due livelli, paginazione, richieste lazy e Preferiti dopo ricaricamento. La verifica del sito pubblicato avviene dopo il deploy; non viene dedotta solo dal codice.
