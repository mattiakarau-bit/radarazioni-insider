import unittest,tempfile,json,gzip,hashlib
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from scanner.semester import build,CurrentEvidence,Capitalization
from scanner.scoring import ValuationEvidence
from scanner.universe import publish_from_archive
from tests.test_radar import tx

ASOF='2026-10-25'
def purchase(cik,day,amount=250000,n=1):
    x=tx(n,day,file=cik,shares=amount/100,price=100,cik=cik)
    return dict(x,filed=day,purchase_eligible=True,code='P',symbol=f'TEST{cik}',company=f'Fixture {cik}',officer=True)

def verified(days):
    fin=dict(as_of=ASOF,evidence_valid=True,fresh=True,revenue_growing=True,eps_growing=True,
             cashflow_positive=True,eps_latest_positive=True,cashflow_latest_positive=True)
    return CurrentEvidence(financials=fin,valuation=ValuationEvidence(ASOF,'https://fixture.example/current',1e9,'USD',True,'test-only'),
        historical_caps={d:Capitalization(1e9,d,'https://fixture.example/historical','test-only') for d in days},
        current_price=100,price_as_of=ASOF,price_source='https://fixture.example/price',adjusted_insider_prices={d:100 for d in days},
        split_review_reference='test-only',balance_sheet_review_as_of=ASOF,debt_review_pass=True,
        changes_review_start='2026-04-25',changes_review_as_of=ASOF,review_reference='synthetic-fixture-never-production')

