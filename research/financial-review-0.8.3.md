# Analisi finanziaria 0.8.3 — risultati effettivi

## Il prerequisito di mercato non è ancora soddisfatto

Lo snapshot pubblicato il 25 ottobre 2026 contiene **881 candidate** per acquisti
insider, ma **zero** società che superano insieme acquisti, prezzi e capitalizzazioni
verificati. Il precedente aggiornamento documentava questo blocco, non lo aveva
risolto. Non sono state trattate le 881 candidate come investimenti confermati.

Questo aggiornamento analizza offline le **60 cache finanziarie SEC esistenti**,
senza nuove richieste HTTP e senza riscaricare archivi insider. Le altre **821**
candidate non hanno ancora una cache finanziaria: non vengono classificate come
società con fondamentali negativi. Nessuno dei 60 controlli preliminari equivale
a una valutazione d'investimento completa.

## Riscontri nelle cache reali

| Dato presente, datato e utilizzabile come osservazione | Candidate |
| --- | ---: |
| Ricavi annuali con tag/periodo/unità | 33 |
| EPS annuali con tag/periodo/unità | 34 |
| Flusso operativo annuale | 40 |
| Ultimo utile periodico, senza annualizzazione | 53 |
| Ultimo flusso operativo periodico | 53 |
| Liquidità osservata e datata | 50 |
| Singola osservazione del debito, **non totale riconciliato** | 27 |
| Utile annuale nella nuova serie richiesta | 0 |
| Capex monetario annuale nella cache | 0 |
| Free cash flow verificabile | 0 |
| P/E, P/FCF o confronto prezzi rettificati verificabili | 0 |
| Superamento di tutti i criteri / società in homepage | **0 / 0** |

I conteggi riguardano disponibilità di osservazioni, non certificazioni di solidità.
Un ricavo con periodo valido può ancora avere perimetro parziale: l'indicatore
`revenue_scope_verified` resta visibile e i controlli esistenti non vengono aggirati.
Una liquidità trimestrale conserva la sua data economica: non viene rietichettata
come importo di oggi. 40 cache hanno almeno un fattore negativo osservato negli
utili/EPS/cassa annuali o periodici; le mancanze non entrano in questo conteggio.

Il [rapporto generato](../docs/data/companies/financial/report.json) viene ricalcolato
con la pipeline e distingue candidate insider, cache esaminate, società realmente
prequalificate sui dati di mercato e schede della homepage.

## Calcoli implementati

- Ricavi, EPS e flussi operativi annuali mantengono le serie già estratte e le loro
  date pubbliche. Aggiunta l'estrazione di utili annuali e capex dal medesimo
  `companyfacts` che il refresh ordinario riceverà: **nessuna richiesta supplementare**.
  Le cache attuali prive di questi campi rimangono incomplete; non sono invalidate
  o riscaricate per riempirli. Le nuove serie saranno disponibili soltanto dopo un
  aggiornamento ordinario, se i concetti sono presenti nei bilanci.
- FCF = cassa operativa meno acquisti monetari di immobili, impianti e attrezzature.
  Richiede inizio/fine periodo e unità identici, valori finiti e capex non negativo.
  Non si usano cassa operativa da sola, `abs(capex)`, trimestri annualizzati,
  aggiunte non monetarie o serie di anni diversi. Non viene presentato come FCFE.
- P/E = capitalizzazione riconciliata / utili annuali positivi attribuibili agli
  azionisti ordinari. `NetIncomeLoss` da solo non certifica tale perimetro; nessun
  join non verificato fra prezzo di una classe ed EPS di un'altra.
- P/FCF = capitalizzazione riconciliata / FCF annuale documentato positivo.
  Multipli riferiti all'ultimo esercizio disponibile, **non TTM**. I periodi
  degli utili/FCF e la data della cap restano distinti. Denominatori negativi,
  nulli, mancanti o risultati non finiti non producono multipli favorevoli.
- Il comparatore accetta soltanto il contratto interno di mercato già verificato
  e un prezzo insider sulla stessa base split documentata. In produzione mancano
  tali evidenze: confronto assente, nessun prezzo Form 4 spacciato per corrente.
- Liquidità, utile/cassa periodici e debito osservato conservano tag, unità,
  periodo e deposito. Nessuna somma di componenti del debito sovrapposte o assenti;
  `debt_scope_verified` non viene promosso automaticamente. Mancano ancora
  riconciliazione del debito/lease, perimetri settoriali e revisione eventi successivi.

I calcolatori di multipli/comparazione sono testati con fixture esplicitamente
sintetiche e contratti interni. **Non c'è un adapter di mercato collegato** e non
sono emessi risultati reali fittizi. Un multiplo calcolabile non diventa da solo
una valutazione favorevole: nessuna nuova soglia P/E/P/FCF arbitraria è introdotta.

## Pubblicazione e interfaccia

Versione PWA **0.8.3**, stesso layout. Nei Dettagli già esistenti si aggiungono
utile, capex, FCF, multipli, osservazioni periodiche e mancanze specifiche. Le
società restano consultabili in **In verifica**; la homepage rimane correttamente
vuota. Nessuna classifica artificiale: rimangono le regole 70% opportunità / 30%
insider, le verifiche attuali e una scheda per CIK, senza cambiare scoring o prezzi.

La pubblicazione su push riutilizza ora i dati locali, evitando chiamate SEC per
una modifica di codice. Le scansioni programmate/manuali conservano il normale
aggiornamento incrementale di nuovi depositi e cache scadute. Nessuna modifica al
workflow di importazione storica, ai Secrets, ai Preferiti o al machine learning.

Verifiche: regressioni Python/JavaScript, campione reale GPI senza HTTP, rifiuto
di periodi diversi/fatti futuri/dati mancanti, fixture di FCF e multipli, verifiche
del semestre sugli archivi locali e browser WebKit/Chromium mobile. GitHub Pages
pubblica soltanto dopo il superamento della qualità. Nessun BUY, trading automatico,
notifica d'investimento o servizio a pagamento.
