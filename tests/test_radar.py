import unittest
from scanner.radar import aggregate, filter_result, historical_windows, historical_review, price_band, publish
from scanner.scoring import screen


def tx(n,day='2026-10-23',file=1,shares=1000,price=100,cik=1,title='Common Stock'):
    url=f'https://www.sec.gov/Archives/edgar/data/1/0000000001-26-{file:06d}.txt'
    return dict(id=f'{url}#tx{n}',form_url=url,cik=cik,symbol='TEST',company='Test',transaction_date=day,
                filed='2026-10-24',amount=shares*price,shares=shares,unit_price=price,security_title=title,
                owners=['Fund A'],insider='Fund A',officer_title='CEO',fundamentals=None)

class RadarTests(unittest.TestCase):
    def test_seven_day_boundaries_and_issuer(self):
        groups=aggregate([tx(1,'2026-10-18'),tx(2,'2026-10-24'),tx(3,'2026-10-17'),tx(4,cik=2)],'2026-10-18','2026-10-24')
        self.assertEqual(len(groups),2)
        self.assertEqual(next(g for g in groups if g['cik']==1)['transaction_count'],2)
    def test_alias_dedup_and_distinct_rows_in_one_form(self):
        a=tx(1);alias=dict(a,id=a['id'].replace('/1/','/2/'),form_url=a['form_url'].replace('/1/','/2/'))
        g=aggregate([a,alias,tx(2)],'2026-10-18','2026-10-24')[0]
        self.assertEqual(g['transaction_count'],2)
        self.assertEqual(g['reported_transaction_count'],2)
    def test_cross_form_co_reporting_never_double_counts(self):
        rows=[tx(1,file=1),tx(1,file=2),tx(1,file=3)]
        g=aggregate(rows,'2026-10-18','2026-10-24')[0]
        self.assertEqual(g['amount'],100000)
        self.assertEqual(g['reported_amount'],300000)
        self.assertEqual(len(g['transactions']),3)
        self.assertFalse(g['aggregation_verified'])
        self.assertIsNone(g['independent_insiders'])
        self.assertIsNone(g['weighted_price'])
    def test_security_classes_do_not_merge(self):
        g=aggregate([tx(1,file=1,title='Class A'),tx(1,file=2,title='Class B')],'2026-10-18','2026-10-24')[0]
        self.assertEqual(g['amount'],200000)
        self.assertIsNone(g['weighted_price'])
    def test_filter_units_and_capped_proportion(self):
        self.assertEqual(filter_result(100000,500000000)['status'],'supera')
        self.assertEqual(filter_result(1999999,200000000000)['status'],'escluso')
        self.assertEqual(filter_result(2000000,200000000000)['required_amount'],2000000)
        self.assertEqual(filter_result(999999,1e9,dict(proportional_pct=0.1))['required_amount'],1e6)
        self.assertEqual(filter_result(1e9,499999999)['status'],'escluso')
        self.assertEqual(filter_result(1e9)['status'],'non_verificabile')
    def test_radar_weights_and_caps(self):
        a=screen(dict(amount=1e6,officer_title='CEO'),dict(revenue_growing=True,eps_growing=True,cashflow_positive=True))
        self.assertAlmostEqual(a['radar_uncapped'],0.7*49+0.3*80)
        self.assertEqual(a['radar_score'],49)
        self.assertLessEqual(screen(dict(amount=1e6,officer_title='CEO'),None)['radar_score'],29)
        self.assertFalse(a['buy_signal']);self.assertFalse(a['notify'])
    def test_history_months_and_price_band_is_not_a_signal(self):
        rows=[tx(1,'2026-03-01'),tx(2,'2026-09-01')]
        self.assertEqual(len(historical_windows(rows,'2026-10-24',6)),1)
        self.assertEqual(len(historical_windows(rows,'2026-10-24',12)),2)
        self.assertTrue(price_band(95,100)['within_band'])
        self.assertTrue(price_band(105,100)['within_band'])
        self.assertFalse(price_band(105.01,100)['within_band'])
        self.assertIsNone(price_band(None,100))
        self.assertEqual(historical_review({},dict(current_price=100,split_adjusted=True),'2026-10-24')['status'],'non_verificabile')
    def test_future_filings_not_in_published_observations(self):
        self.assertEqual(publish([dict(tx(1),filed='2026-11-01')],'2026-10-24')['groups'],[])