class SemesterTests(unittest.TestCase):
    def test_may_june_september_enter_october_without_recent_purchases(self):
        dates=['2026-05-12','2026-06-19','2026-09-08'];events=[purchase(i+1,d) for i,d in enumerate(dates)]
        r,_,_=build(events,ASOF,{i+1:verified([d]) for i,d in enumerate(dates)})
        self.assertEqual({c['cik'] for c in r['groups']},{1,2,3})
        self.assertEqual(r['search_start'],'2026-04-25');self.assertEqual(r['aggregation_days'],7)
        self.assertTrue(all(c['analysis']['radar_score']>80 for c in r['groups']))
        self.assertFalse(r['buy_signal']);self.assertFalse(r['notify'])
    def test_multiple_significant_windows_one_company_and_small_purchase_excluded(self):
        events=[purchase(1,'2026-05-12'),purchase(1,'2026-06-19',300000,2),purchase(2,'2026-09-08',99999)]
        r,companies,details=build(events,ASOF,{1:verified(['2026-05-12','2026-06-19']),2:verified(['2026-09-08'])})
        self.assertEqual(len(r['groups']),1);self.assertEqual(r['groups'][0]['cik'],1)
        self.assertEqual(len(details[1]['significant_windows']),2)
        self.assertEqual(next(c for c in companies if c['cik']==2)['selection_status'],'excluded')
    def test_seven_day_window_is_not_six_month_sum(self):
        events=[purchase(1,'2026-05-01',60000),purchase(1,'2026-05-08',60000,2)]
        r,_,_=build(events,ASOF,{1:verified(['2026-05-01','2026-05-08'])})
        self.assertEqual(r['stats']['companies_weekly_base_pass'],0)
        joined=[purchase(1,'2026-05-01',60000),purchase(1,'2026-05-07',60000,2)]
        self.assertEqual(build(joined,ASOF,{1:verified(['2026-05-01','2026-05-07'])})[0]['stats']['companies_weekly_base_pass'],1)
    def test_historical_and_current_caps_are_separate(self):
        e=verified(['2026-05-12'])
        # Current 200bn cap must not raise a historical 1bn weekly threshold.
        e=replace(e,valuation=replace(e.valuation,market_cap=200e9))
        self.assertEqual(len(build([purchase(1,'2026-05-12')],ASOF,{1:e})[0]['groups']),1)
        missing=replace(e,historical_caps={})
        self.assertEqual(build([purchase(1,'2026-05-12')],ASOF,{1:missing})[0]['groups'],[])
        self.assertEqual(build([purchase(1,'2026-05-12')],ASOF,{1:replace(e,valuation=replace(e.valuation,market_cap=499e6))})[0]['groups'],[])
    def test_missing_prices_debt_changes_and_bad_cash_cannot_confirm(self):
        e=verified(['2026-05-12']);event=purchase(1,'2026-05-12')
        for missing in (replace(e,current_price=None),replace(e,debt_review_pass=False),replace(e,changes_review_as_of=None),replace(e,adjusted_insider_prices={}),replace(e,financials=dict(e.financials,cashflow_latest_positive=False,cashflow_positive=False))):
            r,_,_=build([event],ASOF,{1:missing});self.assertEqual(r['groups'],[])
        self.assertEqual(build([dict(event,filed='2026-11-01')],ASOF,{1:e})[0]['stats']['companies_with_purchase_rows'],0)
        self.assertEqual(build([purchase(1,'2026-04-24')],ASOF,{1:e})[0]['stats']['companies_with_purchase_rows'],0)
    def test_unrelated_reporters_and_amendments_are_not_added(self):
        a=purchase(1,'2026-05-12',60000)
        b=dict(a,id=a['id'].replace('000001','000002'),form_url=a['form_url'].replace('000001','000002'))
        r,_,_=build([a,b,dict(purchase(2,'2026-05-12'),amendment=True)],ASOF)
        self.assertEqual(r['stats']['companies_weekly_base_pass'],0)
    def test_archive_and_daily_sources_feed_same_pipeline_without_http(self):
        from scanner.bulk import normalize
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'data/insider';folder.mkdir(parents=True)
            row=dict(ACCESSION_NUMBER='0000000001-26-000001',NONDERIV_TRANS_SK='1',TRANS_DATE='12-MAY-2026',TRANS_SHARES='3000',TRANS_PRICEPERSHARE='100',TRANS_CODE='P',TRANS_ACQUIRED_DISP_CD='A',SECURITY_TITLE='Common Stock',EQUITY_SWAP_INVOLVED='0',TRANS_TIMELINESS='')
            sub=dict(ISSUERCIK='1',ISSUERNAME='Archive May fixture',ISSUERTRADINGSYMBOL='MAY',FILING_DATE='14-MAY-2026',PERIOD_OF_REPORT='12-MAY-2026',DOCUMENT_TYPE='4')
            owners={'0000000001-26-000001':[dict(RPTOWNERCIK='2',RPTOWNERNAME='Person',RPTOWNER_RELATIONSHIP='OFFICER')]}
            event=normalize(row,sub,owners,'2026q2');event['purchase_eligible']=True;event['exclusion_reasons']=[]
            path=folder/'2026q2.events.jsonl.gz'
            with gzip.open(path,'wt') as f:f.write(json.dumps(event)+'\n')
            (folder/'manifest.json').write_text(json.dumps(dict(quarters={'2026q2':dict(status='complete',event_sha256=hashlib.sha256(path.read_bytes()).hexdigest())})))
            (root/'docs/data').mkdir(parents=True)
            # Same accession supplied by XML must not double count alongside bulk.
            alias=dict(purchase(1,'2026-05-12',300000),form_url=event['form_url'],id=event['accession']+'#tx0')
            daily=purchase(3,'2026-09-08')
            (root/'docs/data/events_history.json').write_text(json.dumps(dict(filings=[alias,daily])))
            with patch('scanner.sec.get',side_effect=AssertionError('No SEC HTTP during reuse')):
                r=publish_from_archive(root,ASOF,force=True)
            self.assertEqual(r['stats']['companies_with_purchase_rows'],2)
            self.assertEqual(r['stats']['companies_weekly_base_pass'],2)
            self.assertEqual(r['source_coverage']['reconciliation']['source_alias_rows_suppressed'],1)
            self.assertEqual(len(json.loads((root/'docs/data/companies/1.json').read_text())['transactions']),1)
            self.assertEqual(r['groups'],[])

