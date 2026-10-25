"""Acceptance audit on authentic checked-out SEC shards, never on fixtures."""
import gzip,json,re,sys
from pathlib import Path
from datetime import date
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scanner.radar import months_before

root=Path(__file__).resolve().parents[1]
radar=json.loads((root/'docs/data/radar.json').read_text())
as_of=radar['as_of'];first=months_before(date.fromisoformat(as_of),6).isoformat()
assert radar['search_months']==6 and radar['search_start']==first and radar['aggregation_days']==7
manifest=json.loads((root/'data/insider/manifest.json').read_text())
raw={};accessions=set()
for q,r in manifest['quarters'].items():
    if r['status']!='complete':continue
    with gzip.open(root/f'data/insider/{q}.events.jsonl.gz','rt') as f:
        for line in f:
            row=json.loads(line);accessions.add(row['accession'])
            if first<=row['transaction_date']<=as_of and row['filed']<=as_of:raw[row['id']]=row
for row in json.loads((root/'docs/data/events_history.json').read_text())['filings']:
    match=re.search(r'(\d{10})-?(\d{2})-?(\d{6})(?:[./#]|$)',row['form_url'])
    accession='-'.join(match.groups()) if match else row['form_url']
    if accession not in accessions and first<=row['transaction_date']<=as_of and row['filed']<=as_of:raw[row['id']]=row
assert radar['stats']['companies_with_purchase_rows']==len({x['cik'] for x in raw.values()})
assert radar['stats']['purchase_rows']==len(raw)
assert radar['source_coverage']['reconciliation']['bulk_rows']>0
assert len({c['cik'] for c in radar['groups']})==len(radar['groups'])==radar['stats']['selected_companies']
assert not radar['buy_signal'] and not radar['notify']
pending=json.loads((root/'docs/data/pending_index.json').read_text())['companies']
assert len(pending)==radar['stats']['pending_base_candidates']
assert len({c['cik'] for c in pending})==len(pending)
assert len(radar['preliminary_groups'])==min(20,len(pending))
assert radar['preliminary_groups']==pending[:20]
assert radar['preliminary_total']==len(pending)
for flag in (False,True):
    amounts=[c['amount'] for c in pending if c['amount_review_required']==flag]
    assert amounts==sorted(amounts,reverse=True)
assert not ({c['cik'] for c in pending}&{c['cik'] for c in radar['groups']})
assert all(c['analysis']['radar_score'] is None and c['preliminary'] for c in pending)
may_windows=0
for c in pending+radar['groups']:
    d=json.loads((root/f'docs/data/companies/{c["cik"]}.json').read_text())
    assert d['significant_windows']
    assert any(w['amount']>=100000 for w in d['significant_windows'])
    for w in d['significant_windows']:
        assert w['aggregation_verified'] and w['amount']>=100000 and first<=w['window_start']<=w['window_end']<=as_of
        assert (date.fromisoformat(w['window_end'])-date.fromisoformat(w['window_start'])).days<=6
        total=sum(x['amount'] for x in d['transactions'] if x['purchase_eligible'] and not x['amendment'] and w['window_start']<=x['transaction_date']<=w['window_end'])
        assert abs(total-w['amount'])<.02,(c['cik'],total,w['amount'])
        may_windows+=w['window_end'].startswith('2026-05')
    if c in radar['groups']:
        assert all(c['current_checks'].values()) and c['weekly_economic_verified'] and c['split_comparison_verified']
        assert c['analysis']['score_status']=='verificato' and c['analysis']['quality_pass']
if first<='2026-05-01' and as_of>='2026-05-31':assert may_windows>0,'Imported May purchases must reach company details'
index=json.loads((root/'docs/data/search_index.json').read_text())
for record in index['issuers']:
    d=json.loads((root/f'docs/data/companies/{record["company"]["cik"]}.json').read_text())
    for window in record.get('semester_windows',[]):
        assert first<=window['window_start']<=window['window_end']<=as_of,'Annual window leaked into semester index'
        total=sum(x['amount'] for x in d['transactions'] if x['purchase_eligible'] and not x['amendment'] and window['window_start']<=x['transaction_date']<=window['window_end'])
        if window['aggregation_verified']:assert abs(total-window['amount'])<.02
size=(root/'docs/data/radar.json').stat().st_size
assert size<2*1024*1024,'Homepage should be compact; move large lists to lazy pages'
assert sum(p.stat().st_size for p in (root/'docs').rglob('*') if p.is_file())<150*1024*1024,'Pages internal 150 MiB guard'
print(json.dumps(dict(authentic_SEC_acceptance='passed',as_of=as_of,first=first,companies=len({x['cik'] for x in raw.values()}),weekly_pass=radar['stats']['companies_weekly_base_pass'],may_significant_windows=may_windows,homepage_companies=len(radar['groups']),homepage_bytes=size)))
