import csv,gzip,io,json,tempfile,unittest,zipfile
from pathlib import Path
from scanner.bulk import archives_from_html,import_zip,reconcile,normalize


def sample_zip(path):
    subs=[dict(ACCESSION_NUMBER='0000000001-21-000001',FILING_DATE='04-JAN-2021',PERIOD_OF_REPORT='01-JAN-2021',DATE_OF_ORIG_SUB='',DOCUMENT_TYPE='4',ISSUERCIK='1',ISSUERNAME='Fixture Company',ISSUERTRADINGSYMBOL='FIX'),
          dict(ACCESSION_NUMBER='0000000001-21-000002',FILING_DATE='05-JAN-2021',PERIOD_OF_REPORT='01-JAN-2021',DATE_OF_ORIG_SUB='04-JAN-2021',DOCUMENT_TYPE='4/A',ISSUERCIK='1',ISSUERNAME='Fixture Company',ISSUERTRADINGSYMBOL='FIX')]
    owners=[dict(ACCESSION_NUMBER=s['ACCESSION_NUMBER'],RPTOWNERCIK='7',RPTOWNERNAME='Fixture Fund',RPTOWNER_RELATIONSHIP='TENPERCENTOWNER',RPTOWNER_TITLE='',RPTOWNER_STREET1='not-needed') for s in subs]
    rows=[]
    for i,code in enumerate(('P','M','P')):
        rows.append(dict(ACCESSION_NUMBER=subs[int(i==2)]['ACCESSION_NUMBER'],NONDERIV_TRANS_SK=str(i),SECURITY_TITLE='Common Stock',TRANS_DATE='01-JAN-2021',TRANS_CODE=code,TRANS_ACQUIRED_DISP_CD='A',TRANS_SHARES='100',TRANS_PRICEPERSHARE='20',EQUITY_SWAP_INVOLVED='0',DIRECT_INDIRECT_OWNERSHIP='I'))
    def tsv(rows,fields=None):
        out=io.StringIO();w=csv.DictWriter(out,fieldnames=fields or list(rows[0]),delimiter='\t');w.writeheader();w.writerows(rows);return out.getvalue()
    with zipfile.ZipFile(path,'w') as z:
        for name,rs in [('SUBMISSION',subs),('REPORTINGOWNER',owners),('NONDERIV_TRANS',rows)]:z.writestr(name+'.tsv',tsv(rs))
        z.writestr('FOOTNOTES.tsv','ACCESSION_NUMBER\tFOOTNOTE_ID\tFOOTNOTE_TXT\n')

class BulkTests(unittest.TestCase):
    def test_catalogue_only_sec_requested_years(self):
        html='<a href="/files/structureddata/data/insider-transactions-data-sets/2021q1_form345.zip">Q</a><a href="https://evil.example/2022q1_form345.zip">bad</a>'
        r=archives_from_html(html);self.assertEqual(list(r),['2021q1'])
        with self.assertRaises(ValueError):archives_from_html('blocked')
    def test_streaming_idempotent_import_amendments_and_exclusions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);sample_zip(root/'q.zip')
            stats=import_zip(root/'q.zip','2021q1',root/'raw.gz',root/'events.gz')
            self.assertEqual(stats['counts']['non_derivative_rows'],3)
            self.assertEqual(stats['counts']['retained_purchase_candidates'],2)
            self.assertEqual(stats['counts']['excluded_non_purchase'],1)
            with gzip.open(root/'events.gz','rt') as f:events=[json.loads(x) for x in f]
            self.assertFalse(events[1]['purchase_eligible']);self.assertTrue(events[1]['amendment'])
            self.assertEqual(len(reconcile(events,'2021-01-04')),1)
            self.assertTrue(reconcile(events,'2021-01-04')[0]['current_eligible'])
            self.assertTrue(all(not x['current_eligible'] for x in reconcile(events,'2021-01-05')))
            again=import_zip(root/'q.zip','2021q1',root/'raw.gz',root/'events.gz')
            self.assertEqual(again['counts'],stats['counts'])
            with gzip.open(root/'raw.gz','rt') as f:self.assertNotIn('not-needed',f.read())
    def test_corrupt_zip_cannot_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'bad.zip').write_text('error page')
            with self.assertRaises(zipfile.BadZipFile):import_zip(p/'bad.zip','2021q1',p/'r.gz',p/'e.gz')
            self.assertFalse((p/'e.gz').exists())
