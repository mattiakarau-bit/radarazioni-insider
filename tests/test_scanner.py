import unittest
from scanner.identity import filing_key, iso_date, normalize_events
from scanner.parser import parse_form4
from scanner.scoring import screen
from scanner.run import distinct_insiders_near

class RegressionTests(unittest.TestCase):
    def test_accession_aliases(self):
        a='https://www.sec.gov/Archives/edgar/data/1/0001012975-26-000982.txt'
        b=a.replace('/1/', '/2/')
        self.assertEqual(filing_key(a), filing_key(b))
        events=[dict(id=u+'#tx0',form_url=u,filed='20261023',transaction_date='2026-10-21') for u in (a,b)]
        self.assertEqual(len(normalize_events(events)),1)
        events.append(dict(events[0], id=a+'#tx1'))
        self.assertEqual(len(normalize_events(events)),2)
    def test_dates(self):
        self.assertEqual(iso_date('20261023'),'2026-10-23')
        with self.assertRaises(ValueError): iso_date('20260230')
    def test_parser_price_and_dates(self):
        xml='''<ownershipDocument><issuer><issuerCik>1</issuerCik><issuerTradingSymbol>TEST</issuerTradingSymbol></issuer><nonDerivativeTable><nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding><transactionDate><value>2026-10-21</value></transactionDate><transactionAmounts><transactionAcquiredDisposedCode><value>A</value></transactionAcquiredDisposedCode><transactionShares><value>100</value></transactionShares><transactionPricePerShare><value>0.123456</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>'''
        x=parse_form4(xml,dict(url='https://www.sec.gov/Archives/edgar/data/1/0001012975-26-000982.txt',filed='20261023',company='Test'))[0]
        self.assertEqual(x['unit_price'],0.123456)
        self.assertEqual(x['filed'],'2026-10-23')
        self.assertEqual(x['amount'],12.35)
    def test_incomplete_financials(self):
        x=dict(amount=1000000,officer_title='CEO')
        for fin in (None,{},dict(revenue_growing=True,eps_growing=True)):
            a=screen(x,fin,2)
            self.assertLessEqual(a['score'],49)
            self.assertFalse(a['notify'])
        self.assertFalse(screen(x,dict(revenue_growing=True,eps_growing=True,cashflow_positive=True),2)['notify'])
    def test_cluster_excludes_future(self):
        a=dict(cik=1,filed='2026-10-20',owners=['A'])
        self.assertEqual(distinct_insiders_near(a,[a,dict(a,filed='2026-10-21',owners=['B'])]),1)

if __name__ == '__main__': unittest.main()

class DualScoreTests(unittest.TestCase):
    def test_strong_purchase_is_not_high_opportunity(self):
        x=dict(amount=1000000,officer_title='CEO')
        a=screen(x,None,20)
        self.assertEqual(a['insider_strength_score'],80)
        self.assertEqual(a['opportunity_score'],0)
        self.assertFalse(a['notify'])
    def test_unverified_names_never_create_cluster_bonus(self):
        x=dict(amount=1000000,officer_title='CEO')
        self.assertEqual(screen(x,None,1),screen(x,None,15))
        events=[dict(cik=1,filed='2026-10-20',owners=['Fund A','Fund B','Holding LLC'])]
        self.assertEqual(distinct_insiders_near(events[0],events),1)
    def test_cashflow_and_valuation_caps(self):
        x=dict(amount=1000000,officer_title='CEO',valuation_verified=True)
        for cf,cap in [(None,39),(False,39),(True,49)]:
            a=screen(x,dict(revenue_growing=True,eps_growing=True,cashflow_positive=cf))
            self.assertIsNone(a['radar_score'])
            self.assertEqual(a['score_status'],'non_verificabile')
            self.assertLessEqual(a['radar_provisional'],29)
            self.assertFalse(a['valuation_verified'])
            self.assertFalse(a['notify'])
            self.assertFalse(a['buy_signal'])
    def test_opportunity_independent_of_purchase_size(self):
        f=dict(revenue_growing=True,eps_growing=True,cashflow_positive=True)
        self.assertEqual(screen(dict(amount=1),f)['opportunity_score'], screen(dict(amount=1000000,officer_title='CEO'),f)['opportunity_score'])
