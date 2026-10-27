"""Offline-first archive -> semester -> compact Pages pipeline.

Never downloads quarterly archives. Optional SEC financial refresh is budgeted,
rotates the queue and persists small extracted observations with provenance.
"""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from datetime import date,datetime,timezone
from scanner.identity import filing_key,event_key,suspend_security_aliases
from scanner.semester import build,issuer_windows,CurrentEvidence
from scanner.radar import months_before
from scanner.fundamentals import summarize_company_facts,EXTRACTOR_VERSION

ROOT=Path(__file__).resolve().parents[1]
ENGINE_VERSION='semester-v1.5'


def read(path,default):
    return json.loads(path.read_text()) if path.exists() else default


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(path)


def load_sources(root,as_of):
    from scanner.bulk import iter_events,reconcile,reconcile_sources
    # Read ALL existing structured purchase shards for amendment context; no SEC HTTP.
    manifest=read(root/'data/insider/manifest.json',{'quarters':{}})
    for q,record in manifest['quarters'].items():
        if record.get('status')=='complete':
            path=root/f'data/insider/{q}.events.jsonl.gz'
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=record['event_sha256']:
                raise ValueError('Archive event shard integrity failure: '+q)
    raw=list(iter_events(root));live=read(root/'docs/data/events_history.json',{'filings':[]})['filings']
    live=[dict(x) for x in live if x.get('filed','9999')<=as_of]
    reconciled=reconcile(raw,as_of);reconciled,bridge=reconcile_sources(reconciled,live)
    covered={e['accession'] for e in raw}
    combined=[]
    for x in reconciled:
        x=dict(x);x['purchase_eligible']=x['current_eligible']
        x['currency']='USD';x['currency_basis']='SEC Form 4 instruction 5: USD as reported; not individually audited'
        x['officer_title']=' / '.join(o.get('title','') for o in x['owners'])
        # Historical filing-day financial snapshots are not current evidence.
        x.pop('fundamentals',None);combined.append(x)
    for x in live:
        if filing_key(x['form_url']) in covered:continue
        # Old v0.3 rows lack security/swap eligibility: preserve, do not certify.
        x['purchase_eligible']=x.get('purchase_eligible') is True and not x.get('amendment') and x.get('amendment_known_from','9999')>as_of
        x['currency']='USD';x['currency_basis']='SEC Form 4 instruction 5'
        if not x['purchase_eligible']:x['review_reasons']=list(x.get('review_reasons',[]))+['live_eligibility_or_amendment_requires_review']
        x.pop('fundamentals',None);x.pop('analysis',None);combined.append(x)
    from scanner.amendments import registry,apply
    amendment_rows=registry(root,manifest)+list(read(root/'docs/data/state.json',{}).get('amendment_filings',{}).values())
    bridge['amendment_filings_including_without_P']=len({x['accession'] for x in amendment_rows if x['filed']<=as_of})
    bridge['additional_purchases_suspended_by_amendments']=apply(combined,amendment_rows,as_of)
    bridge['additional_cross_title_alias_rows_suspended']=suspend_security_aliases(combined)
    unique={event_key(x):x for x in combined}
    return list(unique.values()),dict(bulk_rows=len(raw),realtime_rows=len(live),merged_rows=len(unique),**bridge)


def finite_record(entry):
    # Preserve source dates and filing links in compact current balance snapshots.
    return {k:entry.get(k) for k in ('val','start','end','filed','accn','form','unit','tag')}