class NonPurchaseAmendmentTests(unittest.TestCase):
    def test_sale_only_amendment_metadata_and_public_cutoff(self):
        from scanner.parser import parse_form4,amendment_metadata
        from scanner.amendments import apply
        xml='''<ownershipDocument><documentType>4/A</documentType><periodOfReport>2026-05-12</periodOfReport><dateOfOriginalSubmission>2026-05-13</dateOfOriginalSubmission><issuer><issuerCik>1</issuerCik><issuerName>Fixture</issuerName></issuer><reportingOwner><reportingOwnerId><rptOwnerCik>2</rptOwnerCik></reportingOwnerId></reportingOwner><nonDerivativeTable><nonDerivativeTransaction><transactionCoding><transactionCode>S</transactionCode></transactionCoding></nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>'''
        filing=dict(form='4/A',filed='2026-06-01',url='https://www.sec.gov/Archives/edgar/data/1/0000000001-26-000002.txt',company='Fixture')
        self.assertEqual(parse_form4(xml,filing),[])
        meta=amendment_metadata(xml,filing)
        original=dict(purchase(1,'2026-05-12'),filed='2026-05-13',owner_ciks=['2'])
        self.assertEqual(apply([original],[meta],'2026-05-31'),0);self.assertTrue(original['purchase_eligible'])
        self.assertEqual(apply([original],[meta],ASOF),1);self.assertFalse(original['purchase_eligible'])
    def test_audit_registry_reads_amendments_without_any_purchase_row_and_reuses_hash(self):
        from scanner.amendments import registry
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'data/insider';folder.mkdir(parents=True)
            source=folder/'2026q2.audit.jsonl.gz'
            with gzip.open(source,'wt') as f:
                for table,row in [('SUBMISSION',dict(ACCESSION_NUMBER='0000000001-26-000002',DOCUMENT_TYPE='4/A',ISSUERCIK='1',FILING_DATE='01-JUN-2026',PERIOD_OF_REPORT='12-MAY-2026',DATE_OF_ORIG_SUB='13-MAY-2026')),('REPORTINGOWNER',dict(ACCESSION_NUMBER='0000000001-26-000002',RPTOWNERCIK='2')),('NONDERIV_TRANS',dict(TRANS_CODE='S'))]:
                    f.write(json.dumps(dict(table=table,row=row),separators=(',',':'))+'\n')
            manifest=dict(quarters={'2026q2':dict(status='complete',audit_sha256=hashlib.sha256(source.read_bytes()).hexdigest())})
            self.assertEqual(len(registry(root,manifest)),1)
            with patch('scanner.amendments.gzip.open',side_effect=AssertionError('Do not decompress unchanged audit again')):
                self.assertEqual(len(registry(root,manifest)),1)
    def test_cache_refresh_keeps_dated_financial_snapshot_on_error(self):
        from scanner.universe import refresh_financials,read
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'data/analysis/1.json';p.parent.mkdir(parents=True)
            p.write_text(json.dumps(dict(cik=1,attempted_on='2026-10-01',fetched_on='2026-10-01',financials={'as_of':'2026-10-01'})))
            with patch('scanner.sec.get',side_effect=OSError('offline')):
                result=refresh_financials(root,[dict(cik=1,selection_status='pending',amount=100000)],ASOF,1)
            self.assertEqual(result['failed'],1)
            self.assertEqual(read(p,{})['financials']['as_of'],'2026-10-01')

class DatedMarketEvidenceTests(unittest.TestCase):
    def test_current_price_and_valuation_must_use_same_date(self):
        e=verified(['2026-05-12'])
        e=replace(e,price_as_of='2026-10-23')
        r,_,_=build([purchase(1,'2026-05-12')],ASOF,{1:e})
        self.assertEqual(r['groups'],[])
        self.assertEqual(r['stats']['companies_current_cap_pass'],1)
        self.assertEqual(r['stats']['companies_valuation_verified'],0)
    def test_future_capitalization_never_validates_past_week(self):
        e=verified(['2026-05-12'])
        cap=replace(e.historical_caps['2026-05-12'],as_of=ASOF)
        e=replace(e,historical_caps={'2026-05-12':cap})
        self.assertEqual(build([purchase(1,'2026-05-12')],ASOF,{1:e})[0]['groups'],[])
