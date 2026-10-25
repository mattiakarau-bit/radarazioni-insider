"""Official quarterly SEC structured importer. Streaming, immutable quarter shards.

No original filing is downloaded; amendments are preserved, never blindly added/replaced.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, math, os, re, sqlite3, tempfile, time, urllib.request, zipfile
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urljoin, urlparse
from scanner.sec import get
from scanner.identity import filing_key
from scanner.run import load_json, save_json

ROOT=Path(__file__).resolve().parents[1]
CATALOG='https://www.sec.gov/data-research/sec-markets-data/insider-transactions-data-sets'
TICKERS='https://www.sec.gov/files/company_tickers_exchange.json'
SCHEMA=1


def sec_date(value):
    value=(value or '').strip()
    for fmt in ('%Y-%m-%d','%d-%b-%Y','%d-%b-%y','%Y%m%d'):
        try:return datetime.strptime(value,fmt).date().isoformat()
        except ValueError:pass
    raise ValueError('Invalid SEC date: '+value[:25])


def number(v):
    try:
        n=Decimal(str(v).strip())
        return float(n) if n.is_finite() and math.isfinite(float(n)) else None
    except (InvalidOperation,ValueError):return None


def accession(v):
    v=str(v).strip()
    if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',v):raise ValueError('Invalid accession')
    return v


def archives_from_html(html,start=2021,end=2026):
    result={}
    for href in re.findall(r'href=[\"\']([^\"\']+)[\"\']',html,re.I):
        match=re.search(r'(20\d{2})q([1-4])_form345\.zip$',href,re.I)
        if not match or not start<=int(match[1])<=end:continue
        url=urljoin(CATALOG,href)
        if urlparse(url).netloc!='www.sec.gov':continue
        result[f'{match[1]}q{match[2]}']=url
    if not result:raise ValueError('Official catalogue contains no requested archives')
    return dict(sorted(result.items()))


def download(url,path,max_bytes=80*1024*1024):
    """Bounded streaming download with the existing SEC identity; never log its value."""
    ua=os.getenv('SEC_USER_AGENT','').strip()
    if '@' not in ua:raise RuntimeError('Existing SEC_USER_AGENT is required')
    if urlparse(url).netloc!='www.sec.gov' or not url.startswith('https://'):raise ValueError('Non SEC URL')
    tmp=path.with_suffix('.part');tmp.parent.mkdir(parents=True,exist_ok=True)
    req=urllib.request.Request(url,headers={'User-Agent':ua,'Accept-Encoding':'identity'})
    time.sleep(.6)
    try:
        with urllib.request.urlopen(req,timeout=90) as response,tmp.open('wb') as out:
            size=0
            while chunk:=response.read(1024*1024):
                size+=len(chunk)
                if size>max_bytes:raise ValueError('Download size limit')
                out.write(chunk)
        with zipfile.ZipFile(tmp) as z:
            if sum(i.file_size for i in z.infolist())>1500*1024*1024:raise ValueError('Expansion limit')
            if z.testzip():raise ValueError('ZIP CRC failed')
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True);raise
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(z,name):
    members=[x for x in z.namelist() if Path(x).stem.upper()==name and Path(x).suffix.lower() in ('.tsv','.txt')]
    if len(members)!=1:raise ValueError('Missing/ambiguous table '+name)
    reader=csv.DictReader(io.TextIOWrapper(z.open(members[0]),encoding='utf-8-sig',newline=''),delimiter='\t')
    if not reader.fieldnames:raise ValueError('Empty table '+name)
    required={'SUBMISSION':{'ACCESSION_NUMBER','FILING_DATE','PERIOD_OF_REPORT','DOCUMENT_TYPE','ISSUERCIK','ISSUERNAME'},'REPORTINGOWNER':{'ACCESSION_NUMBER','RPTOWNERCIK','RPTOWNERNAME','RPTOWNER_RELATIONSHIP'},'NONDERIV_TRANS':{'ACCESSION_NUMBER','NONDERIV_TRANS_SK','TRANS_DATE','TRANS_CODE','TRANS_ACQUIRED_DISP_CD','TRANS_SHARES','TRANS_PRICEPERSHARE'},'FOOTNOTES':{'ACCESSION_NUMBER','FOOTNOTE_ID'}}
    if not required[name] <= {k.strip().upper() for k in reader.fieldnames}:raise ValueError('Unsupported schema '+name)
    for row in reader:
        if None in row:raise ValueError('Malformed TSV '+name)
        yield {k.strip().upper():(v or '').strip() for k,v in row.items()}


def eligibility(row,sub):
    reasons=[]
    if sub.get('DOCUMENT_TYPE')!='4':reasons.append('amendment_or_non_form4')
    if row.get('TRANS_CODE')!='P' or row.get('TRANS_ACQUIRED_DISP_CD')!='A':reasons.append('not_P_acquisition')
    shares,price=number(row.get('TRANS_SHARES')),number(row.get('TRANS_PRICEPERSHARE'))
    if shares is None or price is None or shares<=0 or price<=0:reasons.append('missing_or_nonpositive_price_quantity')
    if row.get('EQUITY_SWAP_INVOLVED','').lower() not in ('0','false','n'):reasons.append('swap_or_unknown_swap')
    title=row.get('SECURITY_TITLE','').casefold()
    if not re.search(r'common|ordinary',title) or re.search(r'preferred|warrant|option|convertible|note|unit|phantom|restricted stock unit',title):reasons.append('equity_class_not_verified_common_ordinary')
    if sub.get('NOT_SUBJECT_SEC16') in ('1','true','TRUE'):reasons.append('not_subject_sec16')
    return not reasons,reasons


def normalize(row,sub,owners,quarter):
    acc=accession(row['ACCESSION_NUMBER']);cik=int(sub['ISSUERCIK'])
    if not 0<cik<10**10:raise ValueError('Invalid issuer CIK')
    filed=sec_date(sub['FILING_DATE']);trans=sec_date(row['TRANS_DATE'])
    okay,reasons=eligibility(row,sub)
    if trans>filed:okay=False;reasons.append('transaction_after_filing')
    shares=number(row.get('TRANS_SHARES'));price=number(row.get('TRANS_PRICEPERSHARE'))
    owner_rows=owners.get(acc,[])
    if not owner_rows or any(not o.get('RPTOWNERCIK','').isdigit() for o in owner_rows):okay=False;reasons.append('reporting_owner_identity_missing')
    return dict(id=f'{acc}#nd:{row["NONDERIV_TRANS_SK"]}',accession=acc,source_row_id=row['NONDERIV_TRANS_SK'],
                source='SEC quarterly insider dataset',currency='unknown',currency_verified=False,quarter=quarter,cik=cik,company=sub['ISSUERNAME'],symbol=sub.get('ISSUERTRADINGSYMBOL',''),
                filed=filed,transaction_date=trans,available_from=(date.fromisoformat(filed)+timedelta(days=1)).isoformat(),
                availability_precision='filing_date_only_conservative_next_calendar_day',form=sub['DOCUMENT_TYPE'],
                original_filing_date=sec_date(sub['DATE_OF_ORIG_SUB']) if sub.get('DATE_OF_ORIG_SUB') else None,
                period_of_report=sec_date(sub['PERIOD_OF_REPORT']),amendment=sub['DOCUMENT_TYPE'].endswith('/A'),
                security_title=row.get('SECURITY_TITLE',''),shares=shares,unit_price=price,
                amount=round(shares*price,2) if shares is not None and price is not None else None,
                ownership_type=row.get('DIRECT_INDIRECT_OWNERSHIP'),code=row.get('TRANS_CODE'),
                owner_ciks=sorted({o['RPTOWNERCIK'] for o in owner_rows}),
                owners=[dict(cik=o['RPTOWNERCIK'],name=o['RPTOWNERNAME'],relationship=o.get('RPTOWNER_RELATIONSHIP','').upper(),title=o.get('RPTOWNER_TITLE','')) for o in owner_rows],
                insider=', '.join(o['RPTOWNERNAME'] for o in owner_rows),independence_verified=False,
                officer=any('OFFICER' in o.get('RPTOWNER_RELATIONSHIP','').upper() for o in owner_rows),
                director=any('DIRECTOR' in o.get('RPTOWNER_RELATIONSHIP','').upper() for o in owner_rows),
                ten_pct=any('TENPERCENTOWNER' in o.get('RPTOWNER_RELATIONSHIP','').upper() for o in owner_rows),
                purchase_eligible=okay,exclusion_reasons=reasons,venue='not_verified_open_market',
                original_url_status='issuer_accession_index_not_individually_fetched',
                form_url=f'https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace("-","")}/{acc}-index.html',
                price_footnote=row.get('TRANS_PRICEPERSHARE_FN',''),shares_footnote=row.get('TRANS_SHARES_FN',''))


@contextmanager
def gzip_writer(path):
    with path.open('wb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
            with io.TextIOWrapper(compressed,encoding='utf-8',newline='') as text:
                yield text


def import_zip(path,quarter,raw_path,event_path):
    """Atomic per quarter. All rows retained in compressed audit shards, no addresses."""
    raw_tmp=raw_path.with_suffix('.tmp');event_tmp=event_path.with_suffix('.tmp')
    raw_path.parent.mkdir(parents=True,exist_ok=True);event_path.parent.mkdir(parents=True,exist_ok=True)
    counts=Counter();issuers=set();candidate_issuers=set();roles=Counter();events=[]
    with zipfile.ZipFile(path) as z,gzip_writer(raw_tmp) as audit:
        submissions={};owners=defaultdict(list)
        def keep(kind,row):audit.write(json.dumps({'table':kind,'row':row},ensure_ascii=False,separators=(',',':'))+'\n')
        for row in table(z,'SUBMISSION'):
            acc=accession(row['ACCESSION_NUMBER'])
            if acc in submissions:raise ValueError('Duplicate submission key')
            submissions[acc]=row;counts['submissions']+=1
            if row.get('ISSUERCIK','').isdigit():issuers.add(int(row['ISSUERCIK']))
            keep('SUBMISSION',row)
        for row in table(z,'REPORTINGOWNER'):
            # Addresses are not needed for investment research; preserve identifiers/roles.
            minimal={k:row.get(k,'') for k in ('ACCESSION_NUMBER','RPTOWNERCIK','RPTOWNERNAME','RPTOWNER_RELATIONSHIP','RPTOWNER_TITLE','RPTOWNER_TXT')}
            owners[minimal['ACCESSION_NUMBER']].append(minimal);counts['reporting_owners']+=1;keep('REPORTINGOWNER',minimal)
        seen=set()
        for row in table(z,'NONDERIV_TRANS'):
            counts['non_derivative_rows']+=1;keep('NONDERIV_TRANS',row)
            key=(row.get('ACCESSION_NUMBER'),row.get('NONDERIV_TRANS_SK'))
            if key in seen:raise ValueError('Duplicate source transaction key')
            seen.add(key)
            if row.get('TRANS_CODE')!='P' or row.get('TRANS_ACQUIRED_DISP_CD')!='A':counts['excluded_non_purchase']+=1;continue
            counts['P_acquisition_rows']+=1
            try:
                sub=submissions[row['ACCESSION_NUMBER']]
                event=normalize(row,sub,owners,quarter)
                if sub['DOCUMENT_TYPE'] not in ('4','4/A'):counts['excluded_other_forms']+=1;continue
                events.append(event);candidate_issuers.add(event['cik'])
                counts['retained_purchase_candidates']+=1
                if event['purchase_eligible']:counts['as_filed_equity_candidates']+=1
                else:counts['excluded_or_unverified_equity_candidates']+=1
                if event['amendment']:counts['amendment_rows']+=1
                for o in event['owners']:roles[o['relationship']]+=1
            except (KeyError,ValueError,TypeError) as exc:
                counts['invalid_purchase_rows']+=1
                keep('QUARANTINE',dict(key=key,error=str(exc)[:150]))
        for row in table(z,'FOOTNOTES'):counts['footnotes']+=1;keep('FOOTNOTES',row)
    if counts['P_acquisition_rows'] and not counts['retained_purchase_candidates']:raise ValueError('All purchase rows invalid; quarter not accepted')
    with gzip_writer(event_tmp) as output:
        for e in sorted(events,key=lambda e:e['id']):output.write(json.dumps(e,ensure_ascii=False,separators=(',',':'))+'\n')
    if raw_tmp.stat().st_size>40*1024*1024:raise ValueError('Quarter audit shard exceeds storage guard')
    index_path=raw_path.with_name(quarter+'.accessions.json.gz');index_tmp=index_path.with_suffix('.tmp')
    with gzip_writer(index_tmp) as idx:
        json.dump(sorted(acc for acc,sub in submissions.items() if sub.get('DOCUMENT_TYPE') in ('4','4/A')),idx)
    raw_tmp.replace(raw_path);event_tmp.replace(event_path);index_tmp.replace(index_path)
    return dict(accessions_sha256=hashlib.sha256(index_path.read_bytes()).hexdigest(),counts=counts,issuer_ciks=sorted(issuers),candidate_issuer_ciks=sorted(candidate_issuers),owner_categories=dict(roles),
                event_sha256=hashlib.sha256(event_path.read_bytes()).hexdigest(),audit_sha256=hashlib.sha256(raw_path.read_bytes()).hexdigest())


def iter_events(root):
    canonical={}
    manifest=load_json(root/'data/insider/manifest.json',{'quarters':{}})
    allowed={q for q,r in manifest['quarters'].items() if r.get('status')=='complete'}
    fields=('cik','filed','transaction_date','shares','unit_price','form')
    for path in sorted((root/'data/insider').glob('*.events.jsonl.gz')):
        if path.name.split('.')[0] not in allowed:continue
        with gzip.open(path,'rt',encoding='utf-8') as f:
            for line in f:
                event=json.loads(line);key=event['id']
                if key not in canonical:canonical[key]=event
                elif any(canonical[key].get(k)!=event.get(k) for k in fields):
                    canonical[key]['purchase_eligible']=False
                    canonical[key]['exclusion_reasons']=sorted(set(canonical[key]['exclusion_reasons']+['cross_archive_key_conflict']))
    yield from canonical.values()


def known_bulk_accessions(root):
    manifest=load_json(root/'data/insider/manifest.json',{'quarters':{}});known=set()
    for q,r in manifest['quarters'].items():
        if r.get('status')!='complete':continue
        p=root/f'data/insider/{q}.accessions.json.gz'
        if not p.is_file():continue
        try:
            if hashlib.sha256(p.read_bytes()).hexdigest()!=r.get('accessions_sha256'):continue
            with gzip.open(p,'rt',encoding='utf-8') as f:known.update(json.load(f))
        except (OSError,ValueError):continue
    return known


def listed_in_us(row):
    return re.sub('[^A-Z]','',str(row.get('exchange','')).upper()) in {'NASDAQ','NYSE','NYSEAMERICAN','NYSEAMER','NYSEARCA','CBOE','CBOEBZX'}


def reconcile(events,as_of):
    """Current view, never fed back as a historical feature. Raw rows remain unchanged."""
    rows=[dict(e) for e in events if e['filed']<=as_of]
    families=defaultdict(list);economic=defaultdict(list)
    for e in rows:
        for owner in e['owner_ciks']:families[(e['cik'],owner,e['period_of_report'])].append(e)
        if e.get('amount') is not None:
            economic[(e['cik'],e['transaction_date'],e['security_title'].casefold(),e['shares'],e['unit_price'])].append(e)
        e['review_reasons']=list(e.get('exclusion_reasons',[]))
    by_original=defaultdict(list)
    for e in rows:
        for owner in e['owner_ciks']:by_original[(e['cik'],owner,e['filed'])].append(e)
    for e in rows:
        if e['amendment'] and e.get('original_filing_date'):
            for owner in e['owner_ciks']:
                for original in by_original[(e['cik'],owner,e['original_filing_date'])]:
                    original['review_reasons'].append('amendment_original_date_requires_review')
    for family in families.values():
        if any(e['amendment'] for e in family):
            for e in family:e['review_reasons'].append('amendment_family_requires_review')
    for matches in economic.values():
        if len({e['accession'] for e in matches})>1:
            for e in matches:e['review_reasons'].append('possible_co_report_or_duplicate')
    for e in rows:
        e['review_reasons']=sorted(set(e['review_reasons']));e['current_eligible']=e['purchase_eligible'] and not e['review_reasons']
    return rows


def reconcile_sources(bulk_events,realtime_events):
    """Keep both raw sources; suppress duplicate source views only within an accession.
    Dataset numeric precision can differ from XML, so compare only documented 2dp
    extraction and quarantine unmatched filings instead of inventing exact row links.
    """
    rows=[dict(e) for e in bulk_events];by_acc=defaultdict(list)
    for e in rows:by_acc[e['accession']].append(e)
    remaining={acc:Counter((e['transaction_date'],round(e['shares'] or 0,2),round(e['unit_price'] or 0,2)) for e in es) for acc,es in by_acc.items()}
    report=Counter();conflicts=set()
    for e in realtime_events:
        acc=filing_key(e.get('form_url',''))
        if acc not in by_acc:report['realtime_only_rows']+=1;continue
        fingerprint=(e.get('transaction_date'),round(e.get('shares',0),2),round(e.get('unit_price',0),2))
        if any(x['cik']!=e.get('cik') for x in by_acc[acc]) or remaining[acc][fingerprint]<=0:
            conflicts.add(acc);report['unresolved_cross_source_rows']+=1
        else:
            remaining[acc][fingerprint]-=1;report['source_alias_rows_suppressed']+=1
    for e in rows:
        if e['accession'] in conflicts:
            e['current_eligible']=False;e['review_reasons']=sorted(set(e.get('review_reasons',[])+['cross_source_conflict']))
    return rows,dict(report)


def summarize(root,manifest,listing,now):
    events=list(iter_events(root));current=reconcile(events,now[:10]);current,source_bridge=reconcile_sources(current,load_json(root/'docs/data/events_history.json',{'filings':[]}).get('filings',[]));counts=Counter();all_issuers=set();candidate_issuers=set();equity_issuers=set()
    for record in manifest['quarters'].values():
        if record.get('status')!='complete':continue
        counts.update(record['counts']);all_issuers.update(record['issuer_ciks']);candidate_issuers.update(record['candidate_issuer_ciks'])
    current_listing={int(row['cik']):row for row in listing}
    eligible=[]
    for e in current:
        if e['current_eligible']:
            equity_issuers.add(e['cik'])
            if e['cik'] in current_listing and listed_in_us(current_listing[e['cik']]):
                eligible.append(e)
    start_year=manifest.get('target_start',2021);end_year=manifest.get('target_end',2026);calendar_count=(end_year-start_year+1)*4
    completed=[q for q,r in manifest['quarters'].items() if r.get('status')=='complete' and start_year<=int(q[:4])<=end_year];published=manifest.get('published_quarters',[])
    summary=dict(version=1,updated_utc=now,target_start=start_year,target_end=end_year,calendar_quarters_requested=calendar_count,
                 published_quarters=published,completed_quarters=completed,completed_count=len(completed),published_count=len(published),
                 published_archive_coverage_pct=round(100*len(set(completed)&set(published))/len(published),2) if published else None,
                 calendar_target_coverage_pct=round(100*len(completed)/calendar_count,2),
                 counts=dict(counts),unique_candidate_events=len(events),source_reconciliation=source_bridge,unique_issuers_all=len(all_issuers),unique_issuers_purchase_candidates=len(candidate_issuers),
                 unique_issuers_common_equity=len(equity_issuers),unique_issuers_us_listing_current=len({e['cik'] for e in eligible}),
                 reconciled_current_events=len(eligible),ambiguous_current_events=sum(bool(e['review_reasons']) for e in current),
                 financial_verified_issuers=0,market_cap_verified_issuers=0,return_labels_verified=0,
                 listing_observed_at=now,listing_not_historical=True,us_domicile_verified=False,
                 period_filed_start=min((e['filed'] for e in events),default=None),period_filed_end=max((e['filed'] for e in events),default=None),
                 quarters=[dict(quarter=q,**{k:v for k,v in r.items() if k not in ('issuer_ciks','candidate_issuer_ciks')}) for q,r in sorted(manifest['quarters'].items())],
                 note='Copertura degli archivi pubblicati, non del mercato o di tutti i documenti SEC; listing corrente non è prova di listing storico o domicilio USA.',
                 source=CATALOG)
    save_json(root/'docs/data/history_coverage.json',summary)
    # Lightweight issuer inventory. No large historical dataset is loaded at app startup.
    by_cik=defaultdict(list)
    for e in eligible:by_cik[e['cik']].append(e)
    inventory=[]
    for cik,rows in by_cik.items():
        latest=max(rows,key=lambda e:(e['filed'],e['id']))
        inventory.append(dict(cik=cik,company=latest['company'],symbol=latest['symbol'],exchange=current_listing[cik]['exchange'],events=len(rows),
                              last_filed=latest['filed'],quarters=sorted({e['quarter'] for e in rows}),status='in_verifica',radar_score=None))
    save_json(root/'docs/data/bulk_issuers.json',dict(updated_utc=now,issuers=sorted(inventory,key=lambda x:x['last_filed'],reverse=True)))
    # Compact public per-quarter candidates, retained out of the main startup payload.
    for q in completed:
        qrows=[e for e in current if e['quarter']==q]
        fields=('id','currency','cik','company','symbol','filed','transaction_date','security_title','shares','unit_price','amount','form','amendment','current_eligible','review_reasons','officer','director','ten_pct','form_url')
        public=[]
        for e in qrows:
            item={k:e.get(k) for k in fields}
            item['insider']=', '.join(o['name'] for o in e['owners'][:2])+(f" + {len(e['owners'])-2} dichiaranti" if len(e['owners'])>2 else '')
            item['owner_count']=len(e['owner_ciks'])
            item['owner_categories']=sorted({o['relationship'] for o in e['owners']})
            item['us_listing_current']=e['cik'] in current_listing and listed_in_us(current_listing[e['cik']])
            public.append(item)
        destination=root/f'docs/data/bulk/{q}.json';destination.parent.mkdir(parents=True,exist_ok=True)
        tmp=destination.with_suffix('.tmp');tmp.write_text(json.dumps(dict(quarter=q,events=public),ensure_ascii=False,separators=(',',':')),encoding='utf-8');tmp.replace(destination)
    return summary


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--max-quarters',type=int,default=2);parser.add_argument('--start',type=int,default=2021);parser.add_argument('--end',type=int,default=2026)
    args=parser.parse_args();root=args.root;cache=root/'data/cache';cache.mkdir(parents=True,exist_ok=True)
    manifest_path=root/'data/insider/manifest.json';manifest=load_json(manifest_path,dict(schema=SCHEMA,quarters={}))
    now=datetime.now(timezone.utc).isoformat(timespec='seconds')
    try:catalogue=archives_from_html(get(CATALOG),args.start,args.end)
    except Exception as exc:
        manifest.update(last_attempt_utc=now,catalogue_error=f'{type(exc).__name__}: {str(exc)[:180]}');save_json(manifest_path,manifest)
        save_json(root/'docs/data/history_coverage.json',dict(status='import_blocked',updated_utc=now,error=manifest['catalogue_error'],completed_count=sum(r.get('status')=='complete' for r in manifest['quarters'].values()),source=CATALOG));raise
    manifest.update(target_start=args.start,target_end=args.end)
    manifest['published_quarters']=list(catalogue);manifest.pop('catalogue_error',None)
    for q,record in manifest['quarters'].items():
        if record.get('status')!='complete':continue
        for suffix,key in (('audit','audit_sha256'),('events','event_sha256'),('accessions','accessions_sha256')):
            shard=root/f'data/insider/{q}.{suffix}.jsonl.gz' if suffix!='accessions' else root/f'data/insider/{q}.accessions.json.gz'
            if not shard.is_file() or hashlib.sha256(shard.read_bytes()).hexdigest()!=record.get(key):
                record.update(status='failed',error='Shard integrity failure; quarter queued for repair')
                break
    selected=[q for q in sorted(catalogue,reverse=True) if manifest['quarters'].get(q,{}).get('status')!='complete'][:max(0,min(args.max_quarters,24))]
    for q in selected:
        url=catalogue[q];path=cache/(q+'.zip')
        try:
            if sum(p.stat().st_size for p in (root/'data/insider').glob('*'))>400*1024*1024:raise ValueError('400 MiB audit storage guard; import paused')
            sha=download(url,path)
            stats=import_zip(path,q,root/f'data/insider/{q}.audit.jsonl.gz',root/f'data/insider/{q}.events.jsonl.gz')
            manifest['quarters'][q]=dict(status='complete',source_url=url,source_sha256=sha,imported_utc=now,**stats)
            print(q,dict(stats['counts']),flush=True)
        except Exception as exc:
            manifest['quarters'][q]=dict(status='failed',source_url=url,error=f'{type(exc).__name__}: {str(exc)[:200]}',last_attempt_utc=now)
            print(q,'failed',type(exc).__name__,flush=True)
        finally:
            path.unlink(missing_ok=True);save_json(manifest_path,manifest)
    listing=[]
    try:
        raw=json.loads(get(TICKERS));listing=[dict(zip(raw['fields'],r)) for r in raw['data']]
    except Exception as exc:manifest['listing_error']=f'{type(exc).__name__}: {str(exc)[:150]}'
    summary=summarize(root,manifest,listing,now)
    save_json(manifest_path,manifest)
    if sum(p.stat().st_size for p in (root/'docs').rglob('*') if p.is_file())>150*1024*1024:raise RuntimeError('Pages 150 MiB guard exceeded; do not publish')
    print(json.dumps({k:summary[k] for k in ('completed_count','published_count','unique_issuers_all','unique_issuers_purchase_candidates','reconciled_current_events')},ensure_ascii=False))

if __name__=='__main__':main()