def current_balance(raw,as_of):
    gaap=raw.get('facts',{}).get('us-gaap',{})
    def latest(tags,duration=False):
        values=[]
        for tag in tags:
            for e in gaap.get(tag,{}).get('units',{}).get('USD',[]):
                if e.get('form') not in ('10-Q','10-K','10-Q/A','10-K/A') or e.get('filed','9999')>=as_of or e.get('end','9999')>as_of:continue
                if duration:
                    try:
                        span=(date.fromisoformat(e['end'])-date.fromisoformat(e['start'])).days
                        if not 60<=span<=380:continue
                    except (KeyError,ValueError):continue
                elif e.get('start'):continue
                if not isinstance(e.get('val'),(float,int)):continue
                values.append(dict(e,tag=tag,unit='USD'))
        if not values:return None
        return finite_record(max(values,key=lambda e:(e['end'],e['filed'])))
    # Do not sum overlapping debt tags, infer debt=0 or apply industrial heuristics to banks.
    cash=latest(['CashAndCashEquivalentsAtCarryingValue'])
    debt=latest(['LongTermDebtAndFinanceLeaseObligationsIncludingCurrentMaturities','LongTermDebtCurrent','LongTermDebtNoncurrent','LongTermDebt'])
    operating=latest(['NetCashProvidedByUsedInOperatingActivities'],True)
    income=latest(['NetIncomeLoss'],True)
    return dict(cash=cash,debt_observation=debt,operating_cashflow=operating,net_income=income,
                debt_scope_verified=False,review_pass=False,
                note='Singole osservazioni SEC: debito corrente/non corrente, lease e perimetro settoriale richiedono riconciliazione. Nessuno zero imputato.')


def refresh_financials(root,companies,as_of,budget):
    from scanner.sec import get
    cache=root/'data/analysis';cache.mkdir(parents=True,exist_ok=True)
    # Missing first, then oldest fetched first. Persistent queue advances each run.
    candidates=[c for c in companies if c['selection_status']=='pending']
    listed={x['cik'] for x in read(root/'docs/data/bulk_issuers.json',{'issuers':[]})['issuers']}
    def priority(c):
        old=read(cache/f'{c["cik"]}.json',{})
        outdated=bool(old.get('financials')) and (old['financials'].get('extractor_version')!=EXTRACTOR_VERSION or old.get('review_schema',0)<2)
        return (not outdated,c['cik'] not in listed,old.get('attempted_on',''),-c['amount'])
    candidates.sort(key=priority)
    refreshed=0;failed=0
    for company in candidates:
        path=cache/f'{company["cik"]}.json';old=read(path,{})
        attempted=old.get('attempted_on')
        if attempted and (old.get('error') or old.get('financials',{}).get('extractor_version')==EXTRACTOR_VERSION and old.get('review_schema',0)>=2) and 0<=(date.fromisoformat(as_of)-date.fromisoformat(attempted)).days<7:continue
        if refreshed+failed>=budget:break
        source=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{company["cik"]:010d}.json'
        try:
            raw=json.loads(get(source))
            if int(raw.get('cik',-1))!=company['cik']:raise ValueError('CIK companyfacts mismatch')
            fin=summarize_company_facts(raw,as_of);fin['source_url']=source
            snapshot=dict(cik=company['cik'],attempted_on=as_of,fetched_on=as_of,source_url=source,
                          financials=fin,balance=current_balance(raw,as_of))
            from scanner.preliminary import shares_observations, recent_filings
            snapshot['shares_observations']=shares_observations(raw,as_of)
            # One additional small index request; no original filings/quarter archives.
            submissions={}
            try:
                submissions=json.loads(get(f'https://data.sec.gov/submissions/CIK{company["cik"]:010d}.json'))
                if int(submissions.get('cik',-1))!=company['cik']:raise ValueError('CIK submissions mismatch')
                snapshot['corporate_filings']=recent_filings(submissions,company['window_start'],as_of)
            except Exception as exc:
                snapshot['corporate_filings']=old.get('corporate_filings')
                snapshot['corporate_filings_error']=type(exc).__name__
            from scanner.quarterly import analyze, compact
            snapshot['quarterly_financials']=compact(analyze(raw,as_of,submissions.get('sic'),fin.get('revenue_scope_verified') is True),company['cik'])
            snapshot['review_schema']=2
            write(path,snapshot);refreshed+=1
        except Exception as exc:
            old.update(cik=company['cik'],attempted_on=as_of,error=f'{type(exc).__name__}: {str(exc)[:100]}')
            write(path,old);failed+=1
    return dict(refreshed=refreshed,failed=failed,budget=budget,ttl_days=7,
                note='Cache di estrazioni SEC persistente, massimo 50 società per scansione; nessun prezzo/cap inventato. Debito ed eventi successivi non certificati automaticamente.')


