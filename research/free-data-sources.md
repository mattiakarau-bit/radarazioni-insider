# Fonti gratuite: valutazione al 24 ottobre 2026

Nessuna nuova API attivata, chiave creata o abbonamento sottoscritto.
Le metriche mancanti restano non verificate e non aumentano il punteggio opportunità.

| Fonte ufficiale | Uso possibile | Limiti e decisione |
|---|---|---|
| [SEC EDGAR API](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) e [accesso dati](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) | Bilanci XBRL, depositi, utili, cassa e azioni dichiarate | Fonte primaria già integrata; non fornisce una serie giornaliera di prezzi di borsa. Per multipli storici servono prezzi, azioni coerenti e dati disponibili alla data. Indici giornalieri notturni, non tempo reale. Client limitato a circa 2 richieste/sec. |
| [Stooq](https://stooq.com/db/h/) e [istruzioni](https://stooq.com/db/i/) | Candidato per serie storiche giornaliere gratuite e calcolo ribasso | Il sito offre download storici. Prima di integrazione/pubblicazione verificare diritti di redistribuzione, rettifiche split/dividendi, copertura delistati e stabilità identificativi. Non è ancora una fonte validata nell’app. |
| [Alpha Vantage documentazione](https://www.alphavantage.co/documentation/) e [supporto](https://www.alphavantage.co/support/) | Candidato per un piccolo campione di controllo | Piano gratuito standard: 25 richieste/giorno. Storico completo daily e funzioni adjusted possono richiedere premium: non abilitarle. Non sufficiente come base gratuita per l’intero universo SEC; verificare licenza prima di mostrare dati. Nessuna chiave richiesta in questo aggiornamento. |
| [Nasdaq Data Link WIKI](https://data.nasdaq.com/databases/WIKIP) | Solo ricerca storica limitata | Feed non più supportato dall’11 aprile 2018; il fornitore ne sconsiglia l’uso per investimenti/analisi. Escluso per dati correnti. |

## Contratto dati prima di un’integrazione

Ogni osservazione deve conservare fonte/URL, timestamp di acquisizione, data di mercato,
valuta, tipo di prezzo (close/high/adjusted), metodo di rettifica e identificativo stabile
CIK + titolo/classe. Non unire ticker riciclati. Non trattare errori HTTP, risposte di quota
o sedute mancanti come prezzi zero. Non usare il prezzo Form 4 come prezzo corrente.

Ribasso a 52 settimane: `close_alla_data / massimo_close_sedute_ultimi_365_giorni - 1`;
è un ribasso da massimi di chiusura, non dai massimi intraday. Serie omogenea e rettificata
per split, con copertura documentata; con storia insufficiente restituire `null`, non 0.
Per rendimenti ML usare serie total-return adeguate, includendo dividendi e delisting.

Valutazione: P/E solo con EPS trailing positivo e coerente con rettifiche/classi; P/FCF
solo con cassa operativa meno capex validi e positivi; EV richiede debito, cassa, azioni e
prezzo temporalmente coerenti. Un multiplo basso non equivale a fair value verificato.
Memorizzare esplicitamente dati assenti, obsoleti e rettificati; evitare look-ahead.

Decisione: mantenere SEC come primaria per i bilanci; validare Stooq su un campione
prima di collegare prezzi al punteggio. Non esiste ancora una fonte integrata che renda
la valutazione verificata: i limiti 49/39 e l’assenza di notifiche restano applicati.

## Verifica diritti per release 0.5.0

[Termini Stooq](https://stooq.com/terms.html): i risultati della ricerca ufficiale
indicano che la redistribuzione richiede consenso; la [pagina download](https://stooq.com/db/h/)
indica uso personale. La pagina termini completa richiede verifica JavaScript al lettore
automatico: non si assume alcuna autorizzazione per pubblicare serie o derivati nel sito.
Stooq non viene integrato e non viene scaricato alcun dataset.

[Termini Alpha Vantage](https://www.alphavantage.co/terms_of_service/), letti il 24/10/2026:
licenza ordinaria personale/non commerciale; accordo scritto per altri usi. Il sito pubblico
non riceve prezzi o capitalizzazioni da questo provider. Nessuna chiave o licenza attivata.

SEC fornisce fatti finanziari, non un feed giornaliero di prezzi. Il public float riportato
nei bilanci non viene usato come sostituto della capitalizzazione corrente. Yahoo Finance
o wrapper non ufficiali non vengono considerati un’autorizzazione alla redistribuzione.

Esito concreto: nessun provider gratuito di prezzi/capitalizzazioni è stato validato per la
redistribuzione in RadarAzioni. Filtri e storico espongono `non_verificabile`, non risultati
calcolati da prezzi ipotetici. Comparatore matematico ±5% testato, gate reale chiuso fino
alla verifica di fonte/licenza, split, classe azionaria, eventi e fondamentali aggiornati.

## Riesame 0.6.0

Verificate nuovamente le condizioni pubbliche di Stooq e Alpha Vantage: nessuna nuova
fonte autorizzata alla redistribuzione integrata. Anche [FMP](https://site.financialmodelingprep.com/pricing-plans)
richiede uno specifico accordo per visualizzazione/redistribuzione: un endpoint gratuito
non basta per pubblicarne i dati. Nessuna registrazione, abbonamento o chiave attivata.
SEC resta attiva per dati finanziari; public float e prezzi Form 4 non diventano
capitalizzazione corrente. Il campo capitalizzazione resta assente finché non c’è una
fonte utilizzabile e riconciliata. Vedi diagnosi dei rating per problemi dei tag ricavi.
