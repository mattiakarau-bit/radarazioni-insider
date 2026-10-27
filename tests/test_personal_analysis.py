import json,unittest
from pathlib import Path
from scanner.personal_analysis import analyze_company

class PersonalAnalysisTests(unittest.TestCase):
    def test_actual_gpi_without_licensed_quotes_cannot_qualify(self):
        root=Path(__file__).resolve().parents[1]
        detail=json.loads((root/'docs/data/companies/1031203.json').read_text())
        r=analyze_company(detail,{'cik':1031203,'security_titles':{},'securities':{}},{},detail['as_of'])
        self.assertGreater(len(r['windows']),0)
        self.assertEqual(r['near_price_count'],0)
        self.assertFalse(r['redistribution_allowed'])
        self.assertTrue(all(w['historical_market_cap'] is None and w['current_market_cap'] is None and not w['fully_verified_opportunity'] for w in r['windows']))

    def test_wrong_cik_review_rejected(self):
        with self.assertRaises(ValueError):analyze_company({'company':{'cik':1}}, {'cik':2},{},'2026-10-27')

    def test_private_join_computes_near_price_without_financial_promotion(self):
        # Entire fixture is synthetic; no provider activation or real-market claim.
        detail={'company':{'cik':1},'search_start':'2026-04-27','significant_windows':[{'window_start':'2026-05-01','window_end':'2026-05-01','amount':200000}],
                'transactions':[{'id':'fixture','security_title':'Common','purchase_eligible':True,'amendment':False,'transaction_date':'2026-05-01','shares':2000,'unit_price':100,'currency':'USD'}]}
        identity=dict(symbol='TEST',exchange='TESTEX',currency='USD',valid_from='2026-01-01',valid_to='2026-12-31',
                      identity_source_url='https://www.sec.gov/Archives/synthetic-fixture',class_review_reference='fixture',corporate_actions_review_reference='fixture')
        reviews={'cik':1,'security_titles':{'Common':'test:A'},'securities':{'test:A':identity}}
        caches={'TEST':{'license_scope':'personal_internal_only','redistribution_allowed':False,'metadata':{'ticker':'TEST','exchangeCode':'TESTEX'},'prices':[{'date':'2026-05-01','close':100,'splitFactor':1},{'date':'2026-10-26','close':110,'splitFactor':1}]}}
        r=analyze_company(detail,reviews,caches,'2026-10-27');self.assertEqual(r['near_price_count'],1)
        self.assertFalse(r['windows'][0]['fully_verified_opportunity'])
        self.assertIsNone(r['windows'][0]['current_market_cap'])
