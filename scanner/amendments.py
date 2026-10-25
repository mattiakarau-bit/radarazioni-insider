"""Reuse the audit SUBMISSION/REPORTINGOWNER tables, including 4/A with NO P row."""
import gzip,hashlib,json
from pathlib import Path
from collections import defaultdict


def registry(root,manifest):
    from scanner.bulk import sec_date
    from scanner.universe import read,write
    path=root/'data/insider/amendments.v1.json';cache=read(path,{'version':1,'quarters':{}})
    for quarter,record in manifest['quarters'].items():
        if record.get('status')!='complete':continue
        cached=cache['quarters'].get(quarter,{})
        cached_hash=hashlib.sha256(json.dumps(cached.get('rows',[]),sort_keys=True).encode()).hexdigest()
        if cached.get('audit_sha256')==record.get('audit_sha256') and cached.get('rows_sha256')==cached_hash:continue
        source=root/f'data/insider/{quarter}.audit.jsonl.gz'
        # Small synthetic unit shards may not include an audit table; their P/A
        # amendments still go through existing reconciliation. Real manifest requires hash.
        if not record.get('audit_sha256'):continue
        if not source.exists() or hashlib.sha256(source.read_bytes()).hexdigest()!=record['audit_sha256']:raise ValueError('Audit shard integrity failure: '+quarter)
        amendments={}
        with gzip.open(source,'rt',encoding='utf-8') as f:
            for line in f:
                if line.startswith('{"table":"NONDERIV_TRANS"') or line.startswith('{"table":"FOOTNOTES"'):break
                item=json.loads(line);row=item['row']
                if item['table']=='SUBMISSION' and row.get('DOCUMENT_TYPE')=='4/A':
                    acc=row['ACCESSION_NUMBER']
                    amendments[acc]=dict(accession=acc,cik=int(row['ISSUERCIK']),filed=sec_date(row['FILING_DATE']),
                        period_of_report=sec_date(row['PERIOD_OF_REPORT']),original_filing_date=sec_date(row['DATE_OF_ORIG_SUB']) if row.get('DATE_OF_ORIG_SUB') else None,owner_ciks=[])
                elif item['table']=='REPORTINGOWNER' and row['ACCESSION_NUMBER'] in amendments:
                    amendments[row['ACCESSION_NUMBER']]['owner_ciks'].append(row['RPTOWNERCIK'])
        rows=sorted(amendments.values(),key=lambda a:a['accession'])
        cache['quarters'][quarter]=dict(audit_sha256=record['audit_sha256'],rows_sha256=hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),rows=rows)
    write(path,cache)
    return [x for q,r in cache['quarters'].items() if manifest['quarters'].get(q,{}).get('status')=='complete' for x in r['rows']]


def apply(rows,amendments,as_of):
    families=defaultdict(list);originals=defaultdict(list);unknown=defaultdict(list)
    for a in amendments:
        if a['filed']>as_of:continue
        owners=a.get('owner_ciks') or []
        if not owners:unknown[(a['cik'],a.get('period_of_report'))].append(a)
        for owner in owners:
            families[(a['cik'],str(owner),a.get('period_of_report'))].append(a)
            if a.get('original_filing_date'):originals[(a['cik'],str(owner),a['original_filing_date'])].append(a)
    count=0
    for row in rows:
        if row.get('amendment'):continue
        period=row.get('period_of_report',row.get('transaction_date'))
        matches=list(unknown[(row['cik'],period)])
        for owner in row.get('owner_ciks',[]):
            matches+=families[(row['cik'],str(owner),period)]+originals[(row['cik'],str(owner),row['filed'])]
        if matches:
            if row.get('purchase_eligible'):count+=1
            row['purchase_eligible']=False
            row['review_reasons']=sorted(set(row.get('review_reasons',[])+['amendment_including_non_purchase_requires_review']))
    return count
