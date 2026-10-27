# Dati personali Tiingo — 0.10.0

La modalità è implementata per esecuzione locale con il token del singolo utente. Non alimenta GitHub Pages. Non è stata attivata: nessun token ricevuto, account creato o abbonamento sottoscritto. Una risposta HTTP 403 alla richiesta metadata senza token è registrata in quarterly-sample/access-check.json; non è un collaudo autenticato dei prezzi.

Il [Developer Program ufficiale](https://www.tiingo.com/documentation/appendix/developers) consente software in cui ciascun utente fornisce il proprio token, senza redistribuire dati altrui. Attribuzione Tiingo obbligatoria. Il [piano Starter](https://www.tiingo.com/about/pricing) dichiara 0 USD, 500 simboli/mese, 50 richieste/ora, 1.000/giorno, 1 GB/mese. Il piano non copre tutte le circa 905 candidate contemporaneamente. I fondamentali API Tiingo sono un add-on, non utilizzato. I limiti effettivi del proprio account prevalgono; altre applicazioni possono già consumarne la quota. Nessun upgrade automatico.

## Uso locale

1. L'utente deve avere un proprio account Starter e accettarne personalmente le condizioni sul sito ufficiale. Non inviare token o password in chat e non inserirli in GitHub Secrets per questa modalità.
2. Eseguire `python -m scanner.personal_market --symbol GPI --start 2026-04-27`. Il comando chiede il token con input nascosto; in alternativa legge la variabile locale `TIINGO_API_TOKEN`. La variabile non viene creata o cambiata dal programma.
3. Metadata, prezzi EOD grezzi, split e dividendi sono conservati solo nella cartella ignorata `.private-market`, con permessi restrittivi. Non c'è endpoint pubblico, export verso Pages, invio di valori nei log o telemetria. Non condividere neppure risultati derivati se la licenza personale lo vieta.
4. Il programma rifiuta CI/GitHub Actions, percorsi pubblici e symlink della cache. Usa esclusivamente api.tiingo.com, con token nell'header Authorization; nessun token nell'URL, nessun inoltro su redirect. Errori 401/403/429 fermano il recupero. Le cache precedenti sono conservate e gli aggiornamenti riacquisiscono solo gli ultimi sette giorni, per eventuali correzioni.

La modalità è Python locale: **non è ancora una modalità utilizzabile direttamente sull'iPad**. Non è una soluzione già attiva per i prezzi dell'app pubblica. Per un uso sull'iPad servirà un client personale con le medesime garanzie, da collaudare con un account reale e con CORS/limiti effettivi prima di distribuirlo.

## Identità, capitalizzazione e confronto

`python -m scanner.personal_analysis --cik 1031203 --tolerance 15` elabora i dati personali contro i Dettagli SEC locali. Produce esclusivamente `.private-market/analysis/1031203.json`. Il parametro ±15% è modificabile. Serve una revisione di classe/valuta e degli eventi nella cartella privata `reviews/1031203.json` con:

- `cik`, `all_equity_classes_review_reference` e `security_titles` (titoli Form 4 esatti → ID stabili di classe);
- `securities`: per ID, `symbol` Tiingo esatto (nessuna trasformazione BRK.B/BRK-A indovinata), `exchange`, `currency`, `valid_from`, `valid_to`, `identity_source_url` SEC, `class_review_reference`, `corporate_actions_review_reference`;
- `outstanding_shares`: osservazioni datate per classe con `security_id`, `value`, `end`, `filed`, `unit: shares`, tag di azioni effettivamente in circolazione, `accession` e `source_url` del filing SEC.

Queste revisioni non vengono inventate dal software. Se mancano, prezzi o calcoli restano non verificati. Le azioni medie per EPS, le azioni emesse e il flottante non sono sostituti automatici delle azioni in circolazione. La capitalizzazione richiede tutte le classi, quote grezze USD e numero di azioni alla stessa data. Non si moltiplicano azioni di luglio per prezzi di ottobre senza riconciliazione. Le osservazioni storiche pubblicate dopo la settimana restano esplicitamente datate: non possono diventare feature ML prima della data di pubblicazione.

Il confronto usa ogni operazione della settimana, rettifica la quantità con gli split successivi e ricalcola il prezzo ponderato sulla medesima base del prezzo corrente. `adjClose` Tiingo include anche dividendi e **non** viene usato per rettificare il costo degli insider. Frazionamenti, ADS, spin-off e distribuzioni richiedono revisione degli eventi; non basta un ticker uguale. Valori duplicati, classi ambigue, dati obsoleti o prezzi futuri vengono rifiutati. Un confronto vicino al prezzo insider non certifica solidità, valutazione conveniente o BUY.

## Dati SEC reali già verificati

Tre risposte Companyfacts ufficiali sono state recuperate il 27 ottobre 2026, senza archivi insider: GPI, RSG e ABT (controllo). Le proiezioni riproducibili e gli hash delle risposte complete sono in quarterly-sample. I test verificano che GPI Q2 2026 abbia CFO 62,6 milioni, capex 42,8 milioni e FCF 19,8 milioni USD. La data pubblica è 30 luglio 2026; questi valori non sono disponibili per un segnale precedente. ABT nella risposta ottenuta termina al Q1 2026: è marcato obsoleto per la data di analisi, senza immaginare trimestri successivi.

L'estrazione trimestrale è inserita nella coda SEC esistente (massimo 50 società/esecuzione), con avanzamento persistente e cache. Niente ricostruzione degli archivi 2021–2026. Le schede conservano la grafica corrente e ricevono osservazioni nei Dettagli. Banche, assicurazioni e REIT non ricevono automaticamente i parametri industriali. Debito totale/lease e cambiamenti societari richiedono ancora riconciliazione sostanziale; la presenza di dati non apre la classifica verificata.

## Stato del lavoro

Fonte pubblica dei prezzi: nessuna approvata. Tiingo personale: adapter implementato, autenticazione e copertura su dati veri ancora da collaudare con token dell'utente. Financial Datasets, [condizioni aggiornate il 26 ottobre](https://www.financialdatasets.ai/terms-of-use): uso personale esclusivamente proprio; redistribuzione solo sui piani che la includono, vietati export raw/bulk. Non è un feed gratuito per i JSON pubblici di RadarAzioni.

Il report generato `docs/data/companies/financial/market-gates.json` distingue prezzi verificati, capitalizzazioni, vicinanza ±15%, controlli finanziari completi e classifica finale. Il ML non viene addestrato: zero target verificati a 30/90/180 giorni. L'ipotesi +20 punti percentuali oltre il benchmark a 180 giorni è registrata come non testata; non è stata sostituita con una probabilità o con risultati sintetici. Lo scoring 70/30 e i limiti conservativi rimangono attivi.
