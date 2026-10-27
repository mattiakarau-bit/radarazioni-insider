import copy,unittest
from scanner.market_math import near_insider,capitalization


def tx(id,day,price=100,shares=10):return dict(id=id,transaction_date=day,unit_price=price,shares=shares,security_id='test:A',currency='USD')
def quote(day,close=100,split=1):return dict(day=day,close=close,split_factor=split,security_id='test:A',currency='USD',exchange='TEST')

def capclass():
    return dict(security_id='test:A',class_review_reference='synthetic reviewed class',price=quote('2026-10-20'),
                shares=dict(value=10_000_000,unit='shares',end='2026-10-20',filed='2026-10-21',accession='0000000001-26-000001',tag='EntityCommonStockSharesOutstanding',security_id='test:A',source_url='https://www.sec.gov/Archives/synthetic-fixture'))

class MarketMathTests(unittest.TestCase):
    def test_fifteen_percent_inclusive_and_configurable(self):
        for close,expected in [(85,True),(115,True),(115.01,False),(84.99,False)]:
            r=near_insider([tx('a','2026-05-01')],[quote('2026-05-01'),quote('2026-10-23',close)],'2026-10-27',security_id='test:A',actions_reviewed=True)
            self.assertEqual(r['within_band'],expected)
            self.assertFalse(r['financial_opportunity_verified'])
        self.assertFalse(near_insider([tx('a','2026-05-01')],[quote('2026-05-01'),quote('2026-10-23',110)],'2026-10-27',security_id='test:A',actions_reviewed=True,tolerance_pct=5)['within_band'])

    def test_split_inside_purchase_week_adjusts_each_quantity_before_vwap(self):
        # 10 old shares at 100 => 20 new shares at 50, then 10 new shares at 55.
        rows=[quote('2026-05-01'),quote('2026-05-02',50,2),quote('2026-10-23',52)]
        rows[-1]['adjClose']=1 # Dividend-adjusted number must not be used.
        r=near_insider([tx('a','2026-05-01'),tx('b','2026-05-03',55)],rows,'2026-10-27',security_id='test:A',actions_reviewed=True)
        self.assertAlmostEqual(r['adjusted_insider_price'],1550/30)
        self.assertAlmostEqual(r['current_price'],52)

    def test_missing_actions_duplicate_transactions_wrong_class_and_stale_rejected(self):
        t=tx('a','2026-05-01');rows=[quote('2026-05-01'),quote('2026-10-23')]
        self.assertIsNone(near_insider([t],rows,'2026-10-27',security_id='test:A')['within_band'])
        for ts,ps in [([t,t],rows),([dict(t,security_id='test:B')],rows),([t],rows[:1]),([t],[dict(rows[0],split_factor=None),rows[1]])]:
            self.assertIsNone(near_insider(ts,ps,'2026-10-27',security_id='test:A',actions_reviewed=True)['within_band'])

    def test_exact_date_all_classes_cap(self):
        c=capclass();r=capitalization([c],'2026-10-20','2026-10-27',all_classes_review_reference='fixture scope')
        self.assertEqual(r['value'],1e9)
        second=copy.deepcopy(c);second['security_id']='test:B';second['price']['security_id']='test:B';second['shares']['security_id']='test:B'
        self.assertEqual(capitalization([c,second],'2026-10-20','2026-10-27',all_classes_review_reference='fixture scope')['value'],2e9)

    def test_cap_rejects_old_shares_ytd_eps_share_counts_future_or_currency_mismatch(self):
        for change in [('end','2026-07-24'),('filed','2026-10-28'),('tag','WeightedAverageNumberOfDilutedSharesOutstanding')]:
            c=capclass();c['shares'][change[0]]=change[1]
            self.assertIsNone(capitalization([c],'2026-10-20','2026-10-27',all_classes_review_reference='fixture')['value'])
        c=capclass();c['price']['currency']='EUR'
        self.assertIsNone(capitalization([c],'2026-10-20','2026-10-27',all_classes_review_reference='fixture')['value'])

class PublicSelectionPriceBandTests(unittest.TestCase):
    def test_same_evidence_requires_price_band_and_keeps_one_card(self):
        from scanner.semester import build
        from tests.test_semester import purchase,verified,ASOF
        from dataclasses import replace
        day='2026-05-12';events=[purchase(1,day)]
        evidence=replace(verified([day]),current_price=120)
        self.assertEqual(build(events,ASOF,{1:evidence})[0]['groups'],[])
        r=build(events,ASOF,{1:evidence},price_band_pct=25)[0]
        self.assertEqual(len(r['groups']),1)
        self.assertEqual(r['price_band_pct'],25)
        with self.assertRaises(ValueError):build(events,ASOF,price_band_pct=float('nan'))
