# Prezzi e capitalizzazioni: verifica effettiva del 25 ottobre 2026

**Esito: integrazione di mercato bloccata, non simulata.** Non è stata individuata,
tra le fonti esaminate, una soluzione che soddisfi insieme gratuità permanente,
copertura 2026, prezzi datati per classe azionaria e permesso di distribuirli nei
JSON pubblici di RadarAzioni. Questo non dimostra che una tale fonte non possa
esistere: documenta l'esito delle verifiche, senza trasformare l'accessibilità
tecnica di un endpoint in una licenza.

Motore semestrale, periodo, scoring, homepage, Preferiti e machine learning non
sono modificati. Non sono stati riscaricati archivi trimestrali insider SEC.
Nessun abbonamento, account, chiave o credenziale è stato aggiunto o modificato.

## Risultati sullo snapshot reale

Input del 25 ottobre 2026: `docs/data/semester_report.json`,
`pending_index.json` e i dettagli delle **878 candidate**, una per CIK.
L'audit legge i risultati già calcolati, non ricostruisce lo storico.

| Controllo | Società |
| --- | ---: |
| Candidate con almeno 100.000 USD in una finestra di sette giorni | 878 |
| Con un valore di capitalizzazione storica presente nei dettagli | 0 |
| Con un valore di capitalizzazione corrente presente | 0 |
| Superamento verificato di cap storica + soglia settimanale proporzionale | 0 |
| Con capitalizzazione corrente verificata | 0 |
| Con entrambi i controlli di capitalizzazione verificati | 0 |
| Senza entrambe le capitalizzazioni necessarie | 878 |
| Nuove capitalizzazioni prodotte da questa attività | 0 |

Lo zero indica **assenza di verifica**, non che le società siano tutte sotto
500 milioni USD. I conteggi di disponibilità sono distinti dai conteggi di
superamento dei filtri. Il report pubblico
[`market_availability_report.json`](../docs/data/market_availability_report.json)
conserva data dello snapshot e hash SHA256 degli input e dei dettagli.
È un rapporto datato, non un feed aggiornato automaticamente a ogni scansione.

## Verifica delle fonti e dei diritti

Sono stati consultati documenti del fornitore, non soltanto liste di API gratuite.
La distribuzione prevista comprende visualizzazione pubblica, cache persistente,
risultati derivati e JSON scaricabili da GitHub Pages: un permesso per il solo
display potrebbe comunque non coprire tutti questi usi.

