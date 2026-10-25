import unittest
from datetime import date,timedelta
from scanner.ml import make_target,point_in_time_features,select_public_facts,chronological_split,train_models

class MLTests(unittest.TestCase):
    def test_no_verified_prices_no_target(self):
        for h in (30,90,180):self.assertIsNone(make_target([],[],'2021-01-01',h)['label'])
        self.assertIsNone(make_target([dict(day='2021-01-01',total_return_index=100)],[],'2021-01-01',30)['label'])
    def test_split_dividend_adjusted_excess_and_cost(self):
        def prices(end):return [dict(day=d,total_return_index=v,adjustments_verified=True,license_approved=True,source_url='https://fixture.example/total-return') for d,v in [('2021-01-04',100),('2021-02-03',end)]]
        t=make_target(prices(110),prices(105),'2021-01-02',30,20)
        self.assertEqual(t['status'],'verified');self.assertAlmostEqual(t['excess_return'],.048);self.assertEqual(t['label'],1)
        broken=prices(110)+[dict(day='2021-01-20',kind='delisted')]
        self.assertIsNone(make_target(broken,prices(105),'2021-01-02',30)['label'])
    def test_publication_cutoff(self):
        rows=[dict(public_at='2021-02-01',period_end='2020-12-31'),dict(public_at='2021-05-01',period_end='2021-03-31')]
        self.assertEqual(len(select_public_facts(rows,'2021-02-01')),1)
    def test_features_ignore_future_amendment_current_listing_and_scores(self):
        e=dict(purchase_eligible=True,amendment=False,filed='2021-01-04',transaction_date='2021-01-01',amount=10000,shares=100,officer=True,director=False,ten_pct=False)
        a=point_in_time_features(e);b=point_in_time_features(dict(e,current_listing=True,future_return=.9,review_reasons=['amended_in_2026']))
        self.assertEqual(a,b);self.assertIsNone(point_in_time_features(dict(e,amendment=True)))
    def test_purge_removes_targets_crossing_boundaries(self):
        start=date(2010,1,1);rows=[dict(as_of=(start+timedelta(days=i*10)).isoformat(),exit_day=(start+timedelta(days=i*10+180)).isoformat()) for i in range(100)]
        train,val,test=chronological_split(rows)
        self.assertLess(train[-1]['exit_day'],val[0]['as_of']);self.assertLess(val[-1]['exit_day'],test[0]['as_of'])
    def test_no_fabricated_training_results(self):
        r=train_models([]);self.assertFalse(r['trained']);self.assertIsNone(r['metrics'])
