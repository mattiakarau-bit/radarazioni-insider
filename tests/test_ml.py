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
    def test_price_flag_alone_cannot_approve_provider(self):
        import tempfile
        from pathlib import Path
        from scanner.ml import connect,populate_targets
        with tempfile.TemporaryDirectory() as tmp:
            db=connect(Path(tmp)/'test.sqlite')
            db.execute("INSERT INTO events VALUES('e',1,'security','2021-01-01','2021-01-02','2021-01-01','{}')")
            db.execute("INSERT INTO features VALUES('e','2021-01-02','v1','{}',NULL,'2021-01-01','SEC_real')")
            db.execute("INSERT INTO prices VALUES('security','2021-01-04',100,1,1,'https://unapproved.example','2021-01-04',1)")
            populate_targets(db)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM targets WHERE status='verified'").fetchone()[0],0)
            db.close()
    def test_malformed_class_balance_cannot_train_on_one_class(self):
        rows=[dict(as_of=(date(2010,1,1)+timedelta(days=i*4)).isoformat(),exit_day=(date(2010,1,1)+timedelta(days=i*4+180)).isoformat(),issuer_cik=i%150,label=1) for i in range(1000)]
        self.assertFalse(train_models(rows)['trained'])
    def test_co_report_dedup_is_point_in_time_not_future_selection(self):
        from scanner.ml import eligible_feature_ids
        base=dict(id='a',accession='a',cik=1,security_title='Common Stock',shares=100,unit_price=10,amount=1000,transaction_date='2021-01-01',filed='2021-01-04',purchase_eligible=True,amendment=False,owner_ciks=['1'],period_of_report='2021-01-01',officer=False,director=False,ten_pct=True)
        later=dict(base,id='b',accession='b',filed='2021-01-05')
        self.assertIn('a',eligible_feature_ids([base,later]));self.assertNotIn('b',eligible_feature_ids([base,later]))
        same_day=dict(later,filed='2021-01-04')
        self.assertEqual(eligible_feature_ids([base,same_day]),set())
