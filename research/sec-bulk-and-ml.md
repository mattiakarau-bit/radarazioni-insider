# Archivi SEC e ricerca ML · 0.7.0

## Dati ufficiali e copertura

Fonte: [SEC Insider Transactions Data Sets](https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets)
e [documentazione](https://www.sec.gov/files/insider_transactions_readme.pdf).
Al 25 ottobre 2026 il catalogo pubblica 2006 Q1–2026 Q3. La fase corrente richiede
2021 Q1–2026 Q4: 23 archivi pubblicati e un trimestre non ancora disponibile.
I dataset sono as-filed, includono Form 3/4/5 e rettifiche; non sostituiscono i documenti.
Depositi oltre il cutoff serale di fine trimestre possono comparire nell’archivio successivo.
Le date effettive sono nel report, non vengono dedotte come copertura di tutto il mercato.

`scanner.bulk` legge TSV UTF-8 SUBMISSION, REPORTINGOWNER, NONDERIV_TRANS e FOOTNOTES.
Conserva i campi rilevanti in shard JSONL gzip deterministici; non conserva indirizzi personali.
Non scarica i documenti originali. Manifest con URL, SHA256 ZIP/shard, timestamp e conteggi.
CRC, schema, limiti di espansione, file temporanei e sostituzione atomica per trimestre.
Ogni trimestre completato viene salvato su GitHub: un’interruzione non perde quelli precedenti.
Gli shard mancanti/corrotti sono rimessi in coda; i trimestri completi non vengono riscaricati.
Gli archivi SEC possono essere revisionati dal fornitore: il manifest identifica la revisione
scaricata; non si afferma una sincronizzazione continua delle revisioni dei file già importati.

Metriche distinte: tutti gli emittenti nei depositi, emittenti con candidati P, equity comuni
riconciliate, listing USA corrente nella mappa ufficiale SEC e società finanziariamente verificate.
La mappa corrente CIK/ticker/exchange non prova listing storico, domicilio USA o assenza di
errori: non viene usata come caratteristica retroattiva del modello. Fondi e foreign issuers
possono essere quotati negli USA; la verifica settoriale/domiciliare resta da completare.
Copertura archivi pubblicati e copertura del periodo calendario richiesto sono separate.

## Riconciliazione

Identità fonte: accession + NONDERIV_TRANS_SK, mantenuta distinta dall’indice XML del live scanner.
Alias tra dataset e scanner riconciliati solo entro lo stesso accession/CIK con quantità,
prezzo e data compatibili con la precisione dell’estrazione. Conflitti sospesi, non sommati.
Co-dichiarazioni economiche su accession diversi richiedono revisione; nomi diversi non provano
insider indipendenti. Categorie OFFICER/DIRECTOR/TENPERCENTOWNER/OTHER sono quelle dichiarate.
Form 4/A e possibili originali (CIK/owner/periodo o data originale) vengono conservati e sospesi
nel quadro corrente: una rettifica non viene automaticamente sommata o usata per cancellare
l’intero originale. Le annotazioni correnti non entrano nei feature set dei depositi precedenti.

Solo non-derivative P/A, quantità/prezzo positivi, common/ordinary equity e swap escluso
sono candidati tecnici; non equivale a open-market buy verificato. Opzioni, warrant, preferred,
unità, conversioni, grant, esercizi M e classi non identificabili non sono segnali azionari.
I link all’indice documento sono costruiti da CIK/accession, non scaricati/verificati uno per uno.
Righe originarie e footnote restano negli shard; nessun BUY o rating alto nasce dall’import.

## Database e target

`scanner.ml` ricostruisce SQLite locale: eventi, identità persistenti, prezzi, corporate actions,
fatti finanziari con data pubblica, caratteristiche as-of, target e registro delle fonti.
Il DB è rigenerabile e non viene caricato nel sito. I dati fonte compressi restano nel repository.

Caratteristiche iniziali: importo/quantità log, ruoli e ritardo del deposito. Non includono
listing corrente, rettifiche future o fondamentali successivi. La data pubblica disponibile
nel bulk è giornaliera: decisione non prima del giorno seguente e prima seduta comune utile.
Doppioni/co-report già noti al deposito vengono esclusi dai feature set; quelli emersi in
seguito non cancellano retroattivamente un precedente insieme informativo.

Target 30/90/180 giorni di calendario: prima seduta comune dopo la disponibilità e dopo
l’orizzonte, su indice total-return verificato di titolo e benchmark. Entry/exit non saltano
oltre sette giorni di dati mancanti. Split/dividendi/proventi di delisting devono essere inclusi
e verificati. Nessun forward-fill, rendimento zero per titoli spariti o join su ticker riciclati.
Costo iniziale roundtrip: 20 bps configurabili, ipotesi di ricerca da validare, non costo osservato.
Un provider deve essere espressamente approvato con licenza di redistribuzione e provenance;
un semplice flag su una serie prezzi non basta. Nessun provider è attualmente approvato.

## Modelli e controlli

Regressione logistica standardizzata e gradient boosting poco profondo, implementati con
scikit-learn. Minimi ingegneristici: 500 target verificati, 100 emittenti, tre anni, almeno
50 esempi e due classi con 20 casi ciascuna per blocco dopo il purge. Non sono una garanzia
di potenza statistica o validità economica. Split cronologico 60/20/20, purge usando la fine
effettiva del target e embargo di sette giorni. Fit/scaling solo sul train; scelta sul Brier
in validazione; test tenuto separato. AUC, precision-recall, Brier, accuracy, confronto baseline
costante e regole point-in-time dove disponibili, intervalli bootstrap a cluster emittente.

Senza target non vengono addestrati modelli, salvate performance fittizie o presentate
previsioni. I risultati di ricerca non entrano nel Radar Score o nelle notifiche. Le fixture
di test sono esplicitamente fittizie e non fanno parte del dataset reale.

## Esecuzione e limiti gratuiti

`python -m scanner.bulk --max-quarters 1` importa un trimestre mancante; `--start 2006`
permette l’estensione futura. Il workflow storico è separato dalla scansione recente;
alla prima pubblicazione prova fino a 23 checkpoint, poi due a esecuzione settimanale/manuale.
Stop a mancato progresso, file audit massimo 40 MiB, guardia audit 400 MiB e sito 150 MiB.
GitHub Pages ammette un sito fino a 1 GB, sorgente raccomandata 1 GB e timeout deploy 10 minuti:
restiamo su shard contenuti e caricamento a richiesta, senza un enorme payload iniziale.
Runner Ubuntu standard del repository pubblico; nessun larger runner o servizio esterno.

Fonti prezzi rivalutate: Stooq vieta redistribuzione senza consenso; Alpha Vantage limita
la licenza ordinaria all’uso personale/non commerciale; FMP richiede accordi di display.
Nessun account/chiave/pagamento attivato. Restano mancanti prezzi, benchmark, rettifiche,
delisting verificati e mapping storico di classe/ticker. SEC resta primaria per fondamentali
point-in-time; prezzi Form 4 e public float non vengono spacciati per capitalizzazione corrente.

I numeri effettivi aggiornati sono in `docs/data/history_coverage.json`,
`docs/data/ml_status.json` e `data/insider/manifest.json`; non vengono fissati in questo documento.

Gli accession già presenti in shard trimestrali integri vengono riconosciuti anche dallo
scanner recente/backfill: non riscarica il documento originale. Il report giornaliero distingue
quelli coperti dagli archivi da quelli appena scaricati; non copia milioni di accession nello
stato pubblico. La UI usa proiezioni compatte; i record completi per ricerca restano negli
shard compressi, non vengono eliminati per ridurre il sito.

Il bulk non fornisce una colonna valuta: gli importi calcolati quantità×prezzo sono valori
dichiarati, non conversioni USD. La UI li marca come valuta non verificata. Le caratteristiche
as-filed possono conservarli come dichiarati, ma il gate di training richiede anche la valuta
transazione verificata prima di classificare una riga come addestrabile. Nessuna conversione
FX o base valutaria viene inventata.