def financial_evidence(root,as_of):
    result={}
    for path in (root/'data/analysis').glob('*.json'):
        x=read(path,{})
        # Past summaries stay dated; current_checks rejects old cache instead of relabeling it.
        fin=dict(x.get('financials',{}))
        if fin and fin.get('extractor_version')!=EXTRACTOR_VERSION:
            fin.update(evidence_valid=False,fresh=False,data_warnings=fin.get('data_warnings',[])+['Estrazione precedente in coda di ricalcolo: non certifica i fondamentali correnti'])
        result[x['cik']]=CurrentEvidence(financials=fin)
    return result


def compact_window(w):
    return {k:w.get(k) for k in ('window_start','window_end','amount','reported_amount','transaction_count','reported_transaction_count','aggregation_verified','weighted_price','historical_market_cap','historical_market_cap_as_of','weekly_economic_verified','split_comparison_verified','adjusted_insider_price','distance_from_insider_pct')}


def publish_from_archive(root=ROOT,as_of=None,refresh_budget=0,force=False):
    root=Path(root);as_of=as_of or date.today().isoformat()
    # Fingerprint includes date, source content hashes, engine and cached financial evidence.
    digest=hashlib.sha256((ENGINE_VERSION+as_of).encode())
    inputs=[root/'data/insider/manifest.json',root/'docs/data/events_history.json',root/'docs/data/results.json',root/'docs/data/state.json']+sorted((root/'data/analysis').glob('*.json'))
    for path in sorted((root/'data/insider').glob('*.events.jsonl.gz')):
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    digest.update(Path(__file__).read_bytes())
    digest.update((Path(__file__).parent/'identity.py').read_bytes())
    digest.update((Path(__file__).parent/'fundamentals.py').read_bytes())
    digest.update((Path(__file__).parent/'semester.py').read_bytes())
    digest.update((Path(__file__).parent/'amendments.py').read_bytes())
    digest.update((Path(__file__).parent/'financial_review.py').read_bytes())
    digest.update((Path(__file__).parent/'preliminary.py').read_bytes())
    digest.update((Path(__file__).parent/'quarterly.py').read_bytes())
    digest.update((Path(__file__).parent/'evidence_report.py').read_bytes())
    for path in inputs:
        digest.update(str(path.relative_to(root)).encode());digest.update(path.read_bytes() if path.exists() else b'absent')
    marker=root/'data/cache/semester_checkpoint.json';old=read(marker,{})
    # Cache marker is runner-local; persistent finance summaries are the cross-run cache.
    if not force and not refresh_budget and old.get('digest')==digest.hexdigest() and (root/'docs/data/radar.json').exists():return read(root/'docs/data/radar.json',{})
    events,bridge=load_sources(root,as_of)
    radar,companies,details=build(events,as_of,financial_evidence(root,as_of))
    refresh=dict(refreshed=0,failed=0,budget=0)
    if refresh_budget:
        refresh=refresh_financials(root,companies,as_of,max(0,min(refresh_budget,50)))
        radar,companies,details=build(events,as_of,financial_evidence(root,as_of))
    first_year=months_before(date.fromisoformat(as_of),12).isoformat()
    # Custom search receives WINDOW summaries, never bulk raw transactions.
    year_windows=issuer_windows(events,as_of,12);by_cik={c['cik']:c for c in companies};search={}
    for w in year_windows:
        cik=w['cik']
        if cik not in search:
            company=by_cik.get(cik)
            if company is None:
                # Outside semester stays available in personalized 365-day search only.
                company={k:v for k,v in w.items() if k not in ('transactions','fundamentals','possible_duplicate_ids')}
                company.update(detail_url=f'./data/companies/{cik}.json',selection_status='outside_semester',current_price=None)
            search[cik]=dict(company=company,windows=[],semester_windows=details.get(cik,{}).get('semester_windows',[]))
        if cik in details:
            match=next((x for x in details[cik]['significant_windows'] if x['window_end']==w['window_end']),None)
            if match:w.update({k:match[k] for k in ('historical_market_cap','historical_market_cap_as_of','weekly_economic_verified','split_comparison_verified','adjusted_insider_price','distance_from_insider_pct')})
        search[cik]['windows'].append(compact_window(w))
        if cik not in details:
            details[cik]=dict(company=search[cik]['company'],as_of=as_of,significant_windows=[],transactions=[])
    # Full per-company source rows and significant windows are lazy-loaded by details.
    yearly_sources={}
    for x in events:
        if first_year<=x['transaction_date']<=as_of:yearly_sources.setdefault(x['cik'],[]).append(x)
    from scanner.financial_review import review, report as financial_report
    reviews={}
    for cik,d in details.items():
        d['transactions']=yearly_sources.get(cik,[])
        d['transaction_period_start']=first_year
        d['transaction_period_end']=as_of
        d.pop('semester_windows',None)
        d['financial_snapshot']=read(root/f'data/analysis/{cik}.json',None)
        if d['financial_snapshot']:
            d['financial_snapshot']['extractor_current']=d['financial_snapshot'].get('financials',{}).get('extractor_version')==EXTRACTOR_VERSION
        d['financial_review']=review(d['financial_snapshot'],as_of)
        reviews[cik]=d['financial_review']
        fields=('id','form_url','cik','company','symbol','filed','transaction_date','amount','shares','unit_price','security_title','insider','currency','currency_basis','amendment','purchase_eligible','review_reasons')
        d['transactions']=[{k:x.get(k) for k in fields} for x in d['transactions']]
        write(root/f'docs/data/companies/{cik}.json',d)
    def index_company(c):
        fields=('id','cik','symbol','company','window_start','window_end','amount','reported_amount','transaction_count','reported_transaction_count','aggregation_verified','weighted_price','market_cap','market_cap_verified','current_price','current_price_as_of','current_valuation_as_of','detail_url','selection_status','significant_window_count')
        result={k:c.get(k) for k in fields}
        result['analysis']={k:c.get('analysis',{}).get(k) for k in ('radar_score','score_status','quality_pass','opportunity_score','insider_strength_score')}
        return result
    for r in search.values():r['company']=index_company(r['company'])
    write(root/'docs/data/search_index.json',dict(as_of=as_of,search_start=first_year,aggregation_days=7,issuers=list(search.values())))
    from scanner.preliminary import rank
    preliminary=rank(companies,reviews)
    # First page inline, further cards loaded on demand; never raw transactions.
    radar['preliminary_groups']=preliminary[:20]
    radar['preliminary_total']=len(preliminary)
    radar['sec_screening'] = dict(
        annual_observations_available=sum(bool(c['sec_evidence']['available_count']) for c in preliminary),
        candidates_with_usable_sec_observations=sum(c['sec_evidence']['sec_documented_for_review'] for c in preliminary),
        candidates_with_recorded_risks=sum(bool(c['sec_risks']) for c in preliminary),
        note='Provenienza SEC XBRL, solo dati storici e incompleti; non sono verificate capitalizzazione, prezzi o convenienza.'
    )
    radar['preliminary_amount_review_count']=sum(c['amount_review_required'] for c in preliminary)
    radar['preliminary_order']='Priorità di approfondimento: prima osservazioni SEC annuali favorevoli e documentate, poi copertura dati, forza insider e importo. Non è una classifica di investimenti verificati.'
    write(root/'docs/data/pending_index.json',dict(as_of=as_of,companies=preliminary))
    manifest=read(root/'data/insider/manifest.json',{'quarters':{}})
    radar['source_coverage']=dict(archive_quarters=[q for q,r in manifest['quarters'].items() if r.get('status')=='complete'],
                                  reconciliation=bridge,finance_refresh=refresh,
                                  latest_realtime_scan=read(root/'docs/data/results.json',{}).get('last_scan_utc'),
                                  note='Archivi trimestrali + depositi giornalieri già raccolti. Scansione giornaliera parziale: non copertura completa SEC. Legacy senza verifica titolo esclusi dalle soglie.')
    listing={x['cik'] for x in read(root/'docs/data/bulk_issuers.json',{'issuers':[]})['issuers']}
    in_period={x['cik'] for x in events if radar['search_start']<=x['transaction_date']<=as_of and x['filed']<=as_of}
    radar['stats']['companies_observed_current_us_listing']=len(in_period & listing)
    radar['stats']['weekly_base_companies_observed_current_us_listing']=sum(c['cik'] in listing for c in companies if c['selection_status'] in ('pending','selected'))
    radar['financial_cache_count']=len(list((root/'data/analysis').glob('*.json')))
    radar['financial_extractor_version']=EXTRACTOR_VERSION
    radar['financial_cache_current_count']=sum(read(p,{}).get('financials',{}).get('extractor_version')==EXTRACTOR_VERSION for p in (root/'data/analysis').glob('*.json'))
    candidate_snapshots=[details[c['cik']].get('financial_snapshot') or {} for c in companies if c['selection_status'] in ('pending','selected')]
    radar['financial_progress']=dict(
        candidates=len(candidate_snapshots),
        cached=sum(bool(s.get('financials')) for s in candidate_snapshots),
        quarterly_observations=sum(bool(s.get('quarterly_financials',{}).get('latest_period')) for s in candidate_snapshots),
        fresh_quarterly_observations=sum(s.get('quarterly_financials',{}).get('fresh_latest_period') is True for s in candidate_snapshots),
        outstanding_share_observations=sum(bool(s.get('shares_observations')) for s in candidate_snapshots),
        corporate_indices=sum(isinstance(s.get('corporate_filings'),dict) for s in candidate_snapshots),
        latest_attempt_errors=sum(bool(s.get('error')) for s in candidate_snapshots),
        complete_financial_checks=radar['stats']['companies_current_financials_verified'],
        prices_verified=radar['stats']['companies_current_prices_verified'],
        historical_caps_pass=radar['stats']['companies_historical_cap_threshold_pass'],
        current_caps_pass=radar['stats']['companies_current_cap_pass'])
    radar['source_policy_url']='./data/source_policy.json'
    status=read(root/'docs/data/results.json',{})
    write(root/'docs/data/scan_status.json',{k:status.get(k) for k in ('last_scan_utc','status','coverage','errors','model_status')})
    write(root/'docs/data/radar.json',radar)
    write(root/'docs/data/semester_report.json',radar)
    write(root/'docs/data/companies/financial/report.json',financial_report(companies,reviews,radar))
    from scanner.evidence_report import coverage
    write(root/'docs/data/companies/financial/market-gates.json',coverage(companies,details,radar,read(root/'docs/data/ml_status.json',{})))
    write(marker,dict(digest=digest.hexdigest(),as_of=as_of))
    print(json.dumps(dict(as_of=as_of,search_start=radar['search_start'],stats=radar['stats'],funnel=radar['funnel'],source_coverage=radar['source_coverage']),ensure_ascii=False))
    return radar


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--as-of',default=date.today().isoformat());p.add_argument('--refresh-financials',type=int,default=0);p.add_argument('--force',action='store_true')
    args=p.parse_args();publish_from_archive(args.root,args.as_of,args.refresh_financials,args.force)

if __name__=='__main__':main()