| Fonte / documenti ufficiali | Esito per RadarAzioni pubblica e gratuita |
| --- | --- |
| [SEC: riuso](https://www.sec.gov/about/webmaster-frequently-asked-questions), [API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) | Dati dei depositi riutilizzabili; azioni e fondamentali utilizzabili con provenienza. Le API consultate non sono un listino azionario EOD o corrente. |
| [Alpha Vantage, §2](https://www.alphavantage.co/terms_of_service/) | Licenza ordinaria personale/non commerciale; nessun accordo per questa distribuzione pubblica ottenuto. La disponibilità di richieste gratuite non risolve il diritto di pubblicazione. |
| [FMP, §§2.2.1–2.2.2](https://site.financialmodelingprep.com/terms-of-service) | Display multiutente, anche gratuito, richiede accordo specifico. Nessun accordo ottenuto. |
| [Tiingo, tabella EOD](https://www.tiingo.com/products/end-of-day-stock-price-data) | Free limitato all'uso interno; display/redistribuzione è un'offerta distinta a pagamento, esclusa. |
| [SimFin, §§1–3](https://www.simfin.com/en/commercial-license/) | FREE/BASIC per ricerca personale senza condivisione; la sezione sulla redistribuzione appartiene a una licenza diversa. Non abilita il piano gratuito. |
| [Twelve Data, prezzi Business](https://twelvedata.com/pricing-business), [§2.4](https://twelvedata.com/terms) | Basic gratuito per uso interno senza display. Display esterno e redistribuzione richiedono condizioni differenti; nessuna licenza gratuita compatibile verificata. |
| [Stooq, condizioni](https://stooq.com/terms.html) | In questo controllo pagina bloccata da verifica JavaScript. Rimane la precedente esclusione per redistribuzione senza consenso; non si dichiara di aver ricertificato oggi il testo completo. Nessun consenso ottenuto. |
| [Finazon US Equities Basic](https://finazon.io/dataset/us_stocks_essential) | Diritti di redistribuzione dichiarati, ma accesso a pagamento. “Licence-free” non significa servizio gratuito. Escluso anche il solo trial temporaneo come soluzione permanente. |
| [HF Data Library, §§1–3](https://hfdatalibrary.com/pages/terms) | Ricerca accademica/educativa; non utilizzabile per questo screening di opportunità e valutazioni d'investimento. |
| [yfinance, avvertenze del maintainer](https://github.com/ranaroussi/yfinance), [Yahoo terms](https://legal.yahoo.com/us/en/yahoo/terms/otos/index.html) | Licenza del software distinta dai diritti dei dati. Nessuna autorizzazione alla redistribuzione stabilita. L'endpoint delle condizioni Yahoo ha restituito 999 durante il controllo; non si presume un permesso. Nessun adapter attivato. |
| [Financial Datasets: condizioni](https://www.financial-datasets.ai/terms-of-use), [prezzi](https://www.financial-datasets.ai/pricing) | Licenze personali senza redistribuzione; offerte con display a pagamento e ulteriori limiti sui dati scaricabili. Non compatibile a costo zero. |
| [Kaggle, esempio CC0](https://www.kaggle.com/borismarjanovic/price-volume-data-for-all-us-stocks-etfs), [copia community Yahoo](https://huggingface.co/datasets/defeatbeta/yahoo-finance-data) | Il primo termina nel 2017; la seconda non stabilisce diritti upstream per la pubblicazione di dati Yahoo/Nasdaq. Nessuna copertura 2026 legalmente verificata per questo uso. |

Non sono stati scaricati o pubblicati prezzi da fonti non approvate. Non sono
state inviate richieste di consenso a terzi.

## Campione reale SEC: perché prezzo × azioni non è ancora una cap verificata

Sei richieste piccole, con intervallo fra richieste: tre endpoint ufficiali
`companyconcept/dei/EntityCommonStockSharesOutstanding` e tre `submissions`.
Snapshot originali del concetto e proiezioni delle identità sono conservati in
`research/market-sample/` con URL, data e hash del corpo ricevuto. Nessun archivio
insider scaricato. I tre CIK sono tutti presenti nelle 878 candidate.

| Società | Riscontro reale |
| --- | --- |
| Abbott, CIK 1800, ABT | Il concetto API restituisce `units.shares` vuoto. Ciò non significa zero azioni: la [copertina del 10-Q](https://www.sec.gov/Archives/edgar/data/1800/000162828026050134/abt-20260630.htm) dichiara 1.730.383.296 azioni al 30 giugno 2026. Serve estrazione inline XBRL con contesti, non un riempimento a zero. |
| Group 1 Automotive, CIK 1031203, GPI | 11.922.225 azioni al **24 luglio**, pubbliche il **30 luglio** nel [10-Q](https://www.sec.gov/Archives/edgar/data/1031203/000103120326000123/gpi-20260630.htm). È una quantità di 93 giorni precedente all'audit, non un numero di azioni certificato al 25 ottobre. È esclusa dalle caratteristiche di settimane anteriori al deposito. |
| Berkshire Hathaway, CIK 1067983, BRK.B | Submissions elenca BRK-A e BRK-B. Il concetto non dimensionale offre come ultima osservazione 941.481 azioni del **29 aprile 2011**: non è una quantità corrente, né prova del totale delle due classi. Non viene moltiplicata per il prezzo BRK.B. |

Due dei tre endpoint contengono almeno un'osservazione numerica; questo **non**
equivale a due capitalizzazioni disponibili. Nessun prezzo storico/corrente,
nessuna base split e nessun perimetro completo delle classi sono stati certificati
dal campione. Risultato: **0/3 capitalizzazioni storiche, 0/3 correnti**.

Le API SEC aggregano concetti standard riferiti all'intera entità: non garantiscono
di includere tutte le informazioni dimensionali o personalizzate delle singole
classi. Il test reale mostra perché un join meccanico per ticker sarebbe scorretto.

## Condizioni tecniche prima di una futura integrazione

1. Fonte EOD con permesso esplicito gratuito per display, cache, dati derivati e
   JSON pubblici. Una chiusura va etichettata con data di negoziazione e ritardo,
   senza chiamarla tempo reale. Nessuna disponibilità è stata promessa da terzi.
2. Identità CIK + classe stabile, ticker e listing datati. Gestire ADR/ADS e relativo
   rapporto, cambi ticker, classi non quotate e azioni proprie. Non moltiplicare le
   azioni di tutte le classi per il prezzo di una classe senza un perimetro verificato.
3. Conteggi di azioni in circolazione datati, distinti da azioni emesse, treasury,
   medie ponderate per EPS e flottante pubblico. Il public float esclude affiliati
   e non sostituisce la capitalizzazione totale.
4. Separare data economica delle azioni/prezzo dalla data in cui l'informazione è
   divenuta pubblica. Un conteggio trimestrale riportato in avanti produce una
   **stima datata**, non una capitalizzazione corrente verificata. Gli intervalli
   senza riconciliazione di emissioni/riacquisti restano non verificabili.
5. Prezzo e quantità sulla medesima base split: prezzo raw con quantità della stessa
   data oppure entrambi rettificati coerentemente. Prezzi total-return rettificati
   per dividendi non moltiplicati per azioni raw. Valuta USD documentata; cambi e
   unità non dedotti dal solo simbolo. Sommare valori per classe solo con copertura
   completa e assenza di doppio conteggio.
6. Cap storica della settimana e cap corrente restano osservazioni separate.
   Mantenere i filtri esistenti: 500 milioni USD, 100.000 USD settimanali e importo
   richiesto `max(100000, min(2000000, cap_storica * 0.00002))`.

## Cosa è pubblicato e come riprodurlo

Pubblicati esclusivamente questo rapporto, registro fonti aggiornato, snapshot SEC
del campione, audit offline e test. **Nessun adapter prezzi/cap di produzione** e
nessun valore inventato, neppure per sbloccare un filtro. Scoring e filtri non sono
stati modificati. La versione PWA resta 0.8.2: nessun cambiamento dell'interfaccia
o delle chiavi dei Preferiti.

```sh
python -m research.audit_market_data
python -m unittest discover -s tests -p test_market_availability.py -v
```

Refresh incrementale solo del campione, quando necessario:

```sh
# Riutilizza SEC_USER_AGENT già configurato; non cambiare Secrets/credenziali.
python -m research.audit_market_data --refresh-sec-sample
```

Cache su file, TTL sette giorni, massimo sei piccoli endpoint per aggiornamento,
scrittura atomica; un errore mantiene lo snapshot precedente. Nessun refresh è
collegato ai workflow periodici o esteso alle 878 candidate finché manca una fonte
prezzi approvata. I test verificano dati GPI autentici, assenza di look-ahead,
Abbott senza osservazioni, Berkshire obsoleta e classi non certificate, conflitti,
unità sbagliate e assenza di capitalizzazioni simulate.

## Alternative concrete, senza attivare servizi

- Richiedere un'autorizzazione **senza costi** a un fornitore, specificando GitHub
  Pages, cache, punteggi derivati e JSON pubblici. L'autorizzazione non è stata
  ottenuta e non è garantito che venga concessa.
- Trovare un dataset aperto aggiornato al 2026 con provenienza e diritti upstream
  verificabili; testare campione, split, continuità classi e copertura prima dell'uso.
- Un funzionamento strettamente privato con dati personali potrebbe avere licenze
  diverse, ma richiederebbe un cambio di architettura e di obiettivo. Non risolve
  l'app pubblica attuale e non è stato implementato.

Un'offerta a pagamento non è una soluzione ammessa dai vincoli. Finché manca una
fonte compatibile, le 878 candidate rimangono in verifica per le capitalizzazioni.
